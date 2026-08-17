"""向量存储抽象 — Chroma（默认）/ Mock（内存）

统一接口：add / query / delete / count
条目结构：id, vector, text, metadata
"""

import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """向量存储抽象"""

    name = "base"

    @abstractmethod
    async def add(self, ids: list[str], vectors: list[list[float]], texts: list[str], metadatas: list[dict]) -> None: ...

    @abstractmethod
    async def query(self, vector: list[float], top_k: int = 5, where: Optional[dict] = None) -> list[dict]:
        """返回 [{id, text, metadata, score}] 按相似度降序"""
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> None: ...

    @abstractmethod
    async def count(self) -> int: ...


class MockVectorStore(VectorStore):
    """内存向量存储 — 余弦相似度（测试/降级用）"""

    name = "mock"

    def __init__(self):
        self._items: list[dict] = []  # {id, vector, text, metadata}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)

    async def add(self, ids, vectors, texts, metadatas) -> None:
        for i, vid in enumerate(ids):
            self._items.append({"id": vid, "vector": vectors[i], "text": texts[i], "metadata": metadatas[i]})

    async def query(self, vector, top_k=5, where=None) -> list[dict]:
        scored = []
        for item in self._items:
            meta = item["metadata"] or {}
            if where:
                skip = False
                for k, v in where.items():
                    if meta.get(k) != v and not (v is None and k not in meta):
                        if meta.get(k) != v:
                            skip = True
                            break
                if skip:
                    continue
            scored.append((self._cosine(vector, item["vector"]), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": it["id"], "text": it["text"], "metadata": it["metadata"], "score": round(s, 4)}
            for s, it in scored[:top_k]
        ]

    async def delete(self, ids) -> None:
        self._items = [it for it in self._items if it["id"] not in set(ids)]

    async def count(self) -> int:
        return len(self._items)


class ChromaVectorStore(VectorStore):
    """Chroma 持久化向量存储"""

    name = "chroma"

    def __init__(self, persist_dir: str = "./data/vectorstore", collection: str = "novel_knowledge"):
        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(name=collection, metadata={"hnsw:space": "cosine"})

    async def add(self, ids, vectors, texts, metadatas) -> None:
        self._collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)

    async def query(self, vector, top_k=5, where=None) -> list[dict]:
        where_meta = {k: v for k, v in (where or {}).items() if v is not None}
        results = self._collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where_meta or None,
        )
        items = []
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]
        for i, vid in enumerate(ids):
            items.append({
                "id": vid,
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "score": round(1 - (dists[i] if i < len(dists) else 0), 4),
            })
        return items

    async def delete(self, ids) -> None:
        self._collection.delete(ids=list(ids))

    async def count(self) -> int:
        return self._collection.count()


def create_vector_store(backend: Optional[str] = None) -> VectorStore:
    """按配置创建向量存储（Chroma 失败自动降级 Mock）"""
    from app.config import settings

    name = backend or settings.vector_store.backend or "mock"
    if name == "chroma":
        try:
            return ChromaVectorStore(persist_dir=settings.vector_store.persist_dir)
        except Exception as e:
            logger.warning(f"Chroma 初始化失败，降级 Mock 向量存储: {e}")
            return MockVectorStore()
    return MockVectorStore()
