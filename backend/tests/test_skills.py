"""Skills 测试 — 加载 / 注入 / supervisor 对话路由"""

import json

import pytest

from app.core.llm.schemas import LLMRequest, LLMResponse
from app.core.llm.providers.mock import MockProvider


def test_skill_registry_loads_builtin():
    from app.core.skills import get_registry

    names = get_registry().list_names()
    for expect in ("webnovel-standards", "character-arc", "foreshadow-manager", "pacing-control", "prose-polish", "genre-xuanhuan"):
        assert expect in names, f"内置技能缺失: {expect}"
    assert get_registry().has("webnovel-standards")
    assert not get_registry().has("nonexistent-skill")


def test_skill_apply_returns_injection():
    from app.core.skills import get_runner

    injected = get_runner().apply(["webnovel-standards", "genre-xuanhuan"])
    assert "黄金三章" in injected["prompt"]
    assert "境界体系" in injected["prompt"]
    # genre-xuanhuan 声明了工具白名单
    assert "world_setting_lookup" in injected["tools"]


class RecordingLLM(MockProvider):
    """记录收到的 system 提示词"""

    last_system = ""

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        self.last_system = next((m.content for m in req.messages if m.role == "system"), "")
        return await super().acomplete(req)


async def test_chapter_graph_skill_injection(monkeypatch, db):
    """写作图启用技能后，system prompt 应包含技能片段"""
    import app.agents.nodes.common as common

    llm = RecordingLLM(model="mock")

    def _create(*args, **kwargs):
        return llm

    monkeypatch.setattr(common, "create", _create)

    from app.agents.runner import get_runner

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate",
        "prompt": "第一章", "style": "narrative", "target_word_count": 200,
        "chapter_number": 1, "volume_id": None,
        "skills": ["webnovel-standards", "pacing-control"],
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    await get_runner().ainvoke("chapter", state)
    assert "黄金三章" in llm.last_system, "技能片段应注入 system prompt"
    assert "张弛交替" in llm.last_system


# ── supervisor 对话路由 ──────────────────────────────────────────

@pytest.mark.parametrize(
    "task,expect_graph",
    [
        ("帮我生成世界观设定", "setting"),
        ("设计一个角色叫林玄", "setting"),
        ("写第一章正文", "chapter"),
        ("审核刚才的章节", "review"),
        ("检查一下设定一致性", "review"),
    ],
)
def test_supervisor_classify(task, expect_graph):
    from app.agents.graphs.supervisor import classify

    intent, _ = classify(task)
    assert intent == expect_graph, f"任务 '{task}' 应路由到 {expect_graph}"


async def test_supervisor_graph_routes_setting(monkeypatch, db):
    """chat 图：'生成世界观设定' → setting 子图 → 产出并保存"""
    import app.agents.nodes.common as common

    def _create(*args, **kwargs):
        return MockProvider(model="mock")

    monkeypatch.setattr(common, "create", _create)

    from app.agents.runner import get_runner

    state = {
        "graph": "chat", "project_id": db, "task": "帮我生成世界观设定 九州大陆",
        "name": "九州大陆", "category": "geography",
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    result = await get_runner().ainvoke("chat", state)
    assert result.get("content"), "chat 图应产出世界观内容"
    assert result.get("is_mock") is True
