"""Пути к пользовательским данным приложения: стандартный каталог данных
пользователя ОС, с автоматическим переносом файлов из старого расположения
(рабочей директории процесса) при первом запуске."""
import os
import shutil
import sys

APP_DIR_NAME = "Rule34ArtistFinder"

SETTINGS_FILENAME = "r34_settings.dat"
OLD_SETTINGS_FILENAME = "r34_settings.json"
CREDENTIALS_FILENAME = "r34_credentials.dat"
FOUND_ARTISTS_FILENAME = "found_artists.dat"
DOWNLOAD_QUEUE_FILENAME = "download_queue.dat"
DEBUG_LOG_FILENAME = "debug_search.txt"
CRASH_LOG_FILENAME = "crash_log.txt"
APP_LOG_FILENAME = "app.log"

_cached_app_dir: str | None = None


def _legacy_dir() -> str:
    """Каталог, где приложение раньше (и по умолчанию сейчас) искало свои файлы —
    текущая рабочая директория процесса. Оставляем как аварийный вариант, если
    основной каталог данных пользователя недоступен по какой-то причине."""
    return os.getcwd()


def get_app_data_dir() -> str:
    """Возвращает (и создаёт при необходимости) каталог для данных приложения:
    %APPDATA%\\Rule34ArtistFinder на Windows, ~/Library/Application Support/... на macOS,
    $XDG_DATA_HOME/... (обычно ~/.local/share/...) на Linux."""
    global _cached_app_dir
    if _cached_app_dir:
        return _cached_app_dir

    try:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

        app_dir = os.path.join(base, APP_DIR_NAME)
        os.makedirs(app_dir, exist_ok=True)
        _cached_app_dir = app_dir
        return app_dir
    except OSError:
        # Не смогли создать/использовать штатный каталог - работаем как раньше.
        return _legacy_dir()


def resolve_data_file(filename: str) -> str:
    """Возвращает актуальный путь к пользовательскому файлу данных и, если нужно,
    молча переносит файл из старого места (рядом с exe / в CWD) в новое (AppData),
    чтобы настройки/история не "потерялись" при обновлении с более старой версии."""
    app_dir = get_app_data_dir()
    new_path = os.path.join(app_dir, filename)

    if app_dir == _legacy_dir():
        return new_path  # legacy-каталог и новый - это одно и то же место

    legacy_path = os.path.join(_legacy_dir(), filename)

    if not os.path.exists(new_path) and os.path.exists(legacy_path):
        try:
            shutil.move(legacy_path, new_path)
        except OSError:
            return legacy_path  # не смогли перенести - продолжаем работать со старым файлом

    return new_path
