"""审核服务 — 8 大维度审核 + 综合审核

维度调度封装自 ReviewAgent；P2 起由 LangGraph 审核图（并行 8 维）替代。
"""

import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_factory import get_review_agent

# 维度 key → 审核函数名（ReviewAgent 上的便捷方法）
DIMENSIONS = [
    "consistency",
    "logic",
    "foreshadowing",
    "character-arc",
    "pacing",
    "prose",
    "reader-perspective",
    "comprehensive",
]

_METHOD_MAP = {
    "consistency": "review_consistency",
    "logic": "review_logic",
    "foreshadowing": "review_foreshadowing",
    "character-arc": "review_character_arc",
    "pacing": "review_pacing",
    "prose": "review_prose",
    "reader-perspective": "review_reader_perspective",
    "comprehensive": "review_comprehensive",
}


def _parse_agent_result(result) -> dict:
    """解析 AgentResult → 审核结果 dict（保持与旧 API 完全一致）"""
    data = {
        "score": 0,
        "summary": "",
        "issues": [],
        "suggestions": [],
        "highlights": [],
    }
    if not result.success:
        data["summary"] = f"审核失败: {result.error}"
        return data
    try:
        parsed = json.loads(result.content)
        data["score"] = parsed.get("score", 0)
        data["summary"] = parsed.get("summary", "")
        data["issues"] = parsed.get("issues", [])
        data["suggestions"] = parsed.get("suggestions", [])
        data["highlights"] = parsed.get("highlights", [])
        if "dimension_scores" in parsed:
            data["dimension_scores"] = parsed["dimension_scores"]
    except json.JSONDecodeError:
        data["summary"] = result.content[:500]
        data["score"] = 70
    data["is_mock"] = result.usage.get("mock", False)
    return data


class ReviewService:
    """审核服务"""

    @staticmethod
    async def review(
        db: AsyncSession,
        project_id: str,
        dimension: str,
        content: str,
        context: str = "",
    ) -> dict:
        """按维度审核（comprehensive 为综合审核）"""
        agent = get_review_agent()
        method_name = _METHOD_MAP.get(dimension)
        if not method_name:
            raise HTTPException(status_code=400, detail=f"未知审核维度: {dimension}")
        method = getattr(agent, method_name)
        result = await method(content=content, context=context)
        return _parse_agent_result(result)
