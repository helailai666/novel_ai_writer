"""知识库索引器 — 切片 + 向量化 + 入库"""

import hashlib
import json
import logging
from typing import Optional

from app.core.knowledge.embeddings import EmbeddingProvider, MockEmbeddings
from app.core.knowledge.vector_stores import VectorStore, MockVectorStore
from app.database import async_session_factory
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_doc import KnowledgeDoc

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500   # 字符
DEFAULT_CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """按段落优先、定长兜底切片"""
    text = (text or "").strip()
    if not text:
        return []
    # 优先按段落聚合
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > size:
            if current:
                chunks.append(current)
                current = ""
            # 超长段落定长切
            start = 0
            while start < len(para):
                chunks.append(para[start : start + size])
                start += size - overlap
            continue
        if len(current) + len(para) + 1 > size:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


class KnowledgeIndexer:
    """文档入库索引器"""

    def __init__(self, embeddings: Optional[EmbeddingProvider] = None, vector_store: Optional[VectorStore] = None):
        self.embeddings = embeddings or MockEmbeddings()
        self.vector_store = vector_store or MockVectorStore()

    async def index_doc(self, doc_id: str, content: str, meta: dict) -> int:
        """切片 → 向量化 → 写入 knowledge_chunks 表 + 向量库，返回切片数"""
        chunks = chunk_text(content)
        if not chunks:
            return 0
        vectors = await self.embeddings.embed(chunks)

        ids = [self._chunk_id(doc_id, i) for i in range(len(chunks))]
        metadatas = [{**meta, "doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]

        # 向量库
        await self.vector_store.add(ids, vectors, chunks, metadatas)

        # 关系表
        async with async_session_factory() as db:
            for i, chunk in enumerate(chunks):
                db.add(
                    KnowledgeChunk(
                        id=ids[i],
                        doc_id=doc_id,
                        chunk_index=i,
                        content=chunk,
                        meta=json.dumps(meta, ensure_ascii=False),
                    )
                )
            await db.commit()
        logger.info(f"知识文档 {doc_id} 索引完成: {len(chunks)} 切片")
        return len(chunks)

    async def delete_doc(self, doc_id: str) -> None:
        """删除文档的向量与切片"""
        from sqlalchemy import select

        async with async_session_factory() as db:
            chunks = (await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))).scalars().all()
            ids = [c.id for c in chunks]
            if ids:
                await self.vector_store.delete(ids)
            for c in chunks:
                await db.delete(c)
            await db.commit()

    @staticmethod
    def _chunk_id(doc_id: str, index: int) -> str:
        raw = f"{doc_id}:{index}"
        return hashlib.md5(raw.encode()).hexdigest()
