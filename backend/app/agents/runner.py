"""GraphRunner — 图运行器：astream 事件桥接 + agent_runs 入库

事件流协议（SSE）：
- 节点自行产出 node_start / token / review / node_end 等事件（state.events）
- runner 只做中继，并在图结束后产出 done / error 终态
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

from langgraph.graph.state import CompiledStateGraph

from app.agents import events
from app.agents.state import NovelState
from app.config import settings

logger = logging.getLogger(__name__)

# 图实例缓存（graphs/__init__ 填充）
_graph_cache: dict[str, CompiledStateGraph] = {}


class GraphRunner:
    """LangGraph 运行器"""

    def __init__(self):
        self.persist_runs = settings.agent.persist_runs
        self._final: dict = {}

    # ── 运行 ────────────────────────────────────────────────────

    async def astream(self, graph_name: str, state: NovelState) -> AsyncIterator[dict]:
        """流式运行图，逐事件产出（SSE 消费）"""
        from app.agents.graphs import get_graph

        app = get_graph(graph_name)
        run_id = None
        if self.persist_runs:
            run_id = await self._create_run(graph_name, state)

        final: dict = {}
        try:
            async for mode, chunk in app.astream(state, stream_mode=["updates"]):
                if mode != "updates" or not chunk:
                    continue
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    if update.get("final_output"):
                        final = update["final_output"]
                    for ev in update.get("events") or []:
                        yield ev
            # 终态
            yield events.done(final or {}, run_id)
            if self.persist_runs and run_id:
                await self._finish_run(run_id, final, status="completed")
        except Exception as e:
            logger.error(f"graph '{graph_name}' run failed: {e}")
            yield events.error(str(e))
            if self.persist_runs and run_id:
                await self._finish_run(run_id, {"error": str(e)}, status="failed")
            return

    async def ainvoke(self, graph_name: str, state: NovelState) -> dict:
        """非流式运行，返回 final_output（含错误兜底）"""
        result: dict = {"content": "", "is_mock": True, "error": ""}
        async for ev in self.astream(graph_name, state):
            if ev.get("type") == "done":
                result = ev.get("result") or result
            if ev.get("type") == "error":
                result["error"] = ev.get("message", "")
        return result

    # ── agent_runs 持久化 ───────────────────────────────────────

    async def _create_run(self, graph_name: str, state: NovelState) -> Optional[str]:
        try:
            from app.models.agent_run import AgentRun
            from app.database import async_session_factory

            async with async_session_factory() as db:
                run = AgentRun(
                    graph_name=graph_name,
                    project_id=state.get("project_id"),
                    status="running",
                    input_data=json.dumps({k: v for k, v in state.items() if k != "events"}, ensure_ascii=False, default=str),
                )
                db.add(run)
                await db.flush()
                await db.refresh(run)
                await db.commit()
                return run.id
        except Exception as e:
            logger.warning(f"create agent_run failed: {e}")
            return None

    async def _finish_run(self, run_id: str, final: dict, status: str) -> None:
        try:
            from sqlalchemy import select

            from app.models.agent_run import AgentRun
            from app.database import async_session_factory

            async with async_session_factory() as db:
                result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
                run = result.scalar_one_or_none()
                if run:
                    run.status = status
                    run.output_data = json.dumps(final, ensure_ascii=False, default=str)
                    await db.commit()
        except Exception as e:
            logger.warning(f"finish agent_run failed: {e}")


_runner: Optional[GraphRunner] = None


def get_runner() -> GraphRunner:
    """全局单例 Runner"""
    global _runner
    if _runner is None:
        _runner = GraphRunner()
    return _runner
