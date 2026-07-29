"""写作 Agent — 章节内容生成 + 流式输出"""

from typing import AsyncIterator, Optional

from app.agents.agent_base import BaseAgent, AgentConfig, AgentResult, WRITER_SYSTEM


class WriterAgent(BaseAgent):
    """写作 Agent：负责章节内容生成、续写、改写

    使用示例
    --------
    agent = WriterAgent(llm_provider="deepseek", model="deepseek-chat")

    # 非流式
    result = await agent.generate_chapter(prompt="主角进入秘境...", context={...})

    # 流式（SSE）
    async for chunk in agent.generate_chapter_stream(prompt="...", context={...}):
        print(chunk, end="")
    """

    default_system_prompt: str = WRITER_SYSTEM
    default_model: str = "gpt-4o-mini"

    # ── 章节生成 ──────────────────────────────────────────────────

    async def generate_chapter(
        self,
        prompt: str,
        context: dict = None,
        style: str = "narrative",
        target_word_count: int = 2000,
    ) -> AgentResult:
        """生成章节内容（非流式）

        Args:
            prompt: 生成提示词（章节大纲/概要）
            context: 上下文（已有设定、前文摘要、角色信息等）
            style: 写作风格 (narrative/descriptive/dialogue-heavy/action)
            target_word_count: 目标字数
        """
        style_guide = self._style_guide(style)
        task = (
            f"请根据以下要求创作章节内容：\n\n"
            f"【写作风格】{style_guide}\n"
            f"【目标字数】约 {target_word_count} 字\n"
            f"【内容要求】{prompt}\n\n"
            f"要求：\n"
            f"- 保持与上下文设定的一致性\n"
            f"- 注重场景描写和人物刻画\n"
            f"- 自然的对话和内心独白\n"
            f"- 合理的节奏控制\n"
            f"- 在结尾留下适当的悬念或过渡"
        )
        return await self.run(task, context)

    async def generate_chapter_stream(
        self,
        prompt: str,
        context: dict = None,
        style: str = "narrative",
        target_word_count: int = 2000,
    ) -> AsyncIterator[str]:
        """生成章节内容（流式，用于 SSE）

        Yields:
            str: 逐 token 输出
        """
        style_guide = self._style_guide(style)
        task = (
            f"请根据以下要求创作章节内容：\n\n"
            f"【写作风格】{style_guide}\n"
            f"【目标字数】约 {target_word_count} 字\n"
            f"【内容要求】{prompt}\n\n"
            f"要求：保持与上下文一致性，注重场景描写和人物刻画，自然对话，合理节奏，适当悬念。"
        )
        async for chunk in self.run_stream(task, context):
            yield chunk

    # ── 续写 ──────────────────────────────────────────────────────

    async def continue_chapter(
        self,
        previous_content: str,
        direction: str = "",
        context: dict = None,
    ) -> AgentResult:
        """续写已有内容

        Args:
            previous_content: 已有内容（最后 2000 字左右）
            direction: 续写方向提示
        """
        task = (
            f"请续写以下小说内容：\n\n"
            f"【已有内容】（结尾部分）\n{previous_content[-2000:]}\n\n"
            f"【续写方向】{direction or '请自然延续当前情节'}\n\n"
            f"要求：保持文风一致、人物性格连贯、情节合理推进。"
        )
        return await self.run(task, context)

    async def continue_chapter_stream(
        self,
        previous_content: str,
        direction: str = "",
        context: dict = None,
    ) -> AsyncIterator[str]:
        """续写（流式）"""
        task = (
            f"请续写以下小说内容：\n\n"
            f"【已有内容】（结尾部分）\n{previous_content[-2000:]}\n\n"
            f"【续写方向】{direction or '请自然延续当前情节'}\n\n"
            f"要求：保持文风一致、人物性格连贯、情节合理推进。"
        )
        async for chunk in self.run_stream(task, context):
            yield chunk

    # ── 改写 / 润色 ───────────────────────────────────────────────

    async def polish(
        self,
        content: str,
        aspect: str = "general",
        context: dict = None,
    ) -> AgentResult:
        """润色/改写已有内容

        Args:
            content: 待润色内容
            aspect: 润色方向 (general/descriptive/dialogue/pacing/prose)
        """
        aspect_guides = {
            "general": "全面优化语言表达，提升文学性",
            "descriptive": "增强场景描写和感官细节",
            "dialogue": "优化对话自然度和角色辨识度",
            "pacing": "调整叙事节奏，增强张弛感",
            "prose": "提升文笔质量，丰富词汇和句式",
        }
        guide = aspect_guides.get(aspect, aspect_guides["general"])

        task = (
            f"请润色以下小说内容：\n"
            f"润色方向：{guide}\n\n"
            f"【原文】\n{content}\n\n"
            f"请输出润色后的版本，保持原意和字数大致不变。"
        )
        return await self.run(task, context)

    # ── 抽象接口 ──────────────────────────────────────────────────

    async def generate(self, prompt: str, context: dict = None) -> AgentResult:
        return await self.generate_chapter(prompt, context)

    # ── 辅助 ──────────────────────────────────────────────────────

    def _style_guide(self, style: str) -> str:
        guides = {
            "narrative": "叙事为主，注重情节推进和人物心理描写",
            "descriptive": "描写为主，注重环境和氛围营造，丰富的感官细节",
            "dialogue-heavy": "对话为主，通过人物对话推动情节发展",
            "action": "动作场景为主，快速节奏，紧凑的描写",
            "literary": "文学性强，注重语言艺术和修辞手法",
            "light": "轻松幽默，适合日常和喜剧场景",
        }
        return guides.get(style, guides["narrative"])

    # ── Mock 覆盖 ─────────────────────────────────────────────────

    def _generate_mock(self, task: str, context: dict = None) -> str:
        return (
            "【AI 章节生成 — Mock 示例】\n\n"
            "　　（此处为模拟章节内容，配置 LLM API Key 后将生成真实内容）\n\n"
            "　　夜色如墨，星光黯淡。李云踏着青石板路，独自走向那座古老的塔楼。风穿过狭窄的巷道，"
            "带来远处集市的喧闹声，却无法驱散他心中的不安。\n\n"
            "　　「你真的要去吗？」身后传来熟悉的声音。\n\n"
            "　　他转过身，看到柳月站在月光下，眼中满是担忧。\n\n"
            "　　「我必须去。」李云握紧了手中的剑柄，「有些事情，总要有人去做。」\n\n"
            "　　……\n\n"
            f"💡 提示：设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY 以启用 AI 真实创作。\n"
            f"当前任务：{task[:150]}..."
        )
