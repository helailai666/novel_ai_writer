"""Agent 工具循环 — ReAct 式：LLM 自主决定调用工具或产出最终文本

- 最多 max_iters 轮；每轮调用 LLM（绑定工具白名单）
- 工具调用 → tool_call / tool_result 事件（SSE 可见）
- 工具执行经全局注册表（含超时/异常兜底）
"""

import logging
from typing import Awaitable, Callable, Optional

from app.agents import events
from app.core.llm import LLMMessage, LLMRequest, LLMProvider
from app.core.tools.base import BaseTool
from app.core.tools.registry import get_registry

logger = logging.getLogger(__name__)


async def run_tool_loop(
    llm: LLMProvider,
    system: str,
    user: str,
    tools: list[BaseTool],
    emit: Optional[Callable[[dict], Awaitable[None]]] = None,
    max_iters: int = 5,
) -> tuple[list[LLMMessage], str]:
    """执行工具循环，返回 (消息历史含工具上下文, 最终文本)

    emit: 事件回调（tool_call / tool_result），可为 None
    """
    registry = get_registry()
    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]
    specs = [t.to_spec() for t in tools]
    final_text = ""

    async def _emit(ev: dict):
        if emit:
            await emit(ev)

    for _ in range(max_iters):
        resp = await llm.acomplete(LLMRequest(messages=messages, tools=specs, tool_choice="auto"))
        if not resp.tool_calls:
            final_text = resp.content
            break
        # 记录 assistant 的工具调用意图
        messages.append(
            LLMMessage(role="assistant", content="", tool_calls=[tc.model_dump() for tc in resp.tool_calls])
        )
        for tc in resp.tool_calls:
            await _emit(events.tool_call(tc.name, tc.arguments))
            result = await registry.execute(tc.name, tc.arguments)
            await _emit(events.tool_result(tc.name, result.summary, result.ok))
            messages.append(
                LLMMessage(role="tool", tool_call_id=tc.id, content=result.content or result.error)
            )
    else:
        logger.warning("工具循环达到最大轮次，未产出最终文本")

    return messages, final_text


def resolve_tools(names: list[str]) -> list[BaseTool]:
    """按白名单解析工具实例（跳过未注册的，容忍 P4 前的占位缺失）"""
    registry = get_registry()
    return [t for t in (registry.get(n) for n in names) if t is not None]
