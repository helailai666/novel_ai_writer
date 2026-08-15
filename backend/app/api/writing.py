"""创作 API — 章节生成、批处理、多卷管理（集成 LangChain Agent）"""

import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.models.chapter import Chapter
from app.models.volume import Volume
from app.agents.writer_agent import WriterAgent

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
    volume = Volume(project_id=project_id, **payload.model_dump())
    db.add(volume)
    await db.flush()
    await db.refresh(volume)
    return _volume_to_dict(volume)


@router.get("/volumes")
async def list_volumes(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
    )
    return [_volume_to_dict(v) for v in result.scalars().all()]


@router.delete("/volumes/{volume_id}", status_code=204)
async def delete_volume(project_id: str, volume_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Volume).where(Volume.id == volume_id, Volume.project_id == project_id))
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")
    await db.delete(volume)
    await db.flush()


# ── Chapter Routes ───────────────────────────────────────────────

@router.post("/chapters", status_code=201)
async def create_chapter(project_id: str, payload: ChapterCreate, db: AsyncSession = Depends(get_db)):
    chapter = Chapter(project_id=project_id, **payload.model_dump())
    chapter.word_count = len(payload.content) if payload.content else 0
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)
    return _chapter_to_dict(chapter)


@router.get("/chapters")
async def list_chapters(
    project_id: str,
    volume_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Chapter).where(Chapter.project_id == project_id)
    if volume_id:
        stmt = stmt.where(Chapter.volume_id == volume_id)
    if status:
        stmt = stmt.where(Chapter.status == status)
    stmt = stmt.order_by(Chapter.chapter_number).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [_chapter_to_dict(c) for c in result.scalars().all()]


