"""MCP 客户端 — 桥接外部 MCP Server 的工具进内部注册表

配置格式（backend/config/mcp_servers.yaml）：
- transport: stdio（command/args）或 sse（url）
- tool_allowlist: 允许桥接的工具白名单（空=全部）
- pool_size: 可选，并发会话数（stdio 强制 1；SSE 默认取 MCP_DEFAULT_POOL_SIZE）
- connect_timeout: 可选，建连/初始化超时秒数（默认 MCP_DEFAULT_CONNECT_TIMEOUT）
- max_retries: 可选，调用失败重试次数（默认 MCP_DEFAULT_MAX_RETRIES）
桥接工具命名: mcp_<server_name>_<tool_name>
调用语义（G3/G4）：每 server 维护长连接会话池，跨调用复用（stdio 子进程
不反复启停）；会话失效自动销毁重建（每次调用最多重试 max_retries 次）。
"""

import asyncio
import logging
from types import SimpleNamespace
from typing import Optional

from app.config import settings
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
    """单个外部 MCP server 的长连接池（G3 单会话 → I2 参数化多会话）

    - 惰性建连：首次调用工具时才建立连接
    - 容量控制：stdio 强制 1 会话（子进程不宜并发）；SSE 支持 pool_size>1
      并发会话（忙会话不可复用，满额时等待）
    - 断线自愈：调用/发现失败时销毁该会话，重试（最多 max_retries 次）
    - 超时保护：建连/初始化受 connect_timeout 约束
    """

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("name", "external")
        transport = config.get("transport", "stdio")
        # stdio 子进程串行：强制 1；SSE 取条目配置或全局默认
        requested = int(config.get("pool_size") or settings.mcp.default_pool_size)
        self._max_sessions = 1 if transport == "stdio" else max(1, requested)
        self.connect_timeout = float(config.get("connect_timeout") or settings.mcp.default_connect_timeout)
        self.max_retries = max(0, int(config.get("max_retries") or settings.mcp.default_max_retries))
        self._sessions: list[SimpleNamespace] = []  # {session, stream_cm, busy}
        self._lock = asyncio.Lock()          # 建连/清理/簿记串行
        self._sem = asyncio.Semaphore(self._max_sessions)  # 容量门闩
        self._closed = False

    # ── 连接生命周期 ────────────────────────────────────────────

    async def _connect_one(self) -> SimpleNamespace:
        """新建一个会话（流保持打开；connect_timeout 保护）"""
        from mcp import ClientSession

        ps = SimpleNamespace(session=None, stream_cm=None, busy=False)
        cm = _open_ctx(self.config)
        read, write = await asyncio.wait_for(cm.__aenter__(), timeout=self.connect_timeout)
        try:
            session = ClientSession(read, write)
            await asyncio.wait_for(session.__aenter__(), timeout=self.connect_timeout)
            await asyncio.wait_for(session.initialize(), timeout=self.connect_timeout)
        except BaseException:
            await cm.__aexit__(None, None, None)
            raise
        ps.stream_cm = cm
        ps.session = session
        return ps

    async def _connect(self) -> None:
        """新建一个会话加入池（容量已满时跳过）— 测试打桩点"""
        async with self._lock:
            if self._closed or len(self._sessions) >= self._max_sessions:
                return
            ps = await self._connect_one()
            self._sessions.append(ps)

    @staticmethod
    async def _close_one(ps: SimpleNamespace) -> None:
        """关闭单个会话（幂等；不涉及池簿记）"""
        session, ps.session = ps.session, None
        cm, ps.stream_cm = ps.stream_cm, None
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

    async def _discard(self, ps: SimpleNamespace) -> None:
        """从池中移除并关闭一个会话（调用失败后）"""
        async with self._lock:
            if ps in self._sessions:
                self._sessions.remove(ps)
                await self._close_one(ps)

    async def _disconnect(self) -> None:
        """销毁全部会话（幂等；测试/关闭用）"""
        async with self._lock:
            sessions, self._sessions = self._sessions, []
            for ps in sessions:
                await self._close_one(ps)

    async def close(self) -> None:
        """关闭连接池（应用退出时调用）"""
        self._closed = True
        await self._disconnect()

    # ── 会话获取/释放 ────────────────────────────────────────────

    async def _acquire(self) -> SimpleNamespace:
        """获取一个空闲会话（无则新建，满额等待），标记 busy"""
        await self._sem.acquire()
        try:
            while True:
                async with self._lock:
                    idle = next((s for s in self._sessions if not s.busy and s.session is not None), None)
                    if idle is not None:
                        idle.busy = True
                        return idle
                    if len(self._sessions) < self._max_sessions:
                        need_new = True
                    else:
                        need_new = False
                if need_new:
                    await self._connect()  # 新建（计数打桩点）
                    continue
                await asyncio.sleep(0.005)  # 满额且全忙 → 等释放
        except BaseException:
            self._sem.release()
            raise

    def _release(self, ps: SimpleNamespace) -> None:
        """归还会话（已销毁的跳过忙标记）"""
        if ps in self._sessions:
            ps.busy = False
        self._sem.release()

    # ── 工具发现与调用 ──────────────────────────────────────────

    async def list_tools(self):
        """列出远端工具（复用池连接，失效自动重建一次）"""
        ps = await self._acquire()
        try:
            try:
                return (await ps.session.list_tools()).tools
            except Exception as e:
                logger.warning(f"MCP 工具发现失败，重建会话: {self.name}: {e}")
                await self._discard(ps)
                ps = await self._acquire()
                return (await ps.session.list_tools()).tools
        finally:
            self._release(ps)

    async def call_tool(self, tool_name: str, args: dict) -> str:
        """调用远端工具，返回文本拼接结果（失效自动重建，最多重试 max_retries 次）"""
        if self._closed:
            raise RuntimeError(f"MCP 连接池已关闭: {self.name}")
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            ps = await self._acquire()
            try:
                result = await ps.session.call_tool(tool_name, args)
                texts = [
                    c.text for c in result.content
                    if hasattr(c, "text") and getattr(c, "type", "") == "text"
                ]
                return "\n".join(texts) or "(无文本返回)"
            except Exception as e:
                last_err = e
                logger.warning(f"MCP 调用失败，销毁会话重试: {self.name}.{tool_name} (第{attempt + 1}次): {e}")
                await self._discard(ps)
            finally:
                self._release(ps)
        raise last_err or RuntimeError(f"MCP 调用失败: {self.name}.{tool_name}")


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
        pool.config = config  # 刷新配置（超时/重试下次生效；pool_size 首次建池后固定）
        pool.connect_timeout = float(config.get("connect_timeout") or settings.mcp.default_connect_timeout)
        pool.max_retries = max(0, int(config.get("max_retries") or settings.mcp.default_max_retries))
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
