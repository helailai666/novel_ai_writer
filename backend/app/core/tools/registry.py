"""工具注册表 — 注册 / 查询 / 转换（LLM tools / MCP tools / 外部桥接）"""

import logging
from typing import Optional

from app.core.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表（进程内单例）"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    # ── 注册 ────────────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("工具必须定义 name")
        if tool.name in self._tools:
            logger.warning(f"工具重名，覆盖: {tool.name}")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    # ── 查询 ────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_all(self) -> list["BaseTool"]:
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    # ── 转换 ────────────────────────────────────────────────────

    def to_langchain_tools(self, allowlist: Optional[list[str]] = None) -> list:
        """转 langchain tools（绑定给 LLM）"""
        from langchain_core.tools import StructuredTool

        names = allowlist or list(self._tools.keys())
        lc_tools = []
        for name in names:
            tool = self._tools.get(name)
            if not tool:
                continue
            lc_tools.append(
                StructuredTool.from_function(
                    name=tool.name,
                    description=tool.description,
                    args_schema=tool.args_schema,
                    func=None,
                    coroutine=tool.execute,
                )
            )
        return lc_tools

    def to_specs(self, allowlist: Optional[list[str]] = None) -> list[dict]:
        """转 OpenAI function schema 列表（供 LLM bind_tools）"""
        names = allowlist or list(self._tools.keys())
        return [self._tools[n].to_spec() for n in names if n in self._tools]

    def to_mcp_tools(self, allowlist: Optional[list[str]] = None):
        """转 MCP Tool 定义列表（P5 服务端暴露用）"""
        from mcp.types import Tool

        names = allowlist or list(self._tools.keys())
        return [
            Tool(
                name=self._tools[n].name,
                description=self._tools[n].description,
                inputSchema=self._tools[n].to_mcp_schema(),
            )
            for n in names if n in self._tools
        ]

    # ── 执行 ────────────────────────────────────────────────────

    async def execute(self, name: str, args: dict) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(ok=False, error=f"未知工具: {name}")
        try:
            return await tool.execute(**args)
        except Exception as e:
            logger.exception(f"tool {name} 执行异常: {e}")
            return ToolResult(ok=False, error=str(e))

    # ── 外部工具桥接（MCP 客户端工具接入）─────────────────────────

    def ingest_external(self, name: str, description: str, schema: dict, executor) -> None:
        """把外部能力注册为内部工具（如 MCP 客户端动态发现的工具）"""

        class _ExternalTool(BaseTool):
            pass

        tool = _ExternalTool()
        tool.name = name
        tool.description = description
        tool.args_schema = _schema_to_model(schema)

        async def _execute(**kwargs):
            try:
                return await executor(**kwargs)
            except Exception as e:
                return ToolResult(ok=False, error=str(e))

        tool.execute = _execute  # type: ignore[assignment]
        self.register(tool)


def _schema_to_model(schema: dict):
    """外部 JSON Schema → pydantic 模型（宽松：全部 Optional + 支持 enum）"""
    from typing import Optional as Opt

    from pydantic import create_model

    properties = schema.get("properties") or {}
    fields = {}
    for key, meta in properties.items():
        py_type = _json_type_to_py(meta.get("type", "string"))
        if meta.get("enum"):
            py_type = Opt[py_type]
        fields[key] = (Opt[py_type], None)
    return create_model("ExternalArgs", **fields)


def _json_type_to_py(jtype: str):
    from typing import Any

    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": Any,
    }
    return mapping.get(jtype, str)


# ── 全局单例 ────────────────────────────────────────────────────

_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """全局工具注册表单例（首次调用时装载内置工具）"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _load_builtin(_registry)
    return _registry


def _load_builtin(registry: ToolRegistry) -> None:
    """装载内置工具（每个模块暴露 <name>_tool 实例）"""
    from app.core.tools import builtin

    for attr in dir(builtin):
        if attr.endswith("_tool"):
            tool = getattr(builtin, attr)
            if isinstance(tool, BaseTool):
                registry.register(tool)
