"""向量存储抽象 — Chroma（默认）/ Local（numpy 持久化）/ Mock（内存）

统一接口：add / query / delete / count
条目结构：id, vector, text, metadata
LocalVectorStore（I1）：无外部依赖的确定性离线向量检索，向量与元数据
以 JSON 持久化到 persist_dir，重启后自动加载。
"""

import json
import logging
import math
import os
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


class LocalVectorStore(VectorStore):
    """numpy 暴力余弦检索 + JSON 持久化（I1，无外部依赖）

    - 持久化文件: <persist_dir>/<collection>.json（含全部条目与向量）
    - 每次变更（add/delete）即落盘；query 用向量化余弦全量扫描
    - where 语义与 Mock 一致（元数据等值匹配；None 值匹配缺失键）
    """

    name = "local"

    def __init__(self, persist_dir: str = "./data/vectorstore", collection: str = "novel_knowledge"):
        self.persist_dir = persist_dir
        self.collection = collection
        self._file = os.path.join(persist_dir, f"{collection}.json")
        self._items: list[dict] = []
        self._load()

    # ── 持久化 ──────────────────────────────────────────────────

    def _load(self) -> None:
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file, encoding="utf-8") as f:
                data = json.load(f)
            self._items = data.get("items", []) or []
            logger.info(f"Local 向量存储加载: {self._file}（{len(self._items)} 条）")
        except Exception as e:
            logger.warning(f"Local 向量存储加载失败（空启动）: {e}")
            self._items = []

    def _save(self) -> None:
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            tmp = self._file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"items": self._items}, f, ensure_ascii=False)
            os.replace(tmp, self._file)
        except Exception as e:
            logger.warning(f"Local 向量存储保存失败: {e}")

    # ── 接口 ────────────────────────────────────────────────────

    async def add(self, ids, vectors, texts, metadatas) -> None:
        for i, vid in enumerate(ids):
            self._items.append({"id": vid, "vector": vectors[i], "text": texts[i], "metadata": metadatas[i]})
        self._save()

    async def query(self, vector, top_k=5, where=None) -> list[dict]:
        import numpy as np

        if not self._items:
            return []
        q = np.asarray(vector, dtype=float)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        qn = np.linalg.norm(q, axis=1, keepdims=True)
        qn[qn == 0] = 1.0
        q = q / qn

        mat = np.asarray([it["vector"] for it in self._items], dtype=float)
        mat = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9)
        scores = mat @ q.T  # (N, 1) 余弦相似度
        scores = scores.ravel()

        order = np.argsort(-scores)
        out: list[dict] = []
        for idx in order:
            item = self._items[int(idx)]
            meta = item["metadata"] or {}
            if where:
                skip = False
                for k, v in where.items():
                    if meta.get(k) != v and not (v is None and k not in meta):
                        skip = True
                        break
                if skip:
                    continue
            out.append({
                "id": item["id"],
                "text": item["text"],
                "metadata": meta,
                "score": round(float(scores[int(idx)]), 4),
            })
            if len(out) >= top_k:
                break
        return out

    async def delete(self, ids) -> None:
        idset = set(ids)
        before = len(self._items)
        self._items = [it for it in self._items if it["id"] not in idset]
        if len(self._items) != before:
            self._save()

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
    if name == "local":
        try:
            return LocalVectorStore(persist_dir=settings.vector_store.persist_dir)
        except Exception as e:
            logger.warning(f"Local 向量存储初始化失败，降级 Mock: {e}")
            return MockVectorStore()
    return MockVectorStore()