@router.get("/chapters/{chapter_id}")
async def get_chapter(project_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return _chapter_to_dict(chapter)


@router.patch("/chapters/{chapter_id}")
async def update_chapter(project_id: str, chapter_id: str, payload: ChapterUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, k, v)
    if payload.content is not None:
        chapter.word_count = len(payload.content)
    await db.flush()
    await db.refresh(chapter)
    return _chapter_to_dict(chapter)


@router.delete("/chapters/{chapter_id}", status_code=204)
async def delete_chapter(project_id: str, chapter_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    await db.delete(chapter)
    await db.flush()


# ── Agent 工厂 ──────────────────────────────────────────────────

def _get_writer_agent() -> WriterAgent:
    """创建 WriterAgent 实例"""
    return WriterAgent(
        llm_provider="openai",
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY or "",
        api_base=settings.LLM_API_BASE,
        streaming=True,
    )


# ── AI Generation ────────────────────────────────────────────────

@router.post("/generate")
async def generate_chapter(
    project_id: str,
    payload: ChapterGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 生成单个章节 — 调用 WriterAgent"""
    agent = _get_writer_agent()

    # 构建上下文
    context = {"project_id": project_id}
    if payload.volume_id:
        context["volume_id"] = payload.volume_id

    # 调用 Agent 生成
    result = await agent.generate_chapter(
        prompt=payload.prompt,
        context=context,
        style=payload.style,
        target_word_count=payload.target_word_count,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"章节生成失败: {result.error}")

    # 保存到数据库
    chapter = Chapter(
        project_id=project_id,
        title=f"Chapter {payload.chapter_number}",
        volume_id=payload.volume_id,
        chapter_number=payload.chapter_number,
        content=result.content,
        word_count=len(result.content),
        ai_prompt_used=payload.prompt,
        status="draft",
    )
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)

    response = _chapter_to_dict(chapter)
    response["is_mock"] = agent.is_mock
    return response


@router.post("/generate-stream")
async def generate_chapter_stream(
    project_id: str,
    payload: ChapterGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 流式生成章节 — SSE (Server-Sent Events)"""
    agent = _get_writer_agent()

    context = {"project_id": project_id}
    if payload.volume_id:
        context["volume_id"] = payload.volume_id

    async def event_stream():
        """SSE 事件流"""
        full_content = ""
        try:
            async for chunk in agent.generate_chapter_stream(
                prompt=payload.prompt,
                context=context,
                style=payload.style,
                target_word_count=payload.target_word_count,
            ):
                full_content += chunk
                # SSE 格式: data: {...}\n\n
                yield f"data: {json.dumps({'chunk': chunk, 'is_mock': agent.is_mock}, ensure_ascii=False)}\n\n"

            # 发送完成信号
            yield f"data: {json.dumps({'done': True, 'total_length': len(full_content)}, ensure_ascii=False)}\n\n"

            # 保存到数据库（异步）
            try:
                chapter = Chapter(
                    project_id=project_id,
                    title=f"Chapter {payload.chapter_number}",
                    volume_id=payload.volume_id,
                    chapter_number=payload.chapter_number,
                    content=full_content,
                    word_count=len(full_content),
                    ai_prompt_used=payload.prompt,
                    status="draft",
                )
                db.add(chapter)
                await db.flush()
                await db.refresh(chapter)
                yield f"data: {json.dumps({'saved': True, 'chapter_id': chapter.id}, ensure_ascii=False)}\n\n"
            except Exception as save_err:
                logger.error(f"Failed to save chapter: {save_err}")
                yield f"data: {json.dumps({'error': f'Save failed: {save_err}'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

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
async def batch_generate(
    project_id: str,
    payload: BatchGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """AI 批量生成章节"""
    agent = _get_writer_agent()
    chapters = []
    errors = []

    for i, prompt in enumerate(payload.prompts):
        try:
            result = await agent.generate_chapter(
                prompt=prompt,
                context={"project_id": project_id},
                style=payload.style,
                target_word_count=payload.target_word_count,
            )

            if result.success:
                chapter = Chapter(
                    project_id=project_id,
                    title=f"Chapter {payload.start_chapter_number + i}",
                    volume_id=payload.volume_id,
                    chapter_number=payload.start_chapter_number + i,
                    content=result.content,
                    word_count=len(result.content),
                    ai_prompt_used=prompt,
                    status="draft",
                )
                db.add(chapter)
                chapters.append(chapter)
            else:
                errors.append({"index": i, "prompt": prompt[:100], "error": result.error})
        except Exception as e:
            errors.append({"index": i, "prompt": prompt[:100], "error": str(e)})

    await db.flush()

    return {
        "generated": len(chapters),
        "errors": errors,
        "is_mock": agent.is_mock,
        "chapters": [
            {"id": ch.id, "title": ch.title, "chapter_number": ch.chapter_number}
            for ch in chapters
        ],
    }


@router.post("/continue")
async def continue_chapter(
    project_id: str,
    payload: ContinueRequest,
    db: AsyncSession = Depends(get_db),
):
    """续写已有章节"""
    # 获取已有章节
    result = await db.execute(select(Chapter).where(Chapter.id == payload.chapter_id, Chapter.project_id == project_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    agent = _get_writer_agent()
    gen_result = await agent.continue_chapter(
        previous_content=chapter.content,
        direction=payload.direction,
        context={"project_id": project_id, "chapter_id": payload.chapter_id},
    )

    if not gen_result.success:
        raise HTTPException(status_code=500, detail=f"续写失败: {gen_result.error}")

    # 追加到原章节
    chapter.content = chapter.content + "\n\n" + gen_result.content
    chapter.word_count = len(chapter.content)
    await db.flush()
    await db.refresh(chapter)

    response = _chapter_to_dict(chapter)
    response["is_mock"] = agent.is_mock
    return response


@router.post("/polish")
async def polish_chapter(
    project_id: str,
    payload: PolishRequest,
    db: AsyncSession = Depends(get_db),
):
    """润色/改写章节"""
    result = await db.execute(select(Chapter).where(Chapter.id == payload.chapter_id, Chapter.project_id == project_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    agent = _get_writer_agent()
    gen_result = await agent.polish(
        content=chapter.content,
        aspect=payload.aspect,
        context={"project_id": project_id},
    )

    if not gen_result.success:
        raise HTTPException(status_code=500, detail=f"润色失败: {gen_result.error}")

    chapter.content = gen_result.content
    chapter.word_count = len(gen_result.content)
    await db.flush()
    await db.refresh(chapter)

    response = _chapter_to_dict(chapter)
    response["is_mock"] = agent.is_mock
    return response


# ── Helpers ──────────────────────────────────────────────────────

def _chapter_to_dict(ch: Chapter) -> dict:
    return {
        "id": ch.id,
        "project_id": ch.project_id,
        "volume_id": ch.volume_id,
        "title": ch.title,
        "chapter_number": ch.chapter_number,
        "content": ch.content,
        "word_count": ch.word_count,
        "status": ch.status,
        "ai_prompt_used": ch.ai_prompt_used,
        "created_at": ch.created_at.isoformat() if ch.created_at else "",
        "updated_at": ch.updated_at.isoformat() if ch.updated_at else "",
    }


def _volume_to_dict(v: Volume) -> dict:
    return {
        "id": v.id,
        "project_id": v.project_id,
        "title": v.title,
        "volume_number": v.volume_number,
        "summary": v.summary,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else "",
        "updated_at": v.updated_at.isoformat() if v.updated_at else "",
    }
