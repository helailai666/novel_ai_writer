"""Alembic 迁移环境 — 使用 app 的 Base.metadata 与 DATABASE_URL"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 把 backend/ 加入路径（迁移在 backend 目录运行时可直接 import app）
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  确保全部模型注册到 metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 数据库 URL 一律从应用配置注入（覆盖 alembic.ini 占位）
# Alembic 用同步驱动，这里把异步 URL 转成同步等价形式
_sync_url = settings.DATABASE_URL
_sync_url = _sync_url.replace("sqlite+aiosqlite", "sqlite")
_sync_url = _sync_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
