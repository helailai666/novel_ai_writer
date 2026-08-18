"""节点共享工具 — LLM 解析 / 消息构造 / 提示词（从旧 Agent 迁移）"""

from typing import Optional

from app.core.llm import LLMMessage, LLMProvider, create, create_for
from app.core.llm.providers.mock import MockProvider
from app.agents.state import NovelState


def resolve_llm(state: NovelState, **kwargs) -> LLMProvider:
    """按 state 解析 LLM 实例

    state["model"] 支持 "provider:model" 或 "model"（用全局 provider）
    """
    override = state.get("model") or ""
    if ":" in override:
        provider, _, model = override.partition(":")
        return create_for(provider, model or None, **kwargs)
    if override:
        return create(model=override, **kwargs)
    return create(**kwargs)


def is_mock_provider(llm: LLMProvider) -> bool:
    return isinstance(llm, MockProvider)


def merge_skills(requested: Optional[list[str]], project: Optional[list[str]]) -> list[str]:
    """合并请求级与项目级技能（G2 细化策略）

    优先级模型：
    - requested 为 None（未指定） → 仅用项目级技能
    - requested 为空列表 []        → 显式禁用全部技能（覆盖项目级）
    - requested 非空              → 请求级优先 + 项目级补齐（去重保序）
    """
    if requested is None:
        return list(project or [])
    if not requested:  # 显式空列表 → 禁用全部技能（覆盖项目级）
        return []
    result = list(requested)
    for name in project or []:
        if name and name not in result:
            result.append(name)
    return result


def messages(system: str, user: str) -> list[LLMMessage]:
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]


def with_history(state: NovelState, user_msg: str, max_turns: int = 6) -> str:
    """把对话历史前缀到用户消息（L 轮多轮上下文；缺省/空历史原样返回）

    历史格式: [{"role": "user"/"assistant", "content": "..."}]
    """
    history = state.get("history") or []
    if not history:
        return user_msg
    lines = ["【对话历史（此前轮次）】"]
    for turn in history[-max_turns:]:
        role = "用户" if turn.get("role") == "user" else "助手"
        content = str(turn.get("content") or "").strip()
        if content:
            lines.append(f"- {role}: {content[:500]}")
    return "\n".join(lines) + "\n\n" + user_msg


def skill_context(state: NovelState) -> dict:
    """按 state.skills 组装技能注入内容：{prompt, tools, knowledge_refs}"""
    names = state.get("skills") or []
    if not names:
        return {"prompt": "", "tools": [], "knowledge_refs": []}
    try:
        from app.core.skills import get_runner

        return get_runner().apply(names)
    except Exception:
        return {"prompt": "", "tools": [], "knowledge_refs": []}


def enhance_system(state: NovelState, base_system: str) -> str:
    """把技能 prompt 追加到系统提示词"""
    ctx = skill_context(state)
    if ctx["prompt"]:
        return f"{base_system}\n\n{ctx['prompt']}"
    return base_system


# ── 提示词（迁移自旧 agent_base / creative / writer / review）────────

CREATIVE_SYSTEM = """You are a creative novelist and world-builder assistant.
You specialize in creating rich, consistent fictional worlds, characters, items, and settings for novels.
Always output structured, well-formatted content in Chinese by default.
Be imaginative but maintain internal consistency with any provided context."""

WRITER_SYSTEM = """You are a professional novelist specializing in long-form fiction.
Write engaging, well-paced chapter content with vivid descriptions, natural dialogue, and consistent characterization.
Follow the provided outline and context strictly. Output in Chinese by default.
Maintain the tone and style specified by the user."""

REVIEWER_SYSTEM = """You are a professional editor and literary critic.
Review the provided text for consistency, logic, pacing, prose quality, character development,
foreshadowing, and reader engagement. Provide detailed, actionable feedback.
Always output a structured review with scores, issues, suggestions, and highlights.
Respond in Chinese."""

STYLE_GUIDES = {
    "narrative": "叙事为主，注重情节推进和人物心理描写",
    "descriptive": "描写为主，注重环境和氛围营造，丰富的感官细节",
    "dialogue-heavy": "对话为主，通过人物对话推动情节发展",
    "action": "动作场景为主，快速节奏，紧凑的描写",
    "literary": "文学性强，注重语言艺术和修辞手法",
    "light": "轻松幽默，适合日常和喜剧场景",
}

