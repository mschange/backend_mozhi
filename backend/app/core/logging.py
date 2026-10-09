"""应用文件日志与 LangSmith 追踪配置。"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import (
    LANGSMITH_API_KEY,
    LANGSMITH_ENDPOINT,
    LANGSMITH_PROJECT,
    LANGSMITH_TRACING,
    LOG_BACKUP_COUNT,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    TAVILY_API_KEY,
    log_path,
)

_FILE_HANDLER_MARKER = "_mozhi_file_handler"
_LOG_FORMAT = "%(asctime)s %(levelname)s [pid=%(process)d] %(name)s: %(message)s"


def _level_value() -> int:
    value = getattr(logging, LOG_LEVEL.upper(), logging.ERROR)
    if not isinstance(value, int):
        return logging.ERROR
    return max(value, logging.ERROR)


def configure_file_logging() -> None:
    """为 app logger 配置单个 UTF-8 轮转文件 handler。"""
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    level = _level_value()
    formatter = logging.Formatter(_LOG_FORMAT)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)

    for handler in list(app_logger.handlers):
        if not getattr(handler, _FILE_HANDLER_MARKER, False):
            continue
        same_config = (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename) == path
            and handler.maxBytes == LOG_MAX_BYTES
            and handler.backupCount == LOG_BACKUP_COUNT
        )
        if same_config:
            handler.setLevel(level)
            handler.setFormatter(formatter)
            return
        app_logger.removeHandler(handler)
        handler.close()

    handler = RotatingFileHandler(
        path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    setattr(handler, _FILE_HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)


def configure_langsmith() -> None:
    """按 .env 打开或关闭 LangSmith；Tavily key 一并写入进程环境。"""
    if not LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ.pop("LANGCHAIN_TRACING_V2", None)
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
    if LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
        os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    if TAVILY_API_KEY:
        os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
