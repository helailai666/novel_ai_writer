"""API 集成测试 — 锁定 AI 端点（mock 模式）与核心业务端点行为"""

import json

import pytest


@pytest.fixture
def client():
    """TestClient（mock 模式，临时 DB）"""
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as c:
        yield c


@pytest.fixture
def project(client):
    """通过 API 创建测试项目"""
    r = client.post("/api/projects/", json={"title": "API集成测试", "genre": "玄幻"})
    assert r.status_code == 201
    return r.json()["id"]


def test_project_crud(client, project):
    r = client.get(f"/api/projects/{project}")
    assert r.status_code == 200 and r.json()["title"] == "API集成测试"
    r = client.patch(f"/api/projects/{project}", json={"status": "writing"})
    assert r.status_code == 200 and r.json()["status"] == "writing"
    r = client.get("/api/projects/")
    assert any(p["id"] == project for p in r.json())


def test_ai_generate_world_endpoint(client, project):
    """设定图端点：生成 + 自动入库"""
    r = client.post(f"/api/projects/{project}/settings/ai/generate-world", json={"name": "九州", "category": "geography"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is True and len(body["content"]) > 0
    # 已入库
    ws = client.get(f"/api/projects/{project}/settings/world").json()
    assert len(ws) == 1 and ws[0]["name"] == "九州"


def test_chapter_generate_endpoint(client, project):
    """写作图端点：生成章节并保存"""
    r = client.post(
        f"/api/projects/{project}/writing/generate",
        json={"prompt": "第一章", "chapter_number": 1, "target_word_count": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is True and body["id"]
    # 续写与润色
    r = client.post(f"/api/projects/{project}/writing/continue", json={"chapter_id": body["id"], "direction": "遇敌"})
    assert r.status_code == 200
    r = client.post(f"/api/projects/{project}/writing/polish", json={"chapter_id": body["id"], "aspect": "prose"})
    assert r.status_code == 200


def test_chapter_stream_typed_events(client, project):
    """SSE 流式：类型化事件协议"""
    with client.stream(
        "POST", f"/api/projects/{project}/writing/generate-stream",
        json={"prompt": "第二章", "chapter_number": 2, "target_word_count": 100},
    ) as resp:
        assert resp.status_code == 200
        events = [json.loads(l[6:]) for l in resp.iter_lines() if l.startswith("data: ")]
    types = {e["type"] for e in events}
    assert {"node_start", "token", "review", "checkpoint", "done"} <= types
    done = [e for e in events if e["type"] == "done"][-1]
    assert done["result"].get("saved") is True


def test_review_endpoints(client, project):
    r = client.post("/api/review/consistency", json={"project_id": project, "content": "测试"})
    assert r.status_code == 200 and r.json()["score"] > 0
    r = client.post("/api/review/comprehensive", json={"project_id": project, "content": "测试"})
    assert r.status_code == 200 and r.json()["score"] > 0


def test_agents_run_endpoints(client, project):
    """chat 图路由 + 审核图并行"""
    r = client.post("/api/agents/run", json={"graph": "chat", "project_id": project, "task": "帮我写第一章", "prompt": "第一章", "chapter_number": 1})
    assert r.status_code == 200 and r.json().get("saved") is True
    r = client.post("/api/agents/run", json={"graph": "review", "project_id": project, "content": "x", "dimensions": ["logic", "prose"]})
    assert set(r.json()["dimension_scores"]) == {"logic", "prose"}
    r = client.get(f"/api/agents/runs?project_id={project}")
    assert len(r.json()) >= 2


def test_agent_runs_timeline_and_detail(client, project):
    """G4: 运行记录含摘要/时长，详情返回事件时间线"""
    r = client.post("/api/agents/run", json={
        "graph": "setting", "project_id": project, "task": "生成世界观",
        "kind": "world", "name": "九州", "category": "geography",
    })
    assert r.status_code == 200

    runs = client.get(f"/api/agents/runs?project_id={project}&graph=setting").json()
    assert runs, "应存在 setting 运行记录"
    run = runs[0]
    assert run["status"] == "completed"
    assert run["summary"], "列表应含运行摘要"
    assert run["duration_seconds"] >= 0
    # 列表视图不应携带完整事件（保持轻量）
    assert "events" not in run

    detail = client.get(f"/api/agents/runs/{run['id']}").json()
    assert detail["id"] == run["id"]
    assert any(e["type"] == "node_start" for e in detail["events"]), "详情应含节点事件"
    assert detail["total_tokens"] >= 0
    assert isinstance(detail["token_counts"], dict)
    # 404
    assert client.get("/api/agents/runs/nonexistent").status_code == 404


def test_agent_runs_delete_and_clear(client, project):
    """I4: 运行记录删除（单条 204/404 + 未限定 400 + 按项目清空）"""
    for task, name, cat in [("生成世界观", "跑一", "world"), ("生成角色", "跑二", "character")]:
        r = client.post("/api/agents/run", json={"graph": "setting", "project_id": project, "task": task, "name": name, "category": cat})
        assert r.status_code == 200

    runs = client.get(f"/api/agents/runs?project_id={project}").json()
    assert len(runs) == 2
    run_id = runs[0]["id"]

    # 删除单条
    assert client.delete(f"/api/agents/runs/{run_id}").status_code == 204
    assert client.get(f"/api/agents/runs/{run_id}").status_code == 404
    assert len(client.get(f"/api/agents/runs?project_id={project}").json()) == 1

    # 未限定范围 → 400（防误清全库）
    assert client.delete("/api/agents/runs").status_code == 400

    # 按项目清空
    r = client.delete(f"/api/agents/runs?project_id={project}")
    assert r.status_code == 200 and r.json()["deleted"] == 1
    assert client.get(f"/api/agents/runs?project_id={project}").json() == []

    # 不存在单条 → 404
    assert client.delete("/api/agents/runs/nonexistent").status_code == 404


def test_knowledge_and_memes_api(client, project):
    r = client.post("/api/knowledge/ingest", params={"title": "神兵", "content": "九天玄剑，剑身刻有九条龙纹。", "category": "item", "project_id": project})
    assert r.status_code == 200
    r = client.post(f"/api/knowledge/search?project_id={project}", json={"query": "玄剑"})
    assert any("神兵" in d["title"] for d in r.json()["docs"])
    r = client.post(f"/api/hot-memes?project_id={project}", json={"phrase": "绝了", "meaning": "非常厉害", "category": "吐槽"})
    assert r.status_code == 201
    assert len(client.get(f"/api/hot-memes/search?q=绝了&project_id={project}").json()) == 1


def test_tools_skills_providers_api(client):
    assert len(client.get("/api/tools").json()) == 10
    assert len(client.get("/api/skills").json()["skills"]) == 6
    providers = client.get("/api/model-providers").json()
    assert len(providers["providers"]) == 10
    r = client.post("/api/model-providers/test", json={"provider": "mock", "model": "mock"})
    assert r.json()["ok"] is True and r.json()["is_mock"] is True


def test_chat_history_endpoint_reconstructs_turns(client, project):
    """L 轮：GET /api/agents/chat/history 由 chat 运行重建 turns"""
    client.post("/api/agents/run", json={"graph": "chat", "project_id": project, "task": "写第一章"})
    client.post("/api/agents/run", json={"graph": "chat", "project_id": project, "task": "介绍一下这个世界的角色有哪些"})
    r = client.get(f"/api/agents/chat/history?project_id={project}")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == project
    turns = body["turns"]
    assert len(turns) == 4, f"2 次运行应重建 4 条 turns: {len(turns)}"
    contents = [t["content"] for t in turns]
    assert "写第一章" in contents and "介绍一下这个世界的角色有哪些" in contents
    intents = {t["intent"] for t in turns if t["role"] == "assistant"}
    assert "chapter" in intents and "qa" in intents, f"意图应含 chapter/qa: {intents}"
    for t in turns:
        if t["role"] == "user":
            assert t.get("intent") is None
        else:
            assert "sources" in t and "is_mock" in t


def test_export_json_full_backup(client, project):
    """L 轮：GET /api/projects/{id}/export?format=json 全量备份"""
    client.post(f"/api/projects/{project}/settings/characters", json={"name": "林玄", "role": "protagonist"})
    client.post(f"/api/projects/{project}/writing/chapters",
                json={"title": "第一章", "content": "正文内容……", "chapter_number": 1})
    r = client.get(f"/api/projects/{project}/export", params={"format": "json"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = json.loads(r.text)
    assert data["project"]["id"] == project
    assert any(ch["title"] == "第一章" for ch in data["chapters"]), data["chapters"]
    assert any(ch["name"] == "林玄" for ch in data["characters"]), data["characters"]
    assert set(data) >= {"volumes", "chapters", "characters", "items", "skills", "factions",
                         "locations", "outlines", "world_settings", "foreshadows", "knowledge_docs", "hot_memes"}


def test_timeline_and_foreshadow_management(client, project):
    """M 轮：时间线 AI 生成 + CRUD/PATCH；伏笔 CRUD + 状态流转"""
    # 时间线 AI 生成（mock 模式）
    r = client.post(f"/api/projects/{project}/settings/ai/generate-timeline",
                    json={"name": "魔潮降临", "category": "上古", "extra": ""})
    assert r.status_code == 200
    assert r.json()["is_mock"] is True and r.json()["content"]
    tl = client.get(f"/api/projects/{project}/settings/timelines").json()
    assert len(tl) == 1 and tl[0]["event"] == "魔潮降临" and tl[0]["era"] == "上古"
    # PATCH 时间线
    r = client.patch(f"/api/projects/{project}/settings/timelines/{tl[0]['id']}",
                     json={"event_date": "天启元年", "involved_characters": "云破天"})
    assert r.status_code == 200 and r.json()["event_date"] == "天启元年"

    # 伏笔 CRUD + 状态流转（planted → revealed）
    ch = client.post(f"/api/projects/{project}/writing/chapters",
                     json={"title": "第一章", "content": "内容", "chapter_number": 1}).json()
    f = client.post(f"/api/projects/{project}/settings/foreshadows",
                    json={"description": "玉佩发光", "plant_chapter_id": ch["id"], "status": "planted"}).json()
    assert f["status"] == "planted" and f["plant_chapter_id"] == ch["id"]
    r = client.patch(f"/api/projects/{project}/settings/foreshadows/{f['id']}",
                     json={"status": "revealed", "reveal_chapter_id": ch["id"]})
    assert r.status_code == 200 and r.json()["status"] == "revealed"

    # 删除
    assert client.delete(f"/api/projects/{project}/settings/timelines/{tl[0]['id']}").status_code == 204
    assert client.delete(f"/api/projects/{project}/settings/foreshadows/{f['id']}").status_code == 204


def test_runtime_config_endpoint(client):
    """J3: /api/runtime/config 返回脱敏有效配置"""
    r = client.get("/api/runtime/config")
    assert r.status_code == 200
    body = r.json()
    for group in ("llm", "search", "embedding", "vector_store", "mcp", "agent", "skills"):
        assert group in body, f"缺少配置分组: {group}"
    # 不允许出现名为 api_key 的键（has_api_key 是布尔标记，允许）
    keys = set()

    def _walk(d):
        for k, v in d.items():
            keys.add(k)
            if isinstance(v, dict):
                _walk(v)

    _walk(body)
    assert "api_key" not in keys, "运行时配置不应包含 api_key 字段"
    assert body["agent"]["llm_supervisor_cache"] is True
    assert body["vector_store"]["backend"] in {"chroma", "local", "mock"}


def test_mcp_servers_endpoint_shape(client):
    """J1: /api/mcp/servers 返回配置 + 实时池状态字段"""
    r = client.get("/api/mcp/servers")
    assert r.status_code == 200
    body = r.json()
    assert "servers" in body
    for s in body["servers"]:
        assert {"name", "transport", "enabled", "configured"} <= set(s)
        assert {"pool_size", "connect_timeout", "max_retries"} <= set(s["configured"])
        assert "status" in s
