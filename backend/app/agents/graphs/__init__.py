"""图构建 — setting / chapter / review / qa 四条主图 + chat 顶图"""

import logging

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.chapter_nodes import (
    persist_chapter,
    retrieve_context,
    review_draft,
    should_rewrite,
    write_draft,
)
from app.agents.nodes.qa_nodes import answer_qa, retrieve_qa_context
from app.agents.nodes.review_nodes import aggregate_review, review_dim, split_review
from app.agents.nodes.setting_nodes import (
    assemble_context,
    consistency_check,
    generate_character,
    generate_faction,
    generate_item,
    generate_location,
    generate_outline,
    generate_skill,
    generate_timeline,
    generate_world,
    persist_setting,
    route_kind,
)
from app.agents.state import NovelState

logger = logging.getLogger(__name__)

_KIND_NODES = {
    "world": generate_world,
    "character": generate_character,
    "item": generate_item,
    "skill": generate_skill,
    "faction": generate_faction,
    "location": generate_location,
    "outline": generate_outline,
    "timeline": generate_timeline,  # M 轮：时间线事件
}


def build_setting_graph():
    """设定生成图：assemble → 路由 → generate_{kind} → consistency → persist"""
    g = StateGraph(NovelState)
    g.add_node("assemble_context", assemble_context)
    for name, fn in _KIND_NODES.items():
        g.add_node(f"generate_{name}", fn)
    g.add_node("consistency_check", consistency_check)
    g.add_node("persist_setting", persist_setting)

    g.add_edge(START, "assemble_context")
    g.add_conditional_edges("assemble_context", route_kind, {k: f"generate_{k}" for k in _KIND_NODES})
    for name in _KIND_NODES:
        g.add_edge(f"generate_{name}", "consistency_check")
    g.add_edge("consistency_check", "persist_setting")
    g.add_edge("persist_setting", END)
    return g.compile()


def build_chapter_graph():
    """章节写作图：retrieve → write(流式) → review → [rewrite 循环 | persist]

    continue / polish 模式跳过审核直接持久化。
    """
    g = StateGraph(NovelState)
    g.add_node("retrieve_context", retrieve_context)
    g.add_node("write_draft", write_draft)
    g.add_node("review_draft", review_draft)
    g.add_node("persist_chapter", persist_chapter)

    g.add_edge(START, "retrieve_context")
    g.add_edge("retrieve_context", "write_draft")

    def after_write(state: NovelState) -> str:
        return "persist" if state.get("mode") in ("continue", "polish") else "review"

    g.add_conditional_edges("write_draft", after_write, {"review": "review_draft", "persist": "persist_chapter"})
    g.add_conditional_edges("review_draft", should_rewrite, {"rewrite": "write_draft", "persist": "persist_chapter"})
    g.add_edge("persist_chapter", END)
    return g.compile()


def build_review_graph():
    """审核图：split(8 维并行) → review_dim → aggregate"""
    g = StateGraph(NovelState)
    g.add_node("review_dim", review_dim)
    g.add_node("aggregate_review", aggregate_review)

    g.add_conditional_edges(START, split_review, ["review_dim"])
    g.add_edge("review_dim", "aggregate_review")
    g.add_edge("aggregate_review", END)
    return g.compile()


def build_qa_graph():
    """知识问答图：retrieve（知识库+web 兜底）→ answer（流式作答）"""
    g = StateGraph(NovelState)
    g.add_node("retrieve_qa_context", retrieve_qa_context)
    g.add_node("answer_qa", answer_qa)
    g.add_edge(START, "retrieve_qa_context")
    g.add_edge("retrieve_qa_context", "answer_qa")
    g.add_edge("answer_qa", END)
    return g.compile()


def build_chat_graph():
    """Supervisor 顶层对话图（自由文本 → 自动路由子图）"""
    from app.agents.graphs.supervisor import build_supervisor_graph

    return build_supervisor_graph()


_BUILDERS = {
    "setting": build_setting_graph,
    "chapter": build_chapter_graph,
    "review": build_review_graph,
    "qa": build_qa_graph,
    "chat": build_chat_graph,
}


def get_graph(name: str):
    """获取（并缓存）指定图的已编译实例"""
    from app.agents.runner import _graph_cache

    if name not in _BUILDERS:
        raise ValueError(f"未知图: {name}，可选: {list(_BUILDERS.keys())}")
    if name not in _graph_cache:
        _graph_cache[name] = _BUILDERS[name]()
        logger.info(f"图已编译: {name}")
    return _graph_cache[name]


def list_graphs() -> list[str]:
    return list(_BUILDERS.keys())
