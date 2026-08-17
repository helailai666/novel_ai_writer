"""项目管理 API — CRUD + 导出（薄层，逻辑在 ProjectService）"""

from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from fastapi.responses import PlainTextResponse

from app.database import get_db
from app.services.project_service import ProjectService

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
    skill_packs: Optional[str] = Field(None, max_length=300, description="逗号分隔的技能包名")


class ProjectResponse(BaseModel):
    id: str
    title: str
    genre: str
    synopsis: str
    status: str
    skill_packs: str = ""
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────

@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建新项目"""
    return await ProjectService.create(db, payload.model_dump())


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表"""
    return await ProjectService.list(db, status, limit, offset)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个项目"""
    return await ProjectService.get(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    """更新项目"""
    return await ProjectService.update(db, project_id, payload.model_dump(exclude_unset=True))


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """删除项目（级联删除所有关联数据）"""
    await ProjectService.delete(db, project_id)


@router.get("/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = Query("md", pattern="^(md|txt)$"),
    db: AsyncSession = Depends(get_db),
):
    """导出小说为 Markdown 或纯文本"""
    content, filename = await ProjectService.export(db, project_id, format)
    # RFC 5987: 中文文件名走 filename*，ASCII 回退防旧客户端
    ascii_name = filename.encode("ascii", "ignore").decode() or f"novel.{format}"
    disposition = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
    )
    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": disposition},
    )
