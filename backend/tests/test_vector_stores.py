"""I1 本地向量存储测试 — numpy 余弦 / JSON 持久化 / where 过滤 / 工厂接线"""

import pytest


def _vec(*dims: float) -> list[float]:
    return list(dims)


async def test_local_store_add_query_ranked(tmp_path):
    """余弦相似度排序 + where 过滤"""
    from app.core.knowledge.vector_stores import LocalVectorStore

    vs = LocalVectorStore(persist_dir=str(tmp_path), collection="c1")
    await vs.add(
        ["d1", "d2", "d3"],
        [_vec(1, 0, 0), _vec(0, 1, 0), _vec(0.9, 0.1, 0)],
        ["主角", "配角", "主角队友"],
        [{"doc_id": "d1", "category": "world"}, {"doc_id": "d2", "category": "character"}, {"doc_id": "d3", "category": "world"}],
    )
    # 查询与 d1 同向向量 → d1 最相似，d3 次之
    hits = await vs.query(_vec(1, 0, 0), top_k=3)
    assert [h["id"] for h in hits] == ["d1", "d3", "d2"]
    assert hits[0]["score"] > hits[1]["score"] > hits[2]["score"]

    # where 过滤
    world = await vs.query(_vec(1, 0, 0), top_k=5, where={"category": "world"})
    assert {h["id"] for h in world} == {"d1", "d3"}
    char = await vs.query(_vec(1, 0, 0), top_k=5, where={"category": "character"})
    assert {h["id"] for h in char} == {"d2"}


async def test_local_store_persists_across_instances(tmp_path):
    """JSON 持久化：新实例自动加载既有数据"""
    from app.core.knowledge.vector_stores import LocalVectorStore

    vs1 = LocalVectorStore(persist_dir=str(tmp_path), collection="persist")
    await vs1.add(["p1", "p2"], [_vec(1, 0), _vec(0, 1)], ["甲", "乙"], [{"doc_id": "p1"}, {"doc_id": "p2"}])
    assert await vs1.count() == 2

    vs2 = LocalVectorStore(persist_dir=str(tmp_path), collection="persist")
    assert await vs2.count() == 2, "新实例应加载磁盘数据"
    hits = await vs2.query(_vec(1, 0), top_k=1)
    assert hits[0]["id"] == "p1"


async def test_local_store_delete_persists(tmp_path):
    from app.core.knowledge.vector_stores import LocalVectorStore

    vs = LocalVectorStore(persist_dir=str(tmp_path), collection="del")
    await vs.add(["a", "b"], [_vec(1), _vec(2)], ["A", "B"], [{"doc_id": "a"}, {"doc_id": "b"}])
    await vs.delete(["a"])
    assert await vs.count() == 1
    vs2 = LocalVectorStore(persist_dir=str(tmp_path), collection="del")
    assert await vs2.count() == 1, "删除应落盘"


async def test_local_store_handles_empty(tmp_path):
    from app.core.knowledge.vector_stores import LocalVectorStore

    vs = LocalVectorStore(persist_dir=str(tmp_path), collection="empty")
    assert await vs.query(_vec(1, 2, 3), top_k=5) == []


def test_create_vector_store_local_backend(monkeypatch, tmp_path):
    """工厂接线：VECTOR_STORE_BACKEND=local → LocalVectorStore；mock → MockVectorStore"""
    from app.config import settings as app_settings
    from app.core.knowledge.vector_stores import (
        LocalVectorStore, MockVectorStore, create_vector_store,
    )

    monkeypatch.setattr(app_settings.vector_store, "backend", "local")
    monkeypatch.setattr(app_settings.vector_store, "persist_dir", str(tmp_path))
    assert isinstance(create_vector_store(), LocalVectorStore)

    monkeypatch.setattr(app_settings.vector_store, "backend", "mock")
    assert isinstance(create_vector_store(), MockVectorStore)
