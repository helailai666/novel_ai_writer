"""通用 TTL 缓存 — 供 supervisor 分类 / 知识检索等热点路径复用（H 轮）

线程安全（asyncio 单线程事件循环内亦有并发交叠点，用锁兜底）；
条目数上限 + 惰性过期；缓存值默认深拷贝返回，防调用方污染缓存。
"""

import copy
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class TTLCache:
    """带 TTL 与容量上限的有序缓存（LRU 淘汰）

    J 轮：命中/未命中/淘汰计数（stats() 供可观测性端点）。
    """

    def __init__(self, ttl: float = 300.0, max_entries: int = 1024, copy_on_get: bool = True):
        self.ttl = ttl
        self.max_entries = max(1, max_entries)
        self.copy_on_get = copy_on_get
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _now(self) -> float:
        return time.monotonic()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                self._misses += 1
                return None
            ts, value = item
            if self.ttl > 0 and self._now() - ts > self.ttl:
                del self._data[key]
                self._misses += 1
                self._evictions += 1
                return None
            # LRU 提升
            self._data.move_to_end(key)
            self._hits += 1
        return copy.deepcopy(value) if self.copy_on_get else value

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._data[key] = (self._now(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)
                self._evictions += 1

    def delete(self, key: Any) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def reset_stats(self) -> None:
        """清零计数（保留数据）"""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    def stats(self) -> dict:
        """可观测性统计（不加密钥/值）"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "size": len(self._data),
                "ttl": self.ttl,
                "max_entries": self.max_entries,
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


def memoize_async(ttl: float = 300.0, max_entries: int = 1024):
    """异步函数缓存装饰器 — key 由参数元组（可哈希化）计算

    Args:
        ttl: 缓存秒数（<=0 表示不过期）
        max_entries: 容量上限

    Example:
        @memoize_async(ttl=300)
        async def fetch(q: str) -> dict: ...
    """
    cache: TTLCache = TTLCache(ttl=ttl, max_entries=max_entries)

    def decorator(fn: Callable):
        async def wrapper(*args, **kwargs) -> Any:
            key = _freeze_key(args, kwargs)
            hit = cache.get(key)
            if hit is not None:
                return hit
            value = await fn(*args, **kwargs)
            cache.set(key, value)
            return value

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _freeze_key(args: tuple, kwargs: dict) -> Any:
    """把参数冻结为可哈希 key（list/dict/set 递归转 tuple）"""
    parts = [_freeze(v) for v in args]
    parts.append((tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())),))
    return tuple(parts)


def _freeze(v: Any) -> Any:
    if isinstance(v, dict):
        return tuple(sorted((k, _freeze(x)) for k, x in v.items()))
    if isinstance(v, (list, tuple)):
        return tuple(_freeze(x) for x in v)
    if isinstance(v, set):
        return tuple(sorted(_freeze(x) for x in v))
    return v
