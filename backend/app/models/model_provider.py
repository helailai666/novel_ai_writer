"""模型供应商配置 — 前台可管理的 LLM 供应商注册表（替代 .env 单一配置）

每个配置 = 一个可复用的供应商端点（适配器类型 + API Key + Base + 默认模型），
项目通过 llm_provider_id 引用；is_default 表示全局兜底配置。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelProvider(Base):
    __tablename__ = "model_providers"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 显示名，如 "DeepSeek 主力"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 适配器类型: openai/deepseek/...
    model: Mapped[str] = mapped_column(String(100), default="")  # 该配置默认模型
    api_key: Mapped[str] = mapped_column(String(500), default="")
    api_base: Mapped[str] = mapped_column(String(300), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