# ── 设定生成任务构造（迁移自 CreativeAgent）────────────────────────

def build_world_task(name: str, category: str) -> str:
    cat_prompts = {
        "power_system": "请详细设计力量体系/修炼体系的层级、规则、限制和进阶路径",
        "race": "请详细设计种族设定：外观特征、文化传统、天赋能力、社会结构",
        "culture": "请详细设计文化设定：宗教、节日、礼仪、价值观、艺术形式",
        "geography": "请详细设计地理设定：地形、气候、资源分布、特殊区域",
        "history": "请详细设计历史设定：重大事件时间线、传说、古代文明遗迹",
    }
    extra = cat_prompts.get(category, "请详细描述该设定的各个方面")
    return f"为小说生成世界观设定：「{name}」\n类别: {category}\n{extra}\n\n请输出结构化的设定内容，使用标题和分段。"


def build_timeline_task(name: str, era: str, extra: str = "") -> str:
    """时间线事件生成任务（M 轮）"""
    return (
        f"为小说生成一条时间线事件：「{name}」\n时代/纪元: {era or 'present'}\n"
        f"{extra or ''}\n\n"
        f"请输出这段事件的具体描述（发生了什么、前因后果、对剧情的影响），"
        f"并说明涉及的主要角色。保持与作品世界观一致，输出中文。"
    )


def build_character_task(name: str, role: str) -> str:
    role_descs = {
        "protagonist": "主角，需要有完整的成长弧光和复杂性格",
        "antagonist": "反派/对手，需要有合理的动机和立体的人格",
        "supporting": "配角，在主线中发挥特定作用",
        "mentor": "导师角色，引导主角成长",
        "comic_relief": "喜剧调剂角色",
    }
    role_desc = role_descs.get(role, role)
    return (
        f"为小说设计角色：「{name}」\n角色定位: {role_desc}\n\n"
        f"请输出结构化的角色设定，包含以下方面：\n"
        f"1. 基本信息（性别、年龄、外貌）\n2. 性格特点（核心性格、优缺点）\n"
        f"3. 背景故事\n4. 能力特长\n5. 人际关系建议\n6. 成长弧光设计"
    )


def build_item_task(name: str, category: str) -> str:
    return (
        f"为小说设计道具：「{name}」\n类别: {category}\n\n"
        f"请输出结构化的道具设定：名称、外观描述、功能效果、来源/历史、使用限制、稀有度评估"
    )


def build_skill_task(name: str, category: str) -> str:
    return (
        f"为小说设计技能：「{name}」\n类别: {category}\n\n"
        f"请输出结构化的技能设定：技能描述、使用方式、消耗/代价、等级/熟练度阶段、学习条件"
    )


def build_faction_task(name: str, faction_type: str) -> str:
    return (
        f"为小说设计势力：「{name}」\n类型: {faction_type}\n\n"
        f"请输出结构化的势力设定：组织宗旨/目标、等级结构、核心成员、资源/领土、对外关系、历史沿革"
    )


def build_location_task(name: str, category: str) -> str:
    return (
        f"为小说设计场景/地点：「{name}」\n类别: {category}\n\n"
        f"请输出结构化的场景设定：地理位置、外观描述、气候环境、特色景观、文化氛围、在故事中的作用"
    )


def build_outline_task(title: str, level: int = 1) -> str:
    level_desc = {1: "卷/部", 2: "章节", 3: "场景", 4: "小节"}
    return (
        f"为小说大纲生成「{title}」\n层级: {level_desc.get(level, str(level))}\n\n"
        f"请输出该大纲节点的简要描述（100-300字），包含核心情节和关键转折"
    )


# ── 章节任务构造（迁移自 WriterAgent）──────────────────────────────

