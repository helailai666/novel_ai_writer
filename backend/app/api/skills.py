"""Skills API — 技能包列表 / 应用信息"""

from fastapi import APIRouter

from app.core.skills import get_registry, get_runner

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills():
    """列出全部可用技能包"""
    return {"skills": [s.to_dict() for s in get_registry().get_all()]}


@router.get("/{name}")
async def get_skill(name: str):
    """获取单个技能包详情（含注入内容预览）"""
    skill = get_registry().get(name)
    if not skill:
        return {"error": f"技能不存在: {name}"}
    return skill.to_dict() | {"prompt": skill.prompt[:2000]}


@router.post("/{name}/apply")
async def apply_skill(name: str):
    """应用技能：返回将注入 system prompt 的组装内容（请求级应用见 /api/agents/chat skills 字段）"""
    injected = get_runner().apply([name])
    if not injected["prompt"] and not injected["tools"]:
        return {"applied": False, "error": f"技能不存在或未启用: {name}"}
    return {"applied": True, "skill": name, **injected}
