"""Agent API — LangGraph 通用入口（SSE 流式 + 非流式 + 运行记录）"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
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
    skills: Optional[list[str]] = Field(None, description="启用的技能包名列表")
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
            "skills": self.skills,
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
    summary: str = ""
    input_data: str = ""
    output_data: str = ""
    duration_seconds: float = 0.0
    created_at: str = ""
    updated_at: str = ""


def _run_summary(output_data: str) -> str:
    """从 output_data 提取摘要（content 前缀 / error）"""
    if not output_data:
        return ""
    try:
        data = json.loads(output_data)
    except Exception:
        return output_data[:120]
    if isinstance(data, dict):
        if data.get("error"):
            return f"错误: {str(data['error'])[:120]}"
        content = data.get("content") or ""
        if content:
            return str(content)[:120]
    return output_data[:120]


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
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """查询图运行记录（列表视图：不含完整事件时间线）"""
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc())
    if project_id:
        stmt = stmt.where(AgentRun.project_id == project_id)
    if graph:
        stmt = stmt.where(AgentRun.graph_name == graph)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        AgentRunResponse(
            id=r.id,
            graph_name=r.graph_name,
            project_id=r.project_id,
            status=r.status,
            summary=_run_summary(r.output_data),
            duration_seconds=_run_duration(r),
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in runs
    ]


def _run_duration(r) -> float:
    """运行时长（秒）；running 状态按当前时间估算"""
    end = r.updated_at or r.created_at
    if r.status == "running":
        import datetime

        end = datetime.datetime.utcnow()
    if not r.created_at or not end:
        return 0.0
    return round((end - r.created_at).total_seconds(), 2)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """运行记录详情：输入/输出 + 压缩事件时间线（G4 可视化）"""
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    parsed: dict = {}
    if run.events_data:
        try:
            parsed = json.loads(run.events_data)
        except Exception:
            parsed = {}
    return {
        "id": run.id,
        "graph_name": run.graph_name,
        "project_id": run.project_id,
        "status": run.status,
        "summary": _run_summary(run.output_data),
        "input_data": run.input_data,
        "output_data": run.output_data,
        "duration_seconds": _run_duration(run),
        "created_at": run.created_at.isoformat() if run.created_at else "",
        "updated_at": run.updated_at.isoformat() if run.updated_at else "",
        "events": parsed.get("events", []),
        "token_counts": parsed.get("token_counts", {}),
        "total_tokens": parsed.get("total_tokens", 0),
    }


# ── I4 运行记录清理 ──────────────────────────────────────────────

@router.delete("/runs", status_code=200)
async def clear_runs(
    project_id: Optional[str] = Query(None),
    graph: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """按项目/图清空运行记录（必须限定 project_id 或 graph，防误清全库）"""
    if not project_id and not graph:
        raise HTTPException(status_code=400, detail="必须提供 project_id 或 graph 限定范围")
    stmt = delete(AgentRun)
    if project_id:
        stmt = stmt.where(AgentRun.project_id == project_id)
    if graph:
        stmt = stmt.where(AgentRun.graph_name == graph)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount}


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """删除单条运行记录"""
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    await db.delete(run)
    await db.commit()
