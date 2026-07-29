"""审核 Agent — 8 大维度审核"""

import json
import re
from typing import Optional

from app.agents.agent_base import BaseAgent, AgentConfig, AgentResult, REVIEWER_SYSTEM


class ReviewAgent(BaseAgent):
    """审核 Agent：8 维度内容审核 + 综合评估

    使用示例
    --------
    agent = ReviewAgent(llm_provider="openai")

    result = await agent.review_consistency(content="...", context="...")
    result = await agent.review_comprehensive(content="...", context="...")
    """

    default_system_prompt: str = REVIEWER_SYSTEM
    default_model: str = "gpt-4o-mini"

    # ── 维度映射 ──────────────────────────────────────────────────

    DIMENSIONS = {
        "consistency": {
            "name": "一致性",
            "prompt": (
                "请审核内容与设定的一致性：\n"
                "- 角色行为是否符合其性格设定\n"
                "- 世界观规则是否前后一致\n"
                "- 时间线/地点是否有矛盾\n"
                "- 物品/能力使用是否符合设定"
            ),
        },
        "logic": {
            "name": "逻辑性",
            "prompt": (
                "请审核情节逻辑：\n"
                "- 因果关系是否合理\n"
                "- 情节转折是否有铺垫\n"
                "- 时间线是否存在跳跃\n"
                "- 人物行为是否有合理动机"
            ),
        },
        "foreshadowing": {
            "name": "伏笔管理",
            "prompt": (
                "请审核伏笔状态：\n"
                "- 识别新埋设的伏笔\n"
                "- 检查已回收的伏笔是否合理\n"
                "- 标记未回收的伏笔及其状态\n"
                "- 评估伏笔密度是否合适"
            ),
        },
        "character_arc": {
            "name": "人物弧光",
            "prompt": (
                "请审核人物发展：\n"
                "- 角色是否有明显的成长/变化\n"
                "- 成长转折点是否合理\n"
                "- 配角是否有足够的存在感\n"
                "- 人物关系发展是否自然"
            ),
        },
        "pacing": {
            "name": "节奏",
            "prompt": (
                "请审核叙事节奏：\n"
                "- 紧张与舒缓段落是否交替得当\n"
                "- 是否存在过长的平淡段落\n"
                "- 高潮部分是否紧凑有力\n"
                "- 过渡段落是否自然"
            ),
        },
        "prose": {
            "name": "文笔",
            "prompt": (
                "请审核文笔质量：\n"
                "- 语言是否流畅优美\n"
                "- 是否存在重复用词/句式\n"
                "- 对话是否自然有辨识度\n"
                "- 描写是否生动具体"
            ),
        },
        "reader_perspective": {
            "name": "读者视角",
            "prompt": (
                "请从读者角度审核：\n"
                "- 开头是否吸引人\n"
                "- 信息密度是否合适（不过多不过少）\n"
                "- 是否有足够的悬念和钩子\n"
                "- 情感共鸣是否到位"
            ),
        },
        "grammar": {
            "name": "语法",
            "prompt": (
                "请审核语法和基础质量：\n"
                "- 错别字和标点错误\n"
                "- 病句和不通顺表达\n"
                "- 人称/视角一致性问题\n"
                "- 格式规范问题"
            ),
        },
    }

    # ── 单维度审核 ────────────────────────────────────────────────

    async def review_dimension(
        self,
        content: str,
        dimension: str,
        context: str = "",
    ) -> AgentResult:
        """按指定维度审核内容

        Args:
            content: 待审核文本
            dimension: 维度 key (consistency/logic/...)
            context: 补充上下文
        """
        dim = self.DIMENSIONS.get(dimension)
        if not dim:
            return AgentResult(
                success=False,
                content="",
                error=f"Unknown dimension: {dimension}. Available: {list(self.DIMENSIONS.keys())}",
            )

        task = (
            f"【审核维度】{dim['name']}\n{dim['prompt']}\n\n"
            f"【上下文】{context or '无'}\n\n"
            f"【待审核内容】\n{content[:8000]}\n\n"
            f"请输出 JSON 格式结果：\n"
            f'{{"score": 0-100, "summary": "审核摘要", '
            f'"issues": ["问题1", "问题2"], '
            f'"suggestions": ["建议1", "建议2"], '
            f'"highlights": ["亮点1", "亮点2"]}}'
        )

        result = await self.run(task)

        # 尝试解析 JSON
        parsed = self._parse_review_json(result.content)
        if parsed:
            result.content = json.dumps(parsed, ensure_ascii=False)
        return result

    # ── 便捷方法 ──────────────────────────────────────────────────

    async def review_consistency(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "consistency", context)

    async def review_logic(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "logic", context)

    async def review_foreshadowing(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "foreshadowing", context)

    async def review_character_arc(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "character_arc", context)

    async def review_pacing(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "pacing", context)

    async def review_prose(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "prose", context)

    async def review_reader_perspective(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "reader_perspective", context)

    async def review_grammar(self, content: str, context: str = "") -> AgentResult:
        return await self.review_dimension(content, "grammar", context)

    # ── 综合审核 ──────────────────────────────────────────────────

    async def review_comprehensive(
        self,
        content: str,
        context: str = "",
        dimensions: list[str] = None,
    ) -> AgentResult:
        """综合审核：一次调用覆盖多个维度

        Args:
            content: 待审核文本
            context: 补充上下文
            dimensions: 指定维度列表（None=全部）
        """
        dims = dimensions or list(self.DIMENSIONS.keys())
        dim_details = "\n\n".join(
            f"{i+1}. {self.DIMENSIONS[d]['name']}\n{self.DIMENSIONS[d]['prompt']}"
            for i, d in enumerate(dims)
            if d in self.DIMENSIONS
        )

        task = (
            f"请对以下内容进行综合审核，覆盖以下维度：\n\n"
            f"{dim_details}\n\n"
            f"【上下文】{context or '无'}\n\n"
            f"【待审核内容】\n{content[:8000]}\n\n"
            f"请输出 JSON 格式的综合结果：\n"
            f'{{"score": 0-100, "summary": "综合审核摘要", '
            f'"issues": ["跨维度问题"], '
            f'"suggestions": ["改进建议"], '
            f'"highlights": ["亮点"], '
            f'"dimension_scores": {{"consistency": 85, ...}}}}'
        )

        result = await self.run(task)
        parsed = self._parse_review_json(result.content)
        if parsed:
            result.content = json.dumps(parsed, ensure_ascii=False)
        return result

    # ── 抽象接口 ──────────────────────────────────────────────────

    async def generate(self, prompt: str, context: dict = None) -> AgentResult:
        task = f"请对以下内容进行审核:\n\n{prompt}"
        return await self.run(task, context)

    async def review(self, content: str, criteria: str = "") -> AgentResult:
        return await self.review_comprehensive(content, criteria)

    # ── JSON 解析 ─────────────────────────────────────────────────

    def _parse_review_json(self, text: str) -> Optional[dict]:
        """从 LLM 输出中提取 JSON"""
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    # ── Mock 覆盖 ─────────────────────────────────────────────────

    def _generate_mock(self, task: str, context: dict = None) -> str:
        return json.dumps({
            "score": 82,
            "summary": "[Mock] 综合审核结果 — 配置 LLM API Key 后获取真实 AI 审核",
            "issues": ["[Mock] 建议检查角色行为一致性", "[Mock] 段落 3 节奏略慢"],
            "suggestions": ["[Mock] 加强主角性格刻画", "[Mock] 压缩环境描写"],
            "highlights": ["[Mock] 对话自然流畅", "[Mock] 世界观设定丰富"],
            "dimension_scores": {
                "consistency": 85, "logic": 82, "foreshadowing": 78,
                "character_arc": 80, "pacing": 75, "prose": 88,
                "reader_perspective": 84, "grammar": 90,
            },
        }, ensure_ascii=False)
