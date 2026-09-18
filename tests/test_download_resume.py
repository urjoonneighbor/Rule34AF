"""Тесты возобновления прерванного скачивания: что очередь переживает
закрытие приложения, а уже скачанные файлы не качаются заново."""
import os
import threading

import pytest

from src.app.startup import StartupMixin
from src.core.download import queue_store
from src.core.download.manager import DownloadManager
from src.core.storage import paths


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "get_app_data_dir", lambda: str(tmp_path / "appdata"))
    monkeypatch.setattr(paths, "_cached_app_dir", str(tmp_path / "appdata"), raising=False)
    os.makedirs(str(tmp_path / "appdata"), exist_ok=True)
    return tmp_path


class FakeApi:
    """Вместо сети просто создаёт файл. Может "уронить" приложение (как при
    закрытии окна) после заданного числа успешных скачиваний."""

    def __init__(self, app=None, stop_after=None):
        self.app = app
        self.stop_after = stop_after
        self.downloaded_urls = []
        self._lock = threading.Lock()

    def download_file(self, url, filepath):
        with self._lock:
            if self.stop_after is not None and len(self.downloaded_urls) >= self.stop_after:
                # Имитируем закрытие приложения прямо посреди задачи.
                self.app.is_closing = True
                self.app.stop_event.set()
                return False
            self.downloaded_urls.append(url)

        with open(filepath, "wb") as f:
            f.write(b"payload")
        return True


class FakeApp:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.download_queue = []
        self.current_download_task = None
        self.is_downloading = False
        self.is_closing = False
        self.stop_event = threading.Event()
        self.logs = []
        self.api = FakeApi(self)

    def log(self, msg, is_progress=False):
        self.logs.append(msg)

    def tr(self, key):
        return key

    def after(self, _delay, func=None, *args):
        if callable(func):
            func(*args)

    # Заглушки того, что настоящий app подмешивает из UI-миксинов.
    def _check_unlock_ui(self):
        pass

    def _progress_start(self, _total):
        pass

    def _progress_update(self, _done):
        pass

    def _progress_stop(self):
        pass


def _task(base_dir, artist="artist_a", files=4):
    return {
        "artist": artist,
        "dir": base_dir,
        "custom_name": "",
        "data_list": [{"url": f"https://example.com/{artist}_{i}.jpg", "size": 7, "tags": "1girl", "md5": ""}
                      for i in range(files)],
    }


def test_interrupted_download_is_saved_and_resumed(data_dir):
    base_dir = str(data_dir / "downloads")
    os.makedirs(base_dir, exist_ok=True)

    # --- Первый запуск: скачали 2 файла из 4 и закрыли приложение ---
    app = FakeApp(base_dir)
    app.api = FakeApi(app, stop_after=2)
    manager = DownloadManager(app)

    first_task = _task(base_dir, "artist_a", files=4)
    second_task = _task(base_dir, "artist_b", files=2)
    app.download_queue.extend([first_task, second_task])
    manager._persist_queue()

    manager.download_worker_loop()

    # Прерванная задача не потерялась вместе с остатком очереди
    saved = queue_store.load_queue()
    assert saved == [first_task, second_task]
    assert len(app.api.downloaded_urls) == 2

    downloaded_before = set(app.api.downloaded_urls)

    # --- Второй запуск: продолжаем с того же места ---
    app2 = FakeApp(base_dir)
    manager2 = DownloadManager(app2)

    app2.is_downloading = True  # чтобы resume только наполнил очередь, без потока
    manager2.resume_saved_queue(queue_store.load_queue())
    app2.is_downloading = False
    assert len(app2.download_queue) == 2

    manager2.download_worker_loop()

    # Уже лежащие на диске файлы второй раз не качались
    assert downloaded_before.isdisjoint(app2.api.downloaded_urls)
    # А всё остальное (2 оставшихся у artist_a + 2 у artist_b) - скачалось
    assert len(app2.api.downloaded_urls) == 4

    # Очередь доделана - сохранённого состояния больше нет
    assert queue_store.load_queue() == []
    assert app2.current_download_task is None


