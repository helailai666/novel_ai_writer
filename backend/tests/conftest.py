"""pytest 全局配置 — 临时数据库 + 强制 Mock LLM（在任何 app 导入前生效）"""

import os
import tempfile

import pytest

# ── 必须在导入 app.* 之前设置 ────────────────────────────────────
_TMPDIR = tempfile.mkdtemp(prefix="naw_test_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMPDIR}/test.db"
os.environ["LLM_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""
os.environ["SEARCH_PROVIDER"] = "mock"


@pytest.fixture
async def db():
    """临时数据库：建表 + 一个测试项目（显式 commit）"""
    from app.database import async_session_factory, init_db
    from app.services.project_service import ProjectService

    await init_db()
    async with async_session_factory() as session:
        pid = (await ProjectService.create(session, {"title": "图测试", "genre": "玄幻"}))["id"]
        await session.commit()
    yield pid
    async with async_session_factory() as session:
        await ProjectService.delete(session, pid)
        await session.commit()
