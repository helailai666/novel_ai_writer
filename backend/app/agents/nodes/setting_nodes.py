"""设定生成图节点 — assemble / generate_* / consistency_check / persist

迁移自旧 CreativeAgent 的生成逻辑；LLM 调用统一走 core/llm 工厂。
"""

import logging
from typing import Optional

from sqlalchemy import select

from app.agents import events
from app.agents.nodes.common import (
    CREATIVE_SYSTEM,
    build_character_task,
    build_faction_task,
    build_item_task,
    build_location_task,
    build_outline_task,
    build_skill_task,
    build_world_task,
    enhance_system,
    is_mock_provider,
    messages,
    resolve_llm,
)

# 设定图工具白名单（P3 补全）：查证参考 / 知识库 / 已有设定
SETTING_TOOL_NAMES = ["web_search", "knowledge_retrieve", "setting_query"]
from app.agents.state import NovelState
from app.database import async_session_factory
from app.models.character import Character
from app.models.faction import Faction
from app.models.item import Item
from app.models.location import Location
from app.models.outline import Outline
from app.models.project import Project
from app.models.skill import Skill
from app.models.world_setting import WorldSetting

logger = logging.getLogger(__name__)


async def assemble_context(state: NovelState) -> dict:
    """加载项目信息与已有设定，构造上下文快照"""
    evs = [events.node_start("assemble_context")]
    snapshot: dict = {}
    try:
        async with async_session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == state["project_id"]))
            project = result.scalar_one_or_none()
            if project:
                snapshot["project"] = {"title": project.title, "genre": project.genre, "synopsis": project.synopsis}
            # 项目级技能（请求未显式指定时使用项目配置）
            project_skills = None
            if project and project.skill_packs and not state.get("skills"):
                project_skills = [s.strip() for s in project.skill_packs.split(",") if s.strip()]
            for model in (WorldSetting, Character, Item, Skill, Faction):
                rows = (await db.execute(select(model).where(model.project_id == state["project_id"]))).scalars().all()
                cols = [c.name for c in model.__table__.columns if c.name not in ("id", "project_id", "created_at", "updated_at")]
                snapshot[model.__tablename__] = [
                    {c: getattr(r, c) for c in cols if getattr(r, c, None)} for r in rows[:20]
                ]
    except Exception as e:  # 上下文加载失败不阻断生成
        logger.warning(f"assemble_context failed: {e}")
    ret: dict = {"settings_snapshot": snapshot, "events": evs}
    if "project_skills" in locals() and project_skills:
        ret["skills"] = project_skills
    return ret


def route_kind(state: NovelState) -> str:
    """按 kind/category 路由到对应生成节点"""
    return state.get("kind") or "world"


async def _generate(state: NovelState, task: str, node_name: str = "generate") -> dict:
    """通用生成：调用 LLM（可启用工具循环），产出 draft + final_output

    工具白名单: web_search（查证参考）/ knowledge_retrieve（知识库）/ setting_query（已有设定）
    """
    from app.core.llm import LLMRequest

    llm = resolve_llm(state)
    evs = [events.node_start(node_name)]
    try:
        system = enhance_system(state, CREATIVE_SYSTEM)
        from app.agents.nodes.tool_loop import resolve_tools, run_tool_loop

        tools = resolve_tools(SETTING_TOOL_NAMES)
        if tools:
            async def _emit(ev: dict):
                evs.append(ev)

            _, final_text = await run_tool_loop(llm, system, task, tools, emit=_emit)
            content = final_text.strip()
        else:
            resp = await llm.acomplete(LLMRequest(messages=messages(system, task)))
            content = resp.content.strip()
        mock = is_mock_provider(llm)
        return {
            "draft": content,
            "final_output": {"content": content, "is_mock": mock},
            "events": evs + [events.node_end(node_name)],
        }
    except Exception as e:
        logger.error(f"generate failed: {e}")
        return {"final_output": {"content": "", "is_mock": True, "error": str(e)},
                "events": evs + [events.error(str(e))]}


async def generate_world(state: NovelState) -> dict:
    name = state.get("name") or "未命名设定"
    category = state.get("category") or "general"
    task = build_world_task(name, category)
    return await _generate(state, task, "generate_world")


async def generate_character(state: NovelState) -> dict:
    name = state.get("name") or "未命名角色"
    role = state.get("role") or "supporting"
    return await _generate(state, build_character_task(name, role), "generate_character")


async def generate_item(state: NovelState) -> dict:
    name = state.get("name") or "未命名道具"
    category = state.get("category") or "weapon"
    return await _generate(state, build_item_task(name, category), "generate_item")


async def generate_skill(state: NovelState) -> dict:
    name = state.get("name") or "未命名技能"
    category = state.get("category") or "magic"
    return await _generate(state, build_skill_task(name, category), "generate_skill")


async def generate_faction(state: NovelState) -> dict:
    name = state.get("name") or "未命名势力"
    category = state.get("category") or "kingdom"
    return await _generate(state, build_faction_task(name, category), "generate_faction")


async def generate_location(state: NovelState) -> dict:
    name = state.get("name") or "未命名地点"
    category = state.get("category") or "city"
    return await _generate(state, build_location_task(name, category), "generate_location")


async def generate_outline(state: NovelState) -> dict:
    name = state.get("name") or "未命名大纲节点"
    level = int(state.get("category") or "1") if (state.get("category") or "x").isdigit() else 1
    return await _generate(state, build_outline_task(name, level), "generate_outline")


async def consistency_check(state: NovelState) -> dict:
    """设定一致性预检（P3 接入 setting_query 工具后增强；当前为占位）"""
    return {"events": [events.node_start("consistency_check"), events.node_end("consistency_check")]}


async def persist_setting(state: NovelState) -> dict:
    """把生成的设定保存到对应数据表"""
    evs = [events.node_start("persist_setting")]
    content = (state.get("draft") or "").strip()
    kind = state.get("kind") or "world"
    name = state.get("name") or "未命名"
    category = state.get("category") or "general"
    if not content:
        evs.append(events.error("生成内容为空，跳过保存"))
        return {"events": evs}
    try:
        async with async_session_factory() as db:
            model_map = {
                "world": (WorldSetting, {"name": name, "category": category, "content": content}),
                "character": (Character, {"name": name, "role": state.get("role") or "supporting", "background": content}),
                "item": (Item, {"name": name, "category": category, "description": content}),
                "skill": (Skill, {"name": name, "category": category, "description": content}),
                "faction": (Faction, {"name": name, "type": category, "goal": content}),
                "location": (Location, {"name": name, "category": category, "description": content}),
                "outline": (Outline, {"title": name, "summary": content}),
            }
            model, fields = model_map[kind]
            obj = model(project_id=state["project_id"], **fields)
            db.add(obj)
            await db.flush()
            await db.refresh(obj)
            await db.commit()
            final = dict(state.get("final_output") or {})
            final["saved"] = True
            final["id"] = obj.id
            evs.append(events.node_end("persist_setting"))
            return {"final_output": final, "events": evs}
    except Exception as e:
        logger.error(f"persist_setting failed: {e}")
        evs.append(events.error(str(e)))
        return {"events": evs}
