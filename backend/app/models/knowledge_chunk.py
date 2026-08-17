"""M15 KnowledgeChunk — 知识文档切片（向量化单元）"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("knowledge_docs.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[str] = mapped_column(Text, default="")  # JSON: {project_id, title, category, tags, source}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    doc: Mapped["KnowledgeDoc"] = relationship(back_populates="chunks")
