"""知识库测试 — 切片 / 摄取+检索 / 热梗 / API / 写作图注入"""

import pytest

from app.core.knowledge.indexer import chunk_text


def test_chunk_text():
    text = "\n".join(f"段落{i}：这是第{i}段的测试内容，用于验证切片逻辑。" for i in range(30))
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) > 1, "长文本应切成多片"
    assert all(len(c) <= 140 for c in chunks)


async def test_knowledge_ingest_and_search(db):
    from app.database import async_session_factory
    from app.services.knowledge_service import KnowledgeService

    async with async_session_factory() as session:
        await KnowledgeService.ingest_text(
            session, "唐朝官制", "唐朝三省六部制：中书省决策、门下省审核、尚书省执行。六部为吏户礼兵刑工。",
            category="history", tags="历史,官制", project_id=db,
        )
        await KnowledgeService.ingest_text(
            session, "修仙境界", "练气→筑基→金丹→元婴→化神，每层分为初期、中期、后期。",
            category="worldview", tags="修仙,力量体系", project_id=db,
        )
        # 全局知识
        await KnowledgeService.ingest_text(session, "通用写作技巧", "黄金三章：第一章抛出冲突与悬念。", category="general")

    result = await KnowledgeService.search("三省六部", db, top_k=5)
    docs = result.get("docs") or []
    assert any("唐朝官制" in d["title"] for d in docs), "关键词检索应命中《唐朝官制》"

    result2 = await KnowledgeService.search("修仙 金丹", db, top_k=5)
    assert any("修仙境界" in d["title"] for d in (result2.get("docs") or []))


async def test_retriever_accepts_string_categories(db):
    """真实 LLM 常把单值数组参数传成字符串（"worldview"）→ 不应抛错"""
    from app.database import async_session_factory
    from app.services.knowledge_service import KnowledgeService

    async with async_session_factory() as session:
        await KnowledgeService.ingest_text(
            session, "修仙境界", "练气→筑基→金丹→元婴→化神。", category="worldview", project_id=db,
        )

    # 字符串 categories（LLM 工具调用的常见形态）
    result = await KnowledgeService.search("金丹", db, top_k=5, categories="worldview")
    assert any("修仙境界" in d["title"] for d in (result.get("docs") or []))
    # 列表 categories 仍正常
    result2 = await KnowledgeService.search("金丹", db, top_k=5, categories=["worldview"])
    assert any("修仙境界" in d["title"] for d in (result2.get("docs") or []))


async def test_hot_meme_crud_and_search(db):
    from app.database import async_session_factory
    from app.services.knowledge_service import KnowledgeService

    async with async_session_factory() as session:
        await KnowledgeService.create_meme(
            session, {"phrase": "破防了", "meaning": "心理防线被击穿", "usage_example": "他看到反派抢走女主时直接破防了", "category": "吐槽"},
            project_id=db,
        )
        rows = await KnowledgeService.search_memes(session, "破防", db)
        assert len(rows) == 1 and rows[0]["phrase"] == "破防了"
        meme_id = rows[0]["id"]
        await KnowledgeService.delete_meme(session, meme_id)
        rows2 = await KnowledgeService.search_memes(session, "破防", db)
        assert len(rows2) == 0


async def test_knowledge_api_e2e(db):
    """知识库 API 全链路：摄取 → 检索 → 热梗 → 删除"""
    from fastapi.testclient import TestClient

    import app.main as m

    with TestClient(m.app) as client:
        # 文档摄取
        r = client.post("/api/knowledge/ingest", params={
            "title": "明朝火器", "content": "明代神机营装备火铳、火炮，是世界最早成建制火器部队之一。",
            "category": "history", "tags": "历史,火器", "project_id": db,
        })
        assert r.status_code == 200
        doc_id = r.json()["id"]

        # 检索
        r = client.post(f"/api/knowledge/search?project_id={db}", json={"query": "神机营", "top_k": 5})
        assert r.status_code == 200
        assert any("明朝火器" in d["title"] for d in r.json()["docs"])

        # 列表/详情/删除
        assert client.get(f"/api/knowledge?project_id={db}").status_code == 200
        assert client.get(f"/api/knowledge/{doc_id}").status_code == 200
        assert client.delete(f"/api/knowledge/{doc_id}").status_code == 204

        # 热梗
        r = client.post(f"/api/hot-memes?project_id={db}", json={"phrase": "绷不住了", "meaning": "忍不住笑", "usage_example": "这剧情我绷不住了", "category": "搞笑"})
        assert r.status_code == 201
        r = client.get(f"/api/hot-memes/search?q=绷不住&project_id={db}")
        assert len(r.json()) == 1


async def test_chapter_graph_knowledge_injection(db, mock_llm):
    """章节写作图 retrieve_context 应注入知识库内容"""
    from app.database import async_session_factory
    from app.services.knowledge_service import KnowledgeService
    from app.agents.nodes.chapter_nodes import retrieve_context

    async with async_session_factory() as session:
        await KnowledgeService.ingest_text(
            session, "宗门设定", "青云宗位于青云山，宗门大殿有九根盘龙柱。", category="worldview", project_id=db,
        )

    state = {
        "graph": "chapter", "project_id": db, "mode": "generate", "task": "写主角加入青云宗的第一章",
        "prompt": "主角加入青云宗", "settings_snapshot": {}, "knowledge": [],
        "draft": None, "review": {}, "reviews": [], "revision_round": 0,
        "max_revisions": 2, "review_threshold": 75, "final_output": {}, "events": [], "run_id": None,
    }
    result = await retrieve_context(state)
    snapshot = result["settings_snapshot"]
    knowledge = result["knowledge"]
    assert any("宗门设定" in str(d.get("title", "")) for d in (snapshot.get("knowledge") or knowledge)), "知识库内容应注入上下文"
