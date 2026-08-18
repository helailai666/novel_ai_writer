"""M1 项目模型"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import CHAR

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), default="fantasy")
    synopsis: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / writing / completed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # 项目级技能包（逗号分隔技能名，如 "webnovel-standards,genre-xuanhuan"）
    # 注意：勿命名为 skills，与 M4 技能 relationship 重名
    skill_packs: Mapped[str] = mapped_column(String(300), default="")

    # 项目级模型配置：llm_provider_id 引用 model_providers 表；llm_model 为本项目模型覆盖
    # （空 = 用该供应商配置的默认模型；都为空 = 全局默认/环境变量）
    llm_provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    llm_model: Mapped[str] = mapped_column(String(100), default="")

    # 关联
    world_settings: Mapped[list["WorldSetting"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    items: Mapped[list["Item"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    factions: Mapped[list["Faction"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    outlines: Mapped[list["Outline"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    locations: Mapped[list["Location"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    timelines: Mapped[list["Timeline"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    foreshadows: Mapped[list["Foreshadow"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    volumes: Mapped[list["Volume"]] = relationship(back_populates="project", cascade="all, delete-orphan")
