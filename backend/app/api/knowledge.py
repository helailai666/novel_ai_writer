"""知识库 API — 文档 CRUD / 上传摄取 / 检索"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ── Schemas ──────────────────────────────────────────────────────

class KnowledgeDocCreate(BaseModel):
    title: str = Field(..., max_length=300)
    content: str = Field(..., description="文档内容")
    category: str = Field(default="general", max_length=50)
    tags: str = Field(default="", max_length=500)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    top_k: int = Field(5, ge=1, le=20)
    categories: Optional[list[str]] = None
    include_memes: bool = True


# ── 路由 ─────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_doc(payload: KnowledgeDocCreate, project_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    """创建知识文档（project_id 缺省=全局）"""
    return await KnowledgeService.create_doc(db, payload.model_dump(), project_id=project_id)


@router.post("/ingest")
async def ingest_text(
    title: str = Query(..., max_length=300),
    content: str = Query(...),
    category: str = Query("general"),
    tags: str = Query(""),
    project_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """文本摄取（自动切片+向量化）"""
    return await KnowledgeService.ingest_text(db, title, content, category, tags, project_id)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """上传 txt/md 文件摄取"""
    raw = await file.read()
    return await KnowledgeService.ingest_file(db, file.filename or "doc.txt", raw, project_id)


@router.get("")
async def list_docs(
    project_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await KnowledgeService.list_docs(db, project_id, category, limit, offset)


@router.get("/{doc_id}")
async def get_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    return await KnowledgeService.get_doc(db, doc_id)


@router.delete("/{doc_id}", status_code=204)
async def delete_doc(doc_id: str, db: AsyncSession = Depends(get_db)):
    await KnowledgeService.delete_doc(db, doc_id)


@router.post("/search")
async def search(payload: KnowledgeSearchRequest, project_id: Optional[str] = Query(None)):
    """混合检索（关键词 ∪ 向量）"""
    return await KnowledgeService.search(
        payload.query, project_id, payload.top_k, payload.categories, payload.include_memes
    )
