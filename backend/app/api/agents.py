"""Agent API — LangGraph 通用入口（SSE 流式 + 非流式 + 运行记录）"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.agents import events
from app.agents.runner import get_runner
from app.agents.state import NovelState
from app.database import get_db
from app.models.agent_run import AgentRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Schemas ──────────────────────────────────────────────────────

class AgentChatRequest(BaseModel):
    """通用 LangGraph 调用请求"""
    graph: str = Field(..., description="图名: setting / chapter / review")
    project_id: str = Field(..., description="项目ID")
    task: str = Field(default="", description="任务描述")
    kind: Optional[str] = Field(None, description="设定类型 (setting 图)")
    name: Optional[str] = Field(None, description="设定/角色名")
    category: Optional[str] = Field(None, description="类别")
    role: Optional[str] = Field(None, description="角色定位")
    extra: Optional[str] = Field(None, description="额外要求")
    mode: Optional[str] = Field(None, description="章节模式: generate/continue/polish")
    prompt: Optional[str] = Field(None, description="章节提示词")
    style: Optional[str] = Field(None, description="写作风格")
    target_word_count: Optional[int] = Field(None, description="目标字数")
    chapter_id: Optional[str] = Field(None, description="续写/润色章节ID")
    content: Optional[str] = Field(None, description="待审核/润色内容")
    context: Optional[str] = Field(None, description="补充上下文")
    dimensions: Optional[list[str]] = Field(None, description="审核维度列表")
    model: Optional[str] = Field(None, description="供应商/模型覆盖，如 deepseek:deepseek-chat")

    def to_state(self) -> NovelState:
        return {
            "graph": self.graph,
            "project_id": self.project_id,
            "task": self.task,
            "kind": self.kind,
            "name": self.name,
            "category": self.category,
            "role": self.role,
            "extra": self.extra,
            "mode": self.mode,
            "prompt": self.prompt,
            "style": self.style,
            "target_word_count": self.target_word_count,
            "chapter_id": self.chapter_id,
            "content": self.content,
            "context": self.context,
            "dimensions": self.dimensions,
            "model": self.model,
            "settings_snapshot": {},
            "knowledge": [],
            "draft": None,
            "review": {},
            "reviews": [],
            "revision_round": 0,
            "max_revisions": 2,
            "review_threshold": 75,
            "final_output": {},
            "events": [],
            "run_id": None,
        }


class AgentRunResponse(BaseModel):
    id: str
    graph_name: str
    project_id: Optional[str]
    status: str
    input_data: str = ""
    output_data: str = ""
    created_at: str = ""
    updated_at: str = ""


# ── 路由 ─────────────────────────────────────────────────────────

@router.post("/chat")
async def agent_chat(payload: AgentChatRequest):
    """通用 LangGraph 流式入口 — SSE 事件流"""
    runner = get_runner()
    state = payload.to_state()

    async def event_stream():
        try:
            async for ev in runner.astream(payload.graph, state):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"agent_chat stream error: {e}")
            yield f"data: {json.dumps(events.error(str(e)), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/run")
async def agent_run(payload: AgentChatRequest):
    """非流式运行 — 返回 final_output JSON"""
    runner = get_runner()
    return await runner.ainvoke(payload.graph, payload.to_state())


@router.get("/runs", response_model=list[AgentRunResponse])
async def list_runs(
    project_id: Optional[str] = Query(None),
    graph: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """查询图运行记录"""
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc())
    if project_id:
        stmt = stmt.where(AgentRun.project_id == project_id)
    if graph:
        stmt = stmt.where(AgentRun.graph_name == graph)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        AgentRunResponse(
            id=r.id,
            graph_name=r.graph_name,
            project_id=r.project_id,
            status=r.status,
            input_data=r.input_data,
            output_data=r.output_data,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in runs
    ]
