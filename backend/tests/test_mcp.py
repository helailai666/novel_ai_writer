"""MCP 测试 — 服务端真实工具暴露（stdio 握手）/ 客户端桥接外部 server"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

# 子进程环境：强制 mock、复用测试 DB
_SUBPROC_ENV = {
    **os.environ,
    "DATABASE_URL": "",
    "LLM_API_KEY": "",
    "OPENAI_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
    "EMBEDDING_PROVIDER": "mock",
    "VECTOR_STORE_BACKEND": "mock",
    "MCP_SERVERS_FILE": "/nonexistent.yaml",
}


@pytest.fixture(autouse=True)
async def _close_mcp_pools():
    """每个测试后关闭外部 MCP 连接池并注销桥接工具

    连接池不复用会遗留 stdio 子进程、拖住事件循环退出；桥接工具不注销
    会污染全局注册表（影响 /api/tools 数量等顺序相关断言）。
    """
    yield
    from app.core.mcp.client import close_all_pools
    from app.core.tools.registry import get_registry

    registry = get_registry()
    for t in registry.get_all():
        if t.name.startswith("mcp_"):
            registry.unregister(t.name)
    await close_all_pools()


async def test_mcp_server_exposes_real_tools(db, test_db_url):
    """MCP 服务端：stdio 握手 → 工具列表含真实工具 → 调用 project_summary 返回真实数据"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**_SUBPROC_ENV, "DATABASE_URL": test_db_url}
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.core.mcp.server"], cwd=str(BACKEND_DIR), env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            names = [t.name for t in tools]
            assert len(names) >= 10, f"应暴露全部内置工具: {names}"
            for expect in ("setting_query", "knowledge_retrieve", "hot_meme_lookup", "web_search", "weapon_lookup"):
                assert expect in names, f"MCP 缺工具: {expect}"

            # 真实调用：project_summary 应返回测试项目
            res = await session.call_tool("project_summary", {"project_id": db})
            assert res.content and "图测试" in res.content[0].text


FAKE_MCP_SERVER = '''
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(name="fake")

@mcp.tool(name="echo", description="回声测试工具")
def echo(text: str) -> str:
    """回声测试工具"""
    return f"echo:{text}"

mcp.run(transport="stdio")
'''


async def test_mcp_client_bridges_external_server(tmp_path):
    """MCP 客户端：桥接外部 stdio server 的工具进注册表并可调用"""
    from app.core.mcp.client import bridge_mcp_server
    from app.core.tools.registry import get_registry

    server_file = tmp_path / "fake_mcp_server.py"
    server_file.write_text(FAKE_MCP_SERVER, encoding="utf-8")

    cfg = {"name": "fake", "transport": "stdio", "command": sys.executable, "args": [str(server_file)]}
    registry = get_registry()
    bridged = await bridge_mcp_server(cfg, registry)
    assert "mcp_fake_echo" in bridged, f"桥接工具名应为 mcp_fake_echo: {bridged}"

    result = await registry.execute("mcp_fake_echo", {"text": "你好"})
    assert result.ok is True and "echo:你好" in result.content
    assert registry.get("mcp_fake_echo").description.startswith("[MCP:fake]")