def test_user_stop_discards_saved_queue(data_dir):
    base_dir = str(data_dir / "downloads")
    os.makedirs(base_dir, exist_ok=True)

    app = FakeApp(base_dir)
    manager = DownloadManager(app)
    app.download_queue.append(_task(base_dir, "artist_a", files=2))
    manager._persist_queue()
    assert queue_store.load_queue()

    # Пользователь сам нажал "Стоп" (is_closing остаётся False)
    app.stop_event.set()
    manager.download_worker_loop()

    assert queue_store.load_queue() == []
    assert app.download_queue == []


class FakeStartupApp(FakeApp, StartupMixin):
    """FakeApp + настоящие методы закрытия/возобновления из StartupMixin."""

    def __init__(self, base_dir):
        FakeApp.__init__(self, base_dir)
        self.is_searching = False
        self.destroyed = False
        self.settings_saved = False
        self.downloader = DownloadManager(self)

    def save_settings(self):
        self.settings_saved = True

    def destroy(self):
        self.destroyed = True


def test_exit_is_cancelled_when_user_declines(data_dir, monkeypatch):
    import src.app.startup as startup

    base_dir = str(data_dir / "downloads")
    app = FakeStartupApp(base_dir)
    app.is_downloading = True
    app.download_queue.append(_task(base_dir, "artist_a", files=3))

    asked = {}

    def fake_askyesno(title, message):
        asked["title"] = title
        return False  # "нет, не выходить"

    monkeypatch.setattr(startup.messagebox, "askyesno", fake_askyesno)

    app.on_closing()

    assert asked["title"] == "msg_exit_dl_title", "пользователя должны были предупредить"
    assert not app.destroyed, "приложение не должно закрываться, если пользователь передумал"
    assert not app.is_closing


def test_exit_saves_queue_when_user_confirms(data_dir, monkeypatch):
    import src.app.startup as startup

    base_dir = str(data_dir / "downloads")
    app = FakeStartupApp(base_dir)
    app.is_downloading = True
    task = _task(base_dir, "artist_a", files=3)
    app.download_queue.append(task)

    monkeypatch.setattr(startup.messagebox, "askyesno", lambda *a, **k: True)

    app.on_closing()

    assert app.destroyed
    assert app.is_closing
    assert queue_store.load_queue() == [task], "очередь должна пережить закрытие приложения"


def test_exit_without_downloads_does_not_ask(data_dir, monkeypatch):
    import src.app.startup as startup

    app = FakeStartupApp(str(data_dir / "downloads"))

    def fail_ask(*_a, **_k):
        raise AssertionError("без активного скачивания спрашивать не о чем")

    monkeypatch.setattr(startup.messagebox, "askyesno", fail_ask)

    app.on_closing()
    assert app.destroyed


def test_startup_resumes_saved_queue_when_user_agrees(data_dir, monkeypatch):
    import src.app.startup as startup

    base_dir = str(data_dir / "downloads")
    os.makedirs(base_dir, exist_ok=True)
    task = _task(base_dir, "artist_a", files=2)
    queue_store.save_queue([task])

    app = FakeStartupApp(base_dir)
    app.is_downloading = True  # чтобы resume не поднимал настоящий поток
    monkeypatch.setattr(startup.messagebox, "askyesno", lambda *a, **k: True)

    app.check_unfinished_downloads()

    assert app.download_queue == [task]


def test_startup_discards_saved_queue_when_user_declines(data_dir, monkeypatch):
    import src.app.startup as startup

    base_dir = str(data_dir / "downloads")
    queue_store.save_queue([_task(base_dir, "artist_a", files=2)])

    app = FakeStartupApp(base_dir)
    monkeypatch.setattr(startup.messagebox, "askyesno", lambda *a, **k: False)

    app.check_unfinished_downloads()

    assert app.download_queue == []
    assert queue_store.load_queue() == []


def test_existing_file_with_wrong_md5_is_redownloaded(data_dir):
    base_dir = str(data_dir / "downloads")
    artist_dir = os.path.join(base_dir, "artist_a")
    os.makedirs(artist_dir, exist_ok=True)

    # Файл с таким именем уже есть, но содержимое не то, что ждёт сайт
    with open(os.path.join(artist_dir, "artist_a_0001.jpg"), "wb") as f:
        f.write(b"stale content")

    app = FakeApp(base_dir)
    manager = DownloadManager(app)
    task = _task(base_dir, "artist_a", files=1)
    task["data_list"][0]["md5"] = "0" * 32  # заведомо не совпадёт
    app.download_queue.append(task)

    manager.download_worker_loop()

    assert len(app.api.downloaded_urls) == 1
