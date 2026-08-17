"""pytest 全局配置 — 临时数据库 + 强制 Mock LLM（在任何 app 导入前生效）"""

import os
import tempfile

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
