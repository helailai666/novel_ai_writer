"""0002 项目级技能绑定 — projects 表增加 skills 列

对存量库：ALTER TABLE ADD COLUMN（带列存在性守卫，sqlite 不支持 IF NOT EXISTS）
对全新库：可能已被 create_all 建出该列，同样跳过
对"仅跑迁移"的全新库：projects 表可能尚不存在（由 create_all 负责），跳过
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = [r[0] for r in bind.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "projects" not in tables:
        return  # 表由应用启动 create_all 创建
    cols = [r[1] for r in bind.exec_driver_sql("PRAGMA table_info(projects)").fetchall()]
    if "skill_packs" not in cols:
        op.execute("ALTER TABLE projects ADD COLUMN skill_packs VARCHAR(300) NOT NULL DEFAULT ''")


def downgrade() -> None:
    # sqlite 不支持 DROP COLUMN（旧版本）；此处留空并记录
    pass
