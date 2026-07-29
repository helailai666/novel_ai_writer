"""创意 Agent — 世界观 / 角色 / 道具 / 能力 / 势力 / 场景生成"""

from typing import Optional

from app.agents.agent_base import BaseAgent, AgentConfig, AgentResult, CREATIVE_SYSTEM


class CreativeAgent(BaseAgent):
    """创意生成 Agent：负责世界观构建、角色设计、道具/技能/势力/场景生成

    使用示例
    --------
    agent = CreativeAgent(llm_provider="openai")
    result = await agent.generate_world_setting("修仙世界", category="power_system")
    result = await agent.generate_character("主角", context={"world_setting": "..."})
    """

    default_system_prompt: str = CREATIVE_SYSTEM
    default_model: str = "gpt-4o-mini"

    # ── 世界观 ────────────────────────────────────────────────────

    async def generate_world_setting(
        self,
        name: str,
        category: str = "general",
        context: dict = None,
    ) -> AgentResult:
        """生成世界观设定项

        Args:
            name: 设定名称
            category: 类别 (general/power_system/race/culture/geography/history)
            context: 已有设定上下文
        """
        cat_prompts = {
            "power_system": "请详细设计力量体系/修炼体系的层级、规则、限制和进阶路径",
            "race": "请详细设计种族设定：外观特征、文化传统、天赋能力、社会结构",
            "culture": "请详细设计文化设定：宗教、节日、礼仪、价值观、艺术形式",
            "geography": "请详细设计地理设定：地形、气候、资源分布、特殊区域",
            "history": "请详细设计历史设定：重大事件时间线、传说、古代文明遗迹",
        }
        extra = cat_prompts.get(category, "请详细描述该设定的各个方面")

        task = f"为小说生成世界观设定：「{name}」\n类别: {category}\n{extra}\n\n请输出结构化的设定内容，使用标题和分段。"
        return await self.run(task, context)

    # ── 角色 ──────────────────────────────────────────────────────

    async def generate_character(
        self,
        name: str,
        role: str = "supporting",
        context: dict = None,
    ) -> AgentResult:
        """生成角色设定

        Args:
            name: 角色名
            role: 角色定位 (protagonist/antagonist/supporting/mentor/comic_relief)
            context: 世界观等上下文
        """
        role_descs = {
            "protagonist": "主角，需要有完整的成长弧光和复杂性格",
            "antagonist": "反派/对手，需要有合理的动机和立体的人格",
            "supporting": "配角，在主线中发挥特定作用",
            "mentor": "导师角色，引导主角成长",
            "comic_relief": "喜剧调剂角色",
        }
        role_desc = role_descs.get(role, role)

        task = (
            f"为小说设计角色：「{name}」\n"
            f"角色定位: {role_desc}\n\n"
            f"请输出结构化的角色设定，包含以下方面：\n"
            f"1. 基本信息（性别、年龄、外貌）\n"
            f"2. 性格特点（核心性格、优缺点）\n"
            f"3. 背景故事\n"
            f"4. 能力特长\n"
            f"5. 人际关系建议\n"
            f"6. 成长弧光设计"
        )
        return await self.run(task, context)

    async def generate_characters_batch(
        self,
        names_and_roles: list[tuple[str, str]],
        context: dict = None,
    ) -> list[AgentResult]:
        """批量生成角色"""
        results = []
        for name, role in names_and_roles:
            result = await self.generate_character(name, role, context)
            results.append(result)
        return results

    # ── 道具 / 技能 / 势力 / 场景 ────────────────────────────────

    async def generate_item(
        self,
        name: str,
        category: str = "weapon",
        context: dict = None,
    ) -> AgentResult:
        """生成道具设定"""
        task = (
            f"为小说设计道具：「{name}」\n"
            f"类别: {category}\n\n"
            f"请输出结构化的道具设定：名称、外观描述、功能效果、来源/历史、使用限制、稀有度评估"
        )
        return await self.run(task, context)

    async def generate_skill(
        self,
        name: str,
        category: str = "magic",
        context: dict = None,
    ) -> AgentResult:
        """生成技能/能力设定"""
        task = (
            f"为小说设计技能：「{name}」\n"
            f"类别: {category}\n\n"
            f"请输出结构化的技能设定：技能描述、使用方式、消耗/代价、等级/熟练度阶段、学习条件"
        )
        return await self.run(task, context)

    async def generate_faction(
        self,
        name: str,
        faction_type: str = "kingdom",
        context: dict = None,
    ) -> AgentResult:
        """生成势力/组织设定"""
        task = (
            f"为小说设计势力：「{name}」\n"
            f"类型: {faction_type}\n\n"
            f"请输出结构化的势力设定：组织宗旨/目标、等级结构、核心成员、资源/领土、对外关系、历史沿革"
        )
        return await self.run(task, context)

    async def generate_location(
        self,
        name: str,
        category: str = "city",
        context: dict = None,
    ) -> AgentResult:
        """生成地点/场景设定"""
        task = (
            f"为小说设计场景/地点：「{name}」\n"
            f"类别: {category}\n\n"
            f"请输出结构化的场景设定：地理位置、外观描述、气候环境、特色景观、文化氛围、在故事中的作用"
        )
        return await self.run(task, context)

    async def generate_outline(
        self,
        title: str,
        level: int = 1,
        context: dict = None,
    ) -> AgentResult:
        """生成大纲节点"""
        level_desc = {1: "卷/部", 2: "章节", 3: "场景", 4: "小节"}
        task = (
            f"为小说大纲生成「{title}」\n"
            f"层级: {level_desc.get(level, str(level))}\n\n"
            f"请输出该大纲节点的简要描述（100-300字），包含核心情节和关键转折"
        )
        return await self.run(task, context)

    # ── 抽象接口 ──────────────────────────────────────────────────

    async def generate(self, prompt: str, context: dict = None) -> AgentResult:
        return await self.run(prompt, context)

    # ── Mock 覆盖 ─────────────────────────────────────────────────

    def _generate_mock(self, task: str, context: dict = None) -> str:
        """创意 Mock — 提供示例内容"""
        if "角色" in task or "character" in task.lower():
            return (
                "【角色设定 — Mock 示例】\n\n"
                "姓名：未命名（请配置 LLM API Key 获取 AI 生成）\n"
                "性别：待定\n"
                "年龄：待定\n"
                "性格特点：勇敢、智慧、但有内心深处的不安\n"
                "背景故事：出身平凡，因一次意外踏上冒险之旅\n"
                "能力特长：尚未觉醒的特殊天赋\n"
                "成长弧光：从普通人成长为英雄的经典旅程\n\n"
                "💡 提示：设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY 环境变量以启用 AI 生成。"
            )
        if "道具" in task or "item" in task.lower():
            return (
                "【道具设定 — Mock 示例】\n\n"
                "名称：神秘古剑\n"
                "类别：武器\n"
                "外观：剑身布满古老符文，散发着淡蓝色微光\n"
                "功能：能够感知邪恶力量，在关键时刻释放守护之力\n"
                "来源：远古遗迹中发现\n"
                "限制：需要纯善之心才能发挥真正力量\n\n"
                "💡 提示：设置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY 环境变量以启用 AI 生成。"
            )
        return (
            f"【创意生成 — Mock 示例】\n\n"
            f"主题：{task[:100]}\n\n"
            f"这是一个占位示例。配置 LLM API Key 后即可获得 AI 生成的真实创意内容。\n\n"
            f"💡 设置环境变量：OPENAI_API_KEY / DEEPSEEK_API_KEY / 或使用 Ollama 本地模型"
        )
