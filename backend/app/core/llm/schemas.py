"""LLM 请求/响应协议 — 供应商无关的数据模型"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class LLMMessage(BaseModel):
    """对话消息"""

    role: str = Field(..., description="system / user / assistant / tool")
    content: str = ""
    name: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class ToolCall(BaseModel):
    """模型发起的工具调用"""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMRequest(BaseModel):
    """一次 LLM 调用请求"""

    messages: list[LLMMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: Optional[list[dict]] = None          # OpenAI function schema 列表
    tool_choice: Optional[str] = None           # auto / none / 工具名
    response_format: Optional[dict] = None      # {"type": "json_object"}
    stop: Optional[list[str]] = None
    stream: bool = False


class LLMResponse(BaseModel):
    """一次 LLM 调用响应"""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False
    raw: Optional[dict] = None

    @property
    def text(self) -> str:
        return self.content
