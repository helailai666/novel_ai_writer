"""M16 HotMeme — 热梗库（网络热梗/流行语，项目级或全局）"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class HotMeme(Base):
    __tablename__ = "hot_memes"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(CHAR(36), nullable=True)  # None=全局热梗
    phrase: Mapped[str] = mapped_column(String(100), nullable=False)
    meaning: Mapped[str] = mapped_column(Text, default="")
    usage_example: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), default="general")  # 搞笑/吐槽/战斗/恋爱/...
    tags: Mapped[str] = mapped_column(String(300), default="")
    popularity: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
