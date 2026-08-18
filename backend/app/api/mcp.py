"""MCP API — 外部 MCP server 配置查看 / 重连桥接 / 已桥接工具列表"""

import logging
from typing import Optional

from fastapi import APIRouter

from app.core.mcp import bridge_all, load_mcp_config
from app.core.tools.registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/servers")
async def list_mcp_servers():
    """列出已配置的外部 MCP server（含实时连接池状态，J 轮）"""
    from app.core.mcp.client import _pools

    servers = []
    for cfg in load_mcp_config():
        name = cfg.get("name", "unknown")
        pool = _pools.get(name)
        servers.append({
            "name": name,
            "transport": cfg.get("transport", "stdio"),
            "command": cfg.get("command"),
            "url": cfg.get("url"),
            "enabled": cfg.get("enabled", True),
            "configured": {
                "pool_size": cfg.get("pool_size"),
                "connect_timeout": cfg.get("connect_timeout"),
                "max_retries": cfg.get("max_retries"),
            },
            "status": pool.status() if pool else None,
        })
    return {"servers": servers}


@router.post("/reload")
async def reload_mcp_servers():
    """重新连接并桥接全部外部 MCP server 的工具"""
    results = await bridge_all()
    return {"bridged": results}


@router.get("/tools")
async def list_bridged_tools():
    """列出当前注册表中外部的（mcp_* 前缀）工具"""
    external = [t for t in get_registry().get_all() if t.name.startswith("mcp_")]
    return {"tools": [{"name": t.name, "description": t.description} for t in external]}
