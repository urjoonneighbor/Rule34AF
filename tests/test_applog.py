"""Тесты для src.core.applog - файлового логирования приложения.

Проверяем, что лог теперь ротируется ПО ДНЯМ (TimedRotatingFileHandler),
а не по размеру файла (см. CHANGELOG) - иначе один активный день мог
целиком вытеснить весь предыдущий лог, как только файл упирался в лимит
размера."""
import logging
import logging.handlers
import os

import pytest

from src.core import applog
from src.core.storage import paths


@pytest.fixture(autouse=True)
def _isolate_logger(tmp_path, monkeypatch):
    """logging.getLogger("rule34_finder") - именованный логгер, общий на
    весь процесс, а applog._logger - модульный синглтон поверх него.
    Сбрасываем оба до и после каждого теста, иначе хендлер, поставленный
    одним тестом, останется висеть на следующий."""
    monkeypatch.setattr(paths, "get_app_data_dir", lambda: str(tmp_path))

    logger = logging.getLogger("rule34_finder")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    applog._logger = None

    yield

    logger = logging.getLogger("rule34_finder")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    applog._logger = None


def test_build_logger_uses_timed_rotation_not_size_based(tmp_path):
    logger = applog._get_logger()

    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
    # Не RotatingFileHandler (старое поведение - ротация по размеру) - но
    # TimedRotatingFileHandler на практике тоже наследуется от
    # BaseRotatingHandler, а не от RotatingFileHandler, так что явной
    # проверки "не тот класс" не нужно: isinstance выше уже её обеспечивает.
    assert handler.when.upper() == "MIDNIGHT"
    assert handler.backupCount == applog._LOG_RETENTION_DAYS


def test_log_file_created_in_app_data_dir(tmp_path):
    applog.info("тестовое сообщение")

    log_path = os.path.join(str(tmp_path), paths.APP_LOG_FILENAME)
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "тестовое сообщение" in content


def test_get_logger_returns_cached_singleton(tmp_path):
    first = applog._get_logger()
    second = applog._get_logger()
    assert first is second
    # _build_logger тоже не должен плодить второй хендлер при повторном
    # вызове на уже настроенном логгере (см. `if logger.handlers: return logger`).
    assert len(first.handlers) == 1


def test_all_log_functions_do_not_raise_on_broken_handler(tmp_path, monkeypatch):
    """debug/info/warning/error/exception глотают исключения - падение
    логирования не должно ронять вызывающий код (см. try/except в каждой
    функции)."""
    applog._get_logger()  # инициализируем нормально

    class _ExplodingHandler(logging.Handler):
        def emit(self, record):
            raise RuntimeError("disk on fire")

    logger = logging.getLogger("rule34_finder")
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.addHandler(_ExplodingHandler())

    applog.debug("x")
    applog.info("x")
    applog.warning("x")
    applog.error("x")
    try:
        raise ValueError("boom")
    except ValueError:
        applog.exception("x")  # не должно выбросить исключение наружу


def test_falls_back_to_stream_handler_when_log_dir_unavailable(tmp_path, monkeypatch):
    def _raise(*a, **kw):
        raise OSError("no such directory")

    monkeypatch.setattr(paths, "get_app_data_dir", _raise)

    logger = applog._get_logger()

    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    # Не должно падать при попытке записать сообщение через фоллбэк-хендлер.
    applog.error("сообщение без файла лога")
