"""依赖注入 — FastAPI Depends 提供跨层依赖

P1 阶段提供 legacy Agent 工厂依赖；P2+ 起扩展为 LLM 供应商 / 工具注册表 / 图运行器等。
"""

from typing import AsyncIterator

from app.services.agent_factory import (
    get_creative_agent,
    get_writer_agent,
    get_review_agent,
    get_search_agent,
)


def get_creative() -> "CreativeAgent":
    return get_creative_agent()


def get_writer(streaming: bool = False) -> "WriterAgent":
    return get_writer_agent(streaming=streaming)


def get_reviewer() -> "ReviewAgent":
    return get_review_agent()


def get_searcher() -> "SearchAgent":
    return get_search_agent()
