"""M8 场景/地点模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="city")
    description: Mapped[str] = mapped_column(Text, default="")
    climate: Mapped[str] = mapped_column(String(100), default="")
    notable_features: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship(back_populates="locations")
    children: Mapped[list["Location"]] = relationship("Location", back_populates="parent", remote_side="Location.id", cascade="all, delete-orphan")
