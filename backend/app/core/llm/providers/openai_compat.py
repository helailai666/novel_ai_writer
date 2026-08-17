"""OpenAI 兼容适配器 — 覆盖 openai / deepseek / qwen / glm / kimi / moonshot / minimax / 小米 MiMo 等

基于 langchain-openai ChatOpenAI 实现：任何提供 OpenAI 兼容 /chat/completions 的服务均可接入。
"""

import json
import logging
from typing import AsyncIterator, Optional

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from app.core.llm.base import LLMProvider
from app.core.llm.schemas import LLMMessage, LLMRequest, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


def _to_lc_messages(messages: list[LLMMessage]) -> list:
    lc = []
    for m in messages:
        if m.role == "system":
            lc.append(SystemMessage(content=m.content))
        elif m.role == "tool":
            lc.append(ToolMessage(content=m.content, tool_call_id=m.tool_call_id or ""))
        elif m.role == "assistant":
            lc.append(AIMessage(content=m.content, tool_calls=m.tool_calls))
        else:
            lc.append(HumanMessage(content=m.content, name=m.name))
    return lc


class OpenAICompatProvider(LLMProvider):
    """OpenAI 兼容供应商"""

    provider_name = "openai"

    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, api_base, **kwargs)
        self._llm = self._build_llm(kwargs)

    def _build_llm(self, kwargs: dict) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.api_base,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
            timeout=kwargs.get("timeout", 60.0),
            streaming=False,
        )

    def _apply_request(self, llm: ChatOpenAI, req: LLMRequest) -> ChatOpenAI:
        if req.temperature != 0.7:
            llm = llm.bind(temperature=req.temperature)
        if req.max_tokens != 4096:
            llm = llm.bind(max_tokens=req.max_tokens)
        if req.tools:
            llm = llm.bind_tools(req.tools)
            if req.tool_choice:
                llm = llm.bind(tool_choice=req.tool_choice)
        if req.response_format:
            llm = llm.bind(response_format=req.response_format)
        if req.stop:
            llm = llm.bind(stop=req.stop)
        return llm

    @staticmethod
    def _to_response(resp) -> LLMResponse:
        content = resp.content if isinstance(resp.content, str) else json.dumps(resp.content, ensure_ascii=False)
        tool_calls = []
        raw_tool_calls = getattr(resp, "tool_calls", None) or []
        for tc in raw_tool_calls:
            if getattr(tc, "type", "function") != "function":
                continue
            args = tc.get("function", {}).get("arguments", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            name = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", ""),
                    name=name,
                    arguments=args if isinstance(args, dict) else json.loads(args or "{}"),
                )
            )
        usage = {}
        um = getattr(resp, "usage_metadata", None)
        if um:
            usage = {
                "input_tokens": um.get("input_tokens"),
                "output_tokens": um.get("output_tokens"),
                "total_tokens": um.get("total_tokens"),
            }
        elif hasattr(resp, "response_metadata"):
            usage = dict(getattr(resp.response_metadata, "get", lambda k, d=None: d)("token_usage", {}))
        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        llm = self._apply_request(self._llm, req)
        try:
            resp = await llm.ainvoke(_to_lc_messages(req.messages))
            return self._to_response(resp)
        except Exception as e:
            logger.error(f"[llm:{self.provider_name}] acomplete failed: {e}")
            raise

    async def astream(self, req: LLMRequest) -> AsyncIterator[str]:
        llm = self._apply_request(self._llm, req)
        async for chunk in llm.astream(_to_lc_messages(req.messages)):
            if isinstance(chunk, AIMessageChunk):
                content = chunk.content
                if isinstance(content, list):
                    # OpenAI 工具调用流式内容可能为列表
                    text = "".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                    yield text
                elif content:
                    yield str(content)
            else:
                yield str(chunk)

    def bind_tools(self, tools: list[dict]):
        self._llm = self._llm.bind_tools(tools)
        return self

    def with_structured(self, schema: dict):
        """强制 JSON 结构化输出

        - {"type": "json_object"} → response_format 绑定（OpenAI 兼容模式）
        - 其他 JSON Schema dict → with_structured_output(json_schema 模式)
        """
        if isinstance(schema, dict) and schema.get("type") == "json_object":
            self._llm = self._llm.bind(response_format={"type": "json_object"})
        else:
            self._llm = self._llm.with_structured_output(schema)
        return self
