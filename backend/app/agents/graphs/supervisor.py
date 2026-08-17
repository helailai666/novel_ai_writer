"""Supervisor 顶层对话图 — 自由文本任务自动路由到三条子图

分类策略：关键词匹配（确定性，零额外 LLM 成本）；子图作为节点嵌入。
"""

import logging

from langgraph.graph import END, START, StateGraph

from app.agents import events
from app.agents.state import NovelState

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


def classify(task: str) -> tuple[str, dict]:
    """返回 (intent, 补丁字段)

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


async def supervisor_node(state: NovelState) -> dict:
    """意图分类 → 写入 graph/kind 等字段"""
    evs = [events.node_start("supervisor")]
    intent, patch = classify(state.get("task") or "")
    evs.append({"type": "route", "intent": intent, "task": (state.get("task") or "")[:100]})
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
