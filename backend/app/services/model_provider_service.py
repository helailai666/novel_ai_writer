"""模型供应商服务 — 前台配置的供应商注册表（DB 持久化，替代 .env 单一配置）

解析优先级（谁有谁生效）：
1. 请求级覆盖 state.model（"provider:model" / "model"，见 resolve_llm）
2. 项目级：project.llm_provider_id → 该供应商配置；project.llm_model 覆盖模型
3. 全局默认：model_providers 中 is_default 且 enabled 的配置（无则取第一个 enabled）
4. 环境变量兜底（settings.llm / 各供应商 Key）
"""

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.factory import list_providers
from app.models.model_provider import ModelProvider
from app.models.project import Project

logger = logging.getLogger(__name__)

_KNOWN_PROVIDERS = {p["name"] for p in list_providers()}


def mask_key(api_key: str) -> str:
    """脱敏：保留前 4 后 4，其余星号；空返回空"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


def to_spec(row: ModelProvider, model_override: str = "") -> dict:
    """ModelProvider 行 → factory.create_from_spec 配置字典"""
    return {
        "provider": row.provider,
        "model": (model_override or row.model or "").strip(),
        "api_key": (row.api_key or "").strip() or None,
        "api_base": (row.api_base or "").strip() or None,
        "temperature": row.temperature,
    }


def to_response(row: ModelProvider) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "model": row.model,
        "api_base": row.api_base,
        "api_key": mask_key(row.api_key),
        "has_api_key": bool(row.api_key),
        "temperature": row.temperature,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


async def list_configs(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ModelProvider).order_by(ModelProvider.created_at.asc()))
    return [to_response(r) for r in result.scalars().all()]


async def get_config(db: AsyncSession, provider_id: str) -> ModelProvider:
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="供应商配置不存在")
    return row


async def create_config(db: AsyncSession, data: dict) -> dict:
    provider = (data.get("provider") or "").strip()
    if provider not in _KNOWN_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"未知供应商类型 '{provider}'，可选: {', '.join(_KNOWN_PROVIDERS)}")
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="配置名称不能为空")
    if data.get("is_default"):
        await db.execute(update(ModelProvider).values(is_default=False))
    row = ModelProvider(
        name=name[:100],
        provider=provider,
        model=(data.get("model") or "").strip()[:100],
        api_key=(data.get("api_key") or "").strip()[:500],
        api_base=(data.get("api_base") or "").strip()[:300],
        temperature=float(data.get("temperature") or 0.7),
        enabled=bool(data.get("enabled", True)),
        is_default=bool(data.get("is_default", False)),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return to_response(row)


async def update_config(db: AsyncSession, provider_id: str, data: dict) -> dict:
    row = await get_config(db, provider_id)
    if "provider" in data and data["provider"] not in _KNOWN_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"未知供应商类型 '{data['provider']}'")
    if "is_default" in data and data["is_default"]:
        await db.execute(update(ModelProvider).values(is_default=False))
    for field in ("name", "provider", "model", "api_key", "api_base", "temperature", "enabled", "is_default"):
        if field in data and data[field] is not None:
            setattr(row, field, data[field])
    if row.is_default and not data.get("enabled", row.enabled):
        row.enabled = True  # 默认配置不可禁用（保证兜底可用）
    await db.flush()
    await db.refresh(row)
    return to_response(row)


async def delete_config(db: AsyncSession, provider_id: str) -> None:
    row = await get_config(db, provider_id)
    # 解除项目引用，避免悬空
    await db.execute(update(Project).where(Project.llm_provider_id == provider_id).values(llm_provider_id=None))
    await db.delete(row)
    await db.flush()


async def get_default(db: AsyncSession) -> Optional[ModelProvider]:
    """全局默认配置：is_default 且 enabled → 第一个 enabled → None"""
    result = await db.execute(
        select(ModelProvider).where(ModelProvider.enabled.is_(True)).order_by(ModelProvider.is_default.desc(), ModelProvider.created_at.asc())
    )
    return result.scalars().first()


async def resolve_project_config(db: AsyncSession, project_id: str) -> Optional[dict]:
    """解析项目生效的 LLM 配置字典（None = 走环境变量兜底）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return None
    row: Optional[ModelProvider] = None
    if project.llm_provider_id:
        r2 = await db.execute(select(ModelProvider).where(ModelProvider.id == project.llm_provider_id))
        row = r2.scalar_one_or_none()
        if row and not row.enabled:
            row = None  # 引用的配置被禁用 → 回退默认
    if row is None:
        row = await get_default(db)
    if row is None:
        return None
    return to_spec(row, model_override=project.llm_model or "")