def build_chapter_task(prompt: str, style: str, target_word_count: int) -> str:
    style_guide = STYLE_GUIDES.get(style, STYLE_GUIDES["narrative"])
    return (
        f"请根据以下要求创作章节内容：\n\n"
        f"【写作风格】{style_guide}\n【目标字数】约 {target_word_count} 字\n"
        f"【内容要求】{prompt}\n\n要求：保持与上下文一致性，注重场景描写和人物刻画，"
        f"自然对话，合理节奏，适当悬念。"
    )


def build_continue_task(previous_content: str, direction: str) -> str:
    return (
        f"请续写以下小说内容：\n\n【已有内容】（结尾部分）\n{previous_content[-2000:]}\n\n"
        f"【续写方向】{direction or '请自然延续当前情节'}\n\n要求：保持文风一致、人物性格连贯、情节合理推进。"
    )


def build_polish_task(content: str, aspect: str) -> str:
    aspect_guides = {
        "general": "全面优化语言表达，提升文学性",
        "descriptive": "增强场景描写和感官细节",
        "dialogue": "优化对话自然度和角色辨识度",
        "pacing": "调整叙事节奏，增强张弛感",
        "prose": "提升文笔质量，丰富词汇和句式",
    }
    guide = aspect_guides.get(aspect, aspect_guides["general"])
    return (
        f"请润色以下小说内容：\n润色方向：{guide}\n\n【原文】\n{content}\n\n"
        f"请输出润色后的版本，保持原意和字数大致不变。"
    )


# ── 审核维度（迁移自 ReviewAgent.DIMENSIONS）──────────────────────

REVIEW_DIMENSIONS: dict[str, dict] = {
    "consistency": {
        "name": "一致性",
        "prompt": "请审核内容与设定的一致性：\n- 角色行为是否符合其性格设定\n- 世界观规则是否前后一致\n- 时间线/地点是否有矛盾\n- 物品/能力使用是否符合设定",
    },
    "logic": {
        "name": "逻辑性",
        "prompt": "请审核情节逻辑：\n- 因果关系是否合理\n- 情节转折是否有铺垫\n- 时间线是否存在跳跃\n- 人物行为是否有合理动机",
    },
    "foreshadowing": {
        "name": "伏笔管理",
        "prompt": "请审核伏笔状态：\n- 识别新埋设的伏笔\n- 检查已回收的伏笔是否合理\n- 标记未回收的伏笔及其状态\n- 评估伏笔密度是否合适",
    },
    "character-arc": {
        "name": "人物弧光",
        "prompt": "请审核人物发展：\n- 角色是否有明显的成长/变化\n- 成长转折点是否合理\n- 配角是否有足够的存在感\n- 人物关系发展是否自然",
    },
    "pacing": {
        "name": "节奏",
        "prompt": "请审核叙事节奏：\n- 紧张与舒缓段落是否交替得当\n- 是否存在过长的平淡段落\n- 高潮部分是否紧凑有力\n- 过渡段落是否自然",
    },
    "prose": {
        "name": "文笔",
        "prompt": "请审核文笔质量：\n- 语言是否流畅优美\n- 是否存在重复用词/句式\n- 对话是否自然有辨识度\n- 描写是否生动具体",
    },
    "reader-perspective": {
        "name": "读者视角",
        "prompt": "请从读者角度审核：\n- 开头是否吸引人\n- 信息密度是否合适（不过多不过少）\n- 是否有足够的悬念和钩子\n- 情感共鸣是否到位",
    },
    "grammar": {
        "name": "语法",
        "prompt": "请审核语法和基础质量：\n- 错别字和标点错误\n- 病句和不通顺表达\n- 人称/视角一致性问题\n- 格式规范问题",
    },
}


def build_review_task(dimension: str, content: str, context: str = "") -> str:
    dim = REVIEW_DIMENSIONS.get(dimension, REVIEW_DIMENSIONS["consistency"])
    return (
        f"【审核维度】{dim['name']}\n{dim['prompt']}\n\n"
        f"【上下文】{context or '无'}\n\n【待审核内容】\n{content[:8000]}\n\n"
        f'请输出 JSON 格式结果：\n{{"score": 0-100, "summary": "审核摘要", '
        f'"issues": ["问题1"], "suggestions": ["建议1"], "highlights": ["亮点1"]}}'
    )


REVIEW_JSON_SCHEMA = {
    "type": "json_object",
}
