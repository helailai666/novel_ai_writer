"""LangGraph 图测试 — setting / chapter(含重写循环) / review(并行)

使用 Mock LLM（无网络无 Key）；通过 monkeypatch 控制评分以驱动重写分支。
"""

import json

import pytest

from app.core.llm.schemas import LLMRequest, LLMResponse
from app.core.llm.providers.mock import MockProvider


# ── 可控 Mock：可指定审核评分 ─────────────────────────────────────

class FakeScoreProvider(MockProvider):
    """Mock 变体：审核请求返回固定评分（用于驱动重写分支）"""

    score: int = 50

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        if req.response_format and req.response_format.get("type") == "json_object":
            return LLMResponse(
                content=json.dumps(
                    {"score": self.score, "summary": "测试", "issues": ["i"], "suggestions": ["s"], "highlights": ["h"]},
                    ensure_ascii=False,
                ),
                usage={"mock": True},
                is_mock=True,
            )
        return await super().acomplete(req)


@pytest.fixture
def mock_llm(monkeypatch):
    """替换 common.create 为 FakeScoreProvider（通过返回的 dict 控制评分）"""
    import app.agents.nodes.common as common

    ctrl = {"score": 82}

    def _create(*args, **kwargs):
        provider = FakeScoreProvider(model="mock")
        provider.score = ctrl["score"]
        return provider

    monkeypatch.setattr(common, "create", _create)
    return ctrl


# ── setting 图 ────────────────────────────────────────────────────

async def test_setting_graph_generates_and_persists(db, mock_llm):
    from app.agents.runner import get_runner

    state = {
        "graph": "setting", "project_id": db, "task": "生成世界观",
        "kind": "world", "name": "九州大陆", "category": "geography",
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    result = await get_runner().ainvoke("setting", state)
    assert result.get("content"), "设定图应产出内容"
    assert result.get("is_mock") is True

    # 持久化验证
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.world_setting import WorldSetting

    async with async_session_factory() as session:
        rows = (await session.execute(select(WorldSetting).where(WorldSetting.project_id == db))).scalars().all()
    assert len(rows) == 1 and rows[0].name == "九州大陆"


# ── chapter 图：重写循环 ──────────────────────────────────────────

async def test_chapter_graph_rewrite_loop(db, mock_llm):
    """低分审核 → 触发重写循环 → 最终持久化"""
    from app.agents.runner import get_runner

    # 先让评分 < 阈值以驱动重写
    mock_llm["score"] = 40

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
    assert "token" in types, "应有 token 流式事件"
    assert "checkpoint" in types, "应有 checkpoint 事件"
    write_starts = [e for e in events_list if e["type"] == "node_start" and e["node"] == "write_draft"]
    assert len(write_starts) == 2, f"低分应触发 1 次重写（共 2 次写作），实际 {len(write_starts)}"

    done = [e for e in events_list if e["type"] == "done"][-1]
    assert done["result"].get("saved") is True


# ── review 图：并行维度 ───────────────────────────────────────────

async def test_review_graph_parallel_dimensions(db, mock_llm):
    from app.agents.runner import get_runner

    state = {
        "graph": "review", "project_id": db, "content": "测试章节内容",
        "dimensions": ["consistency", "logic", "pacing"],
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    result = await get_runner().ainvoke("review", state)
    dims = result.get("dimension_scores") or {}
    assert set(dims.keys()) == {"consistency", "logic", "pacing"}, f"应有 3 个并行维度结果: {dims}"
    assert result.get("score") == 82
