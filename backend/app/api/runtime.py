"""Runtime API — 脱敏后的有效运行时配置（J 轮，供前端只读展示）"""

import logging

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/config")
async def runtime_config():
    """当前生效配置（不含任何密钥）"""
    return {
        "llm": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "has_api_key": bool(settings.llm.api_key),
            "streaming": settings.llm.streaming,
        },
        "search": {
            "provider": settings.search.provider,
            "cache_ttl": settings.search.cache_ttl,
        },
        "embedding": {
            "provider": settings.embedding.provider,
            "model": settings.embedding.model,
        },
        "vector_store": {
            "backend": settings.vector_store.backend,
            "persist_dir": settings.vector_store.persist_dir,
        },
        "mcp": {
            "enabled": settings.mcp.enabled,
            "servers_file": settings.mcp.servers_file,
            "default_pool_size": settings.mcp.default_pool_size,
            "default_connect_timeout": settings.mcp.default_connect_timeout,
            "default_max_retries": settings.mcp.default_max_retries,
        },
        "agent": {
            "max_revisions": settings.agent.max_revisions,
            "review_threshold": settings.agent.review_threshold,
            "persist_runs": settings.agent.persist_runs,
            "llm_supervisor": settings.agent.llm_supervisor,
            "llm_supervisor_cache": settings.agent.llm_supervisor_cache,
            "llm_supervisor_cache_ttl": settings.agent.llm_supervisor_cache_ttl,
            "knowledge_cache": settings.agent.knowledge_cache,
            "knowledge_cache_ttl": settings.agent.knowledge_cache_ttl,
        },
        "skills": {"dirs": settings.skills.dirs},
    }
