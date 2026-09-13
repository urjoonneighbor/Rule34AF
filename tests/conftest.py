"""Общий conftest для всех тестов: добавляет корень проекта в sys.path,
чтобы `import src...` работал независимо от того, откуда запущен pytest,
и предоставляет пару общих fixture-заглушек, переиспользуемых в разных
тестовых модулях (fake Tk-переменная и fake-объект приложения)."""
import os
import sys

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class FakeVar:
    """Минимальная замена tkinter.StringVar/BooleanVar/IntVar - без Tk-рантайма
    (не поднимает реальное окно), но с тем же интерфейсом .get()/.set(),
    которым пользуется остальной код (ConfigManager и т.д.)."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeApp:
    """Минимальная замена Rule34ArtistFinderApp для тестов ConfigManager -
    содержит только те атрибуты, которые реально читает/пишет
    src.core.storage.config.ConfigManager, без создания настоящего Tk-окна."""

    def __init__(self):
        self.site_var = FakeVar("rule34.xxx")
        self.api_key_var = FakeVar("")
        self.user_id_var = FakeVar("")
        self.any_amount_var = FakeVar(False)
        self.min_posts_var = FakeVar("1000")
        self.dl_limit_var = FakeVar("0")
        self.skip_bad_marks_var = FakeVar(True)
        self.exclude_q_var = FakeVar(False)
        self.exclude_ai_var = FakeVar(False)
        self.auto_save_var = FakeVar(True)
        self.auto_exclude_copied_var = FakeVar(False)
        self.debug_var = FakeVar(False)
        self.dl_exclude_var = FakeVar("")
        self.show_ai_tab_var = FakeVar(False)
        self.show_hist_site_var = FakeVar(True)

        self.site_credentials = {
            "rule34.xxx": {"api_key": "", "user_id": ""},
            "allthefallen.moe": {"api_key": "", "user_id": ""},
            "rule34.paheal.net": {"api_key": "", "user_id": ""},
        }
        self._current_site_internal = "rule34.xxx"
        self.included_tags = set()
        self.excluded_tags = set()
        self.artist_marks = {}
        self.gal_base_dir = ""
        self.current_lang = "ru"
        self.current_theme = "dark"
        self.grouped_history_data = {}

        class _FakeApi:
            def set_site(self_inner, site):
                pass

        self.api = _FakeApi()


@pytest.fixture
def fake_app():
    return FakeApp()
