"""Agent 工厂 — 统一各 API 层的 Agent 构造（P2 将替换为 core/llm 工厂 + LangGraph）

集中管理 legacy Agent 的构造参数，消除各 router 中重复的 _get_*_agent()。
"""

from app.config import settings
from app.agents.creative_agent import CreativeAgent
from app.agents.writer_agent import WriterAgent
from app.agents.review_agent import ReviewAgent
from app.agents.search_agent import SearchAgent


def _llm_kwargs(streaming: bool = False) -> dict:
    """从全局配置构造 legacy Agent 的 LLM 参数"""
    return {
        "llm_provider": settings.llm.provider or "openai",
        "model": settings.llm.model or settings.LLM_MODEL,
        "api_key": settings.llm.api_key or settings.LLM_API_KEY or "",
        "api_base": settings.llm.api_base or settings.LLM_API_BASE,
        "streaming": streaming,
    }


def get_creative_agent() -> CreativeAgent:
    return CreativeAgent(**_llm_kwargs())


def get_writer_agent(streaming: bool = False) -> WriterAgent:
    return WriterAgent(**_llm_kwargs(streaming=streaming))


def get_review_agent() -> ReviewAgent:
    return ReviewAgent(**_llm_kwargs())


def get_search_agent() -> SearchAgent:
    return SearchAgent(**_llm_kwargs())
