"""Anthropic / Gemini / Ollama / Azure 专用适配器 — 均基于官方 langchain 供应商包"""

from typing import Optional

from app.core.llm.base import LLMProvider
from app.core.llm.schemas import LLMRequest, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude"""

    provider_name = "anthropic"

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, api_base, **kwargs)
        from langchain_anthropic import ChatAnthropic

        self._llm = ChatAnthropic(
            model=self.model,
            api_key=self.api_key,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
        )

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        resp = await self._llm.ainvoke(messages)
        return LLMResponse(content=str(resp.content), usage={})

    async def astream(self, req: LLMRequest):
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    def bind_tools(self, tools: list[dict]):
        self._llm = self._llm.bind_tools(tools)
        return self

    def with_structured(self, schema: dict):
        self._llm = self._llm.with_structured_output(schema)
        return self


class GeminiProvider(LLMProvider):
    """Google Gemini"""

    provider_name = "gemini"

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, api_base, **kwargs)
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._llm = ChatGoogleGenerativeAI(
            model=self.model,
            api_key=self.api_key,
            temperature=kwargs.get("temperature", 0.7),
            max_output_tokens=kwargs.get("max_tokens", 4096),
        )

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        resp = await self._llm.ainvoke(messages)
        return LLMResponse(content=str(resp.content), usage={})

    async def astream(self, req: LLMRequest):
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    def bind_tools(self, tools: list[dict]):
        self._llm = self._llm.bind_tools(tools)
        return self

    def with_structured(self, schema: dict):
        self._llm = self._llm.with_structured_output(schema)
        return self


class OllamaProvider(LLMProvider):
    """Ollama 本地模型 — 走 OpenAI 兼容端点"""

    provider_name = "ollama"

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        from app.core.llm.providers.openai_compat import OpenAICompatProvider

        self._inner = OpenAICompatProvider(
            model=model,
            api_key=api_key or "ollama",
            api_base=api_base or "http://localhost:11434/v1",
            **kwargs,
        )
        self.model = model

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        return await self._inner.acomplete(req)

    async def astream(self, req: LLMRequest):
        async for chunk in self._inner.astream(req):
            yield chunk

    def bind_tools(self, tools: list[dict]):
        self._inner.bind_tools(tools)
        return self

    def with_structured(self, schema: dict):
        self._inner.with_structured(schema)
        return self


class AzureProvider(LLMProvider):
    """Azure OpenAI"""

    provider_name = "azure"

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, api_base, **kwargs)
        from langchain_openai import AzureChatOpenAI

        self._llm = AzureChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            azure_endpoint=self.api_base,
            api_version=kwargs.get("api_version", "2024-02-01"),
            temperature=kwargs.get("temperature", 0.7),
        )

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        resp = await self._llm.ainvoke(messages)
        return LLMResponse(content=str(resp.content), usage={})

    async def astream(self, req: LLMRequest):
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=m.content) if m.role == "system" else HumanMessage(content=m.content)
            for m in req.messages
        ]
        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield str(chunk.content)

    def bind_tools(self, tools: list[dict]):
        self._llm = self._llm.bind_tools(tools)
        return self

    def with_structured(self, schema: dict):
        self._llm = self._llm.with_structured_output(schema)
        return self
