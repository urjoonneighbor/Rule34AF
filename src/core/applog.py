"""Файловое логирование приложения: пишет ошибки и предупреждения в
`app.log` в каталоге данных приложения, не показывая пользователю лишние
всплывающие окна."""
import logging
import logging.handlers
import os
import sys

_logger: logging.Logger | None = None


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("rule34_finder")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    handler = None
    try:
        # Локальный импорт, чтобы избежать циклических зависимостей на старте модулей.
        from src.core.storage.paths import APP_LOG_FILENAME, get_app_data_dir

        log_path = os.path.join(get_app_data_dir(), APP_LOG_FILENAME)
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    except OSError:
        handler = None

    if handler is None:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = _build_logger()
    return _logger


def debug(message: str) -> None:
    try:
        _get_logger().debug(message)
    except Exception:
        pass


def info(message: str) -> None:
    try:
        _get_logger().info(message)
    except Exception:
        pass


def warning(message: str) -> None:
    try:
        _get_logger().warning(message)
    except Exception:
        pass


def error(message: str) -> None:
    try:
        _get_logger().error(message)
    except Exception:
        pass


def exception(message: str) -> None:
    """Логирует сообщение вместе с текущим traceback (звать из except-блока)."""
    try:
        _get_logger().exception(message)
    except Exception:
        pass
