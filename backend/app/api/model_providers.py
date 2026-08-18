"""模型供应商 API — 前台配置的供应商注册表（DB 持久化 CRUD）+ 连通性测试

- GET    /api/model-providers            供应商列表（注册表）+ DB 配置 + 当前生效全局配置
- POST   /api/model-providers            新增供应商配置
- PATCH  /api/model-providers/{id}       更新配置
- DELETE /api/model-providers/{id}       删除配置（解除项目引用）
- POST   /api/model-providers/test       连通性测试（可用 provider_id 引用已存配置）
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm import LLMMessage, LLMRequest, create_for, list_providers
from app.database import get_db
from app.services import model_provider_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-providers", tags=["model-providers"])


# ── Schemas ──────────────────────────────────────────────────────

class ProviderConfigIn(BaseModel):
    name: str = Field(..., max_length=100, description="配置显示名，如「DeepSeek 主力」")
    provider: str = Field(..., description="供应商类型: openai/deepseek/qwen/glm/kimi/ollama/anthropic/gemini/azure/mock")
    model: str = Field("", max_length=100, description="默认模型（空则用内置默认）")
    api_key: str = Field("", description="API Key（留空可复用环境变量）")
    api_base: str = Field("", max_length=300, description="OpenAI 兼容端点（可选）")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    enabled: bool = Field(True, description="启用状态")
    is_default: bool = Field(False, description="设为全局默认（每个项目未指定时兜底）")


class ProviderConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    provider: str | None = None
    model: str | None = Field(None, max_length=100)
    api_key: str | None = None
    api_base: str | None = Field(None, max_length=300)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    enabled: bool | None = None
    is_default: bool | None = None


class ProviderTestRequest(BaseModel):
    provider: str = Field("", description="供应商名（provider_id 与 provider 二选一）")
    model: str = Field("", description="模型名（空则用默认）")
    api_key: str = Field("", description="API Key（空则用环境变量/已存配置）")
    api_base: str = Field("", description="API Base（空则用默认）")
    provider_id: str = Field("", description="引用已保存的供应商配置")


# ── 路由 ─────────────────────────────────────────────────────────

@router.get("")
async def get_providers(db: AsyncSession = Depends(get_db)):
    """供应商列表 + DB 配置 + 当前生效的全局配置"""
    configs = await svc.list_configs(db)
    default_row = await svc.get_default(db)
    # 当前全局生效配置：DB 默认 > 环境变量
    if default_row:
        current = {
            "provider": default_row.provider,
            "model": default_row.model,
            "api_base": default_row.api_base or "",
            "has_api_key": bool(default_row.api_key),
            "source": "db-default",
            "provider_id": default_row.id,
        }
    else:
        current = {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "api_base": settings.llm.api_base or "",
            "has_api_key": bool(settings.llm.api_key),
            "source": "env",
            "provider_id": None,
        }
    return {
        "providers": list_providers(),  # 注册表（供应商类型 + 内置默认模型）
        "configs": configs,
        "current": current,
    }


@router.post("", status_code=201)
async def create_provider(payload: ProviderConfigIn, db: AsyncSession = Depends(get_db)):
    """新增供应商配置（前台持久化，无需改 .env）"""
    return await svc.create_config(db, payload.model_dump())


@router.patch("/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderConfigUpdate, db: AsyncSession = Depends(get_db)):
    """更新供应商配置"""
    return await svc.update_config(db, provider_id, payload.model_dump(exclude_unset=True))


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """删除供应商配置（引用它的项目自动回退默认/环境变量）"""
    await svc.delete_config(db, provider_id)


@router.post("/test")
async def test_provider(payload: ProviderTestRequest, db: AsyncSession = Depends(get_db)):
    """连通性测试：向供应商发一条极短请求（支持引用已存配置）"""
    provider, model, api_key, api_base = payload.provider, payload.model, payload.api_key, payload.api_base
    if payload.provider_id:
        row = await svc.get_config(db, payload.provider_id)
        provider = provider or row.provider
        model = model or row.model
        api_key = api_key or row.api_key
        api_base = api_base or row.api_base
    try:
        llm = create_for(
            provider=provider or settings.llm.provider,
            model=model or None,
            api_key=api_key or None,
            api_base=api_base or None,
            max_tokens=16,
        )
        resp = await llm.acomplete(
            LLMRequest(messages=[LLMMessage(role="user", content="ping")], max_tokens=16)
        )
        return {"ok": True, "reply": resp.content[:100], "is_mock": resp.is_mock}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
