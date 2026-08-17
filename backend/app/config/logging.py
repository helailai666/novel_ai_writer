"""日志配置 — 统一 logging 初始化"""

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO", debug: bool = False) -> None:
    """初始化根日志器（幂等）"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    lvl = "DEBUG" if debug else (level or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, lvl, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # 压制第三方噪声
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