async def test_bridged_external_tool_used_by_writer(tmp_path, db, monkeypatch):
    """外部 MCP 工具桥接后，写作图 ReAct 工具循环可真实调用它"""
    import app.agents.nodes.common as common
    from app.core.llm.providers.mock import MockProvider
    from app.core.llm.schemas import LLMRequest, LLMResponse, ToolCall

    # 1) 桥接一个独立命名的 fake echo server
    server_file = tmp_path / "fake_mcp_server2.py"
    server_file.write_text(FAKE_MCP_SERVER, encoding="utf-8")
    cfg = {"name": "fake2", "transport": "stdio", "command": sys.executable, "args": [str(server_file)]}
    from app.core.mcp.client import bridge_mcp_server
    from app.core.tools.registry import get_registry

    registry = get_registry()
    bridged = await bridge_mcp_server(cfg, registry)
    assert "mcp_fake2_echo" in bridged

    # 2) Fake LLM：第一轮调用外部工具，第二轮成稿
    class FakeExternalLLM(MockProvider):
        call_count = 0

        async def acomplete(self, req: LLMRequest) -> LLMResponse:
            self.call_count += 1
            if self.call_count == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="c1", name="mcp_fake2_echo", arguments={"text": "写作前先回声"})],
                    usage={"mock": True}, is_mock=True,
                )
            return LLMResponse(content="正文成稿", usage={"mock": True}, is_mock=True)

    fake = FakeExternalLLM(model="mock")

    def _create(*args, **kwargs):
        return fake

    monkeypatch.setattr(common, "create", _create)

    # 3) 跑写作图
    from app.agents.runner import get_runner

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate",
        "prompt": "第一章", "style": "narrative", "target_word_count": 100,
        "chapter_number": 1, "volume_id": None,
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    events_list = []
    async for ev in get_runner().astream("chapter", state):
        events_list.append(ev)

    tool_calls = [e for e in events_list if e["type"] == "tool_call"]
    assert any(e["tool"] == "mcp_fake2_echo" for e in tool_calls), "writer 应调用桥接的外部 MCP 工具"
    done = [e for e in events_list if e["type"] == "done"][-1]
    assert done["result"].get("saved") is True


# ── G3 连接池 ─────────────────────────────────────────────────────

def _counting_connect(monkeypatch, counter):
    """monkeypatch _connect 为计数版本，返回原实现"""
    import app.core.mcp.client as mcp_client

    orig = mcp_client.McpConnectionPool._connect

    async def counting_connect(self):
        counter["n"] += 1
        return await orig(self)

    monkeypatch.setattr(mcp_client.McpConnectionPool, "_connect", counting_connect)
    return counter


async def test_mcp_pool_reuses_session(tmp_path, monkeypatch):
    """连接池复用：工具发现 + 多次调用只建连一次"""
    from app.core.mcp.client import bridge_mcp_server
    from app.core.tools.registry import get_registry

    counter = _counting_connect(monkeypatch, {"n": 0})
    server_file = tmp_path / "fake_mcp_server3.py"
    server_file.write_text(FAKE_MCP_SERVER, encoding="utf-8")
    cfg = {"name": "fake3", "transport": "stdio", "command": sys.executable, "args": [str(server_file)]}

    registry = get_registry()
    await bridge_mcp_server(cfg, registry)
    assert counter["n"] == 1, "工具发现阶段应建连一次"

    r1 = await registry.execute("mcp_fake3_echo", {"text": "a"})
    r2 = await registry.execute("mcp_fake3_echo", {"text": "b"})
    assert r1.ok and r2.ok and "echo:a" in r1.content and "echo:b" in r2.content
    assert counter["n"] == 1, "多次调用应复用同一会话，不重建连接"


async def test_mcp_pool_reconnects_after_session_death(tmp_path, monkeypatch):
    """会话失效后自动重连一次并成功"""
    from app.core.mcp.client import bridge_mcp_server, get_pool
    from app.core.tools.registry import get_registry

    counter = _counting_connect(monkeypatch, {"n": 0})
    server_file = tmp_path / "fake_mcp_server4.py"
    server_file.write_text(FAKE_MCP_SERVER, encoding="utf-8")
    cfg = {"name": "fake4", "transport": "stdio", "command": sys.executable, "args": [str(server_file)]}

    registry = get_registry()
    await bridge_mcp_server(cfg, registry)
    pool = get_pool(cfg)
    assert counter["n"] == 1

    await registry.execute("mcp_fake4_echo", {"text": "a"})
    assert counter["n"] == 1

    # 模拟会话死亡（直接销毁底层连接）
    await pool._disconnect()
    r = await registry.execute("mcp_fake4_echo", {"text": "b"})
    assert r.ok and "echo:b" in r.content
    assert counter["n"] == 2, "会话失效后应自动重连一次"


# ── I2 连接池参数化（pool_size / 超时 / 重试）──────────────────────

class _FakeMCPResult:
    def __init__(self, text="ok"):
        self.content = [type("C", (), {"text": text, "type": "text"})()]


class _FakeMCPCallSession:
    """可编程失败次数的假 MCP 会话（失败计数全局共享：重试的新会话不重复失败）"""

    def __init__(self, shared=None):
        self.shared = shared or {"fail_left": 0}

    async def call_tool(self, name, args):
        if self.shared["fail_left"] > 0:
            self.shared["fail_left"] -= 1
            raise RuntimeError("boom")
        await asyncio.sleep(0.01)
        return _FakeMCPResult(text=f"ok:{name}")


