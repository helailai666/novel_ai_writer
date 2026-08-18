"""Skills API — 技能包列表 / 详情 / 管理（CRUD，H4）/ 应用信息"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.skills import get_manager, get_registry, get_runner
from app.core.skills.manager import SkillError

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillPayload(BaseModel):
    """技能包写入载荷（创建/更新共用）"""

    name: Optional[str] = Field(None, description="技能名（创建必填；仅字母/数字/下划线/连字符）")
    description: str = ""
    version: str = "1.0.0"
    prompt: str = Field("", description="注入 system prompt 的正文")
    tools: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)
    enabled: bool = True


@router.get("")
async def list_skills():
    """列出全部可用技能包"""
    return {"skills": [s.to_dict() for s in get_registry().get_all()]}


@router.get("/{name}")
async def get_skill(name: str):
    """获取单个技能包详情（含注入内容预览）"""
    skill = get_registry().get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"技能不存在: {name}")
    return skill.to_dict() | {"prompt": skill.prompt[:20000]}


@router.post("", status_code=201)
async def create_skill(payload: SkillPayload):
    """创建技能包（写入 skills/<name>/SKILL.md，刷新注册表）"""
    if not payload.name:
        raise HTTPException(status_code=400, detail="技能名必填（name）")
    try:
        skill = get_manager().create(payload.model_dump())
    except SkillError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return skill.to_dict() | {"prompt": skill.prompt}


@router.put("/{name}")
async def update_skill(name: str, payload: SkillPayload):
    """更新技能包（名称不可改；正文/元数据可改）"""
    try:
        skill = get_manager().update(name, payload.model_dump(exclude_unset=True))
    except SkillError as e:
        raise HTTPException(status_code=404 if "不存在" in str(e) else 400, detail=str(e))
    return skill.to_dict() | {"prompt": skill.prompt}


@router.delete("/{name}")
async def delete_skill(name: str):
    """删除技能包目录"""
    try:
        get_manager().delete(name)
    except SkillError as e:
        raise HTTPException(status_code=404 if "不存在" in str(e) else 400, detail=str(e))
    return {"deleted": name}


@router.patch("/{name}/enabled")
async def set_skill_enabled(name: str, payload: dict):
    """启用/禁用技能包（enabled: bool）"""
    enabled = bool(payload.get("enabled"))
    try:
        skill = get_manager().set_enabled(name, enabled)
    except SkillError as e:
        raise HTTPException(status_code=404 if "不存在" in str(e) else 400, detail=str(e))
    return skill.to_dict() | {"prompt": skill.prompt}


@router.post("/{name}/apply")
async def apply_skill(name: str):
    """应用技能：返回将注入 system prompt 的组装内容（请求级应用见 /api/agents/chat skills 字段）"""
    injected = get_runner().apply([name])
    if not injected["prompt"] and not injected["tools"]:
        return {"applied": False, "error": f"技能不存在或未启用: {name}"}
    return {"applied": True, "skill": name, **injected}
