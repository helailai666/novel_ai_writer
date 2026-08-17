"""审核 API — 8 大审核维度（薄层，逻辑在 ReviewService）"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["review"])


# ── Schemas ──────────────────────────────────────────────────────

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


# ── 维度审核端点 ─────────────────────────────────────────────────

@router.post("/consistency", response_model=ReviewResponse)
async def review_consistency(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核内容与设定的一致性（角色性格、世界观规则等）"""
    return await ReviewService.review(db, payload.project_id, "consistency", payload.content, payload.context or "")


@router.post("/logic", response_model=ReviewResponse)
async def review_logic(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核情节逻辑、时间线合理性"""
    return await ReviewService.review(db, payload.project_id, "logic", payload.content, payload.context or "")


@router.post("/foreshadowing", response_model=ReviewResponse)
async def review_foreshadowing(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核伏笔的埋设与回收状态"""
    return await ReviewService.review(db, payload.project_id, "foreshadowing", payload.content, payload.context or "")


@router.post("/character-arc", response_model=ReviewResponse)
async def review_character_arc(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核角色成长曲线和人物弧光"""
    return await ReviewService.review(db, payload.project_id, "character-arc", payload.content, payload.context or "")


@router.post("/pacing", response_model=ReviewResponse)
async def review_pacing(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核叙事节奏、紧张-舒缓交替"""
    return await ReviewService.review(db, payload.project_id, "pacing", payload.content, payload.context or "")


@router.post("/prose", response_model=ReviewResponse)
async def review_prose(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """审核文笔质量、语言表达"""
    return await ReviewService.review(db, payload.project_id, "prose", payload.content, payload.context or "")


@router.post("/reader-perspective", response_model=ReviewResponse)
async def review_reader_perspective(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """从读者角度审核可读性、吸引力"""
    return await ReviewService.review(db, payload.project_id, "reader-perspective", payload.content, payload.context or "")


@router.post("/comprehensive", response_model=ReviewResponse)
async def review_comprehensive(payload: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """综合审核：汇总以上所有维度"""
    return await ReviewService.review(db, payload.project_id, "comprehensive", payload.content, payload.context or "")
