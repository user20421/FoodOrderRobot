"""
结构化日志配置
"""
import logging
import sys
from app.core.config import settings


# 避免重复配置
_logging_configured = False


def setup_logging():
    """配置应用日志（幂等）。"""
    global _logging_configured
    if _logging_configured:
        return

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    # Windows 控制台默认编码可能为 GBK，强制 UTF-8 避免中文日志乱码/报错
    handler.encoding = "utf-8"

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=[handler],
    )

    # 降低第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.debug else logging.INFO)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
