"""设定管理 API — 世界观/角色/能力/道具/势力/大纲/场景/时间线/伏笔（薄层，逻辑在 SettingService）"""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.setting_service import SettingService

router = APIRouter(prefix="/api/projects/{project_id}/settings", tags=["settings"])


# ── Schemas ──────────────────────────────────────────────────────

class WorldSettingCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(default="general", max_length=50)
    content: str = Field(default="")


class WorldSettingUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = None


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


class SkillCreate(BaseModel):
    name: str = Field(..., max_length=100)
    category: str = Field(default="magic", max_length=50)
    level: int = Field(default=1, ge=1, le=10)
    description: str = ""
    cost: str = ""
    owner_id: Optional[str] = None


class ItemCreate(BaseModel):
    name: str = Field(..., max_length=100)
    category: str = Field(default="weapon", max_length=50)
    rarity: str = Field(default="common", max_length=20)
    quantity: int = Field(default=1, ge=1)
    description: str = ""
    effects: str = ""
    owner_id: Optional[str] = None


class FactionCreate(BaseModel):
    name: str = Field(..., max_length=100)
    type: str = Field(default="kingdom", max_length=50)
    goal: str = ""
    structure: str = ""
    notable_members: str = ""


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


class LocationCreate(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[str] = None
    category: str = Field(default="city", max_length=50)
    description: str = ""
    climate: str = ""
    notable_features: str = ""


class TimelineCreate(BaseModel):
    event: str = Field(..., max_length=300)
    era: str = Field(default="present", max_length=100)
    event_date: str = Field(default="")
    sort_order: int = Field(default=0)
    description: str = ""
    involved_characters: str = ""


class ForeshadowCreate(BaseModel):
    description: str = ""
    plant_chapter_id: Optional[str] = None
    reveal_chapter_id: Optional[str] = None
    status: str = Field(default="planted", max_length=20)
    related_characters: str = ""


class TimelineUpdate(BaseModel):
    """时间线事件更新（M 轮：全可选，PATCH 部分字段）"""
    event: Optional[str] = Field(None, max_length=300)
    era: Optional[str] = Field(None, max_length=100)
    event_date: Optional[str] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None
    involved_characters: Optional[str] = None


class ForeshadowUpdate(BaseModel):
    """伏笔更新（M 轮：全可选，含状态流转）"""
    description: Optional[str] = None
    plant_chapter_id: Optional[str] = None
    reveal_chapter_id: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)
    related_characters: Optional[str] = None


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


# ── World Setting (M2) ───────────────────────────────────────────

@router.post("/world", status_code=201)
async def create_world_setting(project_id: str, payload: WorldSettingCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "world", payload.model_dump())


@router.get("/world")
async def list_world_settings(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "world")


@router.patch("/world/{setting_id}")
async def update_world_setting(project_id: str, setting_id: str, payload: WorldSettingUpdate, db: AsyncSession = Depends(get_db)):
    return await SettingService.update(db, project_id, "world", setting_id, payload.model_dump(exclude_unset=True))


@router.delete("/world/{setting_id}", status_code=204)
async def delete_world_setting(project_id: str, setting_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "world", setting_id)


# ── Character (M3) ───────────────────────────────────────────────

@router.post("/characters", status_code=201)
async def create_character(project_id: str, payload: CharacterCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "characters", payload.model_dump())


@router.get("/characters")
async def list_characters(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "characters")


