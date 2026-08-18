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
