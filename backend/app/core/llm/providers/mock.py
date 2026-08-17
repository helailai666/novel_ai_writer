"""Mock LLM 适配器 — 无 API Key 时的确定性降级（结构化输出 / 工具调用 / 流式全支持）

用于开发与测试：无网络、无成本、行为可预测。
"""

import json
import re
from typing import AsyncIterator, Optional

from app.core.llm.base import LLMProvider
from app.core.llm.schemas import LLMRequest, LLMResponse

_WELCOME = (
    "【Mock 生成 — 未配置 LLM API Key】\n\n"
    "请设置环境变量 LLM_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY 等以启用真实 AI 生成。\n"
    "当前支持: openai / deepseek / ollama / azure / anthropic / gemini / qwen / glm / kimi"
)


class MockProvider(LLMProvider):
    """确定性 Mock：根据请求内容返回占位文本"""

    provider_name = "mock"

    def __init__(self, model: str = "mock", api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, api_base, **kwargs)

    def _compose(self, req: LLMRequest) -> str:
        # 结构化输出：生成与 schema 形状匹配的 JSON
        if req.response_format and req.response_format.get("type") == "json_object":
            return json.dumps(
                {"score": 82, "summary": "[Mock] 审核结果 — 配置 LLM API Key 后获取真实 AI 审核",
                 "issues": ["[Mock] 建议检查角色行为一致性"], "suggestions": ["[Mock] 加强主角性格刻画"],
                 "highlights": ["[Mock] 对话自然流畅"], "dimension_scores": {"consistency": 85}},
                ensure_ascii=False,
            )
        last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        task = re.sub(r"\s+", " ", last_user)[:200]
        return f"{_WELCOME}\n\n任务: {task}"

    async def acomplete(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(content=self._compose(req), usage={"mock": True}, is_mock=True)

    async def astream(self, req: LLMRequest) -> AsyncIterator[str]:
        content = self._compose(req)
        for word in content:
            yield word
        # 流式末尾补一个换行（模拟真实流）
        yield "\n"

    def bind_tools(self, tools: list[dict]):
        return self

    def with_structured(self, schema: dict):
        return self
