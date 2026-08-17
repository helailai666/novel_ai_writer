"""模型供应商 API — 供应商列表 + 连通性测试"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm import LLMMessage, create_for, list_providers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/model-providers", tags=["model-providers"])


class ProviderTestRequest(BaseModel):
    provider: str = Field(..., description="供应商名")
    model: str = Field("", description="模型名（空则用默认）")
    api_key: str = Field("", description="API Key（空则用环境变量）")
    api_base: str = Field("", description="API Base（空则用默认）")


@router.get("")
async def get_providers():
    """供应商列表 + 当前配置"""
    return {
        "providers": list_providers(),
        "current": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "api_base": settings.llm.api_base,
            "has_api_key": bool(settings.llm.api_key),
        },
    }


@router.post("/test")
async def test_provider(payload: ProviderTestRequest):
    """连通性测试：向供应商发一条极短请求"""
    try:
        llm = create_for(
            provider=payload.provider,
            model=payload.model or None,
            api_key=payload.api_key or None,
            api_base=payload.api_base or None,
            max_tokens=16,
        )
        resp = await llm.acomplete(
            LLMMessageRequest([LLMMessage(role="user", content="ping")])
        )
        return {"ok": True, "reply": resp.content[:100], "is_mock": resp.is_mock}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def LLMMessageRequest(messages, max_tokens=16):
    """构造 LLMRequest（延迟导入）"""
    from app.core.llm import LLMRequest

    return LLMRequest(messages=messages, max_tokens=max_tokens)
