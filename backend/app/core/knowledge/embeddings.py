"""嵌入模型抽象 — OpenAI 兼容 / Mock（哈希向量）"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """向量化嵌入抽象"""

    name = "base"
    dim: int = 768

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]


class OpenAICompatEmbeddings(EmbeddingProvider):
    """OpenAI 兼容 embeddings API（text-embedding-3-small 等）"""

    name = "openai"

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None, api_base: Optional[str] = None, dim: int = 1536):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.dim = dim
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_base)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        resp = await client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class MockEmbeddings(EmbeddingProvider):
    """确定性 Mock 嵌入 — 基于字符哈希的伪向量（无网络、可复现）"""

    name = "mock"

    def __init__(self, dim: int = 64):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import math

        results = []
        for text in texts:
            vec = [0.0] * self.dim
            for ch in text:
                h = int(hashlib.md5(ch.encode("utf-8")).hexdigest()[:8], 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            results.append([v / norm for v in vec])
        return results


def create_embeddings(provider: Optional[str] = None) -> EmbeddingProvider:
    """按配置创建嵌入模型"""
    from app.config import settings

    name = provider or settings.embedding.provider or "mock"
    if name == "openai":
        return OpenAICompatEmbeddings(
            model=settings.embedding.model,
            api_key=settings.embedding.api_key,
            api_base=settings.embedding.api_base,
        )
    if name == "local":
        logger.warning("本地嵌入暂未启用，回退 Mock（后续可接入 sentence-transformers）")
        return MockEmbeddings()
    return MockEmbeddings()
