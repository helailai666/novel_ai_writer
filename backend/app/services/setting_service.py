"""设定服务 — 9 大创作模块 CRUD + AI 生成

模块: world / characters / skills / items / factions / outlines / locations / timelines / foreshadows
所有方法接收 FastAPI 依赖注入的 AsyncSession，事务由 get_db 依赖统一提交。
"""

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
from app.services.agent_factory import get_creative_agent


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

    # ── AI 生成（P2 起由 LangGraph 节点替代内部 agent 调用）────────

    @staticmethod
    async def ai_generate_world(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        """AI 生成世界观设定并自动保存"""
        agent = get_creative_agent()
        result = await db.execute(select(WorldSetting).where(WorldSetting.project_id == project_id))
        existing = [
            {"name": ws.name, "category": ws.category, "content": ws.content[:200]}
            for ws in result.scalars().all()
        ]
        gen = await agent.generate_world_setting(name=name, category=category, context={"existing_settings": existing})
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        ws = WorldSetting(project_id=project_id, name=name, category=category, content=gen.content)
        db.add(ws)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_character(db: AsyncSession, project_id: str, name: str, role: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        result = await db.execute(select(WorldSetting).where(WorldSetting.project_id == project_id))
        world_context = "\n".join(f"{ws.name}: {ws.content[:300]}" for ws in result.scalars().all())
        gen = await agent.generate_character(name=name, role=role, context={"world_setting": world_context, "extra": extra})
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        char = Character(project_id=project_id, name=name, role=role, background=gen.content)
        db.add(char)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_item(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        gen = await agent.generate_item(name=name, category=category)
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        item = Item(project_id=project_id, name=name, category=category, description=gen.content)
        db.add(item)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_skill(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        gen = await agent.generate_skill(name=name, category=category)
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        skill = Skill(project_id=project_id, name=name, category=category, description=gen.content)
        db.add(skill)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_faction(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        gen = await agent.generate_faction(name=name, faction_type=category)
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        faction = Faction(project_id=project_id, name=name, type=category, goal=gen.content)
        db.add(faction)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_location(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        gen = await agent.generate_location(name=name, category=category)
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        loc = Location(project_id=project_id, name=name, category=category, description=gen.content)
        db.add(loc)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}

    @staticmethod
    async def ai_generate_outline(db: AsyncSession, project_id: str, name: str, category: str, extra: str = "") -> dict:
        agent = get_creative_agent()
        level = int(category) if category.isdigit() else 1
        gen = await agent.generate_outline(title=name, level=level)
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"生成失败: {gen.error}")
        outline = Outline(project_id=project_id, title=name, summary=gen.content)
        db.add(outline)
        await db.flush()
        return {"content": gen.content, "is_mock": agent.is_mock}
