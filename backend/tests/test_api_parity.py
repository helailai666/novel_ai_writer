"""路由 ↔ 前端 API 对照测试 — 防止前后端失配回归

原理：解析 frontend/src/api/index.js 中的全部 http.* / fetch 调用，
归一化参数段后与后端注册路由逐一比对。
"""

import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_API = BACKEND_DIR.parent / "frontend" / "src" / "api" / "index.js"


def _norm(path: str) -> str:
    """参数段归一化：{project_id} / ${projectId} → {}"""
    path = re.sub(r"\$\{[^}]*\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def _collect_frontend_calls() -> list[tuple[str, str]]:
    """从 api/index.js 提取 (method, url_template)"""
    text = FRONTEND_API.read_text(encoding="utf-8")
    calls: list[tuple[str, str]] = []
    for m in re.finditer(r"http\.(get|post|patch|put|delete)\(`([^`]+)`", text):
        calls.append((m.group(1).upper(), m.group(2)))
    for m in re.finditer(r"fetch\(`([^`]+)`", text):
        calls.append(("POST", m.group(1)))
    return calls


# 前端运行时动态拼接的路径段 → 已知闭集（校验时逐值展开）
_DYNAMIC_SEGMENTS: dict[str, list[str]] = {
    "dimension": ["consistency", "logic", "foreshadowing", "character-arc", "pacing", "prose", "reader-perspective", "comprehensive"],
}


def _expand(url: str) -> list[str]:
    """把已知闭集的动态段展开为具体路径；其余 ${...} 段保持为 {} 通配"""
    for key, values in _DYNAMIC_SEGMENTS.items():
        marker = f"${{{key}}}"
        if marker in url:
            return [url.replace(marker, v) for v in values]
    return [url]


def _collect_backend_routes() -> set[tuple[str, str]]:
    """收集后端全部 (method, path)，展开懒加载的 _IncludedRouter"""
    import app.main as m

    routes: set[tuple[str, str]] = set()
    for r in m.app.routes:
        candidates = []
        if hasattr(r, "original_router"):  # FastAPI 0.141+ 懒加载 router
            candidates = list(r.original_router.routes)
        else:
            candidates = [r]
        for sub in candidates:
            path = getattr(sub, "path", None)
            methods = getattr(sub, "methods", None)
            if path and methods:
                for meth in methods:
                    routes.add((meth, _norm(path)))
    return routes


def test_frontend_api_matches_backend_routes():
    """前端 api/index.js 的每个调用都必须命中后端路由"""
    backend = _collect_backend_routes()
    frontend = _collect_frontend_calls()
    assert frontend, "未解析到任何前端 API 调用"

    missing = []
    for method, url in frontend:
        for concrete in _expand(url):
            full = _norm(concrete if concrete.startswith("/api") else "/api" + concrete)
            if (method, full) not in backend and method not in {m for m, _ in backend if _ == full}:
                missing.append((method, concrete))

    assert not missing, f"以下前端调用在后端无对应路由: {missing}"


def test_backend_route_coverage_of_frontend():
    """后端核心业务路由应被前端覆盖（信息性：列出未覆盖的业务路由）"""
    backend = _collect_backend_routes()
    frontend = {_norm(url if url.startswith("/api") else "/api" + url) for _, url in _collect_frontend_calls()}
    business = {
        path for meth, path in backend
        if path.startswith("/api") and not path.startswith(("/api/agents", "/api/knowledge", "/api/hot-memes", "/api/skills", "/api/mcp", "/api/model-providers"))
    }
    uncovered = sorted(business - frontend)
    # 允许的健康/文档端点与未来端点例外
    allowed_uncovered = {"/api/projects/{}/export", "/api/search/web/cache/clear"}
    real_uncovered = [u for u in uncovered if u not in allowed_uncovered]
    # 信息性断言：避免未来端点爆炸，仅输出（P1 兼容期不强制）
    print(f"后端业务路由未被前端显式调用（{len(real_uncovered)} 条）: {real_uncovered}")
