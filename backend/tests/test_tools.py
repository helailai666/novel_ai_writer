"""Tools 体系测试 — 注册表 / 内置工具 / 写作图工具循环"""

import json

import pytest

from app.core.llm.schemas import LLMRequest, LLMResponse, ToolCall
from app.core.llm.providers.mock import MockProvider
from app.core.tools.base import ToolResult
from app.core.tools.registry import ToolRegistry, get_registry


# ── 注册表 ────────────────────────────────────────────────────────

def test_registry_builtin_loaded():
    reg = get_registry()
    names = reg.list_names()
    for expect in ("web_search", "setting_query", "chapter_get", "project_summary",
                   "character_lookup", "weapon_lookup", "world_setting_lookup", "foreshadow_query"):
        assert expect in names, f"内置工具缺失: {expect}"


def test_tool_spec_conversion():
    tool = get_registry().get("setting_query")
    spec = tool.to_spec()
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "setting_query"
    props = spec["function"]["parameters"]["properties"]
    assert "project_id" in props and "module" in props
    assert spec["function"]["parameters"]["required"] == ["project_id", "module"]


def test_registry_unknown_tool():
    reg = ToolRegistry()
    import asyncio

    result = asyncio.run(reg.execute("nonexistent", {}))
    assert result.ok is False and "未知工具" in result.error


# ── 内置工具（DB）─────────────────────────────────────────────────

async def test_setting_query_tool(db):
    from app.services.setting_service import SettingService

    from app.database import async_session_factory

    async with async_session_factory() as session:
        await SettingService.create(session, db, "world", {"name": "九州", "category": "geography", "content": "五洲四海"})
        await session.commit()

    tool = get_registry().get("setting_query")
    result = await tool.execute(project_id=db, module="world", keyword="九州")
    assert result.ok is True
    assert "九州" in result.content


async def test_weapon_lookup_tool(db):
    from app.services.setting_service import SettingService

    from app.database import async_session_factory

    async with async_session_factory() as session:
        await SettingService.create(session, db, "items", {"name": "九天玄剑", "category": "weapon", "description": "神兵"})
        await session.commit()

    tool = get_registry().get("weapon_lookup")
    result = await tool.execute(project_id=db)
    assert result.ok is True and "九天玄剑" in result.content


# ── 写作图工具循环（Fake 工具调用 LLM）────────────────────────────

class FakeToolLLM(MockProvider):
    """第一轮返回工具调用，第二轮返回最终文本"""

    call_count = 0
    project_id = "x"

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        self.call_count += 1
        if self.call_count == 1:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="setting_query",
                        arguments={"project_id": self.project_id, "module": "world", "keyword": "九州"},
                    )
                ],
                usage={"mock": True},
                is_mock=True,
            )
        return LLMResponse(content="最终成稿内容测试", usage={"mock": True}, is_mock=True)


async def test_chapter_graph_tool_loop(monkeypatch, db):
    """写作图 generate 模式：writer 调用 setting_query 工具后再成稿"""
    import app.agents.nodes.common as common

    fake = FakeToolLLM(model="mock")
    fake.project_id = db

    def _create(*args, **kwargs):
        return fake

    monkeypatch.setattr(common, "create", _create)
    # 预置一条世界观设定供工具查询
    from app.database import async_session_factory
    from app.services.setting_service import SettingService

    async with async_session_factory() as session:
        await SettingService.create(session, db, "world", {"name": "九州", "category": "geography", "content": "五洲四海"})
        await session.commit()

    from app.agents.runner import get_runner

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate",
        "prompt": "第一章", "style": "narrative", "target_word_count": 200,
        "chapter_number": 1, "volume_id": None,
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    events_list = []
    async for ev in get_runner().astream("chapter", state):
        events_list.append(ev)

    types = [e["type"] for e in events_list]
    tool_calls = [e for e in events_list if e["type"] == "tool_call"]
    tool_results = [e for e in events_list if e["type"] == "tool_result"]
    assert len(tool_calls) >= 1, "writer 应调用工具"
    assert tool_calls[0]["tool"] == "setting_query"
    assert len(tool_results) >= 1 and tool_results[0]["ok"] is True
    done = [e for e in events_list if e["type"] == "done"][-1]
    assert done["result"].get("saved") is True
    # 第二轮 LLM 调用产出成稿
    assert fake.call_count >= 2
