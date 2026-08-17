"""审核图节点 — split_review(并行) / review_dim / aggregate_review

8 大维度通过 Send 并行执行，结果聚合为综合报告。
"""

import logging
from typing import Any

from langgraph.types import Send

from app.agents import events
from app.agents.nodes.common import (
    REVIEWER_SYSTEM,
    REVIEW_JSON_SCHEMA,
    REVIEW_DIMENSIONS,
    build_review_task,
    messages,
    resolve_llm,
)
from app.agents.state import NovelState

logger = logging.getLogger(__name__)

ALL_DIMENSIONS = list(REVIEW_DIMENSIONS.keys())


def split_review(state: NovelState) -> list[Send]:
    """按维度并行分发（comprehensive 特判为单维度综合）"""
    dims = state.get("dimensions") or ALL_DIMENSIONS
    content = state.get("content") or state.get("draft") or ""
    context = state.get("context") or ""
    if "comprehensive" in dims and len(dims) == 1:
        return [Send("review_dim", {"dimension": "comprehensive", "content": content, "context": context})]
    return [
        Send("review_dim", {"dimension": d, "content": content, "context": context})
        for d in dims if d in REVIEW_DIMENSIONS
    ]


async def review_dim(state: NovelState) -> dict:
    """单个维度审核（结构化 JSON）"""
    dim = state.get("dimension") or "consistency"
    content = state.get("content") or state.get("draft") or ""
    context = state.get("context") or ""
    llm = resolve_llm(state)
    evs = [events.node_start(f"review_{dim}")]
    try:
        from app.core.llm import LLMRequest

        resp = await llm.acomplete(
            LLMRequest(
                messages=messages(REVIEWER_SYSTEM, build_review_task(dim, content, context)),
                response_format=REVIEW_JSON_SCHEMA,
            )
        )
        data = _parse_json(resp.content)
        score = int(data.get("score", 0) or 0)
        item = {
            "dimension": dim,
            "score": score,
            "summary": data.get("summary", ""),
            "issues": data.get("issues", []),
            "suggestions": data.get("suggestions", []),
            "highlights": data.get("highlights", []),
        }
        evs.append(events.review(dim, score))
        evs.append(events.node_end(f"review_{dim}"))
        return {"reviews": [item], "events": evs}
    except Exception as e:
        logger.error(f"review_dim({dim}) failed: {e}")
        return {"reviews": [{"dimension": dim, "score": 0, "summary": f"审核失败: {e}", "issues": [], "suggestions": [], "highlights": []}],
                "events": evs + [events.error(str(e))]}


async def aggregate_review(state: NovelState) -> dict:
    """聚合各维度结果 → 综合报告"""
    evs = [events.node_start("aggregate_review")]
    reviews = state.get("reviews") or []
    if not reviews:
        evs.append(events.error("无审核结果"))
        return {"events": evs}

    scores = [r.get("score", 0) for r in reviews]
    overall = round(sum(scores) / len(scores)) if scores else 0
    issues: list[str] = []
    suggestions: list[str] = []
    highlights: list[str] = []
    for r in reviews:
        issues.extend(r.get("issues", []))
        suggestions.extend(r.get("suggestions", []))
        highlights.extend(r.get("highlights", []))

    report = {
        "score": overall,
        "summary": f"综合审核完成：{len(reviews)} 个维度，平均分 {overall}",
        "issues": issues[:20],
        "suggestions": suggestions[:20],
        "highlights": highlights[:20],
        "dimension_scores": {r["dimension"]: r["score"] for r in reviews},
        "reviews": reviews,
    }
    evs.append(events.review("overall", overall))
    evs.append(events.node_end("aggregate_review"))
    return {"review": report, "final_output": report, "events": evs}


def _parse_json(text: str) -> dict:
    import json
    import re

    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
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
