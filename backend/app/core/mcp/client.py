"""MCP 客户端 — 桥接外部 MCP Server 的工具进内部注册表

配置格式（backend/config/mcp_servers.yaml）：
- transport: stdio（command/args）或 sse（url）
- tool_allowlist: 允许桥接的工具白名单（空=全部）
桥接工具命名: mcp_<server_name>_<tool_name>
调用语义：每次调用独立建立连接（stdio 子进程短生命周期；SSE 为短连接）
"""

import logging
from typing import Optional

from app.core.tools.registry import get_registry

logger = logging.getLogger(__name__)


def _open_ctx(config: dict):
    """按 transport 返回异步上下文管理器（read, write）"""
    transport = config.get("transport", "stdio")
    if transport == "stdio":
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=config["command"], args=config.get("args", []), env=config.get("env"))
        return stdio_client(params)
    if transport == "sse":
        from mcp.client.sse import sse_client

        return sse_client(config["url"], headers=config.get("headers"))
    raise ValueError(f"未知 MCP transport: {transport}")


async def bridge_mcp_server(config: dict, registry=None) -> list[str]:
    """连接外部 MCP server，把其工具注册进注册表，返回桥接工具名列表"""
    registry = registry or get_registry()
    name = config.get("name", "external")
    allowlist = set(config.get("tool_allowlist") or [])
    namespace = f"mcp_{name}"

    bridged: list[str] = []
    # 第一轮：发现工具（短连接）
    async with _open_ctx(config) as (read, write):
        from mcp import ClientSession

        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

    for tool in tools_result.tools:
        if allowlist and tool.name not in allowlist:
            continue
        ext_name = f"{namespace}_{tool.name}"

        async def _executor(_cfg=config, _tool_name=tool.name, **kwargs):
            from mcp import ClientSession

            async with _open_ctx(_cfg) as (r2, w2):
                async with ClientSession(r2, w2) as session2:
                    await session2.initialize()
                    result = await session2.call_tool(_tool_name, kwargs)
            texts = [
                c.text for c in result.content
                if hasattr(c, "text") and getattr(c, "type", "") == "text"
            ]
            return "\n".join(texts) or "(无文本返回)"

        registry.ingest_external(
            name=ext_name,
            description=f"[MCP:{name}] {tool.description or tool.name}",
            schema=tool.input_schema or {},
            executor=_executor,
        )
        bridged.append(ext_name)
        logger.info(f"MCP 桥接工具: {ext_name}")
    return bridged


def load_mcp_config(path: Optional[str] = None) -> list[dict]:
    """加载 mcp_servers.yaml 配置（缺文件/空 → []）"""
    import os

    import yaml

    from app.config import settings

    file = path or settings.mcp.servers_file
    if not os.path.exists(file):
        logger.info(f"MCP 配置文件不存在（跳过外部 server 桥接）: {file}")
        return []
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        servers = data.get("servers", []) or []
        return [s for s in servers if s.get("enabled", True)]
    except Exception as e:
        logger.warning(f"MCP 配置加载失败: {e}")
        return []


async def bridge_all(registry=None) -> dict[str, list[str]]:
    """按配置桥接全部外部 server，返回 {server_name: [tools]}"""
    from app.config import settings

    if not settings.mcp.enabled:
        return {}
    results: dict[str, list[str]] = {}
    for cfg in load_mcp_config():
        try:
            results[cfg.get("name", "unknown")] = await bridge_mcp_server(cfg, registry)
        except Exception as e:
            logger.error(f"MCP server '{cfg.get('name')}' 桥接失败: {e}")
    return results
