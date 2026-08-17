"""NovelAI Writer — FastAPI 入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


# ── 生命周期 ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库、桥接外部 MCP server；关闭时清理资源"""
    await init_db()
    try:
        from app.core.mcp import bridge_all

        bridged = await bridge_all()
        if bridged:
            total = sum(len(v) for v in bridged.values())
            print(f"[MCP] 外部 server 桥接完成: {total} 个工具", flush=True)
    except Exception as e:
        print(f"[MCP] 桥接跳过: {e}", flush=True)
    yield


# ── 创建应用 ─────────────────────────────────────────────────────

app = FastAPI(
    title="NovelAI Writer API",
    description="AI 辅助小说创作平台 — 后端核心服务",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 挂载路由 ─────────────────────────────────────────────────────

from app.api.projects import router as projects_router
from app.api.settings import router as settings_router
from app.api.writing import router as writing_router
from app.api.review import router as review_router
from app.api.search import router as search_router
from app.api.agents import router as agents_router
from app.api.tools import router as tools_router
from app.api.knowledge import router as knowledge_router
from app.api.hot_memes import router as hot_memes_router
from app.api.mcp import router as mcp_router
from app.api.skills import router as skills_router

app.include_router(projects_router)
app.include_router(settings_router)
app.include_router(writing_router)
app.include_router(review_router)
app.include_router(search_router)
app.include_router(agents_router)
app.include_router(tools_router)
app.include_router(knowledge_router)
app.include_router(hot_memes_router)
app.include_router(mcp_router)
app.include_router(skills_router)


# ── 健康检查 ─────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "service": "novel_ai_writer",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "NovelAI Writer API",
        "docs": "/docs",
        "health": "/health",
    }


# ── 启动入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
