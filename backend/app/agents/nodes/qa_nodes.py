"""QA 图节点 — 知识问答（K 轮）

retrieve_qa_context: 知识库混合检索（文档+热梗）；无命中时 web 搜索兜底，
汇总为 sources（type: doc/meme/web）。
answer_qa: LLM 流式作答（token 事件），附来源引用，资料不足如实说明。
"""

import logging

from app.agents import events
from app.agents.nodes.common import enhance_system, is_mock_provider, messages, resolve_llm
from app.agents.state import NovelState
from app.core.llm import LLMRequest

logger = logging.getLogger(__name__)

QA_SYSTEM = """你是小说创作平台的知识问答助手。
基于提供的资料回答用户关于作品设定/知识库的问题：
- 优先引用资料回答，保持与作品设定一致
- 资料不足时明确说明"资料中未找到相关内容"，可基于常识简要补充并标注
- 若资料之间相互冲突，指出冲突点供用户核实
- 回答使用中文，简洁有条理"""


async def retrieve_qa_context(state: NovelState) -> dict:
    """检索资料：知识库（文档+热梗）优先，无命中走 web 搜索兜底"""
    node = "retrieve_qa_context"
    evs = [events.node_start(node)]
    task = (state.get("task") or "").strip()
    docs, memes, web = [], [], []
    try:
        from app.services.knowledge_service import KnowledgeService

        kb = await KnowledgeService.search(task, state.get("project_id"), top_k=6, include_memes=True)
        docs = kb.get("docs") or []
        memes = kb.get("memes") or []
        if not docs and not memes:
            try:
                from app.services.search_service import SearchService

                web = await SearchService.search_web(task, max_results=4, use_cache=True)
            except Exception as e:
                logger.debug(f"QA web 兜底搜索失败: {e}")
    except Exception as e:
        logger.warning(f"QA 知识检索失败: {e}")

    sources: list[dict] = []
    for d in docs:
        sources.append({
            "type": "doc", "title": d.get("title", ""), "category": d.get("category", ""),
            "content": (d.get("content") or "")[:300],
        })
    for m in memes:
        sources.append({
            "type": "meme", "title": m.get("phrase", ""), "category": m.get("category", ""),
            "content": (m.get("meaning") or "")[:200],
        })
    for w in web:
        sources.append({
            "type": "web", "title": w.get("title", ""), "category": "web",
            "content": (w.get("snippet") or "")[:300], "url": w.get("url", ""),
        })

    evs.append({"type": "retrieve", "hits": len(sources), "source_types": sorted({s["type"] for s in sources})})
    evs.append(events.node_end(node))
    return {"knowledge": docs + memes, "sources": sources, "events": evs}


async def answer_qa(state: NovelState) -> dict:
    """基于资料流式作答（token 事件），产出 final_output{content, sources}"""
    node = "answer_qa"
    llm = resolve_llm(state)
    evs = [events.node_start(node)]
    task = (state.get("task") or "").strip()
    sources = state.get("sources") or []
    if sources:
        lines = ["【检索到的资料】"]
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. [{s['type']}] {s.get('title', '')}: {(s.get('content') or '')[:400]}")
        context_text = "\n".join(lines)
    else:
        context_text = "（知识库与网络均未检索到相关资料）"
    user_msg = f"{context_text}\n\n【用户问题】\n{task}"
    try:
        system = enhance_system(state, QA_SYSTEM)
        full = ""
        mock = is_mock_provider(llm)
        async for chunk in llm.astream(LLMRequest(messages=messages(system, user_msg))):
            if chunk:
                full += chunk
                evs.append(events.token(chunk))
        content = full.strip()
        evs.append(events.node_end(node))
        return {
            "final_output": {"content": content, "is_mock": mock, "sources": sources, "qa": True},
            "events": evs,
        }
    except Exception as e:
        logger.error(f"answer_qa failed: {e}")
        return {
            "final_output": {"content": "", "is_mock": True, "error": str(e)},
            "events": evs + [events.error(str(e))],
        }
