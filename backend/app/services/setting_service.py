"""设定服务 — 9 大创作模块 CRUD + AI 生成 + 全项目体检

模块: world / characters / skills / items / factions / outlines / locations / timelines / foreshadows
所有方法接收 FastAPI 依赖注入的 AsyncSession，事务由 get_db 依赖统一提交。
"""

import json
import logging
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.world_setting import WorldSetting
from app.models.character import Character
from app.models.skill import Skill
from app.models.item import Item
from app.models.faction import Faction
from app.models.outline import Outline
from app.models.location import Location
from app.models.timeline import Timeline
from app.models.foreshadow import Foreshadow


# ── 模块注册表 ────────────────────────────────────────────────────

MODULES: dict[str, Any] = {
    "world": WorldSetting,
    "characters": Character,
    "skills": Skill,
    "items": Item,
    "factions": Faction,
    "outlines": Outline,
    "locations": Location,
    "timelines": Timeline,
    "foreshadows": Foreshadow,
}

# 各模块列表排序字段
_ORDER_BY = {
    "outlines": Outline.sort_order,
    "timelines": Timeline.sort_order,
}


def _dict_from_model(obj) -> dict:
    """通用 model → dict 转换（保持与旧 API 完全一致）"""
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        d[col.name] = val
    return d


async def _get_or_404(model, obj_id: str, db: AsyncSession, project_id: str):
    """按 id + project_id 取对象，不存在则 404"""
    stmt = select(model).where(model.id == obj_id)
    if hasattr(model, "project_id"):
        stmt = stmt.where(model.project_id == project_id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


class SettingService:
    """设定模块服务"""

    # ── 通用 CRUD ────────────────────────────────────────────────

    @staticmethod
    async def create(db: AsyncSession, project_id: str, module: str, data: dict) -> dict:
        model = MODULES[module]
        obj = model(project_id=project_id, **data)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return _dict_from_model(obj)

    @staticmethod
    async def list(db: AsyncSession, project_id: str, module: str) -> list[dict]:
        model = MODULES[module]
        stmt = select(model).where(model.project_id == project_id)
        order = _ORDER_BY.get(module)
        if order is not None:
            stmt = stmt.order_by(order)
        result = await db.execute(stmt)
        return [_dict_from_model(o) for o in result.scalars().all()]

    @staticmethod
    async def get(db: AsyncSession, project_id: str, module: str, obj_id: str) -> dict:
        model = MODULES[module]
        obj = await _get_or_404(model, obj_id, db, project_id)
        return _dict_from_model(obj)

    @staticmethod
    async def update(db: AsyncSession, project_id: str, module: str, obj_id: str, data: dict) -> dict:
        model = MODULES[module]
        obj = await _get_or_404(model, obj_id, db, project_id)
        for k, v in data.items():
            setattr(obj, k, v)
        await db.flush()
        await db.refresh(obj)
        return _dict_from_model(obj)

    @staticmethod
    async def delete(db: AsyncSession, project_id: str, module: str, obj_id: str) -> None:
        model = MODULES[module]
        obj = await _get_or_404(model, obj_id, db, project_id)
        await db.delete(obj)
        await db.flush()

    # ── 全项目设定体检（N 轮）───────────────────────────────────

    AUDIT_SYSTEM = """你是小说设定一致性审查员。审查给定作品的设定资料，找出相互冲突、矛盾或明显不合理之处。
输出 JSON：{"issues": [{"severity": "high|medium|low", "module": "world|characters|items|skills|factions|locations|outlines|timelines|foreshadows", "title": "设定条目名", "issue": "冲突描述", "suggestion": "修改建议"}], "summary": "总体一致性评价"}。
没有冲突时 issues 为空数组。仅输出 JSON。"""

    @staticmethod
    async def audit(db: AsyncSession, project_id: str) -> dict:
        """全项目设定体检：汇总 9 模块设定 → LLM 一致性扫描 → issues"""
        modules = list(MODULES.keys())
        payload: list[str] = []
        for module in modules:
            model = MODULES[module]
            result = await db.execute(select(model).where(model.project_id == project_id))
            for o in result.scalars().all():
                d = _dict_from_model(o)
                title = d.get("name") or d.get("title") or d.get("event") or d.get("id", "")
                content = (
                    d.get("content") or d.get("description") or d.get("background")
                    or d.get("summary") or d.get("goal") or ""
                )
                if content:
                    payload.append(f"[{module}] {title}: {str(content)[:400]}")
        if not payload:
            return {"checked": 0, "issues": [], "summary": "项目暂无设定资料"}
        from app.core.llm import LLMMessage, LLMRequest, create
        from app.agents.nodes.common import is_mock_provider

        llm = create()
        resp = await llm.acomplete(LLMRequest(
            messages=[
                LLMMessage(role="system", content=SettingService.AUDIT_SYSTEM),
                LLMMessage(role="user", content=f"【项目设定资料】\n{chr(10).join(payload[:80])[:12000]}"),
            ],
            response_format={"type": "json_object"},
        ))
        try:
            data = json.loads(resp.content)
        except Exception:
            data = {}
        issues: list[dict] = []
        for it in (data.get("issues") or [])[:50]:
            if isinstance(it, dict):
                issues.append({
                    "severity": str(it.get("severity") or "medium"),
                    "module": str(it.get("module") or "?"),
                    "title": str(it.get("title") or "")[:120],
                    "issue": str(it.get("issue") or "")[:500],
                    "suggestion": str(it.get("suggestion") or "")[:300],
                })
        return {
            "checked": len(payload),
            "issues": issues,
            "summary": str(data.get("summary") or "")[:300],
            "is_mock": is_mock_provider(llm),
        }

    # ── AI 生成（LangGraph setting 图驱动；生成+持久化在图内完成）──

    @staticmethod
    async def ai_generate_world(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        """AI 生成世界观设定（setting 图）"""
        return await _run_setting_graph(project_id, "world", name, category, extra=extra)

    @staticmethod
    async def ai_generate_character(db: AsyncSession, project_id: str, name: str, role: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "character", name, category, role=role, extra=extra)

    @staticmethod
    async def ai_generate_item(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "item", name, category, extra=extra)

    @staticmethod
    async def ai_generate_skill(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "skill", name, category, extra=extra)

    @staticmethod
    async def ai_generate_faction(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "faction", name, category, extra=extra)

    @staticmethod
    async def ai_generate_location(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "location", name, category, extra=extra)

    @staticmethod
    async def ai_generate_timeline(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        """AI 生成时间线事件（M 轮）：setting 图 kind=timeline"""
        return await _run_setting_graph(project_id, "timeline", name, category, extra=extra)

    @staticmethod
    async def ai_generate_outline(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        return await _run_setting_graph(project_id, "outline", name, category, extra=extra)


async def _run_setting_graph(project_id: str, kind: str, name: str, category: str, role: str = "", extra: str = "") -> dict:
    """运行 setting 图并返回 {content, is_mock}（生成+持久化在图内完成）"""
    from app.agents.runner import get_runner

    state = {
        "graph": "setting", "project_id": project_id,
        "task": f"生成{kind}设定 {name}", "kind": kind,
        "name": name, "category": category, "role": role or None, "extra": extra,
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    result = await get_runner().ainvoke("setting", state)
    if result.get("error") and not result.get("content"):
        raise HTTPException(status_code=500, detail=f"生成失败: {result['error']}")
    return {"content": result.get("content", ""), "is_mock": result.get("is_mock", True)}
