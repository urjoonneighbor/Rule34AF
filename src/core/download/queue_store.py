"""Сохранение очереди скачивания на диск, чтобы незавершённое скачивание
пережило закрытие приложения и продолжилось при следующем запуске.

Очередь хранится отдельным файлом, а не внутри общих настроек, по двум
причинам: она бывает большой (тысячи ссылок), а настройки переписываются
буквально на каждый чих в интерфейсе - складывать одно в другое означало бы
на каждую галочку заново сериализовать всю очередь.
"""
from __future__ import annotations

import os

from src.core import applog
from src.core.storage import blob_codec
from src.core.storage.paths import DOWNLOAD_QUEUE_FILENAME, resolve_data_file

_QUEUE_FORMAT_VERSION = 1


def _queue_path() -> str:
    return resolve_data_file(DOWNLOAD_QUEUE_FILENAME)


def save_queue(tasks: list) -> None:
    """Сохраняет очередь задач. Пустая очередь = сохранённого состояния нет,
    файл удаляется."""
    if not tasks:
        clear_queue()
        return

    payload = {"version": _QUEUE_FORMAT_VERSION, "tasks": tasks}
    try:
        with open(_queue_path(), "wb") as f:
            f.write(blob_codec.encode_json(payload))
    except (OSError, ValueError, TypeError) as e:
        # Не критично: пользователь просто не сможет продолжить с этого места.
        applog.warning(f"Не удалось сохранить очередь скачивания: {e}")


def load_queue() -> list:
    """Возвращает сохранённые задачи (или пустой список, если сохранять было
    нечего либо файл повреждён). Битые/чужие записи отбрасываются."""
    path = _queue_path()
    if not os.path.exists(path):
        return []

    try:
        with open(path, "rb") as f:
            data = blob_codec.decode_json(f.read())
    except OSError as e:
        applog.warning(f"Не удалось прочитать очередь скачивания: {e}")
        return []

    if not isinstance(data, dict) or data.get("version") != _QUEUE_FORMAT_VERSION:
        return []

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return []

    valid = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        data_list = task.get("data_list")
        if not isinstance(data_list, list) or not data_list:
            continue
        if not str(task.get("artist", "")).strip() or not str(task.get("dir", "")).strip():
            continue
        valid.append(task)
    return valid


def clear_queue() -> None:
    """Убирает сохранённое состояние - скачивание доведено до конца или
    пользователь отказался его продолжать."""
    path = _queue_path()
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
    except OSError as e:
        applog.debug(f"Не удалось удалить файл очереди скачивания: {e}")


def count_files(tasks: list) -> int:
    """Сколько всего файлов осталось в сохранённых задачах - для текста
    вопроса пользователю."""
    total = 0
    for task in tasks:
        data_list = task.get("data_list") if isinstance(task, dict) else None
        if isinstance(data_list, list):
            total += len(data_list)
    return total
