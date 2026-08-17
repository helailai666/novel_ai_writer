"""创作 API — 章节生成、批处理、多卷管理（薄层，逻辑在 WritingService）"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.writing_service import WritingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/writing", tags=["writing"])


# ── Schemas ──────────────────────────────────────────────────────

class VolumeCreate(BaseModel):
    title: str = Field(..., max_length=200)
    volume_number: int = Field(default=1, ge=1)
    summary: str = ""
    status: str = Field(default="planned", max_length=20)


class ChapterCreate(BaseModel):
    title: str = Field(..., max_length=200)
    volume_id: Optional[str] = None
    chapter_number: int = Field(default=1, ge=1)
    content: str = ""
    status: str = Field(default="draft", max_length=20)
    ai_prompt_used: str = ""


class ChapterUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)


class ChapterGenerateRequest(BaseModel):
    """AI 章节生成请求"""
    prompt: str = Field(..., description="生成提示词")
    volume_id: Optional[str] = None
    chapter_number: int = Field(default=1, ge=1)
    style: str = Field(default="narrative", description="写作风格")
    target_word_count: int = Field(default=2000, ge=100, le=10000)


class BatchGenerateRequest(BaseModel):
    """批量生成请求"""
    prompts: List[str] = Field(..., min_length=1, max_length=20)
    volume_id: Optional[str] = None
    start_chapter_number: int = Field(default=1, ge=1)
    style: str = Field(default="narrative")
    target_word_count: int = Field(default=2000, ge=100, le=10000)


class ContinueRequest(BaseModel):
    """续写请求"""
    chapter_id: str = Field(..., description="章节ID")
    direction: str = Field(default="", description="续写方向")


class PolishRequest(BaseModel):
    """润色请求"""
    chapter_id: str = Field(..., description="章节ID")
    aspect: str = Field(default="general", description="润色方面")


# ── Volume Routes ────────────────────────────────────────────────

@router.post("/volumes", status_code=201)
async def create_volume(project_id: str, payload: VolumeCreate, db: AsyncSession = Depends(get_db)):
    return await WritingService.create_volume(db, project_id, payload.model_dump())


@router.get("/volumes")
async def list_volumes(project_id: str, db: AsyncSession = Depends(get_db)):
    return await WritingService.list_volumes(db, project_id)


@router.delete("/volumes/{volume_id}", status_code=204)
async def delete_volume(project_id: str, volume_id: str, db: AsyncSession = Depends(get_db)):
    await WritingService.delete_volume(db, project_id, volume_id)


# ── Chapter Routes ───────────────────────────────────────────────

@router.post("/chapters", status_code=201)
async def create_chapter(project_id: str, payload: ChapterCreate, db: AsyncSession = Depends(get_db)):
    return await WritingService.create_chapter(db, project_id, payload.model_dump())


@router.get("/chapters")
async def list_chapters(
    project_id: str,
    volume_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await WritingService.list_chapters(db, project_id, volume_id, status, limit, offset)


@router.get("/chapters/{chapter_id}")
async def get_chapter(project_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    return await WritingService.get_chapter(db, project_id, chapter_id)


@router.patch("/chapters/{chapter_id}")
async def update_chapter(project_id: str, chapter_id: str, payload: ChapterUpdate, db: AsyncSession = Depends(get_db)):
    return await WritingService.update_chapter(db, project_id, chapter_id, payload.model_dump(exclude_unset=True))


@router.delete("/chapters/{chapter_id}", status_code=204)
async def delete_chapter(project_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    await WritingService.delete_chapter(db, project_id, chapter_id)


# ── AI Generation ────────────────────────────────────────────────

@router.post("/generate")
async def generate_chapter(project_id: str, payload: ChapterGenerateRequest, db: AsyncSession = Depends(get_db)):
    """AI 生成单个章节 — 调用 WritingService"""
    return await WritingService.generate_chapter(
        db, project_id, payload.prompt, payload.volume_id, payload.chapter_number,
        payload.style, payload.target_word_count,
    )


@router.post("/generate-stream")
async def generate_chapter_stream(project_id: str, payload: ChapterGenerateRequest, db: AsyncSession = Depends(get_db)):
    """AI 流式生成章节 — SSE (Server-Sent Events)"""
    agent, stream = await WritingService.generate_chapter_stream(
        db, project_id, payload.prompt, payload.volume_id, payload.chapter_number,
        payload.style, payload.target_word_count,
    )

    async def event_stream():
        async for event in stream:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/batch-generate")
async def batch_generate(project_id: str, payload: BatchGenerateRequest, db: AsyncSession = Depends(get_db)):
    """AI 批量生成章节"""
    return await WritingService.batch_generate(
        db, project_id, payload.prompts, payload.volume_id,
        payload.start_chapter_number, payload.style, payload.target_word_count,
    )


@router.post("/continue")
async def continue_chapter(project_id: str, payload: ContinueRequest, db: AsyncSession = Depends(get_db)):
    """续写已有章节"""
    return await WritingService.continue_chapter(db, project_id, payload.chapter_id, payload.direction)


@router.post("/polish")
async def polish_chapter(project_id: str, payload: PolishRequest, db: AsyncSession = Depends(get_db)):
    """润色/改写章节"""
    return await WritingService.polish_chapter(db, project_id, payload.chapter_id, payload.aspect)
