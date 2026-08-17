"""Skill 模型与加载器 — 目录化技能包（SKILL.md + frontmatter）"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """技能包"""

    name: str
    description: str
    version: str = "1.0.0"
    prompt: str = ""                # 注入 system prompt 的片段
    tools: list[str] = field(default_factory=list)      # 工具白名单补充
    knowledge_refs: list[str] = field(default_factory=list)  # 知识类别
    path: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tools": self.tools,
            "knowledge_refs": self.knowledge_refs,
            "enabled": self.enabled,
        }


def parse_skill_md(path: Path) -> Optional[Skill]:
    """解析 skills/<name>/SKILL.md：frontmatter(yaml) + 正文"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(f"Skill 读取失败 {path}: {e}")
        return None
    if not text.startswith("---"):
        logger.warning(f"Skill 缺少 frontmatter: {path}")
        return None
    _, fm, body = text.split("---", 2)
    try:
        meta = yaml.safe_load(fm) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Skill frontmatter 解析失败 {path}: {e}")
        return None
    name = meta.get("name") or path.parent.name
    return Skill(
        name=name,
        description=meta.get("description", ""),
        version=str(meta.get("version", "1.0.0")),
        prompt=(body or "").strip(),
        tools=list(meta.get("tools") or []),
        knowledge_refs=list(meta.get("knowledge_refs") or []),
        path=str(path),
    )
