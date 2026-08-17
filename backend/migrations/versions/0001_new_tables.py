"""0001 新世代表 — agent_runs / knowledge_docs / knowledge_chunks / hot_memes

使用 IF NOT EXISTS 保证对存量库（12 张旧表已存在）与全新库均安全幂等。
旧 12 张表由启动时 create_all 管理，未来变更一律走迁移。
（注：sqlite 驱动不支持多语句单次执行，故逐表 execute）
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            graph_name VARCHAR(50) NOT NULL,
            project_id VARCHAR(36),
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            input_data TEXT NOT NULL DEFAULT '',
            output_data TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            project_id VARCHAR(36),
            title VARCHAR(300) NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            content TEXT NOT NULL DEFAULT '',
            tags VARCHAR(500) NOT NULL DEFAULT '',
            source VARCHAR(200) NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            doc_id VARCHAR(36) NOT NULL REFERENCES knowledge_docs (id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL DEFAULT '',
            meta TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hot_memes (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            project_id VARCHAR(36),
            phrase VARCHAR(100) NOT NULL,
            meaning TEXT NOT NULL DEFAULT '',
            usage_example TEXT NOT NULL DEFAULT '',
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            tags VARCHAR(300) NOT NULL DEFAULT '',
            popularity INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hot_memes")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks")
    op.execute("DROP TABLE IF EXISTS knowledge_docs")
    op.execute("DROP TABLE IF EXISTS agent_runs")
