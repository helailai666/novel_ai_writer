"""H 轮缓存测试 — supervisor 意图分类缓存（H1）+ 知识检索结果缓存（H3）

覆盖：命中免重复调用 / TTL 过期 / 开关关闭 / 写操作失效 / 返回值隔离。
"""

import asyncio
import json

import pytest

from app.config import settings as app_settings


@pytest.fixture(autouse=True)
def _clear_caches():
    """清空模块级缓存，避免测试间互相污染"""
    from app.agents.graphs import supervisor as sup
    from app.core.knowledge import retriever

    sup._classify_cache.clear()
    retriever._retrieve_cache.clear()
    yield
    sup._classify_cache.clear()
    retriever._retrieve_cache.clear()


# ── H1 supervisor 意图分类缓存 ─────────────────────────────────────

def _counting_classify_llm(counter: dict):
    """返回可配置 JSON 的分类 LLM，调用次数计入 counter"""
    from app.core.llm.schemas import LLMResponse

    class _LLM:
        response = {"intent": "setting", "kind": "character"}

        async def acomplete(self, req):
            counter["calls"] += 1
            return LLMResponse(
                content=json.dumps(self.response, ensure_ascii=False),
                usage={"mock": True}, is_mock=True,
            )

    return _LLM()


async def _classify_twice(task, monkeypatch, counter, second_task=None):
    """连续两次分类（第二次可用不同任务），返回两次结果"""
    from app.agents.graphs import supervisor as sup

    monkeypatch.setattr(sup, "create", lambda *a, **k: _counting_classify_llm(counter))
    first = await sup.classify_with_llm(task)
    second = await sup.classify_with_llm(second_task if second_task is not None else task)
    return first, second


async def test_supervisor_classify_cache_hit_skips_llm(monkeypatch):
    """相同任务二次分类命中缓存 → LLM 仅调用一次"""
    counter = {"calls": 0}
    first, second = await _classify_twice("帮我设计一个剑客角色", monkeypatch, counter)
    assert counter["calls"] == 1, "相同任务应命中缓存，不再调用 LLM"
    assert first == second == ("setting", {"kind": "character"})


async def test_supervisor_classify_cache_different_task_misses(monkeypatch):
    """不同任务不共享缓存 → 两次 LLM 调用"""
    counter = {"calls": 0}
    await _classify_twice("帮我设计一个剑客角色", monkeypatch, counter, second_task="写第一章正文")
    assert counter["calls"] == 2


async def test_supervisor_classify_cache_ttl_expiry(monkeypatch):
    """TTL 过期后再次分类 → 重新调用 LLM"""
    from app.agents.graphs import supervisor as sup

    # classify_with_llm 每次调用会用 settings 的 ttl 覆盖缓存实例 → 从配置注入短 TTL
    monkeypatch.setattr(app_settings.agent, "llm_supervisor_cache_ttl", 0.05)
    counter = {"calls": 0}
    monkeypatch.setattr(sup, "create", lambda *a, **k: _counting_classify_llm(counter))
    task = "设计一个势力叫天机阁"
    await sup.classify_with_llm(task)
    await asyncio.sleep(0.06)
    await sup.classify_with_llm(task)
    assert counter["calls"] == 2, "TTL 过期后应重新调用 LLM"


async def test_supervisor_classify_cache_disabled(monkeypatch):
    """开关关闭 → 相同任务每次都调用 LLM"""
    monkeypatch.setattr(app_settings.agent, "llm_supervisor_cache", False)
    counter = {"calls": 0}
    await _classify_twice("设计一个道具", monkeypatch, counter)
    assert counter["calls"] == 2


# ── H3 知识检索结果缓存 ────────────────────────────────────────────

async def _mk_counting_retriever(monkeypatch):
    """Retriever + 计数桩方法（替代真实 DB/向量查询）"""
    from app.core.knowledge.retriever import Retriever

    rt = Retriever()
    counts = {"docs": 0, "memes": 0, "vector": 0}

    async def _fake_docs(self, query, project_id, categories):
        counts["docs"] += 1
        return [{"id": "d1", "title": "修仙体系", "category": "world", "content": "境界划分", "tags": "", "project_id": project_id, "score": 0.9}]

    async def _fake_memes(self, query, project_id):
        counts["memes"] += 1
        return [{"id": "m1", "phrase": "凡人流", "meaning": "", "usage_example": "", "category": "", "tags": "", "popularity": 1}]

    async def _fake_vector(self, query, project_id, categories, top_k):
        counts["vector"] += 1
        return []

    monkeypatch.setattr(Retriever, "_keyword_docs", _fake_docs)
    monkeypatch.setattr(Retriever, "_keyword_memes", _fake_memes)
    monkeypatch.setattr(Retriever, "_vector_docs", _fake_vector)
    return rt, counts


