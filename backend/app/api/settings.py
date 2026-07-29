"""设定管理 API — 世界观/角色/能力/道具/势力/大纲/场景/时间线/伏笔"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.world_setting import WorldSetting
from app.models.character import Character
from app.models.skill import Skill
from app.models.item import Item
from app.models.faction import Faction
from app.models.outline import Outline
from app.models.location import Location
from app.models.timeline import Timeline
from app.models.foreshadow import Foreshadow
from app.agents.creative_agent import CreativeAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/settings", tags=["settings"])


# ── Agent 工厂 ────────────────────────────────────────────────────

def _get_creative_agent() -> CreativeAgent:
    """创建 CreativeAgent 实例"""
    return CreativeAgent(
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "",
        api_base=os.getenv("LLM_API_BASE"),
    )


# ── Generic Helpers ──────────────────────────────────────────────

async def _get_or_404(model, obj_id: str, db: AsyncSession):
    result = await db.execute(select(model).where(model.id == obj_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def _dict_from_model(obj, exclude: set = None) -> dict:
    """通用 model → dict 转换"""
    d = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        d[col.name] = val
    if exclude:
        for k in exclude:
            d.pop(k, None)
    return d


# ── World Setting (M2) ───────────────────────────────────────────

class WorldSettingCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(default="general", max_length=50)
    content: str = Field(default="")


class WorldSettingUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = None


@router.post("/world", status_code=201)
async def create_world_setting(project_id: str, payload: WorldSettingCreate, db: AsyncSession = Depends(get_db)):
    ws = WorldSetting(project_id=project_id, **payload.model_dump())
    db.add(ws)
    await db.flush()
    await db.refresh(ws)
    return _dict_from_model(ws)


@router.get("/world")
async def list_world_settings(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorldSetting).where(WorldSetting.project_id == project_id))
    return [_dict_from_model(ws) for ws in result.scalars().all()]


@router.patch("/world/{setting_id}")
async def update_world_setting(project_id: str, setting_id: str, payload: WorldSettingUpdate, db: AsyncSession = Depends(get_db)):
    ws = await _get_or_404(WorldSetting, setting_id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(ws, k, v)
    await db.flush()
    await db.refresh(ws)
    return _dict_from_model(ws)


@router.delete("/world/{setting_id}", status_code=204)
async def delete_world_setting(project_id: str, setting_id: str, db: AsyncSession = Depends(get_db)):
    ws = await _get_or_404(WorldSetting, setting_id, db)
    await db.delete(ws)
    await db.flush()


# ── Character (M3) ───────────────────────────────────────────────

class CharacterCreate(BaseModel):
    name: str = Field(..., max_length=100)
    role: str = Field(default="supporting", max_length=50)
    gender: str = Field(default="unknown", max_length=20)
    age: int = Field(default=0)
    personality: str = ""
    background: str = ""
    appearance: str = ""
    abilities: str = ""
    relationships: str = ""


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=50)
    gender: Optional[str] = Field(None, max_length=20)
    age: Optional[int] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    abilities: Optional[str] = None
    relationships: Optional[str] = None


@router.post("/characters", status_code=201)
async def create_character(project_id: str, payload: CharacterCreate, db: AsyncSession = Depends(get_db)):
    char = Character(project_id=project_id, **payload.model_dump())
    db.add(char)
    await db.flush()
    await db.refresh(char)
    return _dict_from_model(char)


@router.get("/characters")
async def list_characters(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Character).where(Character.project_id == project_id))
    return [_dict_from_model(c) for c in result.scalars().all()]


@router.get("/characters/{char_id}")
async def get_character(project_id: str, char_id: str, db: AsyncSession = Depends(get_db)):
    char = await _get_or_404(Character, char_id, db)
    return _dict_from_model(char)


@router.patch("/characters/{char_id}")
async def update_character(project_id: str, char_id: str, payload: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    char = await _get_or_404(Character, char_id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(char, k, v)
    await db.flush()
    await db.refresh(char)
    return _dict_from_model(char)


@router.delete("/characters/{char_id}", status_code=204)
async def delete_character(project_id: str, char_id: str, db: AsyncSession = Depends(get_db)):
    char = await _get_or_404(Character, char_id, db)
    await db.delete(char)
    await db.flush()


# ── Skill (M4) ───────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str = Field(..., max_length=100)
    category: str = Field(default="magic", max_length=50)
    level: int = Field(default=1, ge=1, le=10)
    description: str = ""
    cost: str = ""
    owner_id: Optional[str] = None


@router.post("/skills", status_code=201)
async def create_skill(project_id: str, payload: SkillCreate, db: AsyncSession = Depends(get_db)):
    skill = Skill(project_id=project_id, **payload.model_dump())
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return _dict_from_model(skill)


@router.get("/skills")
async def list_skills(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Skill).where(Skill.project_id == project_id))
    return [_dict_from_model(s) for s in result.scalars().all()]


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(project_id: str, skill_id: str, db: AsyncSession = Depends(get_db)):
    skill = await _get_or_404(Skill, skill_id, db)
    await db.delete(skill)
    await db.flush()


# ── Item (M5) ────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    name: str = Field(..., max_length=100)
    category: str = Field(default="weapon", max_length=50)
    rarity: str = Field(default="common", max_length=20)
    quantity: int = Field(default=1, ge=1)
    description: str = ""
    effects: str = ""
    owner_id: Optional[str] = None


@router.post("/items", status_code=201)
async def create_item(project_id: str, payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    item = Item(project_id=project_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return _dict_from_model(item)


@router.get("/items")
async def list_items(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.project_id == project_id))
    return [_dict_from_model(it) for it in result.scalars().all()]


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(project_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    item = await _get_or_404(Item, item_id, db)
    await db.delete(item)
    await db.flush()


# ── Faction (M6) ─────────────────────────────────────────────────

class FactionCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(default="kingdom", max_length=50)
    goal: str = ""
    structure: str = ""
    notable_members: str = ""


@router.post("/factions", status_code=201)
async def create_faction(project_id: str, payload: FactionCreate, db: AsyncSession = Depends(get_db)):
    faction = Faction(project_id=project_id, **payload.model_dump())
    db.add(faction)
    await db.flush()
    await db.refresh(faction)
    return _dict_from_model(faction)


@router.get("/factions")
async def list_factions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Faction).where(Faction.project_id == project_id))
    return [_dict_from_model(f) for f in result.scalars().all()]


@router.delete("/factions/{faction_id}", status_code=204)
async def delete_faction(project_id: str, faction_id: str, db: AsyncSession = Depends(get_db)):
    faction = await _get_or_404(Faction, faction_id, db)
    await db.delete(faction)
    await db.flush()


# ── Outline (M7) ─────────────────────────────────────────────────

class OutlineCreate(BaseModel):
    title: str = Field(..., max_length=200)
    parent_id: Optional[str] = None
    level: int = Field(default=1, ge=1, le=4)
    sort_order: int = Field(default=0)
    summary: str = ""
    status: str = Field(default="planned", max_length=20)


class OutlineUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    level: Optional[int] = None
    sort_order: Optional[int] = None
    summary: Optional[str] = None
    status: Optional[str] = None


@router.post("/outlines", status_code=201)
async def create_outline(project_id: str, payload: OutlineCreate, db: AsyncSession = Depends(get_db)):
    outline = Outline(project_id=project_id, **payload.model_dump())
    db.add(outline)
    await db.flush()
    await db.refresh(outline)
    return _dict_from_model(outline)


@router.get("/outlines")
async def list_outlines(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.sort_order)
    )
    return [_dict_from_model(o) for o in result.scalars().all()]


@router.patch("/outlines/{outline_id}")
async def update_outline(project_id: str, outline_id: str, payload: OutlineUpdate, db: AsyncSession = Depends(get_db)):
    outline = await _get_or_404(Outline, outline_id, db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(outline, k, v)
    await db.flush()
    await db.refresh(outline)
    return _dict_from_model(outline)


@router.delete("/outlines/{outline_id}", status_code=204)
async def delete_outline(project_id: str, outline_id: str, db: AsyncSession = Depends(get_db)):
    outline = await _get_or_404(Outline, outline_id, db)
    await db.delete(outline)
    await db.flush()


# ── Location (M8) ────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[str] = None
    category: str = Field(default="city", max_length=50)
    description: str = ""
    climate: str = ""
    notable_features: str = ""


@router.post("/locations", status_code=201)
async def create_location(project_id: str, payload: LocationCreate, db: AsyncSession = Depends(get_db)):
    loc = Location(project_id=project_id, **payload.model_dump())
    db.add(loc)
    await db.flush()
    await db.refresh(loc)
    return _dict_from_model(loc)


@router.get("/locations")
async def list_locations(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Location).where(Location.project_id == project_id))
    return [_dict_from_model(l) for l in result.scalars().all()]


@router.delete("/locations/{location_id}", status_code=204)
async def delete_location(project_id: str, location_id: str, db: AsyncSession = Depends(get_db)):
    loc = await _get_or_404(Location, location_id, db)
    await db.delete(loc)
    await db.flush()


# ── Timeline (M9) ────────────────────────────────────────────────

class TimelineCreate(BaseModel):
    event: str = Field(..., max_length=300)
    era: str = Field(default="present", max_length=100)
    event_date: str = Field(default="")
    sort_order: int = Field(default=0)
    description: str = ""
    involved_characters: str = ""


@router.post("/timelines", status_code=201)
async def create_timeline(project_id: str, payload: TimelineCreate, db: AsyncSession = Depends(get_db)):
    tl = Timeline(project_id=project_id, **payload.model_dump())
    db.add(tl)
    await db.flush()
    await db.refresh(tl)
    return _dict_from_model(tl)


@router.get("/timelines")
async def list_timelines(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Timeline).where(Timeline.project_id == project_id).order_by(Timeline.sort_order)
    )
    return [_dict_from_model(t) for t in result.scalars().all()]


@router.delete("/timelines/{timeline_id}", status_code=204)
async def delete_timeline(project_id: str, timeline_id: str, db: AsyncSession = Depends(get_db)):
    tl = await _get_or_404(Timeline, timeline_id, db)
    await db.delete(tl)
    await db.flush()


# ── Foreshadow (M10) ─────────────────────────────────────────────

class ForeshadowCreate(BaseModel):
    description: str = ""
    plant_chapter_id: Optional[str] = None
    reveal_chapter_id: Optional[str] = None
    status: str = Field(default="planted", max_length=20)
    related_characters: str = ""


@router.post("/foreshadows", status_code=201)
async def create_foreshadow(project_id: str, payload: ForeshadowCreate, db: AsyncSession = Depends(get_db)):
    fs = Foreshadow(project_id=project_id, **payload.model_dump())
    db.add(fs)
    await db.flush()
    await db.refresh(fs)
    return _dict_from_model(fs)


@router.get("/foreshadows")
async def list_foreshadows(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Foreshadow).where(Foreshadow.project_id == project_id))
    return [_dict_from_model(f) for f in result.scalars().all()]


@router.delete("/foreshadows/{foreshadow_id}", status_code=204)
async def delete_foreshadow(project_id: str, foreshadow_id: str, db: AsyncSession = Depends(get_db)):
    fs = await _get_or_404(Foreshadow, foreshadow_id, db)
    await db.delete(fs)
    await db.flush()


# ── AI 辅助生成端点 ─────────────────────────────────────────────

class AIGenerateRequest(BaseModel):
    """AI 生成请求"""
    name: str = Field(..., max_length=200, description="名称")
    category: str = Field(default="general", max_length=50)
    role: str = Field(default="supporting", max_length=50)
    extra: str = Field(default="", description="额外要求")


class AIGenerateResponse(BaseModel):
    """AI 生成响应"""
    content: str
    is_mock: bool = False


@router.post("/ai/generate-world", response_model=AIGenerateResponse)
async def ai_generate_world_setting(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成世界观设定"""
    agent = _get_creative_agent()

    # 收集已有设定作为上下文
    existing = await db.execute(
        select(WorldSetting).where(WorldSetting.project_id == project_id)
    )
    context = {
        "existing_settings": [
            {"name": ws.name, "category": ws.category, "content": ws.content[:200]}
            for ws in existing.scalars().all()
        ],
    }

    result = await agent.generate_world_setting(
        name=payload.name,
        category=payload.category,
        context=context,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    # 自动保存
    ws = WorldSetting(
        project_id=project_id,
        name=payload.name,
        category=payload.category,
        content=result.content,
    )
    db.add(ws)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-character", response_model=AIGenerateResponse)
async def ai_generate_character(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成角色设定"""
    agent = _get_creative_agent()

    # 收集世界设定作为上下文
    existing = await db.execute(
        select(WorldSetting).where(WorldSetting.project_id == project_id)
    )
    world_context = "\n".join(
        f"{ws.name}: {ws.content[:300]}" for ws in existing.scalars().all()
    )

    result = await agent.generate_character(
        name=payload.name,
        role=payload.role,
        context={"world_setting": world_context, "extra": payload.extra},
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    # 自动保存
    char = Character(
        project_id=project_id,
        name=payload.name,
        role=payload.role,
        background=result.content,
    )
    db.add(char)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-item", response_model=AIGenerateResponse)
async def ai_generate_item(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成道具设定"""
    agent = _get_creative_agent()
    result = await agent.generate_item(
        name=payload.name,
        category=payload.category,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    item = Item(
        project_id=project_id,
        name=payload.name,
        category=payload.category,
        description=result.content,
    )
    db.add(item)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-skill", response_model=AIGenerateResponse)
async def ai_generate_skill(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成技能设定"""
    agent = _get_creative_agent()
    result = await agent.generate_skill(
        name=payload.name,
        category=payload.category,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    skill = Skill(
        project_id=project_id,
        name=payload.name,
        category=payload.category,
        description=result.content,
    )
    db.add(skill)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-faction", response_model=AIGenerateResponse)
async def ai_generate_faction(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成势力设定"""
    agent = _get_creative_agent()
    result = await agent.generate_faction(
        name=payload.name,
        faction_type=payload.category,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    faction = Faction(
        project_id=project_id,
        name=payload.name,
        type=payload.category,
        goal=result.content,
    )
    db.add(faction)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-location", response_model=AIGenerateResponse)
async def ai_generate_location(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成场景/地点设定"""
    agent = _get_creative_agent()
    result = await agent.generate_location(
        name=payload.name,
        category=payload.category,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    loc = Location(
        project_id=project_id,
        name=payload.name,
        category=payload.category,
        description=result.content,
    )
    db.add(loc)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)


@router.post("/ai/generate-outline", response_model=AIGenerateResponse)
async def ai_generate_outline(
    project_id: str,
    payload: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成大纲节点"""
    agent = _get_creative_agent()
    result = await agent.generate_outline(
        title=payload.name,
        level=int(payload.category) if payload.category.isdigit() else 1,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"生成失败: {result.error}")

    outline = Outline(
        project_id=project_id,
        title=payload.name,
        summary=result.content,
    )
    db.add(outline)
    await db.flush()

    return AIGenerateResponse(content=result.content, is_mock=agent.is_mock)
