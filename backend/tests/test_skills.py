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


async def test_project_level_skills_injected(monkeypatch, db):
    """项目配置技能（无请求级 skills）应自动注入写作图"""
    import app.agents.nodes.common as common

    llm = RecordingLLM(model="mock")

    def _create(*args, **kwargs):
        return llm

    monkeypatch.setattr(common, "create", _create)

    # 给项目设置技能
    from app.database import async_session_factory
    from app.services.project_service import ProjectService

    async with async_session_factory() as session:
        await ProjectService.update(session, db, {"skill_packs": "webnovel-standards"})
        await session.commit()

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
    await get_runner().ainvoke("chapter", state)
    assert "黄金三章" in llm.last_system, "项目级技能应注入 system prompt"


# ── G2 技能合并策略 ───────────────────────────────────────────────

def test_merge_skills_strategy():
    from app.agents.nodes.common import merge_skills

    # 未指定 → 仅项目级
    assert merge_skills(None, ["a", "b"]) == ["a", "b"]
    assert merge_skills(None, None) == []
    # 显式空列表 → 禁用全部（覆盖项目级）
    assert merge_skills([], ["a"]) == []
    # 并集去重保序：请求级优先
    assert merge_skills(["b", "a"], ["a", "c"]) == ["b", "a", "c"]
    assert merge_skills(["a"], None) == ["a"]


async def test_request_and_project_skills_merged(monkeypatch, db):
    """请求级 + 项目级技能并集注入（去重），两处技能片段都应出现"""
    import app.agents.nodes.common as common

    llm = RecordingLLM(model="mock")

    def _create(*args, **kwargs):
        return llm

    monkeypatch.setattr(common, "create", _create)

    from app.database import async_session_factory
    from app.services.project_service import ProjectService

    async with async_session_factory() as session:
        await ProjectService.update(session, db, {"skill_packs": "webnovel-standards"})
        await session.commit()

    from app.agents.runner import get_runner

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate",
        "prompt": "第一章", "style": "narrative", "target_word_count": 100,
        "chapter_number": 1, "volume_id": None,
        "skills": ["pacing-control", "webnovel-standards"],
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    await get_runner().ainvoke("chapter", state)
    assert "黄金三章" in llm.last_system, "项目级技能应注入（并集）"
    assert "张弛交替" in llm.last_system, "请求级技能应注入（并集）"


async def test_explicit_empty_skills_disables_project(monkeypatch, db):
    """请求显式传 [] 时禁用项目级技能"""
    import app.agents.nodes.common as common

    llm = RecordingLLM(model="mock")

    def _create(*args, **kwargs):
        return llm

    monkeypatch.setattr(common, "create", _create)

    from app.database import async_session_factory
    from app.services.project_service import ProjectService

    async with async_session_factory() as session:
        await ProjectService.update(session, db, {"skill_packs": "webnovel-standards"})
        await session.commit()

    from app.agents.runner import get_runner

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate",
        "prompt": "第一章", "style": "narrative", "target_word_count": 100,
        "chapter_number": 1, "volume_id": None,
        "skills": [],  # 显式禁用
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    await get_runner().ainvoke("chapter", state)
    assert "黄金三章" not in llm.last_system, "显式 [] 应覆盖项目级技能"


# ── G1 supervisor LLM 意图分类 ────────────────────────────────────

class ClassifyLLM(MockProvider):
    """模拟 LLM 意图分类器（返回可配置 JSON）"""

    response = {"intent": "setting", "kind": "character"}

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        if req.response_format and req.response_format.get("type") == "json_object":
            return LLMResponse(
                content=json.dumps(self.response, ensure_ascii=False),
                usage={"mock": True}, is_mock=True,
            )
        return await super().acomplete(req)


def _chat_state(task: str, project_id, **extra) -> dict:
    state = {
        "graph": "chat", "project_id": project_id, "task": task,
        "settings_snapshot": {}, "knowledge": [], "draft": None,
        "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75,
        "final_output": {}, "events": [], "run_id": None,
    }
    state.update(extra)
    return state


async def _collect_chat_events(state, monkeypatch, classifier=None):
    """跑 chat 图并收集全部事件（可选替换 supervisor 的 LLM）"""
    import app.agents.graphs.supervisor as sup

    if classifier is not None:
        monkeypatch.setattr(sup, "create", lambda *a, **k: classifier)
    from app.agents.runner import get_runner

    events = []
    async for ev in get_runner().astream("chat", state):
        events.append(ev)
    return events


async def test_supervisor_llm_classification_routes_setting(monkeypatch, db):
    """LLM 分类生效：无关键词任务（关键词会误判为 chapter）→ setting/character"""
    llm = ClassifyLLM(model="mock")
    llm.response = {"intent": "setting", "kind": "character"}
    events = await _collect_chat_events(
        _chat_state("我想要一个冷峻的剑客形象", db, name="剑客甲"), monkeypatch, llm
    )
    route = [e for e in events if e["type"] == "route"][0]
    assert route["intent"] == "setting", f"应走 LLM 分类到 setting: {route}"
    assert route["method"] == "llm"
    # kind 补丁生效：角色应已入库
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.character import Character

    async with async_session_factory() as session:
        rows = (await session.execute(select(Character).where(Character.project_id == db))).scalars().all()
    assert any(r.name == "剑客甲" for r in rows), "kind=character 应路由到角色生成并入库"


async def test_supervisor_llm_fallback_keyword_on_invalid(monkeypatch, db):
    """LLM 返回非法 intent → 回退关键词"""
    llm = ClassifyLLM(model="mock")
    llm.response = {"intent": "hiking"}
    events = await _collect_chat_events(_chat_state("写第一章", db), monkeypatch, llm)
    route = [e for e in events if e["type"] == "route"][0]
    assert route["intent"] == "chapter" and route["method"] == "keyword"


async def test_supervisor_keyword_when_llm_disabled(monkeypatch, db):
    """开关 AGENT_LLM_SUPERVISOR=False → 纯关键词分类"""
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings.agent, "llm_supervisor", False)
    llm = ClassifyLLM(model="mock")
    llm.response = {"intent": "setting", "kind": "character"}
    events = await _collect_chat_events(_chat_state("写第一章", db), monkeypatch, llm)
    route = [e for e in events if e["type"] == "route"][0]
    assert route["intent"] == "chapter" and route["method"] == "keyword"