def _fake_connect_one(monkeypatch, counter, fail_times=0):
    """monkeypatch _connect_one：返回假会话并计数（失败次数全局共享）"""
    import app.core.mcp.client as mcp_client

    shared = {"fail_left": fail_times}

    async def fake(self):
        counter["created"] += 1
        from types import SimpleNamespace

        return SimpleNamespace(session=_FakeMCPCallSession(shared), stream_cm=None, busy=False)

    monkeypatch.setattr(mcp_client.McpConnectionPool, "_connect_one", fake)
    return counter


def test_mcp_pool_stdio_forces_single_session():
    """stdio 传输强制单会话（子进程不宜并发）；SSE 接受 pool_size"""
    from app.config import settings

    import app.core.mcp.client as mcp_client

    p = mcp_client.McpConnectionPool({"name": "s", "transport": "stdio", "pool_size": 3})
    assert p._max_sessions == 1
    p2 = mcp_client.McpConnectionPool({"name": "s2", "transport": "sse", "url": "http://x", "pool_size": 3})
    assert p2._max_sessions == 3
    p3 = mcp_client.McpConnectionPool({"name": "s3", "transport": "sse", "url": "http://x"})
    assert p3._max_sessions == max(1, settings.mcp.default_pool_size)


async def test_mcp_pool_sse_pool_size_limits_concurrent_sessions(monkeypatch):
    """pool_size=2：3 个并发调用只建 2 个会话，全部成功；串行复用不再新建"""
    import app.core.mcp.client as mcp_client

    counter = _fake_connect_one(monkeypatch, {"created": 0})
    pool = mcp_client.McpConnectionPool({"name": "sse1", "transport": "sse", "url": "http://x", "pool_size": 2, "max_retries": 0})

    async def call():
        return await pool.call_tool("t", {})

    results = await asyncio.gather(call(), call(), call())
    assert all("ok:t" in r for r in results)
    assert counter["created"] == 2, f"并发下应最多建 2 个会话: {counter['created']}"

    # 串行复用：不新建
    await pool.call_tool("t", {})
    assert counter["created"] == 2
    await pool.close()


async def test_mcp_pool_retries_then_succeeds(monkeypatch):
    """max_retries=1：首次调用失败销毁会话重试，第二次成功"""
    import app.core.mcp.client as mcp_client

    counter = _fake_connect_one(monkeypatch, {"created": 0}, fail_times=1)
    pool = mcp_client.McpConnectionPool({"name": "sse2", "transport": "sse", "url": "http://x", "pool_size": 1, "max_retries": 1})
    result = await pool.call_tool("t", {})
    assert "ok:t" in result
    assert counter["created"] == 2, "失败后应重建会话重试"
    await pool.close()


async def test_mcp_pool_max_retries_exhausted_raises(monkeypatch):
    """始终失败 → max_retries+1 次尝试后抛错"""
    import pytest

    import app.core.mcp.client as mcp_client

    counter = _fake_connect_one(monkeypatch, {"created": 0}, fail_times=999)
    pool = mcp_client.McpConnectionPool({"name": "sse3", "transport": "sse", "url": "http://x", "pool_size": 1, "max_retries": 2})
    with pytest.raises(RuntimeError):
        await pool.call_tool("t", {})
    assert counter["created"] == 3, "应尝试 max_retries+1=3 次"
    await pool.close()


def test_mcp_pool_config_refresh_updates_timeout_and_retries():
    """get_pool 配置刷新：超时/重试生效（pool_size 固定）"""
    import app.core.mcp.client as mcp_client

    p = mcp_client.McpConnectionPool({"name": "cfg", "transport": "sse", "url": "http://x", "max_retries": 1, "connect_timeout": 5.0})
    mcp_client._pools["cfg"] = p  # 注册进池管理，验证 get_pool 复用+刷新
    refreshed = mcp_client.get_pool({"name": "cfg", "transport": "sse", "url": "http://x", "max_retries": 3, "connect_timeout": 12.0})
    assert refreshed is p
    assert p.max_retries == 3 and p.connect_timeout == 12.0