@router.get("/characters/{char_id}")
async def get_character(project_id: str, char_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.get(db, project_id, "characters", char_id)


@router.patch("/characters/{char_id}")
async def update_character(project_id: str, char_id: str, payload: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    return await SettingService.update(db, project_id, "characters", char_id, payload.model_dump(exclude_unset=True))


@router.delete("/characters/{char_id}", status_code=204)
async def delete_character(project_id: str, char_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "characters", char_id)


# ── Skill (M4) ───────────────────────────────────────────────────

@router.post("/skills", status_code=201)
async def create_skill(project_id: str, payload: SkillCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "skills", payload.model_dump())


@router.get("/skills")
async def list_skills(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "skills")


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(project_id: str, skill_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "skills", skill_id)


# ── Item (M5) ────────────────────────────────────────────────────

@router.post("/items", status_code=201)
async def create_item(project_id: str, payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "items", payload.model_dump())


@router.get("/items")
async def list_items(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "items")


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(project_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "items", item_id)


# ── Faction (M6) ─────────────────────────────────────────────────

@router.post("/factions", status_code=201)
async def create_faction(project_id: str, payload: FactionCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "factions", payload.model_dump())


@router.get("/factions")
async def list_factions(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "factions")


@router.delete("/factions/{faction_id}", status_code=204)
async def delete_faction(project_id: str, faction_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "factions", faction_id)


# ── Outline (M7) ─────────────────────────────────────────────────

@router.post("/outlines", status_code=201)
async def create_outline(project_id: str, payload: OutlineCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "outlines", payload.model_dump())


@router.get("/outlines")
async def list_outlines(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "outlines")


@router.patch("/outlines/{outline_id}")
async def update_outline(project_id: str, outline_id: str, payload: OutlineUpdate, db: AsyncSession = Depends(get_db)):
    return await SettingService.update(db, project_id, "outlines", outline_id, payload.model_dump(exclude_unset=True))


@router.delete("/outlines/{outline_id}", status_code=204)
async def delete_outline(project_id: str, outline_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "outlines", outline_id)


# ── Location (M8) ────────────────────────────────────────────────

@router.post("/locations", status_code=201)
async def create_location(project_id: str, payload: LocationCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "locations", payload.model_dump())


@router.get("/locations")
async def list_locations(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "locations")


@router.delete("/locations/{location_id}", status_code=204)
async def delete_location(project_id: str, location_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "locations", location_id)


# ── Timeline (M9) ────────────────────────────────────────────────

@router.post("/timelines", status_code=201)
async def create_timeline(project_id: str, payload: TimelineCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "timelines", payload.model_dump())


@router.get("/timelines")
async def list_timelines(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "timelines")


@router.patch("/timelines/{timeline_id}")
async def update_timeline(project_id: str, timeline_id: str, payload: TimelineUpdate, db: AsyncSession = Depends(get_db)):
    """更新时间线事件（M 轮）"""
    return await SettingService.update(db, project_id, "timelines", timeline_id, payload.model_dump(exclude_unset=True))


@router.delete("/timelines/{timeline_id}", status_code=204)
async def delete_timeline(project_id: str, timeline_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "timelines", timeline_id)


# ── Foreshadow (M10) ─────────────────────────────────────────────

@router.post("/foreshadows", status_code=201)
async def create_foreshadow(project_id: str, payload: ForeshadowCreate, db: AsyncSession = Depends(get_db)):
    return await SettingService.create(db, project_id, "foreshadows", payload.model_dump())


@router.get("/foreshadows")
async def list_foreshadows(project_id: str, db: AsyncSession = Depends(get_db)):
    return await SettingService.list(db, project_id, "foreshadows")


@router.patch("/foreshadows/{foreshadow_id}")
async def update_foreshadow(project_id: str, foreshadow_id: str, payload: ForeshadowUpdate, db: AsyncSession = Depends(get_db)):
    """更新伏笔（含 planted→revealed 状态流转，M 轮）"""
    return await SettingService.update(db, project_id, "foreshadows", foreshadow_id, payload.model_dump(exclude_unset=True))


@router.delete("/foreshadows/{foreshadow_id}", status_code=204)
async def delete_foreshadow(project_id: str, foreshadow_id: str, db: AsyncSession = Depends(get_db)):
    await SettingService.delete(db, project_id, "foreshadows", foreshadow_id)


@router.post("/audit")
async def audit_settings(project_id: str, db: AsyncSession = Depends(get_db)):
    """全项目设定体检（N 轮）：LLM 一致性扫描全部设定"""
    return await SettingService.audit(db, project_id)


# ── AI 辅助生成端点 ─────────────────────────────────────────────

@router.post("/ai/generate-world", response_model=AIGenerateResponse)
async def ai_generate_world_setting(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_world(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-character", response_model=AIGenerateResponse)
async def ai_generate_character(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_character(db, project_id, payload.name, payload.role, payload.category, payload.extra)


@router.post("/ai/generate-item", response_model=AIGenerateResponse)
async def ai_generate_item(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_item(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-skill", response_model=AIGenerateResponse)
async def ai_generate_skill(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_skill(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-faction", response_model=AIGenerateResponse)
async def ai_generate_faction(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_faction(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-location", response_model=AIGenerateResponse)
async def ai_generate_location(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_location(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-timeline", response_model=AIGenerateResponse)
async def ai_generate_timeline(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    """AI 生成时间线事件（M 轮）"""
    return await SettingService.ai_generate_timeline(db, project_id, payload.name, payload.category, payload.extra)


@router.post("/ai/generate-outline", response_model=AIGenerateResponse)
async def ai_generate_outline(project_id: str, payload: AIGenerateRequest, db: AsyncSession = Depends(get_db)):
    return await SettingService.ai_generate_outline(db, project_id, payload.name, payload.category, payload.extra)
