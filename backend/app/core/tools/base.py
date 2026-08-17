"""工具抽象 — BaseTool 协议 + ToolResult"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """工具执行结果"""

    ok: bool = True
    content: str = ""
    data: Any = None
    error: str = ""

    @property
    def summary(self) -> str:
        """面向事件流/日志的短摘要"""
        if not self.ok:
            return f"失败: {self.error[:200]}"
        return self.content[:500]


class BaseTool(ABC):
    """工具协议：name / description / args_schema / execute

    规范：
    - execute 必须容忍异常并返回 ToolResult（不抛）
    - args_schema 用于 JSON Schema 生成（LLM 绑定 / MCP 暴露）
    """

    name: str = ""
    description: str = ""
    args_schema: type[BaseModel] = BaseModel

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...

    def to_spec(self) -> dict:
        """转 OpenAI function schema（供 LLM bind_tools 与 MCP 使用）"""
        properties = {}
        required = []
        schema = self.args_schema.model_json_schema()
        for key, meta in (schema.get("properties") or {}).items():
            props = {
                "type": meta.get("type", "string"),
                "description": meta.get("description", ""),
            }
            if meta.get("enum"):
                props["enum"] = meta["enum"]
            properties[key] = props
            if key in (schema.get("required") or []):
                required.append(key)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }

    def to_mcp_schema(self) -> dict:
        """MCP 工具输入 schema（JSON Schema 格式）"""
        schema = self.args_schema.model_json_schema()
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
