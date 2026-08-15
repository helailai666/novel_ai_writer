"""M10 伏笔模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class Foreshadow(Base):
    __tablename__ = "foreshadows"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    plant_chapter_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    reveal_chapter_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planted")
    related_characters: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship(back_populates="foreshadows")
