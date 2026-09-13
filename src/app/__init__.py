import threading

from src.core import applog
from src.core.download.manager import DownloadManager
from src.core.network.client import Rule34API
from src.core.search.engine import SearchEngine
from src.core.storage.config import ConfigManager
from src.app.ai import AiMixin
from src.app.history import HistoryMixin
from src.app.search import SearchMixin
from src.app.startup import StartupMixin
from src.ui.gui import AppGUI


class Rule34ArtistFinderApp(SearchMixin, HistoryMixin, StartupMixin, AiMixin, AppGUI):
    """Бизнес-логика приложения поверх "пустого" интерфейса AppGUI: поиск и
    автодополнение (SearchMixin), история авторов (HistoryMixin),
    автообновление и проверки при старте (StartupMixin), AI-анализ
    (AiMixin)."""

    def __init__(self):
        super().__init__()

        # --- Настройки ядра ---
        self.site_credentials = {
            "rule34.xxx": {"api_key": "", "user_id": ""},
            "allthefallen.moe": {"api_key": "", "user_id": ""},
            "rule34.paheal.net": {"api_key": "", "user_id": ""}
        }
        self._current_site_internal = "rule34.xxx"
        self.download_queue = []
        self.timer_id = None
        self.MAX_WORKERS = 4
        self.stop_event = threading.Event()

        # --- Инициализация модулей ---
        self.api = Rule34API()
        self.downloader = DownloadManager(self)
        self.search_engine = SearchEngine(self)
        self.config_manager = ConfigManager(self)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Загружаем настройки и отрисовываем UI
        self.config_manager.load_settings()
        self.create_widgets()
        self._apply_net_frame_visibility()
        self.apply_theme()
        self.update_ui_texts()
        self.update_history_tree()
        self.run_startup_checks()
        self._check_for_updates()

    def apply_network_settings(self):
        """Вызывается при изменении поля прокси (см. gui.py, http_proxy_entry)."""
        try:
            self.api.set_proxy(self.http_proxy_var.get().strip())
        except Exception as e:
            applog.warning(f"Не удалось применить настройки прокси: {e}")
        self.save_settings()

    def save_settings(self):
        self.config_manager.save_settings()
