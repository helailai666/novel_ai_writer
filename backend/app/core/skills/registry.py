"""Skill 注册表与执行器 — 扫描目录、按名加载、组装注入内容"""

import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.core.skills.models import Skill, parse_skill_md

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能包注册表（扫描 SKILL_DIRS）"""

    def __init__(self, dirs: Optional[list[str]] = None):
        self.dirs = dirs or settings.skills.dirs
        self._skills: dict[str, Skill] = {}
        self._scan()

    def _scan(self) -> None:
        for d in self.dirs:
            root = Path(d)
            if not root.exists():
                logger.info(f"Skill 目录不存在（跳过）: {d}")
                continue
            for skill_md in root.glob("*/SKILL.md"):
                skill = parse_skill_md(skill_md)
                if skill:
                    self._skills[skill.name] = skill
                    logger.info(f"Skill 加载: {skill.name} ({skill.version})")

    # ── 查询 ────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def get_all(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.enabled]

    def list_names(self) -> list[str]:
        return sorted(s.name for s in self.get_all())

    def has(self, name: str) -> bool:
        return name in self._skills and self._skills[name].enabled


class SkillRunner:
    """技能执行器 — 把技能注入图状态"""

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or SkillRegistry()

    def apply(self, names: list[str]) -> dict:
        """按技能名组装注入内容

        Returns:
            {"prompt": str, "tools": list[str], "knowledge_refs": list[str]}
        """
        prompt_parts: list[str] = []
        tools: list[str] = []
        knowledge_refs: list[str] = []
        for name in names:
            skill = self.registry.get(name)
            if not skill or not skill.enabled:
                logger.warning(f"技能不存在或未启用: {name}")
                continue
            if skill.prompt:
                prompt_parts.append(f"【技能:{skill.name}】\n{skill.prompt}")
            tools.extend(skill.tools)
            knowledge_refs.extend(skill.knowledge_refs)
        return {
            "prompt": "\n\n".join(prompt_parts),
            "tools": list(dict.fromkeys(tools)),
            "knowledge_refs": list(dict.fromkeys(knowledge_refs)),
        }


# ── 全局单例 ────────────────────────────────────────────────────

_registry: Optional[SkillRegistry] = None
_runner: Optional[SkillRunner] = None


def get_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def get_runner() -> SkillRunner:
    global _runner
    if _runner is None:
        _runner = SkillRunner(get_registry())
    return _runner
