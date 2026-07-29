"""搜索 Agent — 网络搜索小说参考"""

import os
import hashlib
import json
import time
from typing import Optional

import httpx

from app.agents.agent_base import BaseAgent, AgentConfig, AgentResult, SEARCH_SYSTEM


class SearchAgent(BaseAgent):
    """搜索 Agent：网络搜索 + LLM 摘要 → 为小说创作提供参考

    使用示例
    --------
    agent = SearchAgent()

    # 搜索 + AI 摘要
    result = await agent.search_and_summarize("明朝科举制度")

    # 纯搜索（不经过 LLM）
    results = await agent.search_raw("中世纪骑士装备")
    """

    default_system_prompt: str = SEARCH_SYSTEM
    default_model: str = "gpt-4o-mini"

    def __init__(self, config: AgentConfig = None, **kwargs):
        super().__init__(config, **kwargs)
        self._tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self._cache: dict[str, tuple[float, list[dict]]] = {}  # {cache_key: (timestamp, results)}
        self._cache_ttl: int = 3600  # 缓存 1 小时

    # ── 搜索 + AI 摘要 ───────────────────────────────────────────

    async def search_and_summarize(
        self,
        query: str,
        max_results: int = 5,
        context: dict = None,
    ) -> AgentResult:
        """搜索并让 LLM 生成结构化摘要

        Args:
            query: 搜索关键词
            max_results: 使用前 N 条结果
            context: 小说上下文
        """
        # 1. 搜索
        search_results = await self.search_raw(query, max_results)

        if not search_results:
            # 降级：让 LLM 直接基于知识回答（或 mock）
            if self._mock_mode:
                return await self._mock_run(query, context)

            task = (
                f"请基于你的知识，为小说创作整理关于「{query}」的参考信息：\n\n"
                f"请输出：\n"
                f"1. 核心知识点总结（3-5 条）\n"
                f"2. 可用于小说的创意启发（2-3 条）\n"
                f"3. 注意事项（避免常识错误）\n"
                f"4. 推荐延伸搜索方向\n\n"
                f"（注：网络搜索不可用，请基于训练数据回答）"
            )
            return await self.run(task, context)

        # 2. 构建 LLM 摘要任务
        results_text = "\n\n".join(
            f"[{i+1}] {r['title']}\n{r['snippet']}\n来源: {r['url']}"
            for i, r in enumerate(search_results)
        )

        task = (
            f"请根据以下搜索结果，为小说创作整理一份结构化参考：\n\n"
            f"【搜索主题】{query}\n\n"
            f"【搜索结果】\n{results_text}\n\n"
            f"请输出：\n"
            f"1. 核心知识点总结（3-5 条）\n"
            f"2. 可用于小说的创意启发（2-3 条）\n"
            f"3. 注意事项（避免常识错误）\n"
            f"4. 推荐延伸搜索方向"
        )

        result = await self.run(task, context)
        return result

    # ── 纯搜索 ────────────────────────────────────────────────────

    async def search_raw(
        self,
        query: str,
        max_results: int = 5,
        use_cache: bool = True,
    ) -> list[dict]:
        """执行原始搜索，返回结果列表

        Args:
            query: 搜索词
            max_results: 最大结果数
            use_cache: 是否使用缓存

        Returns:
            [{"title": ..., "snippet": ..., "url": ...}, ...]
        """
        # 检查缓存
        if use_cache:
            cache_key = self._cache_key(query, max_results)
            cached = self._cache.get(cache_key)
            if cached:
                ts, results = cached
                if time.time() - ts < self._cache_ttl:
                    return results

        # Tavily Search API
        if self._tavily_api_key:
            results = await self._search_tavily(query, max_results)
        else:
            # Fallback: 使用 DuckDuckGo 免费 API
            results = await self._search_duckduckgo(query, max_results)

        # 缓存
        if use_cache and results:
            cache_key = self._cache_key(query, max_results)
            self._cache[cache_key] = (time.time(), results)

        return results

    # ── Tavily API ─────────────────────────────────────────────────

    async def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        """调用 Tavily Search API"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self._tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                return [
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("content", "")[:500],
                        "url": r.get("url", ""),
                    }
                    for r in data.get("results", [])[:max_results]
                ]
        except Exception:
            return []

    # ── DuckDuckGo Fallback ───────────────────────────────────────

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        """DuckDuckGo Instant Answer API（免费，无需 Key）"""
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

                # Abstract
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "snippet": data["AbstractText"][:500],
                        "url": data.get("AbstractURL", ""),
                    })

                # Related Topics
                for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "snippet": topic["Text"][:500],
                            "url": topic.get("FirstURL", ""),
                        })

                return results[:max_results]
        except Exception:
            return []

    # ── 缓存 ──────────────────────────────────────────────────────

    def _cache_key(self, query: str, max_results: int) -> str:
        raw = f"{query}:{max_results}"
        return hashlib.md5(raw.encode()).hexdigest()

    def clear_cache(self):
        """清除搜索缓存"""
        self._cache.clear()

    # ── 抽象接口 ──────────────────────────────────────────────────

    async def generate(self, prompt: str, context: dict = None) -> AgentResult:
        return await self.search_and_summarize(prompt, context=context)

    # ── Mock 覆盖 ─────────────────────────────────────────────────

    def _generate_mock(self, task: str, context: dict = None) -> str:
        return (
            f"【搜索参考 — Mock】\n\n"
            f"搜索主题：{task[:100]}\n\n"
            f"1. 核心知识点：[Mock] 请配置 TAVILY_API_KEY 或 LLM API Key 获取真实搜索结果\n"
            f"2. 创意启发：[Mock] 基于搜索结果的创作建议\n"
            f"3. 注意事项：[Mock] 使用 DuckDuckGo 可获取基础百科信息（无需 API Key）\n"
            f"4. 延伸搜索：[Mock] 建议细化搜索方向\n\n"
            f"💡 当前搜索使用 DuckDuckGo Instant Answer（免费，结果有限）。"
        )
