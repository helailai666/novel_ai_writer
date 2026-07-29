"""项目管理 API — CRUD"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel, Field

from fastapi.responses import PlainTextResponse

from app.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Pydantic Schemas ─────────────────────────────────────────────

class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    genre: str = Field(default="fantasy", max_length=50)
    synopsis: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    genre: Optional[str] = Field(None, max_length=50)
    synopsis: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, max_length=20)


class ProjectResponse(BaseModel):
    id: str
    title: str
    genre: str
    synopsis: str
    status: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────

@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建新项目"""
    project = Project(**payload.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return _to_response(project)


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表"""
    stmt = select(Project).order_by(desc(Project.updated_at))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return [_to_response(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个项目"""
    project = await _get_or_404(project_id, db)
    return _to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    """更新项目"""
    project = await _get_or_404(project_id, db)
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, val)
    await db.flush()
    await db.refresh(project)
    return _to_response(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """删除项目（级联删除所有关联数据）"""
    project = await _get_or_404(project_id, db)
    await db.delete(project)
    await db.flush()


@router.get("/{project_id}/export")
async def export_project(project_id: str, format: str = Query("md", regex="^(md|txt)$"), db: AsyncSession = Depends(get_db)):
    """导出小说为 Markdown 或纯文本"""
    project = await _get_or_404(project_id, db)

    # 获取所有章节
    from sqlalchemy import select as sa_select
    stmt = sa_select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    result = await db.execute(stmt)
    chapters = result.scalars().all()

    lines = []
    lines.append(f"# {project.title}")
    lines.append(f"")
    lines.append(f"> 类型: {project.genre}  |  简介: {project.synopsis or '无'}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for ch in chapters:
        lines.append(f"## 第{ch.chapter_number}章 {ch.title or ''}")
        lines.append(f"")
        lines.append(ch.content or "(内容待生成)")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    content = "\n".join(lines)
    filename = f"{project.title}.{format}"

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Helpers ──────────────────────────────────────────────────────

async def _get_or_404(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_response(p: Project) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "genre": p.genre,
        "synopsis": p.synopsis,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }
