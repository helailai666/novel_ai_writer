"""Tools API — 工具清单与调用（调试/管理用）"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.tools.registry import get_registry
from app.core.tools.base import ToolResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict


class ToolCallRequest(BaseModel):
    name: str = Field(..., description="工具名")
    arguments: dict = Field(default_factory=dict, description="工具参数")


@router.get("", response_model=list[ToolInfo])
async def list_tools():
    """列出注册表全部工具（含外部 MCP 桥接工具）"""
    return [
        ToolInfo(name=t.name, description=t.description, parameters=t.to_spec()["function"]["parameters"])
        for t in get_registry().get_all()
    ]


@router.post("/call")
async def call_tool(payload: ToolCallRequest) -> dict:
    """直接调用工具（调试用）"""
    result = await get_registry().execute(payload.name, payload.arguments)
    return result.model_dump()
