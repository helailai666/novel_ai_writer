"""章节写作图节点 — retrieve_context / write_draft(流式) / review_draft / persist_chapter

迁移自旧 WriterAgent / ReviewAgent；审核未过触发重写循环（由图的条件边驱动）。
"""

import json
import logging
from typing import Optional

from sqlalchemy import select

from app.agents import events
from app.agents.nodes.common import (
    REVIEWER_SYSTEM,
    REVIEW_JSON_SCHEMA,
    WRITER_SYSTEM,
    build_chapter_task,
    build_continue_task,
    build_polish_task,
    build_review_task,
    enhance_system,
    is_mock_provider,
    messages,
    resolve_llm,
    skill_context,
)
from app.agents.state import NovelState
from app.database import async_session_factory
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.foreshadow import Foreshadow
from app.models.item import Item
from app.models.project import Project
from app.models.world_setting import WorldSetting

logger = logging.getLogger(__name__)


async def retrieve_context(state: NovelState) -> dict:
    """检索项目设定 / 前文 / 未回收伏笔 / 知识库 / 热梗 → settings_snapshot + knowledge"""
    evs = [events.node_start("retrieve_context")]
    snapshot: dict = {"project": {}, "settings": [], "previous_tail": "", "foreshadows": []}
    knowledge: list[dict] = []
    try:
        async with async_session_factory() as db:
            pid = state["project_id"]
            proj = (await db.execute(select(Project).where(Project.id == pid))).scalar_one_or_none()
            if proj:
                snapshot["project"] = {"title": proj.title, "genre": proj.genre, "synopsis": proj.synopsis}

            for model in (WorldSetting, Character, Item):
                rows = (await db.execute(select(model).where(model.project_id == pid))).scalars().all()
                for r in rows:
                    cols = [c.name for c in model.__table__.columns if c.name not in ("id", "project_id", "created_at", "updated_at")]
                    snapshot["settings"].append({c: getattr(r, c) for c in cols if getattr(r, c, None)})

            # 前文（最近一章的结尾，用于续写连贯）
            ch = (await db.execute(
                select(Chapter).where(Chapter.project_id == pid).order_by(Chapter.chapter_number.desc()).limit(1)
            )).scalar_one_or_none()
            if ch and ch.content:
                snapshot["previous_tail"] = ch.content[-1500:]

            # 未回收伏笔
            fs = (await db.execute(
                select(Foreshadow).where(Foreshadow.project_id == pid, Foreshadow.status == "planted").limit(20)
            )).scalars().all()
            snapshot["foreshadows"] = [f.description[:200] for f in fs]

        # 知识库混合检索（项目级+全局；P4 起可用向量检索）
        try:
            from app.services.knowledge_service import KnowledgeService

            task = state.get("task") or state.get("prompt") or ""
            if task:
                kb = await KnowledgeService.search(task, state["project_id"], top_k=4, include_memes=True)
                snapshot["knowledge"] = kb.get("docs") or []
                snapshot["memes"] = kb.get("memes") or []
                knowledge = (kb.get("docs") or []) + (kb.get("memes") or [])
        except Exception as e:
            logger.warning(f"知识库检索失败（不影响写作）: {e}")
    except Exception as e:
        logger.warning(f"retrieve_context failed: {e}")
    evs.append(events.node_end("retrieve_context"))
    return {"settings_snapshot": snapshot, "knowledge": knowledge, "events": evs}


def _context_text(state: NovelState) -> str:
    snap = state.get("settings_snapshot") or {}
    parts = []
    proj = snap.get("project") or {}
    if proj:
        parts.append(f"作品:《{proj.get('title','')}》 类型: {proj.get('genre','')}")
    for s in snap.get("settings", [])[:30]:
        label = " / ".join(str(s.get(k, "")) for k in ("name", "title", "category", "role") if s.get(k))
        body = str(s.get("content") or s.get("background") or s.get("description") or "")[:300]
        if label or body:
            parts.append(f"- {label}: {body}")
    if snap.get("previous_tail"):
        parts.append(f"【前文结尾】\n{snap['previous_tail']}")
    if snap.get("foreshadows"):
        parts.append(f"【待回收伏笔】{'; '.join(snap['foreshadows'])}")
    if snap.get("knowledge"):
        parts.append("【知识库资料】")
        for d in snap["knowledge"][:5]:
            parts.append(f"- {d.get('title','')}({d.get('category','')}): {(d.get('content') or d.get('meaning') or '')[:300]}")
    if snap.get("memes"):
        parts.append("【可用热梗】")
        for m in snap["memes"][:5]:
            parts.append(f"- {m.get('phrase','')}: {m.get('meaning','')} 例: {m.get('usage_example','')}")
    return "\n".join(parts)


