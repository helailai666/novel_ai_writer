"""LLM 供应商工厂 — 注册表驱动，支持全局默认 + 显式覆盖"""

import logging
from typing import Optional

from app.config import settings
from app.core.llm.base import LLMProvider
from app.core.llm.schemas import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# ── 供应商注册表 ──────────────────────────────────────────────────

# 提供商名 → (适配器类, 默认模型, 环境变量 Key)
_REGISTRY: dict[str, tuple[type, str, str]] = {}


def register(provider: str, cls: type, default_model: str = "", env_key: str = ""):
    _REGISTRY[provider] = (cls, default_model, env_key)


def _register_defaults():
    from app.core.llm.providers.openai_compat import OpenAICompatProvider
    from app.core.llm.providers.mock import MockProvider
    from app.core.llm.providers.specialized import (
        AnthropicProvider,
        AzureProvider,
        GeminiProvider,
        OllamaProvider,
    )

    register("openai", OpenAICompatProvider, "gpt-4o-mini", "OPENAI_API_KEY")
    register("deepseek", OpenAICompatProvider, "deepseek-chat", "DEEPSEEK_API_KEY")
    register("qwen", OpenAICompatProvider, "qwen-plus", "DASHSCOPE_API_KEY")
    register("glm", OpenAICompatProvider, "glm-4-plus", "ZHIPU_API_KEY")
    register("kimi", OpenAICompatProvider, "moonshot-v1-8k", "MOONSHOT_API_KEY")
    register("ollama", OllamaProvider, "qwen2.5:7b", "")
    register("anthropic", AnthropicProvider, "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY")
    register("gemini", GeminiProvider, "gemini-2.0-flash", "GEMINI_API_KEY")
    register("azure", AzureProvider, "gpt-4o", "AZURE_OPENAI_API_KEY")
    register("mock", MockProvider, "mock", "")


_register_defaults()


def get_env_key(provider: str) -> str:
    return _REGISTRY.get(provider, ("", "", ""))[2]


def list_providers() -> list[dict]:
    """供应商列表（供设置页展示与连通性测试）"""
    return [
        {"name": name, "default_model": default_model}
        for name, (_, default_model, _) in _REGISTRY.items()
    ]


def _resolve_key(provider: str, explicit_key: Optional[str]) -> Optional[str]:
    """解析 API Key：显式 > 环境变量 > settings"""
    if explicit_key:
        return explicit_key
    env_key = get_env_key(provider)
    if env_key:
        import os

        val = os.getenv(env_key)
        if val:
            return val
    # 通用兜底
    if settings.LLM_API_KEY:
        return settings.LLM_API_KEY
    return None


def create(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    **kwargs,
) -> LLMProvider:
    """创建 LLM 供应商实例

    Args:
        provider: 供应商名（默认 settings.llm.provider）
        model: 模型名（默认 settings.llm.model）
        api_key / api_base: 显式覆盖
    """
    name = provider or settings.llm.provider or "openai"
    cls, default_model, _ = _REGISTRY.get(name, (None, "", ""))
    if cls is None:
        logger.warning(f"未知供应商 '{name}'，回退 mock")
        name = "mock"
        cls = _REGISTRY["mock"][0]

    resolved_model = model or settings.llm.model or default_model
    resolved_key = _resolve_key(name, api_key)

    # 无 Key 且非本地/非 mock → 自动降级 mock
    if not resolved_key and name not in ("ollama", "mock"):
        logger.warning(f"⚠️  供应商 '{name}' 无 API Key，降级到 Mock 模式")
        return _REGISTRY["mock"][0](model=resolved_model)

    api_base = api_base or (settings.llm.api_base if name in ("openai", "deepseek", "qwen", "glm", "kimi") else None)

    instance = cls(
        model=resolved_model,
        api_key=resolved_key,
        api_base=api_base,
        **kwargs,
    )
    logger.info(f"✅ LLM provider: {name} / {resolved_model} / base={api_base or 'default'}")
    return instance


def create_for(provider: str, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs) -> LLMProvider:
    """显式指定供应商/模型创建（请求级覆盖用，忽略全局降级）"""
    name = provider or "mock"
    cls, default_model, _ = _REGISTRY.get(name, (_REGISTRY["mock"][0], "", ""))
    return cls(
        model=model or default_model,
        api_key=api_key or _resolve_key(name, None),
        api_base=api_base,
        **kwargs,
    )
