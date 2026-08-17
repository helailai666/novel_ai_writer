"""图事件协议 — LangGraph 节点事件 → SSE 类型化事件

事件类型（与前端 StreamOutput 消费协议一致）：
- node_start / node_end   节点生命周期
- token                   流式正文（writer 节点）
- tool_call / tool_result 工具调用（P3 启用）
- review                  审核维度分数
- checkpoint              重写循环状态
- done / error            终态
"""

import time
from typing import Any, Optional


def _ts() -> float:
    return time.time()


def node_start(node: str) -> dict:
    return {"type": "node_start", "node": node, "ts": _ts()}


def node_end(node: str) -> dict:
    return {"type": "node_end", "node": node, "ts": _ts()}


def token(text: str) -> dict:
    return {"type": "token", "text": text}


def tool_call(tool: str, args: dict) -> dict:
    return {"type": "tool_call", "tool": tool, "args": args}


def tool_result(tool: str, summary: str, ok: bool = True) -> dict:
    return {"type": "tool_result", "tool": tool, "summary": summary[:500], "ok": ok}


def review(dimension: str, score: int, detail: Optional[dict] = None) -> dict:
    ev = {"type": "review", "dimension": dimension, "score": score}
    if detail:
        ev["detail"] = detail
    return ev


def checkpoint(round: int, status: str) -> dict:
    """status: rewrite / approved"""
    return {"type": "checkpoint", "round": round, "status": status}


def done(result: dict, run_id: Optional[str] = None) -> dict:
    ev: dict[str, Any] = {"type": "done", "result": result}
    if run_id:
        ev["run_id"] = run_id
    return ev


def error(message: str) -> dict:
    return {"type": "error", "message": str(message)[:1000]}