def _build_writing_task(state: NovelState) -> str:
    mode = state.get("mode") or "generate"
    prompt = state.get("prompt") or ""
    if mode == "continue":
        return build_continue_task(state.get("content") or _context_text(state), state.get("extra") or "")
    if mode == "polish":
        return build_polish_task(state.get("content") or "", state.get("style") or "general")
    # generate / rewrite
    task = build_chapter_task(prompt, state.get("style") or "narrative", state.get("target_word_count") or 2000)
    if mode == "rewrite" and state.get("review"):
        rev = state["review"]
        feedback = "\n".join(rev.get("suggestions", [])[:5])
        task += f"\n\n【上一稿审核反馈，请针对性修改】\n{feedback}\n【上一稿】\n{(state.get('draft') or '')[:3000]}"
    return task


# 写作图工具白名单（P3：设定/角色/兵器/世界观/伏笔查询 + 搜索；P4 增补知识检索/热梗）
WRITER_TOOL_NAMES = [
    "setting_query",
    "character_lookup",
    "weapon_lookup",
    "world_setting_lookup",
    "foreshadow_query",
    "web_search",
    "knowledge_retrieve",
    "hot_meme_lookup",
]


async def write_draft(state: NovelState) -> dict:
    """流式写作：产出 token 事件 + 完整草稿

    generate/rewrite 模式启用工具循环（ReAct）；continue/polish 保持纯流式打字机。
    """
    from app.core.llm import LLMRequest

    node = "write_draft"
    llm = resolve_llm(state)
    evs = [events.node_start(node)]
    task = _build_writing_task(state)
    context_text = _context_text(state)
    user_msg = f"【上下文】\n{context_text or '无'}\n\n【任务】\n{task}" if context_text else task
    try:
        mode = state.get("mode") or "generate"
        if mode in ("generate", "rewrite"):
            # 工具循环路径（ReAct）：writer 可自主查询设定/兵器/世界观/搜索
            from app.agents.nodes.tool_loop import resolve_tools, run_tool_loop

            system = enhance_system(state, WRITER_SYSTEM)
            ctx = skill_context(state)
            tools = resolve_tools(list(dict.fromkeys(WRITER_TOOL_NAMES + ctx["tools"])))

            async def _emit(ev: dict):
                evs.append(ev)

            if tools:
                _, final_text = await run_tool_loop(llm, system, user_msg, tools, emit=_emit)
                content = final_text.strip()
                if content:
                    # 最终文本作为单条 token 事件输出（保持 SSE 兼容）
                    evs.append(events.token(content))
                return {
                    "draft": content,
                    "revision_round": (state.get("revision_round") or 0) + 1,
                    "events": evs + [events.node_end(node)],
                    "final_output": {"content": content, "is_mock": is_mock_provider(llm)},
                }

        # 纯流式路径（无工具或 continue/polish）
        full = ""
        mock = is_mock_provider(llm)
        system = enhance_system(state, WRITER_SYSTEM)
        async for chunk in llm.astream(LLMRequest(messages=messages(system, user_msg))):
            if chunk:
                full += chunk
                evs.append(events.token(chunk))
        content = full.strip()
        return {
            "draft": content,
            "revision_round": (state.get("revision_round") or 0) + 1,
            "events": evs + [events.node_end(node)],
            "final_output": {"content": content, "is_mock": mock},
        }
    except Exception as e:
        logger.error(f"write_draft failed: {e}")
        return {"events": evs + [events.error(str(e))]}


