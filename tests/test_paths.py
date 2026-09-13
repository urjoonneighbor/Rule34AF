"""Тесты для src.core.storage.paths - определения каталога данных
приложения и миграции старых файлов из legacy-расположения."""
import os

import pytest

from src.core.storage import paths


@pytest.fixture(autouse=True)
def _reset_cached_app_dir():
    """paths.get_app_data_dir() кэширует результат в модульной переменной -
    сбрасываем её до и после каждого теста, чтобы тесты не влияли друг
    на друга через порядок запуска."""
    paths._cached_app_dir = None
    yield
    paths._cached_app_dir = None


def test_get_app_data_dir_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    app_dir = paths.get_app_data_dir()

    assert os.path.isdir(app_dir)
    assert app_dir == os.path.join(str(tmp_path), paths.APP_DIR_NAME)


def test_get_app_data_dir_is_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    first = paths.get_app_data_dir()
    # Изменяем окружение - но кэш должен вернуть то же самое значение.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "other"))
    second = paths.get_app_data_dir()

    assert first == second


def test_resolve_data_file_migrates_legacy_file(tmp_path, monkeypatch):
    xdg_home = tmp_path / "xdg"
    legacy_cwd = tmp_path / "legacy_cwd"
    xdg_home.mkdir()
    legacy_cwd.mkdir()

    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_home))
    monkeypatch.chdir(legacy_cwd)

    legacy_file = legacy_cwd / "r34_settings.dat"
    legacy_file.write_text("old settings content")

    new_path = paths.resolve_data_file("r34_settings.dat")

    assert os.path.exists(new_path)
    assert not legacy_file.exists()
    with open(new_path, "r", encoding="utf-8") as f:
        assert f.read() == "old settings content"


def test_resolve_data_file_no_legacy_file_returns_new_path(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    new_path = paths.resolve_data_file("r34_settings.dat")
    assert not os.path.exists(new_path)
    assert new_path == os.path.join(str(tmp_path), paths.APP_DIR_NAME, "r34_settings.dat")


def test_resolve_data_file_does_not_overwrite_existing_new_file(tmp_path, monkeypatch):
    xdg_home = tmp_path / "xdg"
    legacy_cwd = tmp_path / "legacy_cwd"
    xdg_home.mkdir()
    legacy_cwd.mkdir()

    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_home))
    monkeypatch.chdir(legacy_cwd)

    app_dir = os.path.join(str(xdg_home), paths.APP_DIR_NAME)
    os.makedirs(app_dir, exist_ok=True)
    with open(os.path.join(app_dir, "r34_settings.dat"), "w", encoding="utf-8") as f:
        f.write("new content")

    legacy_file = legacy_cwd / "r34_settings.dat"
    legacy_file.write_text("old content, should not overwrite")

    new_path = paths.resolve_data_file("r34_settings.dat")

    with open(new_path, "r", encoding="utf-8") as f:
        assert f.read() == "new content"
    # Legacy-файл остаётся нетронутым, т.к. в новом месте уже что-то есть.
    assert legacy_file.exists()