async def test_retriever_cache_hit_skips_requery(monkeypatch):
    """相同查询二次检索命中缓存 → 底层三路查询都不再执行"""
    from app.core.knowledge.retriever import Retriever

    rt, counts = await _mk_counting_retriever(monkeypatch)
    r1 = await rt.retrieve("境界划分", top_k=3)
    r2 = await rt.retrieve("境界划分", top_k=3)
    assert counts == {"docs": 1, "memes": 1, "vector": 1}, "缓存命中不应重查"
    assert r1 == r2
    assert r2["docs"][0]["id"] == "d1"


async def test_retriever_cache_key_distinguishes_args(monkeypatch):
    """不同参数（top_k/categories/query）不共享缓存"""
    rt, counts = await _mk_counting_retriever(monkeypatch)
    await rt.retrieve("境界划分", top_k=3)
    await rt.retrieve("境界划分", top_k=5)
    await rt.retrieve("境界划分", top_k=3, categories=["world"])
    assert counts["docs"] == 3, "参数不同应视为不同缓存键"


async def test_retriever_cache_invalidated_on_write(monkeypatch):
    """写操作失效后重新检索 → 底层重查"""
    from app.core.knowledge.retriever import Retriever, invalidate_knowledge_cache

    rt, counts = await _mk_counting_retriever(monkeypatch)
    await rt.retrieve("境界划分")
    invalidate_knowledge_cache()
    await rt.retrieve("境界划分")
    assert counts["docs"] == 2, "失效后应重新检索"


async def test_retriever_cache_disabled(monkeypatch):
    """开关关闭 → 每次检索都重查"""
    monkeypatch.setattr(app_settings.agent, "knowledge_cache", False)
    rt, counts = await _mk_counting_retriever(monkeypatch)
    await rt.retrieve("境界划分")
    await rt.retrieve("境界划分")
    assert counts["docs"] == 2


async def test_retriever_cache_mutation_isolation(monkeypatch):
    """调用方修改返回结果不污染缓存（深拷贝返回）"""
    rt, _ = await _mk_counting_retriever(monkeypatch)
    r1 = await rt.retrieve("境界划分")
    r1["docs"][0]["title"] = "被篡改"
    r1["memes"].append({"id": "x"})
    r2 = await rt.retrieve("境界划分")
    assert r2["docs"][0]["title"] == "修仙体系", "缓存值应隔离调用方修改"
    assert len(r2["memes"]) == 1


# ── J1 缓存可观测性（计数 + 端点）─────────────────────────────────

def test_ttlcache_stats_counting():
    """命中/未命中/淘汰计数正确"""
    from app.core.cache import TTLCache

    c = TTLCache(ttl=60, max_entries=2, copy_on_get=False)
    assert c.get("a") is None
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)  # 超容量 → 淘汰 a
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3

    stats = c.stats()
    assert stats["hits"] == 2, stats
    assert stats["misses"] == 2, stats  # 首次 miss + 淘汰后 miss
    assert stats["evictions"] == 1, stats
    assert stats["size"] == 2 and stats["max_entries"] == 2

    # 过期 → miss + eviction
    c2 = TTLCache(ttl=0.05, copy_on_get=False)
    c2.set("x", 1)
    import time

    time.sleep(0.06)
    assert c2.get("x") is None
    s2 = c2.stats()
    assert s2["misses"] == 1 and s2["evictions"] == 1

    # 清空计数
    c.reset_stats()
    assert c.stats()["hits"] == 0 and c.stats()["misses"] == 0


@pytest.fixture
def client():
    """TestClient（mock 模式，临时 DB）"""
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as c:
        yield c


def test_cache_api_stats_and_clear(client):
    """GET /api/cache/stats 结构 + POST /api/cache/clear 清空"""
    from app.agents.graphs import supervisor as sup
    from app.core.knowledge import retriever as rtr

    # 制造缓存数据与命中
    sup._classify_cache.set("t1", ("setting", {}))
    assert sup._classify_cache.get("t1") == ("setting", {})
    rtr._retrieve_cache.set("q1", {"docs": []})
    assert rtr._retrieve_cache.get("q1") == {"docs": []}

    r = client.get("/api/cache/stats")
    assert r.status_code == 200
    body = r.json()
    assert {"classify", "retrieve"} <= set(body)
    assert body["classify"]["hits"] >= 1 and body["classify"]["size"] == 1
    assert body["retrieve"]["hits"] >= 1 and body["retrieve"]["size"] == 1
    assert "api_key" not in str(body), "统计响应不应含密钥"

    r = client.post("/api/cache/clear")
    assert r.status_code == 200 and r.json()["cleared"] is True
    body = client.get("/api/cache/stats").json()
    assert body["classify"]["size"] == 0 and body["retrieve"]["size"] == 0
    assert body["classify"]["hits"] == 0 and body["retrieve"]["hits"] == 0
