"""M9 时间线模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class Timeline(Base):
    __tablename__ = "timelines"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(String(300), nullable=False)
    era: Mapped[str] = mapped_column(String(100), default="present")
    event_date: Mapped[str] = mapped_column(String(100), default="")
    sort_order: Mapped[int] = mapped_column(default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    involved_characters: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship(back_populates="timelines")
