"""内置工具集 — web_search / setting_query / chapter_get / project_summary / 角色/兵器/世界观/伏笔查询

每个工具模块暴露 <name>_tool 实例（registry._load_builtin 自动扫描 *_tool 属性）。
"""

from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select, or_

from app.core.tools.base import BaseTool, ToolResult
from app.database import async_session_factory
from app.models.character import Character
from app.models.foreshadow import Foreshadow
from app.models.item import Item
from app.models.project import Project
from app.models.world_setting import WorldSetting
from app.services.search_service import SearchService


# ── web_search ───────────────────────────────────────────────────

class WebSearchArgs(BaseModel):
    query: str = Field(..., description="搜索关键词")
    max_results: int = Field(5, ge=1, le=10, description="返回结果数")


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "网络搜索（Tavily/DuckDuckGo/其他后端自动降级），返回带标题与摘要的结果列表，用于查证史实、文化背景、流行题材等"
    args_schema = WebSearchArgs

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        results = await SearchService.search_web(query, max_results)
        if not results:
            return ToolResult(ok=False, error="搜索无结果")
        text = "\n".join(
            f"[{i+1}] {r['title']}\n{r['snippet']}\n来源: {r['url']}"
            for i, r in enumerate(results)
        )
        return ToolResult(ok=True, content=text, data={"results": results})


web_search_tool = WebSearchTool()


# ── setting_query ────────────────────────────────────────────────

class SettingQueryArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    module: str = Field(..., description="模块: world/characters/skills/items/factions/outlines/locations/timelines/foreshadows")
    keyword: str = Field("", description="关键词（留空返回全部）")


class SettingQueryTool(BaseTool):
    name = "setting_query"
    description = "按关键词查询项目的设定数据（世界观/角色/技能/道具/势力/大纲/场景/时间线/伏笔）"
    args_schema = SettingQueryArgs

    async def execute(self, project_id: str, module: str, keyword: str = "") -> ToolResult:
        from app.models.faction import Faction
        from app.models.location import Location
        from app.models.outline import Outline
        from app.models.skill import Skill
        from app.models.timeline import Timeline

        model_map = {
            "world": WorldSetting, "characters": Character, "skills": Skill, "items": Item,
            "factions": Faction, "outlines": Outline, "locations": Location,
            "timelines": Timeline, "foreshadows": Foreshadow,
        }
        model = model_map.get(module)
        if not model:
            return ToolResult(ok=False, error=f"未知模块: {module}")
        cols = [c.name for c in model.__table__.columns if c.name not in ("id", "project_id", "created_at", "updated_at")]
        async with async_session_factory() as db:
            stmt = select(model).where(model.project_id == project_id)
            if keyword:
                like = f"%{keyword}%"
                conds = []
                for c in cols:
                    if c in ("name", "title", "description", "content", "background", "summary", "event", "category", "type", "role"):
                        conds.append(getattr(model, c).ilike(like))
                if conds:
                    stmt = stmt.where(or_(*conds))
            rows = (await db.execute(stmt.limit(20))).scalars().all()
        items = [
            {c: str(getattr(r, c, ""))[:200] for c in cols if getattr(r, c, None)}
            for r in rows
        ]
        if not items:
            return ToolResult(ok=True, content=f"[{module}] 无匹配设定", data=[])
        text = "\n".join(f"- {item}" for item in items)
        return ToolResult(ok=True, content=f"[{module}] 共 {len(items)} 条:\n{text}", data=items)


setting_query_tool = SettingQueryTool()


# ── chapter_get ──────────────────────────────────────────────────

class ChapterGetArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    excerpt: int = Field(1500, ge=100, le=8000, description="返回内容长度")


class ChapterGetTool(BaseTool):
    name = "chapter_get"
    description = "获取指定章节的标题与正文（用于保持前后文连贯、避免重复内容）"
    args_schema = ChapterGetArgs

    async def execute(self, project_id: str, chapter_number: int, excerpt: int = 1500) -> ToolResult:
        from app.models.chapter import Chapter

        async with async_session_factory() as db:
            ch = (await db.execute(
                select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_number == chapter_number)
            )).scalar_one_or_none()
        if not ch:
            return ToolResult(ok=False, error=f"第 {chapter_number} 章不存在")
        return ToolResult(
            ok=True,
            content=f"第{ch.chapter_number}章《{ch.title}》\n{(ch.content or '')[:excerpt]}",
            data={"id": ch.id, "title": ch.title},
        )


chapter_get_tool = ChapterGetTool()


# ── project_summary ──────────────────────────────────────────────

class ProjectSummaryArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")


class ProjectSummaryTool(BaseTool):
    name = "project_summary"
    description = "获取项目整体概况：类型、简介、各设定模块与章节数量"
    args_schema = ProjectSummaryArgs

    async def execute(self, project_id: str) -> ToolResult:
        from app.models.chapter import Chapter
        from app.models.skill import Skill

        async with async_session_factory() as db:
            proj = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
            if not proj:
                return ToolResult(ok=False, error="项目不存在")
            counts = {}
            for label, model in (("world", WorldSetting), ("characters", Character), ("skills", Skill), ("items", Item), ("foreshadows", Foreshadow), ("chapters", Chapter)):
                n = (await db.execute(select(model).where(model.project_id == project_id))).scalars().all()
                counts[label] = len(n)
        text = f"《{proj.title}》[{proj.genre}] {proj.synopsis or ''}\n" + " | ".join(f"{k}:{v}" for k, v in counts.items())
        return ToolResult(ok=True, content=text, data={"project": proj.title, "counts": counts})


