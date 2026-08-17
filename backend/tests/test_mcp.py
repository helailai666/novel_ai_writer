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
