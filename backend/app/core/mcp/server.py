"""NovelAI Writer MCP Server — 通过 MCP 协议控制小说创作全流程

- 服务端: 从全局 ToolRegistry 自动暴露全部内置工具（真实执行 DB/图/搜索，非 Mock）
- 传输: stdio（默认）/ SSE
- 启动:
    cd backend && python -m app.core.mcp.server            # stdio
    cd backend && python -m app.core.mcp.server --sse      # SSE (http://127.0.0.1:8765/sse)
- 注册到外部 MCP 客户端（如 Claude/AstrBot）:
    {"mcpServers": {"novel-writer": {"command": "python", "args": ["-m", "app.core.mcp.server"], "cwd": "<backend路径>"}}}
"""

import argparse
import logging
import typing
from typing import Optional

from app.config import settings
from app.core.tools.base import BaseTool
from app.core.tools.registry import get_registry

logger = logging.getLogger(__name__)


def _type_name(ann) -> str:
    """把 Python 类型注解归一为 MCP 可识别的简单类型名"""
    if ann is None:
        return "str"
    origin = typing.get_origin(ann)
    if origin is typing.Union:
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(args) == 1:
            return _type_name(args[0])
        return "str"
    if origin is list:
        return "list"
    if origin is dict:
        return "dict"
    name = getattr(ann, "__name__", None)
    return name or "str"


def _make_mcp_handler(tool: BaseTool):
    """按 args_schema 生成带类型签名的手柄（MCPServer 从函数签名推导 inputSchema）

    参数重排：必填在前、可选在后（Python 语法要求）。
    """
    fields = list(tool.args_schema.model_fields.items())
    ordered = [f for f in fields if f[1].is_required()] + [f for f in fields if not f[1].is_required()]

    params: list[str] = []
    assigns: list[str] = []
    for fname, finfo in ordered:
        ann_name = _type_name(finfo.annotation)
        if finfo.is_required():
            params.append(f"{fname}: {ann_name}")
        else:
            default = finfo.default
            if default is None or isinstance(default, (str, int, float, bool, list, dict)):
                params.append(f"{fname}: {ann_name} = {default!r}")
            else:
                params.append(f"{fname}: {ann_name} = None")
        assigns.append(f"kwargs[{fname!r}] = {fname}")

    src = (
        "async def _handler(" + ", ".join(params) + "):\n"
        + "    kwargs = {}\n"
        + "    " + "; ".join(assigns) + "\n"
        + "    result = await _TOOL.execute(**kwargs)\n"
        + "    if not result.ok:\n        raise ValueError(result.error)\n"
        + "    return result.content\n"
    )
    ns: dict = {"_TOOL": tool}
    exec(compile(src, f"<mcp_tool_{tool.name}>", "exec"), ns)
    handler = ns["_handler"]
    handler.__name__ = tool.name
    return handler


def create_server() -> "MCPServer":
    """基于全局工具注册表构建 MCP Server（真实工具）"""
    from mcp.server.mcpserver import MCPServer

    registry = get_registry()
    mcp = MCPServer(
        name=settings.mcp.server_name,
        version=settings.mcp.server_version,
        instructions="NovelAI Writer 创作平台 MCP 服务：提供设定生成、章节写作、审核、搜索、知识库检索等工具。",
    )
    for tool in registry.get_all():
        mcp.tool(name=tool.name, description=tool.description)(_make_mcp_handler(tool))
        logger.debug(f"MCP 工具注册: {tool.name}")
    return mcp


def main(argv: Optional[list[str]] = None) -> None:
    """stdio / SSE 启动入口"""
    parser = argparse.ArgumentParser(description="NovelAI Writer MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")

    mcp = create_server()
    logger.info(f"MCP Server 启动: transport={args.transport}, tools={len(get_registry().list_names())}")
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
