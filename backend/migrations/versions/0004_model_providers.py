"""0004 模型供应商注册表 + 项目级模型配置 — model_providers 表 + projects 新列

- 新建 model_providers 表（前台可管理的供应商配置）
- projects 增加 llm_provider_id / llm_model（每小说模型选择）
对存量库：建表 + ALTER TABLE ADD COLUMN（带列存在性守卫）
对全新库：可能已被启动时 create_all 建出，同样跳过
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _table_names(bind) -> list[str]:
    return [r[0] for r in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]


def _columns(bind, table: str) -> list[str]:
    return [r[1] for r in bind.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    if "model_providers" not in tables:
        op.execute(
            """
            CREATE TABLE model_providers (
                id CHAR(36) NOT NULL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                provider VARCHAR(50) NOT NULL,
                model VARCHAR(100) DEFAULT '',
                api_key VARCHAR(500) DEFAULT '',
                api_base VARCHAR(300) DEFAULT '',
                temperature FLOAT DEFAULT 0.7,
                enabled BOOLEAN DEFAULT 1,
                is_default BOOLEAN DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        )
    if "projects" in tables:
        cols = _columns(bind, "projects")
        if "llm_provider_id" not in cols:
            op.execute("ALTER TABLE projects ADD COLUMN llm_provider_id CHAR(36)")
        if "llm_model" not in cols:
            op.execute("ALTER TABLE projects ADD COLUMN llm_model VARCHAR(100) NOT NULL DEFAULT ''")


def downgrade() -> None:
    # sqlite 不支持 DROP COLUMN（旧版本）；此处留空并记录
    pass
