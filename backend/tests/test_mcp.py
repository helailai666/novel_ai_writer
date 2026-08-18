"""MCP 测试 — 服务端真实工具暴露（stdio 握手）/ 客户端桥接外部 server"""

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
