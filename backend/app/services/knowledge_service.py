"""知识库服务 — 文档 CRUD/摄取/检索 + 热梗 CRUD/检索"""

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.knowledge import KnowledgeIndexer, Retriever, create_embeddings, create_vector_store
from app.models.hot_meme import HotMeme
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_doc import KnowledgeDoc

logger = logging.getLogger(__name__)


def _get_indexer() -> KnowledgeIndexer:
    return KnowledgeIndexer(embeddings=create_embeddings(), vector_store=create_vector_store())


def _get_retriever() -> Retriever:
    return Retriever(embeddings=create_embeddings(), vector_store=create_vector_store())


def _doc_to_dict(d: KnowledgeDoc) -> dict:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "title": d.title,
        "category": d.category,
        "content": d.content,
        "tags": d.tags,
        "source": d.source,
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
    }


def _meme_to_dict(m: HotMeme) -> dict:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "phrase": m.phrase,
        "meaning": m.meaning,
        "usage_example": m.usage_example,
        "category": m.category,
        "tags": m.tags,
        "popularity": m.popularity,
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


class KnowledgeService:
    """知识库服务"""

    # ── 文档 CRUD ────────────────────────────────────────────────

    @staticmethod
    async def create_doc(db: AsyncSession, data: dict, project_id: Optional[str] = None, source: str = "manual") -> dict:
        doc = KnowledgeDoc(project_id=project_id, source=source, **data)
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        await db.commit()
        # 异步索引（向量化入库）
        try:
            await _get_indexer().index_doc(
                doc.id, doc.content or "",
                {"project_id": doc.project_id, "title": doc.title, "category": doc.category, "tags": doc.tags},
            )
        except Exception as e:
            logger.warning(f"文档索引失败（内容仍已保存）: {e}")
        return _doc_to_dict(doc)

    @staticmethod
    async def list_docs(db: AsyncSession, project_id: Optional[str] = None, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict]:
        stmt = select(KnowledgeDoc).order_by(KnowledgeDoc.updated_at.desc())
        if project_id:
            stmt = stmt.where(KnowledgeDoc.project_id == project_id)
        if category:
            stmt = stmt.where(KnowledgeDoc.category == category)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await db.execute(stmt)).scalars().all()
        return [_doc_to_dict(d) for d in rows]

    @staticmethod
    async def get_doc(db: AsyncSession, doc_id: str) -> dict:
        doc = (await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return _doc_to_dict(doc)

    @staticmethod
    async def delete_doc(db: AsyncSession, doc_id: str) -> None:
        doc = (await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            await _get_indexer().delete_doc(doc_id)
        except Exception as e:
            logger.warning(f"删除向量失败: {e}")
        await db.delete(doc)
        await db.commit()

    @staticmethod
    async def ingest_text(db: AsyncSession, title: str, content: str, category: str = "general", tags: str = "", project_id: Optional[str] = None, source: str = "text") -> dict:
        return await KnowledgeService.create_doc(
            db, {"title": title, "content": content, "category": category, "tags": tags}, project_id=project_id, source=source
        )

    @staticmethod
    async def ingest_file(db: AsyncSession, filename: str, raw: bytes, project_id: Optional[str] = None) -> dict:
        """摄取 txt/md 文件"""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")
        title = filename.rsplit(".", 1)[0]
        return await KnowledgeService.ingest_text(db, title, text, source=f"file:{filename}", project_id=project_id)

    # ── 检索 ────────────────────────────────────────────────────

    @staticmethod
    async def search(query: str, project_id: Optional[str] = None, top_k: int = 5, categories: Optional[list[str]] = None, include_memes: bool = True) -> dict:
        return await _get_retriever().retrieve(query, project_id, top_k, categories, include_memes)

    # ── 热梗 CRUD ───────────────────────────────────────────────

    @staticmethod
    async def create_meme(db: AsyncSession, data: dict, project_id: Optional[str] = None) -> dict:
        meme = HotMeme(project_id=project_id, **data)
        db.add(meme)
        await db.flush()
        await db.refresh(meme)
        await db.commit()
        return _meme_to_dict(meme)

    @staticmethod
    async def list_memes(db: AsyncSession, project_id: Optional[str] = None, category: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict]:
        stmt = select(HotMeme).order_by(HotMeme.popularity.desc())
        if project_id:
            stmt = stmt.where(HotMeme.project_id == project_id)
        if category:
            stmt = stmt.where(HotMeme.category == category)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await db.execute(stmt)).scalars().all()
        return [_meme_to_dict(m) for m in rows]

    @staticmethod
    async def delete_meme(db: AsyncSession, meme_id: str) -> None:
        meme = (await db.execute(select(HotMeme).where(HotMeme.id == meme_id))).scalar_one_or_none()
        if not meme:
            raise HTTPException(status_code=404, detail="HotMeme not found")
        await db.delete(meme)
        await db.commit()

    @staticmethod
    async def search_memes(db: AsyncSession, query: str, project_id: Optional[str] = None, limit: int = 10) -> list[dict]:
        like = f"%{query}%"
        stmt = select(HotMeme).where(
            HotMeme.phrase.ilike(like) | HotMeme.meaning.ilike(like) | HotMeme.tags.ilike(like)
        )
        if project_id:
            stmt = stmt.where(HotMeme.project_id == project_id)
        stmt = stmt.order_by(HotMeme.popularity.desc()).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        return [_meme_to_dict(m) for m in rows]
