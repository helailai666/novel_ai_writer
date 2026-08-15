"""审核 API — 8 大审核维度（集成 ReviewAgent）"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.agents.review_agent import ReviewAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])


# ── Agent 工厂 ────────────────────────────────────────────────────

def _get_review_agent() -> ReviewAgent:
    """创建 ReviewAgent 实例"""
    return ReviewAgent(
        llm_provider="openai",
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY or "",
        api_base=settings.LLM_API_BASE,
    )


class ReviewRequest(BaseModel):
    """通用审核请求"""
    project_id: str
    content: str = Field(..., description="待审核文本")
    context: Optional[str] = Field(None, description="补充上下文（章节梗概等）")


class ReviewResponse(BaseModel):
    """通用审核响应"""
    score: int = Field(..., ge=0, le=100, description="评分 0-100")
    summary: str = Field(..., description="审核摘要")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    highlights: List[str] = Field(default_factory=list, description="亮点")


# ── 辅助 ────────────────────────────────────────────────────────

def _parse_agent_result(result) -> dict:
    """解析 AgentResult → ReviewResponse dict"""
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

    # 尝试解析 JSON
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
        data["score"] = 70  # 默认分数

    data["is_mock"] = result.usage.get("mock", False)
    return data


# ── 1. 一致性审核 ───────────────────────────────────────────────

@router.post("/consistency", response_model=ReviewResponse)
async def review_consistency(payload: ReviewRequest):
    """审核内容与设定的一致性（角色性格、世界观规则等）"""
    agent = _get_review_agent()
    result = await agent.review_consistency(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 2. 逻辑审核 ─────────────────────────────────────────────────

@router.post("/logic", response_model=ReviewResponse)
async def review_logic(payload: ReviewRequest):
    """审核情节逻辑、时间线合理性"""
    agent = _get_review_agent()
    result = await agent.review_logic(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 3. 伏笔审核 ─────────────────────────────────────────────────

@router.post("/foreshadowing", response_model=ReviewResponse)
async def review_foreshadowing(payload: ReviewRequest):
    """审核伏笔的埋设与回收状态"""
    agent = _get_review_agent()
    result = await agent.review_foreshadowing(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 4. 人物弧光审核 ─────────────────────────────────────────────

@router.post("/character-arc", response_model=ReviewResponse)
async def review_character_arc(payload: ReviewRequest):
    """审核角色成长曲线和人物弧光"""
    agent = _get_review_agent()
    result = await agent.review_character_arc(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 5. 节奏审核 ─────────────────────────────────────────────────

@router.post("/pacing", response_model=ReviewResponse)
async def review_pacing(payload: ReviewRequest):
    """审核叙事节奏、紧张-舒缓交替"""
    agent = _get_review_agent()
    result = await agent.review_pacing(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 6. 文笔审核 ─────────────────────────────────────────────────

@router.post("/prose", response_model=ReviewResponse)
async def review_prose(payload: ReviewRequest):
    """审核文笔质量、语言表达"""
    agent = _get_review_agent()
    result = await agent.review_prose(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 7. 读者视角审核 ─────────────────────────────────────────────

@router.post("/reader-perspective", response_model=ReviewResponse)
async def review_reader_perspective(payload: ReviewRequest):
    """从读者角度审核可读性、吸引力"""
    agent = _get_review_agent()
    result = await agent.review_reader_perspective(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})


# ── 8. 完整综合审核 ─────────────────────────────────────────────

@router.post("/comprehensive", response_model=ReviewResponse)
async def review_comprehensive(payload: ReviewRequest):
    """综合审核：汇总以上所有维度"""
    agent = _get_review_agent()
    result = await agent.review_comprehensive(payload.content, payload.context or "")
    data = _parse_agent_result(result)
    return ReviewResponse(**{k: v for k, v in data.items() if k in ReviewResponse.model_fields})
