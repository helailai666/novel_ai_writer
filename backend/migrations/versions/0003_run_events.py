"""0003 agent_runs 事件时间线 — 增加 events_data 列（G4 前端可视化）

对存量库：ALTER TABLE ADD COLUMN（带列存在性守卫）
对全新库：可能已被 create_all 建出该列，同样跳过
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = [r[0] for r in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "agent_runs" not in tables:
        return  # 表由应用启动 create_all 创建
    cols = [r[1] for r in bind.exec_driver_sql("PRAGMA table_info(agent_runs)").fetchall()]
    if "events_data" not in cols:
        op.execute("ALTER TABLE agent_runs ADD COLUMN events_data TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    # sqlite 不支持 DROP COLUMN（旧版本）；此处留空并记录
    pass
