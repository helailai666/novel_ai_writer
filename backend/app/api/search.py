"""搜索 API — 本地搜索 + 网络搜索"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


# ── Schemas ──────────────────────────────────────────────────────

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchResult(BaseModel):
    title: str
    snippet: str
    url: str


class WebSearchResponse(BaseModel):
    query: str
    results: List[WebSearchResult]
    summary: str = ""
    ai_summary: str = ""
    source: str = ""
    is_mock: bool = False


# ── 本地搜索 ────────────────────────────────────────────────────

@router.get("/projects")
async def search_projects(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """搜索项目"""
    results = await SearchService.search_projects(db, q, limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/projects/{project_id}/characters")
async def search_characters(
    project_id: str,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """在项目内搜索角色"""
    results = await SearchService.search_characters(db, project_id, q)
    return {"query": q, "count": len(results), "results": results}


@router.get("/projects/{project_id}/chapters")
async def search_chapters(
    project_id: str,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """在项目内搜索章节"""
    results = await SearchService.search_chapters(db, project_id, q)
    return {"query": q, "count": len(results), "results": results}


# ── 网络搜索 ────────────────────────────────────────────────────

@router.post("/web", response_model=WebSearchResponse)
async def search_web(payload: WebSearchRequest):
    """网络搜索（纯结果，无 AI 摘要）"""
    structured = await SearchService.search_web_structured(
        query=payload.query,
        max_results=payload.max_results,
    )

    return WebSearchResponse(
        query=payload.query,
        results=[WebSearchResult(**r) for r in structured.get("results", [])],
        summary=structured.get("summary", ""),
        source=structured.get("source", "unknown"),
    )


@router.post("/web/ai-summary", response_model=WebSearchResponse)
async def search_web_with_ai(payload: WebSearchRequest):
    """网络搜索 + AI 摘要（core/llm 驱动，无 Key 自动降级 mock）"""
    result = await SearchService.search_and_summarize(
        query=payload.query,
        max_results=payload.max_results,
    )

    return WebSearchResponse(
        query=payload.query,
        results=[WebSearchResult(**r) for r in result.get("results", [])],
        summary="",
        ai_summary=result.get("content", ""),
        source=result.get("source", "duckduckgo"),
        is_mock=result.get("is_mock", False),
    )


@router.get("/web/cache/clear")
async def clear_search_cache():
    """清除搜索缓存"""
    SearchService.clear_cache()
    return {"message": "搜索缓存已清除"}
