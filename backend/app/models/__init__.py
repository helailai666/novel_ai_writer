"""数据模型注册 — 12 创作表 + 运行记录表"""

from app.models.project import Project
from app.models.world_setting import WorldSetting
from app.models.character import Character
from app.models.skill import Skill
from app.models.item import Item
from app.models.faction import Faction
from app.models.outline import Outline
from app.models.location import Location
from app.models.timeline import Timeline
from app.models.foreshadow import Foreshadow
from app.models.chapter import Chapter
from app.models.volume import Volume
from app.models.agent_run import AgentRun

__all__ = [
    "Project", "WorldSetting", "Character", "Skill", "Item", "Faction",
    "Outline", "Location", "Timeline", "Foreshadow", "Chapter", "Volume",
    "AgentRun",
]
