"""审核服务 — 8 大维度审核 + 综合审核（LangGraph review 图驱动）"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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
        """按维度审核（review 图；comprehensive 为综合审核）"""
        from app.agents.runner import get_runner

        if dimension not in DIMENSIONS:
            raise HTTPException(status_code=400, detail=f"未知审核维度: {dimension}")

        state = {
            "graph": "review", "project_id": project_id,
            "content": content, "context": context,
            "dimensions": [dimension],
            "settings_snapshot": {}, "knowledge": [], "draft": None,
            "review": {}, "reviews": [], "revision_round": 0,
            "max_revisions": 2, "review_threshold": 75,
            "final_output": {}, "events": [], "run_id": None,
        }
        result = await get_runner().ainvoke("review", state)
        if not result.get("score") and result.get("error"):
            raise HTTPException(status_code=500, detail=f"审核失败: {result['error']}")
        return result
