"""写作服务 — 卷 / 章节 CRUD + AI 生成（生成/流式/批量/续写/润色）

AI 生成逻辑暂调用 legacy WriterAgent（P2 起由 LangGraph 章节写作图替代）。
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.volume import Volume
from app.models.chapter import Chapter


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

    # ── AI 生成（LangGraph chapter 图驱动；生成+持久化在图内完成）──

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
        """AI 生成单个章节并保存（chapter 图）"""
        from app.agents.runner import get_runner

        state = _chapter_state(project_id, mode="generate", prompt=prompt, style=style,
                               target_word_count=target_word_count, chapter_number=chapter_number, volume_id=volume_id)
        result = await get_runner().ainvoke("chapter", state)
        if result.get("error") and not result.get("saved"):
            raise HTTPException(status_code=500, detail=f"章节生成失败: {result['error']}")
        chapter = await _get_chapter_obj(db, result["id"])
        response = _chapter_to_dict(chapter)
        response["is_mock"] = result.get("is_mock", True)
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
        """AI 流式生成章节 — 返回事件异步生成器（SSE 消费）

        事件类型见 app/agents/events.py（token/node_start/review/checkpoint/done/error）
        """
        from app.agents.runner import get_runner

        state = _chapter_state(project_id, mode="generate", prompt=prompt, style=style,
                               target_word_count=target_word_count, chapter_number=chapter_number, volume_id=volume_id)
        return get_runner().astream("chapter", state)

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
        from app.agents.runner import get_runner

        chapters = []
        errors = []
        for i, prompt in enumerate(prompts):
            try:
                state = _chapter_state(project_id, mode="generate", prompt=prompt, style=style,
                                       target_word_count=target_word_count,
                                       chapter_number=start_chapter_number + i, volume_id=volume_id)
                result = await get_runner().ainvoke("chapter", state)
                if result.get("saved"):
                    chapters.append({"id": result["id"], "chapter_number": start_chapter_number + i})
                else:
                    errors.append({"index": i, "prompt": prompt[:100], "error": result.get("error", "生成失败")})
            except Exception as e:
                errors.append({"index": i, "prompt": prompt[:100], "error": str(e)})
        return {
            "generated": len(chapters),
            "errors": errors,
            "is_mock": any(True for _ in chapters) or bool(errors),
            "chapters": chapters,
        }

    @staticmethod
    async def continue_chapter(db: AsyncSession, project_id: str, chapter_id: str, direction: str) -> dict:
        from app.agents.runner import get_runner

        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        state = _chapter_state(project_id, mode="continue", chapter_id=chapter_id,
                               content=chapter.content, extra=direction)
        result = await get_runner().ainvoke("chapter", state)
        if result.get("error") and not result.get("saved"):
            raise HTTPException(status_code=500, detail=f"续写失败: {result['error']}")
        updated = await _get_chapter_obj(db, chapter_id)
        response = _chapter_to_dict(updated)
        response["is_mock"] = result.get("is_mock", True)
        return response

    @staticmethod
    async def polish_chapter(db: AsyncSession, project_id: str, chapter_id: str, aspect: str) -> dict:
        from app.agents.runner import get_runner

        chapter = await _get_chapter_or_404(db, project_id, chapter_id)
        state = _chapter_state(project_id, mode="polish", chapter_id=chapter_id,
                               content=chapter.content, style=aspect)
        result = await get_runner().ainvoke("chapter", state)
        if result.get("error") and not result.get("saved"):
            raise HTTPException(status_code=500, detail=f"润色失败: {result['error']}")
        updated = await _get_chapter_obj(db, chapter_id)
        response = _chapter_to_dict(updated)
        response["is_mock"] = result.get("is_mock", True)
        return response


def _chapter_state(
    project_id: str,
    mode: str,
    prompt: str = "",
    style: str = "narrative",
    target_word_count: int = 2000,
    chapter_number: int = 1,
    volume_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    content: str = "",
    extra: str = "",
) -> dict:
    """构造 chapter 图状态"""
    return {
        "graph": "chapter", "project_id": project_id, "mode": mode,
        "prompt": prompt, "style": style, "target_word_count": target_word_count,
        "chapter_number": chapter_number, "volume_id": volume_id,
        "chapter_id": chapter_id, "content": content, "extra": extra,
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }


async def _get_chapter_obj(db: AsyncSession, chapter_id: str) -> Chapter:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter
