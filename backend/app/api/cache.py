"""Cache API — 运行时缓存可观测性（J 轮）：命中统计 + 清空"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])


def _caches() -> dict[str, object]:
    """返回 {标签: TTLCache} 集合（延迟导入避免循环依赖）"""
    from app.agents.graphs.supervisor import _classify_cache
    from app.core.knowledge.retriever import _retrieve_cache

    return {"classify": _classify_cache, "retrieve": _retrieve_cache}


@router.get("/stats")
async def cache_stats():
    """各缓存命中/未命中/淘汰统计"""
    return {name: cache.stats() for name, cache in _caches().items()}


@router.post("/clear")
async def clear_caches():
    """清空全部运行时缓存（计数一并清零）"""
    for cache in _caches().values():
        cache.clear()
        cache.reset_stats()
    return {"cleared": True}
