"""配置管理 — 从环境变量 / .env 加载"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置，自动读取 .env 和环境变量"""

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_ai_writer.db"

    # LLM — 从环境变量加载，不设默认值（走 Mock 降级）
    LLM_API_KEY: Optional[str] = None
    LLM_API_BASE: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
