"""Тесты для src.core.download.queue_store - сохранения очереди скачивания
между запусками приложения."""
import os

import pytest

from src.core.download import queue_store
from src.core.storage import paths


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Перенаправляет каталог данных приложения во временную папку."""
    monkeypatch.setattr(paths, "get_app_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "_cached_app_dir", str(tmp_path), raising=False)
    return tmp_path


def _task(artist="artist_a", files=2):
    return {
        "artist": artist,
        "dir": "D:\\downloads",
        "custom_name": "",
        "data_list": [{"url": f"https://example.com/{artist}_{i}.jpg", "size": 0, "tags": "1girl", "md5": ""}
                      for i in range(files)],
    }


def test_load_returns_empty_when_nothing_saved(data_dir):
    assert queue_store.load_queue() == []


def test_save_and_load_roundtrip(data_dir):
    tasks = [_task("artist_a", 2), _task("artist_b", 3)]
    queue_store.save_queue(tasks)

    assert queue_store.load_queue() == tasks


def test_save_empty_queue_removes_saved_state(data_dir):
    queue_store.save_queue([_task()])
    assert queue_store.load_queue()

    queue_store.save_queue([])
    assert queue_store.load_queue() == []
    assert not os.path.exists(os.path.join(str(data_dir), paths.DOWNLOAD_QUEUE_FILENAME))


def test_clear_queue_removes_file(data_dir):
    queue_store.save_queue([_task()])
    queue_store.clear_queue()

    assert queue_store.load_queue() == []


def test_clear_queue_on_missing_file_is_noop(data_dir):
    queue_store.clear_queue()  # не должно кидать исключение


def test_corrupt_file_is_ignored(data_dir):
    with open(os.path.join(str(data_dir), paths.DOWNLOAD_QUEUE_FILENAME), "wb") as f:
        f.write(b"this is not our format at all")

    assert queue_store.load_queue() == []


def test_tasks_without_files_or_target_are_dropped(data_dir):
    good = _task("artist_ok", 1)
    queue_store.save_queue([
        good,
        {"artist": "no_files", "dir": "D:\\x", "data_list": []},
        {"artist": "", "dir": "D:\\x", "data_list": [{"url": "u"}]},
        {"artist": "no_dir", "dir": "", "data_list": [{"url": "u"}]},
        "не словарь вовсе",
    ])

    assert queue_store.load_queue() == [good]


def test_queue_from_another_format_version_is_ignored(data_dir, monkeypatch):
    queue_store.save_queue([_task()])
    monkeypatch.setattr(queue_store, "_QUEUE_FORMAT_VERSION", 999)

    assert queue_store.load_queue() == []


def test_count_files_sums_across_tasks(data_dir):
    assert queue_store.count_files([_task("a", 2), _task("b", 5)]) == 7
    assert queue_store.count_files([]) == 0
    assert queue_store.count_files(["мусор", {"artist": "x"}]) == 0
