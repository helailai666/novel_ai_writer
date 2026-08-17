"""LLMProvider 抽象 — 所有供应商适配器的统一接口"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, TypeVar

from app.core.llm.schemas import LLMRequest, LLMResponse

Self = TypeVar("Self")


class LLMProvider(ABC):
    """LLM 供应商抽象

    实现要求：
    - acomplete: 非流式补全，返回 LLMResponse（含 usage / tool_calls）
    - astream: 流式补全，逐块产出文本
    - bind_tools: 返回绑定工具后的新实例（或自变异 + 返回 self）
    - with_structured: 返回强制结构化输出（JSON）的新实例
    """

    provider_name: str = "base"
    default_model: str = ""

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        self.model = model or self.default_model
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs

    @abstractmethod
    async def acomplete(self, req: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def astream(self, req: LLMRequest) -> AsyncIterator[str]: ...

    def bind_tools(self, tools: list[dict]) -> Self:
        """返回绑定工具的副本（默认不支持，子类覆盖）"""
        raise NotImplementedError(f"{self.provider_name} does not support tool binding")

    def with_structured(self, schema: dict) -> Self:
        """返回强制 JSON 结构化输出的副本（默认不支持，子类覆盖）"""
        raise NotImplementedError(f"{self.provider_name} does not support structured output")
