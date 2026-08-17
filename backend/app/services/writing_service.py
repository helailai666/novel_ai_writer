"""写作服务 — 卷 / 章节 CRUD + AI 生成（生成/流式/批量/续写/润色）

AI 生成逻辑暂调用 legacy WriterAgent（P2 起由 LangGraph 章节写作图替代）。
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.volume import Volume
from app.models.chapter import Chapter
from app.services.agent_factory import get_writer_agent


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


async def _get_chapter_or_404(db: AsyncSession, project_id: str, chapter_id: str) -> Chapter:
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


class WritingService:
    """写作服务"""

    # ── 卷 ──────────────────────────────────────────────────────

    @staticmethod
    async def create_volume(db: AsyncSession, project_id: str, data: dict) -> dict:
        volume = Volume(project_id=project_id, **data)
        db.add(volume)
        await db.flush()
        await db.refresh(volume)
        return _volume_to_dict(volume)

    @staticmethod
    async def list_volumes(db: AsyncSession, project_id: str) -> list[dict]:
        result = await db.execute(
            select(Volume).where(Volume.project_id == project_id).order_by(Volume.volume_number)
        )
        return [_volume_to_dict(v) for v in result.scalars().all()]

    @staticmethod
    async def delete_volume(db: AsyncSession, project_id: str, volume_id: str) -> None:
        result = await db.execute(
            select(Volume).where(Volume.id == volume_id, Volume.project_id == project_id)
        )
        volume = result.scalar_one_or_none()
        if not volume:
            raise HTTPException(status_code=404, detail="Volume not found")
        await db.delete(volume)
        await db.flush()

    # ── 章节 ────────────────────────────────────────────────────

    @staticmethod
    async def create_chapter(db: AsyncSession, project_id: str, data: dict) -> dict:
        chapter = Chapter(project_id=project_id, **data)
        chapter.word_count = len(chapter.content) if chapter.content else 0
        db.add(chapter)
        await db.flush()
        await db.refresh(chapter)
        return _chapter_to_dict(chapter)

    @staticmethod
    async def list_chapters(
        db: AsyncSession,
        project_id: str,
        volume_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        stmt = select(Chapter).where(Chapter.project_id == project_id)
        if volume_id:
            stmt = stmt.where(Chapter.volume_id == volume_id)
        if status:
            stmt = stmt.where(Chapter.status == status)
        stmt = stmt.order_by(Chapter.chapter_number).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return [_chapter_to_dict(c) for c in result.scalars().all()]

    @staticmethod
    async def get_chapter(db: AsyncSession, project_id: str, chapter_id: str) -> dict:
        return _chapter_to_dict(await _get_chapter_or_404(db, project_id, chapter_id))

    @staticmethod
    async def update_chapter(db: AsyncSession, project_id: str, chapter_id: str, data: dict) -> dict:
        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        for k, v in data.items():
            setattr(chapter, k, v)
        if data.get("content") is not None:
            chapter.word_count = len(chapter.content)
        await db.flush()
        await db.refresh(chapter)
        return _chapter_to_dict(chapter)

    @staticmethod
    async def delete_chapter(db: AsyncSession, project_id: str, chapter_id: str) -> None:
        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        await db.delete(chapter)
        await db.flush()

    # ── AI 生成 ─────────────────────────────────────────────────

    @staticmethod
    async def generate_chapter(
        db: AsyncSession,
        project_id: str,
        prompt: str,
        volume_id: Optional[str],
        chapter_number: int,
        style: str,
        target_word_count: int,
    ) -> dict:
        """AI 生成单个章节并保存"""
        agent = get_writer_agent()
        context = {"project_id": project_id}
        if volume_id:
            context["volume_id"] = volume_id
        result = await agent.generate_chapter(
            prompt=prompt, context=context, style=style, target_word_count=target_word_count
        )
        if not result.success:
            raise HTTPException(status_code=500, detail=f"章节生成失败: {result.error}")
        chapter = Chapter(
            project_id=project_id,
            title=f"Chapter {chapter_number}",
            volume_id=volume_id,
            chapter_number=chapter_number,
            content=result.content,
            word_count=len(result.content),
            ai_prompt_used=prompt,
            status="draft",
        )
        db.add(chapter)
        await db.flush()
        await db.refresh(chapter)
        response = _chapter_to_dict(chapter)
        response["is_mock"] = agent.is_mock
        return response

    @staticmethod
    async def generate_chapter_stream(
        db: AsyncSession,
        project_id: str,
        prompt: str,
        volume_id: Optional[str],
        chapter_number: int,
        style: str,
        target_word_count: int,
    ):
        """AI 流式生成章节 — 返回 (agent, async generator)

        生成器逐 chunk 产出 (chunk, is_mock)，结束后返回保存结果 dict。
        """
        agent = get_writer_agent(streaming=True)
        context = {"project_id": project_id}
        if volume_id:
            context["volume_id"] = volume_id

        async def event_stream():
            full_content = ""
            try:
                async for chunk in agent.generate_chapter_stream(
                    prompt=prompt, context=context, style=style, target_word_count=target_word_count
                ):
                    full_content += chunk
                    yield {"chunk": chunk, "is_mock": agent.is_mock}

                yield {"done": True, "total_length": len(full_content)}

                try:
                    chapter = Chapter(
                        project_id=project_id,
                        title=f"Chapter {chapter_number}",
                        volume_id=volume_id,
                        chapter_number=chapter_number,
                        content=full_content,
                        word_count=len(full_content),
                        ai_prompt_used=prompt,
                        status="draft",
                    )
                    db.add(chapter)
                    await db.flush()
                    await db.refresh(chapter)
                    yield {"saved": True, "chapter_id": chapter.id}
                except Exception as save_err:
                    yield {"error": f"Save failed: {save_err}"}
            except Exception as e:
                yield {"error": str(e)}

        return agent, event_stream()

    @staticmethod
    async def batch_generate(
        db: AsyncSession,
        project_id: str,
        prompts: list[str],
        volume_id: Optional[str],
        start_chapter_number: int,
        style: str,
        target_word_count: int,
    ) -> dict:
        agent = get_writer_agent()
        chapters = []
        errors = []
        for i, prompt in enumerate(prompts):
            try:
                result = await agent.generate_chapter(
                    prompt=prompt,
                    context={"project_id": project_id},
                    style=style,
                    target_word_count=target_word_count,
                )
                if result.success:
                    chapter = Chapter(
                        project_id=project_id,
                        title=f"Chapter {start_chapter_number + i}",
                        volume_id=volume_id,
                        chapter_number=start_chapter_number + i,
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

    @staticmethod
    async def continue_chapter(db: AsyncSession, project_id: str, chapter_id: str, direction: str) -> dict:
        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        agent = get_writer_agent()
        gen = await agent.continue_chapter(
            previous_content=chapter.content,
            direction=direction,
            context={"project_id": project_id, "chapter_id": chapter_id},
        )
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"续写失败: {gen.error}")
        chapter.content = chapter.content + "\n\n" + gen.content
        chapter.word_count = len(chapter.content)
        await db.flush()
        await db.refresh(chapter)
        response = _chapter_to_dict(chapter)
        response["is_mock"] = agent.is_mock
        return response

    @staticmethod
    async def polish_chapter(db: AsyncSession, project_id: str, chapter_id: str, aspect: str) -> dict:
        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        agent = get_writer_agent()
        gen = await agent.polish(content=chapter.content, aspect=aspect, context={"project_id": project_id})
        if not gen.success:
            raise HTTPException(status_code=500, detail=f"润色失败: {gen.error}")
        chapter.content = gen.content
        chapter.word_count = len(gen.content)
        await db.flush()
        await db.refresh(chapter)
        response = _chapter_to_dict(chapter)
        response["is_mock"] = agent.is_mock
        return response
