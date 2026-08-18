"""M13 AgentRun — LangGraph 运行记录（审计/回放）"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    graph_name: Mapped[str] = mapped_column(String(50), nullable=False)   # setting / chapter / review / chat
    project_id: Mapped[str] = mapped_column(CHAR(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")    # running / completed / failed
    input_data: Mapped[str] = mapped_column(Text, default="")
    output_data: Mapped[str] = mapped_column(Text, default="")
    events_data: Mapped[str] = mapped_column(Text, default="")   # G4: 压缩事件时间线（events/token_counts）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
