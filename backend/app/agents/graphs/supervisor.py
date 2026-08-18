"""Supervisor 顶层对话图 — 自由文本任务自动路由到三条子图

分类策略（双层，G1 增强）：
1. LLM 意图分类（AGENT_LLM_SUPERVISOR=True 时启用）— 结构化 JSON 输出
2. 关键词回退（确定性，零额外成本）— LLM 不可用 / 解析失败 / 结果非法时
子图作为节点嵌入。
"""

import json
import logging
from typing import Optional

from langgraph.graph import END, START, StateGraph

from app.agents import events
from app.agents.nodes.common import messages
from app.agents.state import NovelState
from app.config import settings
from app.core.cache import TTLCache
from app.core.llm import LLMRequest, create

logger = logging.getLogger(__name__)

_SETTING_KINDS = {
    "世界观": "world", "设定": "world", "世界": "world",
    "角色": "character", "人物": "character",
    "道具": "item", "兵器": "item", "法宝": "item",
    "技能": "skill", "功法": "skill", "能力": "skill",
    "势力": "faction", "宗门": "faction", "组织": "faction",
    "地点": "location", "场景": "location", "地图": "location",
    "大纲": "outline", "剧情大纲": "outline",
}
_REVIEW_KEYWORDS = ("审核", "检查", "评估", "评分", "审校", "一致性", "连贯", "伏笔管理")
_WRITE_KEYWORDS = ("写", "生成", "创作", "续写", "润色", "章", "正文", "故事")

_VALID_INTENTS = {"review", "setting", "chapter"}
_VALID_KINDS = {"world", "character", "item", "skill", "faction", "location", "outline"}

_CLASSIFY_SYSTEM = """你是小说创作平台的意图分类器。根据用户任务，判断应路由到哪条处理流水线：
- review: 审核/检查/评估既有内容（一致性、逻辑、伏笔、评分等）
- setting: 生成/设计世界观设定（世界观/角色/道具/技能/势力/地点/大纲）
- chapter: 写作/续写/润色章节正文
只输出 JSON：{"intent": "review|setting|chapter", "kind": "world|character|item|skill|faction|location|outline|null"}。
kind 仅在 intent=setting 时填写，其余为 null。"""

# 分类结果缓存（H1 成本门控）：相同任务文本免重复 LLM 调用
_classify_cache = TTLCache(ttl=settings.agent.llm_supervisor_cache_ttl, max_entries=512)


def _classify_key(task: str) -> str:
    """归一化任务文本作为缓存 key（折叠空白）"""
    return " ".join((task or "").split())


def classify(task: str) -> tuple[str, dict]:
    """关键词分类（确定性回退）→ (intent, 补丁字段)

    顺序：审核意图优先（"检查设定一致性"→review）> 设定意图 > 写作意图
    """
    task = task or ""
    if any(k in task for k in _REVIEW_KEYWORDS):
        return "review", {}
    for kw, kind in _SETTING_KINDS.items():
        if kw in task:
            return "setting", {"kind": kind}
    if any(k in task for k in _WRITE_KEYWORDS):
        return "chapter", {}
    return "chapter", {}


async def classify_with_llm(task: str) -> Optional[tuple[str, dict]]:
    """LLM 意图分类 — 返回 (intent, patch)；失败/非法结果返回 None（调用方回退）

    H1 成本门控：结果按归一化任务文本缓存（TTL 内相同任务直接命中，
    不再发起 LLM 调用）；仅缓存成功分类，失败不缓存（允许重试）。
    """
    key = _classify_key(task)
    use_cache = settings.agent.llm_supervisor_cache
    if use_cache:
        _classify_cache.ttl = settings.agent.llm_supervisor_cache_ttl
        hit = _classify_cache.get(key)
        if hit is not None:
            logger.debug(f"意图分类缓存命中: {key[:60]}")
            return hit
    try:
        llm = create()
        resp = await llm.acomplete(
            LLMRequest(messages=messages(_CLASSIFY_SYSTEM, task), response_format={"type": "json_object"})
        )
        data = json.loads((resp.content or "").strip() or "{}")
        intent = str(data.get("intent") or "").strip().lower()
        if intent not in _VALID_INTENTS:
            return None
        patch: dict = {}
        if intent == "setting":
            kind = str(data.get("kind") or "").strip().lower()
            if kind in _VALID_KINDS:
                patch["kind"] = kind
        result = (intent, patch)
        if use_cache:
            _classify_cache.set(key, result)
        return result
    except Exception as e:
        logger.debug(f"LLM 意图分类失败，回退关键词: {e}")
        return None


async def supervisor_node(state: NovelState) -> dict:
    """意图分类（LLM 优先 + 关键词回退）→ 写入 graph/kind 字段"""
    evs = [events.node_start("supervisor")]
    task = state.get("task") or ""
    intent, patch, method = None, {}, "keyword"
    if settings.agent.llm_supervisor:
        result = await classify_with_llm(task)
        if result:
            intent, patch = result
            method = "llm"
    if intent is None:
        intent, patch = classify(task)
    evs.append({"type": "route", "intent": intent, "method": method, "task": task[:100]})
    evs.append(events.node_end("supervisor"))
    return {"graph": intent, **patch, "events": evs}


def _route(state: NovelState) -> str:
    return state.get("graph") or "chapter"


def build_supervisor_graph():
    """chat 图：supervisor → setting/chapter/review 子图"""
    from app.agents.graphs import get_graph

    g = StateGraph(NovelState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("setting_sub", get_graph("setting"))
    g.add_node("chapter_sub", get_graph("chapter"))
    g.add_node("review_sub", get_graph("review"))

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {
        "setting": "setting_sub", "chapter": "chapter_sub", "review": "review_sub",
    })
    g.add_edge("setting_sub", END)
    g.add_edge("chapter_sub", END)
    g.add_edge("review_sub", END)
    return g.compile()
