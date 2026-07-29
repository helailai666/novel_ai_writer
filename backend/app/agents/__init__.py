"""AI Agent 模块 — LangChain Agent 实现"""

from app.agents.agent_base import (
    BaseAgent,
    AgentConfig,
    AgentResult,
    PromptTemplate,
    CREATIVE_SYSTEM,
    WRITER_SYSTEM,
    REVIEWER_SYSTEM,
    SEARCH_SYSTEM,
)
from app.agents.creative_agent import CreativeAgent
from app.agents.writer_agent import WriterAgent
from app.agents.review_agent import ReviewAgent
from app.agents.search_agent import SearchAgent

__all__ = [
    # 基类
    "BaseAgent",
    "AgentConfig",
    "AgentResult",
    "PromptTemplate",
    # 系统提示词
    "CREATIVE_SYSTEM",
    "WRITER_SYSTEM",
    "REVIEWER_SYSTEM",
    "SEARCH_SYSTEM",
    # 子 Agent
    "CreativeAgent",
    "WriterAgent",
    "ReviewAgent",
    "SearchAgent",
]
