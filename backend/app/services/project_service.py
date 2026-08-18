"""项目服务 — 项目 CRUD + 导出 + JSON 导入还原"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.faction import Faction
from app.models.foreshadow import Foreshadow
from app.models.hot_meme import HotMeme
from app.models.item import Item
from app.models.knowledge_doc import KnowledgeDoc
from app.models.location import Location
from app.models.outline import Outline
from app.models.skill import Skill
from app.models.timeline import Timeline
from app.models.volume import Volume
from app.models.world_setting import WorldSetting

logger = logging.getLogger(__name__)

# N 轮：JSON 导入还原的表（与 export_json 对应；知识 doc 单独走 ingest 重建切块）
# 顺序即插入顺序：被引用的表（volumes/chapters）在前，foreshadows 最后（引用章节）
_IMPORT_TABLES: list[tuple[str, type]] = [
    ("volumes", Volume),
    ("chapters", Chapter),
    ("characters", Character),
    ("items", Item),
    ("skills", Skill),
    ("factions", Faction),
    ("locations", Location),
    ("outlines", Outline),
    ("world_settings", WorldSetting),
    ("timelines", Timeline),
    ("hot_memes", HotMeme),
    ("foreshadows", Foreshadow),
]

# 跨表引用重映射：{目标表: {字段: 源表}}
_REMAP = {
    "chapters": {"volume_id": "volumes"},
    "foreshadows": {"plant_chapter_id": "chapters", "reveal_chapter_id": "chapters"},
}


def _to_response(p: Project) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "genre": p.genre,
        "synopsis": p.synopsis,
        "status": p.status,
        "skill_packs": p.skill_packs or "",
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
    async def import_json(db: AsyncSession, backup: dict) -> dict:
        """从 JSON 备份还原项目（N 轮）

        - 项目元信息重建；创作表生成新 id 并维护 old→new 映射，
          跨表引用（chapters.volume_id、foreshadows.*_chapter_id）经 _REMAP 重映射
        - 知识文档走 KnowledgeService.ingest 重建切块与向量
        """
        proj = backup.get("project") or {}
        if not proj.get("title"):
            raise HTTPException(status_code=400, detail="备份缺少 project.title")
        project = Project(
            title=proj["title"][:200],
            genre=proj.get("genre") or "fantasy",
            synopsis=proj.get("synopsis") or "",
            status=proj.get("status") or "draft",
            skill_packs=proj.get("skill_packs") or "",
        )
        db.add(project)
        await db.flush()
        pid = project.id
        id_maps: dict[str, dict[str, str]] = {key: {} for key, _ in _IMPORT_TABLES}
        for key, model in _IMPORT_TABLES:
            remap = _REMAP.get(key) or {}
            for row in backup.get(key) or []:
                if not isinstance(row, dict):
                    continue
                fields = {
                    c.name: row[c.name]
                    for c in model.__table__.columns
                    if c.name in row and c.name not in ("id", "project_id", "created_at", "updated_at")
                }
                for field, src_table in remap.items():
                    ref = fields.get(field)
                    if ref and ref in id_maps.get(src_table, {}):
                        fields[field] = id_maps[src_table][ref]
                old_id = row.get("id")
                obj = model(project_id=pid, **fields)
                db.add(obj)
                await db.flush()
                if old_id:
                    id_maps[key][str(old_id)] = obj.id
        # 知识文档：重建切块与向量
        from app.services.knowledge_service import KnowledgeService

        for d in backup.get("knowledge_docs") or []:
            if not isinstance(d, dict) or not d.get("title"):
                continue
            try:
                await KnowledgeService.ingest_text(
                    db, d["title"], d.get("content") or "",
                    category=d.get("category") or "general",
                    tags=d.get("tags") or "", project_id=pid,
                )
            except Exception as e:
                logger.warning(f"导入知识文档失败（跳过）: {e}")
        await db.commit()
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
        """导出小说 — 返回 (content, filename)

        md/txt: 章节串联；json: 全量备份（项目 + 全部创作表，L 轮）
        """
        if format == "json":
            return await ProjectService.export_json(db, project_id)
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

    @staticmethod
    async def export_json(db: AsyncSession, project_id: str) -> tuple[str, str]:
        """全量 JSON 备份：项目元信息 + 卷/章节/全部设定/伏笔/知识库/热梗（L 轮）

        知识块不随导出（可据 doc 内容重建）；时间字段序列化为 ISO 字符串。
        """
        project = await _get_or_404(db, project_id)
        data: dict = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "version": 1,
            "project": _to_response(project),
        }
        model_groups: list[tuple[str, type]] = [
            ("volumes", Volume),
            ("chapters", Chapter),
            ("characters", Character),
            ("items", Item),
            ("skills", Skill),
            ("factions", Faction),
            ("locations", Location),
            ("outlines", Outline),
            ("world_settings", WorldSetting),
            ("foreshadows", Foreshadow),
            ("knowledge_docs", KnowledgeDoc),
            ("hot_memes", HotMeme),
        ]
        for key, model in model_groups:
            result = await db.execute(
                select(model).where(model.project_id == project_id).order_by(model.created_at)
            )
            rows = result.scalars().all()
            data[key] = [_row_to_dict(r) for r in rows]
        return json.dumps(data, ensure_ascii=False, indent=2), f"{project.title}.json"


def _row_to_dict(row) -> dict:
    """ORM 行 → dict（datetime 序列化为 ISO 字符串）"""
    out: dict = {}
    for c in row.__table__.columns:
        v = getattr(row, c.name)
        if isinstance(v, datetime):
            v = v.isoformat()
        out[c.name] = v
    return out
