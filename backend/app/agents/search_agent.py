"""搜索 Agent — 网络搜索小说参考

搜索后端统一由 SearchService（services/search_service.py）提供，
本 Agent 只负责「搜索 + LLM 摘要」的编排。
"""

from typing import Optional

from app.agents.agent_base import BaseAgent, AgentConfig, AgentResult, SEARCH_SYSTEM
from app.services.search_service import SearchService


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
        """执行原始搜索（统一走 SearchService，含缓存与降级）

        Returns:
            [{"title": ..., "snippet": ..., "url": ...}, ...]
        """
        return await SearchService.search_web(query, max_results, use_cache)

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
