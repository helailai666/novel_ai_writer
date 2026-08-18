"""知识检索器 — 混合检索（关键词 ILIKE ∪ 向量 TopK，去重后按分排序）

H3 增强：检索结果按 (query, project_id, top_k, categories, include_memes)
缓存（TTL，默认 300s）；知识库/热梗写操作经 invalidate_knowledge_cache()
主动失效。缓存值返回时深拷贝，防止调用方篡改污染缓存。
"""

import copy
import logging
from typing import Optional

from sqlalchemy import or_, select

from app.config import settings
from app.core.cache import TTLCache
from app.core.knowledge.embeddings import MockEmbeddings
from app.core.knowledge.vector_stores import MockVectorStore
from app.database import async_session_factory
from app.models.hot_meme import HotMeme
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_doc import KnowledgeDoc

logger = logging.getLogger(__name__)

_SEARCHABLE_DOC_COLS = ("title", "content", "category", "tags")
_SEARCHABLE_MEME_COLS = ("phrase", "meaning", "usage_example", "category", "tags")

_retrieve_cache = TTLCache(ttl=settings.agent.knowledge_cache_ttl, max_entries=256)


def invalidate_knowledge_cache() -> None:
    """知识库/热梗变更后主动失效检索缓存"""
    _retrieve_cache.clear()
    logger.debug("知识检索缓存已失效")


class Retriever:
    """混合检索器：知识库文档 + 热梗"""

    def __init__(self, embeddings=None, vector_store=None):
        self.embeddings = embeddings or MockEmbeddings()
        self.vector_store = vector_store or MockVectorStore()

    async def retrieve(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
        categories: Optional[list[str]] = None,
        include_memes: bool = True,
    ) -> dict:
        """返回 {"docs": [...], "memes": [...], "source": "hybrid|keyword"}"""
        # LLM 工具调用可能把单值数组传成字符串（"worldview"）→ 归一化
        if isinstance(categories, str):
            categories = [categories]
        key = (query, project_id, top_k, tuple(sorted(categories or [])), include_memes)
        if settings.agent.knowledge_cache:
            _retrieve_cache.ttl = settings.agent.knowledge_cache_ttl
            hit = _retrieve_cache.get(key)
            if hit is not None:
                return hit

        keyword_docs = await self._keyword_docs(query, project_id, categories)
        keyword_memes = await self._keyword_memes(query, project_id) if include_memes else []

        vector_docs = await self._vector_docs(query, project_id, categories, top_k)

        # 合并去重（按 id）
        merged: dict[str, dict] = {}
        for item in keyword_docs + vector_docs:
            merged[item["id"]] = item
        docs = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        source = "hybrid" if vector_docs else "keyword"
        result = {"docs": docs, "memes": keyword_memes, "source": source}
        if settings.agent.knowledge_cache:
            _retrieve_cache.set(key, result)
        # 未命中路径也返回深拷贝：防止调用方修改直接污染缓存内对象
        return copy.deepcopy(result)

    # ── 关键词检索（SQL ILIKE，多词 OR）──────────────────────────

    @staticmethod
    def _terms(query: str) -> list[str]:
        """分词：空白拆分；无空白的 CJK 查询生成重叠二元组（OR 匹配）"""
        parts = [t for t in query.replace("，", " ").replace(",", " ").split() if t][:6]
        terms: list[str] = []
        for part in parts:
            if len(part) > 2 and any("\u4e00" <= ch <= "\u9fff" for ch in part):
                # 中文长句 → 重叠二元组
                terms.extend(part[i : i + 2] for i in range(len(part) - 1))
            else:
                terms.append(part)
        return terms[:12] or [query]

    async def _keyword_docs(self, query: str, project_id: Optional[str], categories: Optional[list[str]]) -> list[dict]:
        terms = self._terms(query) or [query]
        async with async_session_factory() as db:
            conds = [
                getattr(KnowledgeDoc, col).ilike(f"%{term}%")
                for term in terms for col in _SEARCHABLE_DOC_COLS
            ]
            stmt = select(KnowledgeDoc).where(or_(*conds))
            if project_id:
                stmt = stmt.where(or_(KnowledgeDoc.project_id == project_id, KnowledgeDoc.project_id.is_(None)))
            if categories:
                stmt = stmt.where(KnowledgeDoc.category.in_(categories))
            rows = (await db.execute(stmt.limit(20))).scalars().all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "category": d.category,
                "content": (d.content or "")[:500],
                "tags": d.tags,
                "project_id": d.project_id,
                "score": 0.9,
            }
            for d in rows
        ]

    async def _keyword_memes(self, query: str, project_id: Optional[str]) -> list[dict]:
        terms = self._terms(query) or [query]
        async with async_session_factory() as db:
            conds = [
                getattr(HotMeme, col).ilike(f"%{term}%")
                for term in terms for col in _SEARCHABLE_MEME_COLS
            ]
            stmt = select(HotMeme).where(or_(*conds))
            if project_id:
                stmt = stmt.where(or_(HotMeme.project_id == project_id, HotMeme.project_id.is_(None)))
            rows = (await db.execute(stmt.limit(10))).scalars().all()
        return [
            {
                "id": m.id,
                "phrase": m.phrase,
                "meaning": (m.meaning or "")[:300],
                "usage_example": (m.usage_example or "")[:300],
                "category": m.category,
                "tags": m.tags,
                "popularity": m.popularity,
            }
            for m in rows
        ]

    # ── 向量检索 ─────────────────────────────────────────────────

    async def _vector_docs(self, query: str, project_id: Optional[str], categories: Optional[list[str]], top_k: int) -> list[dict]:
        try:
            vector = await self.embeddings.embed_one(query)
            where = {}
            if project_id:
                where["project_id"] = project_id
            if categories:
                where["category"] = categories[0]  # Chroma where 单值；多分类留待后续
            items = await self.vector_store.query(vector, top_k=top_k, where=where)
            return [
                {
                    "id": it["metadata"].get("doc_id", it["id"]),
                    "title": it["metadata"].get("title", ""),
                    "category": it["metadata"].get("category", ""),
                    "content": (it.get("text") or "")[:500],
                    "tags": it["metadata"].get("tags", ""),
                    "project_id": it["metadata"].get("project_id"),
                    "score": it.get("score", 0),
                }
                for it in items
            ]
        except Exception as e:
            logger.warning(f"向量检索失败（降级关键词）: {e}")
            return []
