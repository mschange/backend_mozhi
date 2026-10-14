# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
import logging
from logging.handlers import RotatingFileHandler

from app import config
from app.core import logging as app_logging


def _remove_file_handlers() -> None:
    logger = logging.getLogger("app")
    for handler in list(logger.handlers):
        if getattr(handler, app_logging._FILE_HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


def test_log_path_is_relative_to_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "LOG_FILE", "logs/test.log")
    assert config.log_path() == config.BACKEND_DIR / "logs/test.log"

    absolute_path = tmp_path / "absolute.log"
    monkeypatch.setattr(config, "LOG_FILE", str(absolute_path))
    assert config.log_path() == absolute_path


def test_file_logging_is_idempotent_and_writes_traceback(
    monkeypatch,
    tmp_path,
) -> None:
    log_file = tmp_path / "app.log"
    logger = logging.getLogger("app")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    monkeypatch.setattr(app_logging, "log_path", lambda: log_file)
    monkeypatch.setattr(app_logging, "LOG_LEVEL", "DEBUG")
    monkeypatch.setattr(app_logging, "LOG_MAX_BYTES", 100_000)
    monkeypatch.setattr(app_logging, "LOG_BACKUP_COUNT", 2)

    try:
        _remove_file_handlers()
        app_logging.configure_file_logging()
        app_logging.configure_file_logging()
        handlers = [
            handler
            for handler in logger.handlers
            if getattr(handler, app_logging._FILE_HANDLER_MARKER, False)
        ]
        assert len(handlers) == 1
        assert isinstance(handlers[0], RotatingFileHandler)
        assert handlers[0].level == logging.ERROR
        assert [h for h in logger.handlers if h not in original_handlers] == handlers

        logging.getLogger("app.tests").info("普通运行信息")
        try:
            raise RuntimeError("测试异常")
        except RuntimeError:
            logging.getLogger("app.tests").exception("写入失败")
        handlers[0].flush()

        content = log_file.read_text(encoding="utf-8")
        assert "普通运行信息" not in content
        assert "ERROR" in content
        assert "测试异常" in content
        assert "Traceback" in content
    finally:
        _remove_file_handlers()
        logger.setLevel(original_level)


def test_file_logging_rotates_and_limits_backups(monkeypatch, tmp_path) -> None:
    log_file = tmp_path / "app.log"
    logger = logging.getLogger("app")
    original_level = logger.level
    monkeypatch.setattr(app_logging, "log_path", lambda: log_file)
    monkeypatch.setattr(app_logging, "LOG_LEVEL", "INFO")
    monkeypatch.setattr(app_logging, "LOG_MAX_BYTES", 200)
    monkeypatch.setattr(app_logging, "LOG_BACKUP_COUNT", 2)

    try:
        _remove_file_handlers()
        app_logging.configure_file_logging()
        for index in range(20):
            logging.getLogger("app.tests").error("轮转错误 %s %s", index, "x" * 80)
        for handler in logger.handlers:
            if getattr(handler, app_logging._FILE_HANDLER_MARKER, False):
                handler.flush()

        assert log_file.exists()
        assert (tmp_path / "app.log.1").exists()
        assert (tmp_path / "app.log.2").exists()
        assert not (tmp_path / "app.log.3").exists()
    finally:
        _remove_file_handlers()
        logger.setLevel(original_level)
