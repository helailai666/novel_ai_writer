"""MCP 客户端 — 桥接外部 MCP Server 的工具进内部注册表

配置格式（backend/config/mcp_servers.yaml）：
- transport: stdio（command/args）或 sse（url）
- tool_allowlist: 允许桥接的工具白名单（空=全部）
桥接工具命名: mcp_<server_name>_<tool_name>
调用语义（G3）：每个 server 维护长连接会话池，跨调用复用（stdio 子进程
不反复启停）；会话失效自动重连（每次调用最多重连一次）。
"""

import asyncio
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


class McpConnectionPool:
    """单个外部 MCP server 的长连接池（G3）

    - 惰性建连：首次调用工具时才建立连接
    - 串行复用：单会话 + asyncio.Lock（stdio 子进程不宜并发调用）
    - 断线自愈：调用/发现失败时销毁会话，重连一次并重试
    """

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("name", "external")
        self._session: Optional[object] = None   # ClientSession
        self._stream_cm: Optional[object] = None  # stdio/sse 流上下文管理器
        self._lock = asyncio.Lock()
        self._closed = False

    # ── 连接生命周期 ────────────────────────────────────────────

    async def _connect(self) -> None:
        """建立新会话（流保持打开，供后续调用复用）"""
        from mcp import ClientSession

        cm = _open_ctx(self.config)
        read, write = await cm.__aenter__()  # 保持流打开
        try:
            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()
        except BaseException:
            await cm.__aexit__(None, None, None)
            raise
        self._stream_cm = cm
        self._session = session

    async def _disconnect(self) -> None:
        """销毁当前会话（幂等）"""
        session, self._session = self._session, None
        cm, self._stream_cm = self._stream_cm, None
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"MCP 会话关闭异常: {e}")
        if cm is not None:
            try:
                await cm.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"MCP 流关闭异常: {e}")

    async def close(self) -> None:
        """关闭连接池（应用退出时调用）"""
        self._closed = True
        async with self._lock:
            await self._disconnect()

    # ── 工具发现与调用 ──────────────────────────────────────────

    async def list_tools(self):
        """列出远端工具（复用池连接，失效自动重连一次）"""
        async with self._lock:
            if self._session is None:
                await self._connect()
            try:
                return (await self._session.list_tools()).tools
            except Exception as e:
                logger.warning(f"MCP 工具发现失败，重连: {self.name}: {e}")
                await self._disconnect()
                await self._connect()
                return (await self._session.list_tools()).tools

    async def call_tool(self, tool_name: str, args: dict) -> str:
        """调用远端工具，返回文本拼接结果（失效自动重连一次）"""
        if self._closed:
            raise RuntimeError(f"MCP 连接池已关闭: {self.name}")
        async with self._lock:
            if self._session is None:
                await self._connect()
            try:
                result = await self._session.call_tool(tool_name, args)
            except Exception as e:
                logger.warning(f"MCP 调用失败，重连一次: {self.name}.{tool_name}: {e}")
                await self._disconnect()
                await self._connect()
                result = await self._session.call_tool(tool_name, args)
            texts = [
                c.text for c in result.content
                if hasattr(c, "text") and getattr(c, "type", "") == "text"
            ]
            return "\n".join(texts) or "(无文本返回)"


# ── 连接池管理（进程内，按 server name 复用）─────────────────────

_pools: dict[str, McpConnectionPool] = {}


def get_pool(config: dict) -> McpConnectionPool:
    """按 server name 获取连接池（复用已建会话；配置变更时刷新）"""
    name = config.get("name", "external")
    pool = _pools.get(name)
    if pool is None:
        pool = McpConnectionPool(config)
        _pools[name] = pool
    elif not pool._closed:
        pool.config = config  # 刷新配置（下次重连生效）
    return pool


async def close_all_pools() -> None:
    """关闭全部连接池（应用退出 / 测试清理）"""
    for name, pool in list(_pools.items()):
        try:
            await pool.close()
        except Exception as e:
            logger.warning(f"关闭 MCP 连接池失败: {name}: {e}")
    _pools.clear()


async def bridge_mcp_server(config: dict, registry=None) -> list[str]:
    """连接外部 MCP server，把其工具注册进注册表，返回桥接工具名列表"""
    registry = registry or get_registry()
    name = config.get("name", "external")
    allowlist = set(config.get("tool_allowlist") or [])
    namespace = f"mcp_{name}"
    pool = get_pool(config)

    # 清理该 namespace 的旧桥接（reload 时不残留/不重复）
    for t in registry.get_all():
        if t.name.startswith(namespace + "_"):
            registry.unregister(t.name)

    try:
        tools = await pool.list_tools()
    except Exception as e:
        logger.error(f"MCP server '{name}' 工具发现失败: {e}")
        return []

    bridged: list[str] = []
    for tool in tools:
        if allowlist and tool.name not in allowlist:
            continue
        ext_name = f"{namespace}_{tool.name}"

        async def _executor(_pool=pool, _tool_name=tool.name, **kwargs):
            return await _pool.call_tool(_tool_name, kwargs)

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
