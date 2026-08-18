"""Skills 测试 — 加载 / 注入 / supervisor 对话路由 / 技能包管理"""

import json

import pytest

from app.core.llm.schemas import LLMRequest, LLMResponse
from app.core.llm.providers.mock import MockProvider


@pytest.fixture
def client():
    """TestClient（mock 模式，临时 DB）"""
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as c:
        yield c


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


# ── L 轮 多轮对话上下文 ─────────────────────────────────────────

async def test_chapter_history_injection(recording_llm, db):
    """L 轮：写作图把对话历史注入用户消息（continue 纯流式路径）"""
    from app.agents.nodes.chapter_nodes import write_draft

    result = await write_draft({
        "project_id": db, "task": "接着往下写", "mode": "continue",
        "content": "前文：主角踏入宗门。",
        "history": [{"role": "user", "content": "帮我写第一章"}],
    })
    assert result.get("draft"), "应产出草稿"
    assert "【对话历史" in recording_llm.last_user, recording_llm.last_user[:200]
    assert "帮我写第一章" in recording_llm.last_user
    assert "前文：主角踏入宗门" in recording_llm.last_user


# ── K 轮 supervisor qa 意图 ───────────────────────────────────────

def test_supervisor_timeline_keyword():
    """M 轮：时间线关键词 → setting + kind=timeline"""
    from app.agents.graphs.supervisor import classify

    intent, patch = classify("帮我生成一条时间线事件")
    assert intent == "setting" and patch["kind"] == "timeline", (intent, patch)
    intent, patch = classify("补充一条纪事：宗门大比")
    assert intent == "setting" and patch["kind"] == "timeline"


def test_supervisor_qa_keyword_fallback():
    """知识问答关键词回退：明确提问词 → qa；不误伤写作/设定意图"""
    from app.agents.graphs.supervisor import classify

    assert classify("介绍一下这个世界的角色有哪些")[0] == "qa"
    assert classify("修仙境界体系是什么")[0] == "qa"
    assert classify("为什么主角不能修仙")[0] == "qa"
    # 不误伤
    assert classify("写第一章正文")[0] == "chapter"
    assert classify("设计一个角色叫林玄")[0] == "setting"
    assert classify("帮我生成世界观设定")[0] == "setting"


async def test_supervisor_llm_classification_routes_qa(monkeypatch, db):
    """LLM 分类 → qa：chat 图路由到知识问答子图并产出带来源的回答"""
    llm = ClassifyLLM(model="mock")
    llm.response = {"intent": "qa", "kind": None}
    events = await _collect_chat_events(_chat_state("这个世界的修仙境界怎么划分", db), monkeypatch, llm)
    route = [e for e in events if e["type"] == "route"][0]
    assert route["intent"] == "qa" and route["method"] == "llm", f"应走 LLM 分类到 qa: {route}"
    done = [e for e in events if e["type"] == "done"][-1]
    result = done["result"]
    assert result.get("qa") is True, "qa 图应产出 qa=True 的 final_output"
    assert result.get("content"), "qa 图应产出回答内容"


# ── H4 技能包管理 ──────────────────────────────────────────────────

def test_skill_manager_create_update_toggle_delete(tmp_path):
    """SkillManager 文件 CRUD：创建→更新→禁用→启用→删除"""
    from app.core.skills import SkillRegistry
    from app.core.skills.manager import SkillError, SkillManager

    mgr = SkillManager(dirs=[str(tmp_path)])
    skill = mgr.create({
        "name": "my-skill", "description": "测试技能", "prompt": "正文片段",
        "tools": ["web_search"], "knowledge_refs": ["world"],
    })
    assert skill.name == "my-skill" and skill.prompt == "正文片段"
    assert skill.tools == ["web_search"] and skill.knowledge_refs == ["world"]
    assert (tmp_path / "my-skill" / "SKILL.md").exists()

    # 更新 prompt + 禁用
    skill = mgr.update("my-skill", {"prompt": "新正文", "enabled": False})
    assert skill.prompt == "新正文" and skill.enabled is False

    # 独立注册表能看到 frontmatter enabled 状态
    reg = SkillRegistry(dirs=[str(tmp_path)])
    assert "my-skill" not in reg.list_names(), "禁用技能不应出现在可用列表"

    # 重新启用
    skill = mgr.set_enabled("my-skill", True)
    assert skill.enabled is True

    # 删除
    mgr.delete("my-skill")
    assert not (tmp_path / "my-skill").exists()
    with pytest.raises(SkillError):
        mgr.update("my-skill", {"prompt": "x"})


def test_skill_manager_name_validation(tmp_path):
    """非法技能名拒绝（路径穿越/中文/空/超长）"""
    from app.core.skills.manager import SkillError, SkillManager

    mgr = SkillManager(dirs=[str(tmp_path)])
    for bad in ("../evil", "有中文", "", "a" * 65):
        with pytest.raises(SkillError):
            mgr.create({"name": bad, "prompt": "x"})


def test_skill_manager_create_duplicate_raises(tmp_path):
    from app.core.skills.manager import SkillError, SkillManager

    mgr = SkillManager(dirs=[str(tmp_path)])
    mgr.create({"name": "dup", "prompt": "x"})
    with pytest.raises(SkillError):
        mgr.create({"name": "dup", "prompt": "y"})


def test_skills_crud_api(client, tmp_path, monkeypatch):
    """Skills API CRUD：创建/列表/详情/更新/404/非法名 400/删除"""
    from app.core.skills import SkillRegistry
    from app.core.skills.manager import SkillManager
    import app.api.skills as skills_api

    reg = SkillRegistry(dirs=[str(tmp_path)])
    mgr = SkillManager(dirs=[str(tmp_path)], registry=reg)
    monkeypatch.setattr(skills_api, "get_registry", lambda: reg)
    monkeypatch.setattr(skills_api, "get_manager", lambda: mgr)

    # 创建
    r = client.post("/api/skills", json={"name": "api-skill", "description": "d", "prompt": "p", "tools": ["web_search"]})
    assert r.status_code == 201
    assert r.json()["name"] == "api-skill" and r.json()["prompt"] == "p"

    # 列表可见
    r = client.get("/api/skills")
    assert any(s["name"] == "api-skill" for s in r.json()["skills"])

    # 详情
    r = client.get("/api/skills/api-skill")
    assert r.status_code == 200 and r.json()["description"] == "d"

    # 更新 prompt + 禁用
    r = client.put("/api/skills/api-skill", json={"prompt": "p2", "enabled": False})
    assert r.status_code == 200
    assert r.json()["prompt"] == "p2" and r.json()["enabled"] is False

    # 404：不存在的技能
    assert client.get("/api/skills/no-such").status_code == 404
    assert client.put("/api/skills/no-such", json={"prompt": "x"}).status_code == 404
    assert client.delete("/api/skills/no-such").status_code == 404

    # 400：非法技能名
    assert client.post("/api/skills", json={"name": "坏名字"}).status_code == 400

    # 删除
    assert client.delete("/api/skills/api-skill").status_code == 200
    assert client.get("/api/skills/api-skill").status_code == 404
