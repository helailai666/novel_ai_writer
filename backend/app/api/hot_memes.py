"""热梗 API — 热梗 CRUD + 检索"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/hot-memes", tags=["hot-memes"])


class HotMemeCreate(BaseModel):
    phrase: str = Field(..., max_length=100)
    meaning: str = ""
    usage_example: str = ""
    category: str = Field(default="general", max_length=50)
    tags: str = Field(default="", max_length=300)
    popularity: int = Field(0, ge=0)


class HotMemeUpdate(BaseModel):
    """热梗更新（全字段可选，仅提交的字段生效）"""

    phrase: Optional[str] = Field(None, max_length=100)
    meaning: Optional[str] = None
    usage_example: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[str] = Field(None, max_length=300)
    popularity: Optional[int] = Field(None, ge=0)


@router.post("", status_code=201)
async def create_meme(payload: HotMemeCreate, project_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return await KnowledgeService.create_meme(db, payload.model_dump(), project_id=project_id)


@router.get("")
async def list_memes(
    project_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await KnowledgeService.list_memes(db, project_id, category, limit, offset)


@router.get("/search")
async def search_memes(q: str = Query(..., min_length=1), project_id: Optional[str] = Query(None), limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    return await KnowledgeService.search_memes(db, q, project_id, limit)


@router.delete("/{meme_id}", status_code=204)
async def delete_meme(meme_id: str, db: AsyncSession = Depends(get_db)):
    await KnowledgeService.delete_meme(db, meme_id)


@router.put("/{meme_id}")
async def update_meme(meme_id: str, payload: HotMemeUpdate, db: AsyncSession = Depends(get_db)):
    """更新热梗（检索缓存失效）"""
    return await KnowledgeService.update_meme(db, meme_id, payload.model_dump(exclude_unset=True))