project_summary_tool = ProjectSummaryTool()


# ── character_lookup ─────────────────────────────────────────────

class CharacterLookupArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    name: str = Field("", description="角色名关键词（留空返回全部）")


class CharacterLookupTool(BaseTool):
    name = "character_lookup"
    description = "查询项目角色设定（性格/背景/能力/关系），用于保证角色行为一致性"
    args_schema = CharacterLookupArgs

    async def execute(self, project_id: str, name: str = "") -> ToolResult:
        async with async_session_factory() as db:
            stmt = select(Character).where(Character.project_id == project_id)
            if name:
                stmt = stmt.where(Character.name.ilike(f"%{name}%"))
            rows = (await db.execute(stmt.limit(20))).scalars().all()
        items = [
            {"name": r.name, "role": r.role, "personality": (r.personality or "")[:150],
             "background": (r.background or "")[:300], "abilities": (r.abilities or "")[:150]}
            for r in rows
        ]
        if not items:
            return ToolResult(ok=False, error="无匹配角色")
        text = "\n".join(f"- {i['name']}[{i['role']}]: {i['personality']} {i['background']}" for i in items)
        return ToolResult(ok=True, content=text, data=items)


character_lookup_tool = CharacterLookupTool()


# ── weapon_lookup ────────────────────────────────────────────────

class WeaponLookupArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    name: str = Field("", description="兵器名关键词（留空返回全部）")


class WeaponLookupTool(BaseTool):
    name = "weapon_lookup"
    description = "查询项目兵器（道具 category=weapon）设定：外观/效果/来源/限制"
    args_schema = WeaponLookupArgs

    async def execute(self, project_id: str, name: str = "") -> ToolResult:
        async with async_session_factory() as db:
            stmt = select(Item).where(Item.project_id == project_id, Item.category == "weapon")
            if name:
                stmt = stmt.where(Item.name.ilike(f"%{name}%"))
            rows = (await db.execute(stmt.limit(20))).scalars().all()
        items = [
            {"name": r.name, "rarity": r.rarity, "description": (r.description or "")[:300], "effects": (r.effects or "")[:150]}
            for r in rows
        ]
        if not items:
            return ToolResult(ok=False, error="无匹配兵器")
        text = "\n".join(f"- {i['name']}({i['rarity']}): {i['description']}" for i in items)
        return ToolResult(ok=True, content=text, data=items)


weapon_lookup_tool = WeaponLookupTool()


# ── world_setting_lookup ─────────────────────────────────────────

class WorldSettingLookupArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    name: str = Field("", description="设定名关键词（留空返回全部）")
    category: str = Field("", description="类别过滤: general/power_system/race/culture/geography/history")


class WorldSettingLookupTool(BaseTool):
    name = "world_setting_lookup"
    description = "查询项目世界观设定（力量体系/种族/文化/地理/历史），用于保证设定一致"
    args_schema = WorldSettingLookupArgs

    async def execute(self, project_id: str, name: str = "", category: str = "") -> ToolResult:
        async with async_session_factory() as db:
            stmt = select(WorldSetting).where(WorldSetting.project_id == project_id)
            if name:
                stmt = stmt.where(WorldSetting.name.ilike(f"%{name}%"))
            if category:
                stmt = stmt.where(WorldSetting.category == category)
            rows = (await db.execute(stmt.limit(20))).scalars().all()
        items = [
            {"name": r.name, "category": r.category, "content": (r.content or "")[:400]}
            for r in rows
        ]
        if not items:
            return ToolResult(ok=False, error="无匹配世界观设定")
        text = "\n".join(f"- {i['name']}[{i['category']}]: {i['content']}" for i in items)
        return ToolResult(ok=True, content=text, data=items)


world_setting_lookup_tool = WorldSettingLookupTool()


# ── foreshadow_query ─────────────────────────────────────────────

class ForeshadowQueryArgs(BaseModel):
    project_id: str = Field(..., description="项目ID")
    status: str = Field("planted", description="状态: planted/revealed/abandoned（留空全部）")


class ForeshadowQueryTool(BaseTool):
    name = "foreshadow_query"
    description = "查询项目伏笔（已埋设/已回收），用于写作时埋设新伏笔或回收旧伏笔"
    args_schema = ForeshadowQueryArgs

    async def execute(self, project_id: str, status: str = "") -> ToolResult:
        async with async_session_factory() as db:
            stmt = select(Foreshadow).where(Foreshadow.project_id == project_id)
            if status:
                stmt = stmt.where(Foreshadow.status == status)
            rows = (await db.execute(stmt.limit(30))).scalars().all()
        items = [{"id": r.id, "description": (r.description or "")[:200], "status": r.status} for r in rows]
        if not items:
            return ToolResult(ok=True, content="无伏笔记录", data=[])
        text = "\n".join(f"- [{i['status']}] {i['description']}" for i in items)
        return ToolResult(ok=True, content=text, data=items)


foreshadow_query_tool = ForeshadowQueryTool()