async def review_draft(state: NovelState) -> dict:
    """综合审核草稿（结构化 JSON）：score / issues / suggestions / dimension_scores"""
    node = "review_draft"
    llm = resolve_llm(state)
    evs = [events.node_start(node)]
    content = state.get("draft") or ""
    try:
        from app.core.llm import LLMRequest

        system = enhance_system(state, REVIEWER_SYSTEM)
        resp = await llm.acomplete(
            LLMRequest(
                messages=messages(system, build_review_task("comprehensive", content, state.get("context") or "")),
                response_format=REVIEW_JSON_SCHEMA,
            )
        )
        data = _parse_json(resp.content)
        score = int(data.get("score", 0) or 0)
        evs.append(events.review("comprehensive", score))
        # checkpoint：重写轮次状态
        threshold = state.get("review_threshold", 75)
        max_rounds = state.get("max_revisions", 2)
        cur_round = state.get("revision_round") or 0
        status = "rewrite" if score < threshold and cur_round < max_rounds else "approved"
        evs.append(events.checkpoint(cur_round, status))
        evs.append(events.node_end(node))
        return {"review": data, "events": evs}
    except Exception as e:
        logger.error(f"review_draft failed: {e}")
        return {"review": {"score": 0, "issues": [], "suggestions": [], "summary": f"审核失败: {e}"},
                "events": evs + [events.error(str(e))]}


def should_rewrite(state: NovelState) -> str:
    """审核未过且未达最大轮数 → rewrite；无草稿或已达上限 → persist"""
    if not (state.get("draft") or "").strip():
        return "persist"
    score = int((state.get("review") or {}).get("score", 0) or 0)
    threshold = state.get("review_threshold", 75)
    max_rounds = state.get("max_revisions", 2)
    if score < threshold and (state.get("revision_round") or 0) < max_rounds:
        return "rewrite"
    return "persist"


async def persist_chapter(state: NovelState) -> dict:
    """保存章节：generate=新建 / continue=追加 / polish|rewrite=替换"""
    node = "persist_chapter"
    evs = [events.node_start(node)]
    content = (state.get("draft") or "").strip()
    if not content:
        evs.append(events.error("草稿为空，跳过保存"))
        return {"events": evs}
    mode = state.get("mode") or "generate"
    try:
        async with async_session_factory() as db:
            pid = state["project_id"]
            if mode == "continue" and state.get("chapter_id"):
                ch = (await db.execute(
                    select(Chapter).where(Chapter.id == state["chapter_id"], Chapter.project_id == pid)
                )).scalar_one_or_none()
                if ch:
                    ch.content = ch.content + "\n\n" + content
                    ch.word_count = len(ch.content)
                    await db.flush()
                    await db.refresh(ch)
                    await db.commit()
                    final = {"saved": True, "id": ch.id, "chapter_number": ch.chapter_number, "mode": mode}
                    evs.append(events.node_end(node))
                    return {"final_output": final, "events": evs}
            if mode in ("polish", "rewrite") and state.get("chapter_id"):
                ch = (await db.execute(
                    select(Chapter).where(Chapter.id == state["chapter_id"], Chapter.project_id == pid)
                )).scalar_one_or_none()
                if ch:
                    ch.content = content
                    ch.word_count = len(content)
                    await db.flush()
                    await db.refresh(ch)
                    await db.commit()
                    final = {"saved": True, "id": ch.id, "chapter_number": ch.chapter_number, "mode": mode}
                    evs.append(events.node_end(node))
                    return {"final_output": final, "events": evs}
            # generate：新建章节
            ch = Chapter(
                project_id=pid,
                title=f"Chapter {state.get('chapter_number', 1)}",
                volume_id=state.get("volume_id"),
                chapter_number=int(state.get("chapter_number", 1)),
                content=content,
                word_count=len(content),
                ai_prompt_used=state.get("prompt") or "",
                status="draft",
            )
            db.add(ch)
            await db.flush()
            await db.refresh(ch)
            await db.commit()
            final = {"saved": True, "id": ch.id, "chapter_number": ch.chapter_number, "mode": "generate"}
            evs.append(events.node_end(node))
            return {"final_output": final, "events": evs}
    except Exception as e:
        logger.error(f"persist_chapter failed: {e}")
        evs.append(events.error(str(e)))
        return {"events": evs}


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"score": 0, "summary": "[解析失败] 请配置支持 JSON 输出的模型", "issues": [], "suggestions": [], "highlights": []}
