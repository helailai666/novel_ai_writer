"""项目服务 — 项目 CRUD + 导出"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.chapter import Chapter


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


async def _get_or_404(db: AsyncSession, project_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


class ProjectService:
    """项目服务"""

    @staticmethod
    async def create(db: AsyncSession, data: dict) -> dict:
        project = Project(**data)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        return _to_response(project)

    @staticmethod
    async def list(db: AsyncSession, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict]:
        stmt = select(Project).order_by(desc(Project.updated_at))
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await db.execute(stmt)
        return [_to_response(p) for p in result.scalars().all()]

    @staticmethod
    async def get(db: AsyncSession, project_id: str) -> dict:
        return _to_response(await _get_or_404(db, project_id))

    @staticmethod
    async def update(db: AsyncSession, project_id: str, data: dict) -> dict:
        project = await _get_or_404(db, project_id)
        for k, v in data.items():
            setattr(project, k, v)
        await db.flush()
        await db.refresh(project)
        return _to_response(project)

    @staticmethod
    async def delete(db: AsyncSession, project_id: str) -> None:
        project = await _get_or_404(db, project_id)
        await db.delete(project)
        await db.flush()

    @staticmethod
    async def export(db: AsyncSession, project_id: str, format: str = "md") -> tuple[str, str]:
        """导出小说 — 返回 (content, filename)"""
        project = await _get_or_404(db, project_id)
        result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()

        lines = [
            f"# {project.title}",
            "",
            f"> 类型: {project.genre}  |  简介: {project.synopsis or '无'}",
            "",
            "---",
            "",
        ]
        for ch in chapters:
            lines += [
                f"## 第{ch.chapter_number}章 {ch.title or ''}",
                "",
                ch.content or "(内容待生成)",
                "",
                "---",
                "",
            ]
        return "\n".join(lines), f"{project.title}.{format}"
