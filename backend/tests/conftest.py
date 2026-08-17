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
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["VECTOR_STORE_BACKEND"] = "mock"


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


@pytest.fixture
def mock_llm(monkeypatch):
    """替换 agents/nodes/common.create 为可控 Mock LLM

    返回 dict：{"score": int} 控制审核评分（驱动重写分支）
    """
    import app.agents.nodes.common as common

    from app.core.llm.providers.mock import MockProvider
    from app.core.llm.schemas import LLMRequest, LLMResponse
    import json as _json

    class _FakeScoreProvider(MockProvider):
        score = 82

        async def acomplete(self, req: LLMRequest) -> LLMResponse:
            if req.response_format and req.response_format.get("type") == "json_object":
                return LLMResponse(
                    content=_json.dumps(
                        {"score": self.score, "summary": "测试", "issues": ["i"], "suggestions": ["s"], "highlights": ["h"]},
                        ensure_ascii=False,
                    ),
                    usage={"mock": True},
                    is_mock=True,
                )
            return await super().acomplete(req)

    ctrl = {"score": 82}

    def _create(*args, **kwargs):
        provider = _FakeScoreProvider(model="mock")
        provider.score = ctrl["score"]
        return provider

    monkeypatch.setattr(common, "create", _create)
    return ctrl
