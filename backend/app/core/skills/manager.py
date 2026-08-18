"""Skill 管理 — 技能包文件 CRUD（H4 增强）

技能包 = skills/<name>/SKILL.md（frontmatter yaml + 正文 prompt）。
写入目标取目录列表第一个；写后刷新注册表，使运行中的图立即感知。
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import yaml

from app.config import settings
from app.core.skills.models import Skill, parse_skill_md

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SkillError(ValueError):
    """技能包操作错误（name 非法 / 不存在 / 已存在）"""


def _render_skill_md(meta: dict, prompt: str) -> str:
    """组装 SKILL.md：frontmatter(yaml) + 正文"""
    fm = yaml.safe_dump(
        {
            "name": meta["name"],
            "description": meta.get("description", ""),
            "version": str(meta.get("version", "1.0.0")),
            "tools": list(meta.get("tools") or []),
            "knowledge_refs": list(meta.get("knowledge_refs") or []),
            "enabled": bool(meta.get("enabled", True)),
        },
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    body = (prompt or "").strip()
    return f"---\n{fm.strip()}\n---\n\n{body}\n" if body else f"---\n{fm.strip()}\n---\n"


class SkillManager:
    """技能包文件管理器"""

    def __init__(self, dirs: Optional[list[str]] = None, registry=None):
        self.dirs = dirs or settings.skills.dirs
        if not self.dirs:
            raise SkillError("未配置技能目录（SKILLS_DIRS）")
        self._registry = registry  # 为空时写后不刷全局注册表（测试用）

    # ── 内部工具 ────────────────────────────────────────────────

    def _root(self) -> Path:
        return Path(self.dirs[0])

    def _skill_dir(self, name: str) -> Path:
        self.validate_name(name)
        return self._root() / name

    @staticmethod
    def validate_name(name: str) -> str:
        name = (name or "").strip()
        if not _NAME_RE.match(name):
            raise SkillError(
                f"技能名非法: {name!r} — 仅允许字母/数字/下划线/连字符，长度 1-64"
            )
        return name

    def _refresh(self) -> None:
        if self._registry is not None:
            self._registry.reload()

    # ── CRUD ────────────────────────────────────────────────────

    def create(self, data: dict) -> Skill:
        """创建技能包：name 必填；已存在报错"""
        name = self.validate_name(data.get("name"))
        root = self._root()
        root.mkdir(parents=True, exist_ok=True)
        target = root / name
        if target.exists():
            raise SkillError(f"技能已存在: {name}")
        target.mkdir(parents=True, exist_ok=False)
        try:
            (target / "SKILL.md").write_text(
                _render_skill_md({"name": name, **data}, data.get("prompt", "")), encoding="utf-8"
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise
        self._refresh()
        skill = parse_skill_md(target / "SKILL.md")
        if skill is None:
            raise SkillError(f"技能创建后解析失败: {name}")
        logger.info(f"Skill 创建: {name}")
        return skill

    def update(self, name: str, data: dict) -> Skill:
        """更新技能包（name 不可改名；其余字段可改）"""
        name = self.validate_name(name)
        target = self._skill_dir(name)
        md = target / "SKILL.md"
        if not md.exists():
            raise SkillError(f"技能不存在: {name}")
        skill = parse_skill_md(md)
        meta = skill.to_dict() if skill else {}
        meta.update({k: v for k, v in data.items() if k not in ("name", "prompt")})
        md.write_text(
            _render_skill_md({**meta, "name": name}, data.get("prompt", skill.prompt if skill else "")),
            encoding="utf-8",
        )
        self._refresh()
        updated = parse_skill_md(md)
        if updated is None:
            raise SkillError(f"技能更新后解析失败: {name}")
        logger.info(f"Skill 更新: {name}")
        return updated

    def delete(self, name: str) -> None:
        """删除技能包目录"""
        name = self.validate_name(name)
        target = self._skill_dir(name)
        if not target.exists():
            raise SkillError(f"技能不存在: {name}")
        shutil.rmtree(target)
        self._refresh()
        logger.info(f"Skill 删除: {name}")

    def set_enabled(self, name: str, enabled: bool) -> Skill:
        """启用/禁用开关（写入 frontmatter enabled）"""
        return self.update(name, {"enabled": bool(enabled)})


# ── 全局单例（绑定全局注册表：写后自动刷新）────────────────────────

_manager: Optional[SkillManager] = None


def get_manager() -> SkillManager:
    """全局技能管理器 — 写入目录取 SKILLS_DIRS 首目录，写后刷新全局注册表"""
    global _manager
    if _manager is None:
        from app.core.skills.registry import get_registry

        _manager = SkillManager(registry=get_registry())
    return _manager
