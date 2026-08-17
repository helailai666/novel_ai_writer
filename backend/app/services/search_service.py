"""搜索服务 — 全文检索 + Tavily 网络搜索 + 缓存"""

import os
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.project import Project
from app.models.character import Character
from app.models.chapter import Chapter

logger = logging.getLogger(__name__)


class SearchService:
    """跨模块搜索服务：本地全文搜索 + 网络搜索"""

    # 缓存 TTL（秒）
    _CACHE_TTL = 3600
    _cache: dict[str, tuple[float, list[dict]]] = {}

    # ── 本地搜索 ──────────────────────────────────────────────────

    @staticmethod
    async def search_projects(db: AsyncSession, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """在项目标题和简介中搜索"""
        stmt = (
            select(Project)
            .where(
                or_(
                    Project.title.ilike(f"%{query}%"),
                    Project.synopsis.ilike(f"%{query}%"),
                )
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        projects = result.scalars().all()
        return [
            {"id": p.id, "title": p.title, "genre": p.genre, "status": p.status}
            for p in projects
        ]

    @staticmethod
    async def search_characters(db: AsyncSession, project_id: str, query: str) -> List[Dict[str, Any]]:
        """在项目角色中搜索"""
        stmt = (
            select(Character)
            .where(
                Character.project_id == project_id,
                or_(
                    Character.name.ilike(f"%{query}%"),
                    Character.personality.ilike(f"%{query}%"),
                    Character.background.ilike(f"%{query}%"),
                ),
            )
        )
        result = await db.execute(stmt)
        chars = result.scalars().all()
        return [{"id": c.id, "name": c.name, "role": c.role} for c in chars]

    @staticmethod
    async def search_chapters(db: AsyncSession, project_id: str, query: str) -> List[Dict[str, Any]]:
        """在章节标题和内容中搜索"""
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                or_(
                    Chapter.title.ilike(f"%{query}%"),
                    Chapter.content.ilike(f"%{query}%"),
                ),
            )
        )
        result = await db.execute(stmt)
        chapters = result.scalars().all()
        return [
            {"id": ch.id, "title": ch.title, "chapter_number": ch.chapter_number, "status": ch.status}
            for ch in chapters
        ]

    # ── 网络搜索 ──────────────────────────────────────────────────

    @classmethod
    async def search_web(
        cls,
        query: str,
        max_results: int = 5,
        use_cache: bool = True,
    ) -> List[Dict[str, str]]:
        """网络搜索（优先 Tavily，降级到 DuckDuckGo）

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            use_cache: 是否使用缓存

        Returns:
            [{"title": ..., "snippet": ..., "url": ...}, ...]
        """
        # 缓存检查
        cache_key = cls._cache_key(query, max_results)
        if use_cache:
            cached = cls._cache.get(cache_key)
            if cached:
                ts, results = cached
                if time.time() - ts < cls._CACHE_TTL:
                    logger.debug(f"Cache hit: {query}")
                    return results

        # Tavily API
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if tavily_key:
            results = await cls._search_tavily(query, max_results, tavily_key)
        else:
            results = await cls._search_duckduckgo(query, max_results)

        # 更新缓存
        if results:
            cls._cache[cache_key] = (time.time(), results)
            # 限制缓存大小
            if len(cls._cache) > 200:
                oldest = min(cls._cache, key=lambda k: cls._cache[k][0])
                del cls._cache[oldest]

        return results

    @classmethod
    async def search_web_structured(
        cls,
        query: str,
        max_results: int = 5,
        context: dict = None,
    ) -> Dict[str, Any]:
        """网络搜索 + 结构化输出

        Returns:
            {
                "query": str,
                "results": [...],
                "summary": str,
                "references": [str],
                "source": "tavily" | "duckduckgo",
            }
        """
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        source = "tavily" if tavily_key else "duckduckgo"
        results = await cls.search_web(query, max_results)

        summary = ""
        if results:
            snippets = [r["snippet"] for r in results if r["snippet"]]
            if snippets:
                summary = " | ".join(snippets[:3])

        return {
            "query": query,
            "results": results,
            "summary": summary,
            "references": [r["url"] for r in results if r.get("url")],
            "source": source,
        }

    # ── Tavily API ─────────────────────────────────────────────────

    @classmethod
    async def _search_tavily(
        cls, query: str, max_results: int, api_key: str
    ) -> List[Dict[str, str]]:
        """调用 Tavily Search API"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                if resp.status_code != 200:
                    logger.warning(f"Tavily returned {resp.status_code}")
                    return []

                data = resp.json()
                results = []
                for r in data.get("results", [])[:max_results]:
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": (r.get("content", "") or "")[:500],
                        "url": r.get("url", ""),
                    })
                return results

        except httpx.TimeoutException:
            logger.warning("Tavily request timeout")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    # ── DuckDuckGo Fallback ───────────────────────────────────────

    @classmethod
    async def _search_duckduckgo(
        cls, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """DuckDuckGo Instant Answer（免费，无需 API Key）"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                results = []

                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "snippet": data["AbstractText"][:500],
                        "url": data.get("AbstractURL", ""),
                    })

                for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "snippet": topic["Text"][:500],
                            "url": topic.get("FirstURL", ""),
                        })

                return results[:max_results]

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    # ── 网络搜索 + AI 摘要 ───────────────────────────────────────

    @classmethod
    async def search_and_summarize(
        cls,
        query: str,
        max_results: int = 5,
        context: dict = None,
    ) -> Dict[str, Any]:
        """搜索 + LLM 结构化摘要（core/llm 驱动，无 Key 自动降级 mock）

        Returns:
            {"content": str, "is_mock": bool, "results": [...], "source": str}
        """
        from app.core.llm import LLMMessage, create
        from app.core.llm.providers.mock import MockProvider

        results = await cls.search_web(query, max_results)
        source = "tavily" if os.getenv("TAVILY_API_KEY") else "duckduckgo"
        llm = create()

        system = (
            "You are a research assistant for novel writing. "
            "Synthesize search results into useful references for the novelist. "
            "Provide relevant facts, cultural details, historical context, or literary references "
            "that can enrich the novel's world-building and plot development. Output in Chinese."
        )

        if results:
            results_text = "\n\n".join(
                f"[{i+1}] {r['title']}\n{r['snippet']}\n来源: {r['url']}"
                for i, r in enumerate(results)
            )
            task = (
                f"请根据以下搜索结果，为小说创作整理一份结构化参考：\n\n"
                f"【搜索主题】{query}\n\n【搜索结果】\n{results_text}\n\n"
                f"请输出：\n1. 核心知识点总结（3-5 条）\n2. 可用于小说的创意启发（2-3 条）\n"
                f"3. 注意事项（避免常识错误）\n4. 推荐延伸搜索方向"
            )
        else:
            task = (
                f"请基于你的知识，为小说创作整理关于「{query}」的参考信息：\n\n"
                f"请输出：\n1. 核心知识点总结（3-5 条）\n2. 可用于小说的创意启发（2-3 条）\n"
                f"3. 注意事项（避免常识错误）\n4. 推荐延伸搜索方向\n\n"
                f"（注：网络搜索不可用，请基于训练数据回答）"
            )

        resp = await llm.acomplete(_make_request(system, task))
        return {
            "content": resp.content,
            "is_mock": isinstance(llm, MockProvider),
            "results": results,
            "source": source,
        }

    # ── 缓存管理 ──────────────────────────────────────────────────

    @staticmethod
    def _cache_key(query: str, max_results: int) -> str:
        raw = f"{query}:{max_results}"
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def clear_cache(cls):
        """清除搜索缓存"""
        cls._cache.clear()
        logger.info("Search cache cleared")


def _make_request(system: str, user: str):
    """构造 LLMRequest（延迟导入避免循环依赖）"""
    from app.core.llm import LLMMessage, LLMRequest

    return LLMRequest(
        messages=[
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
    )
