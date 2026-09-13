import os
import sys
import tkinter as tk

from src.core import applog
from src.ui.gui.action_stubs import ActionStubsMixin
from src.ui.gui.i18n import I18nMixin
from src.ui.gui.layout import LayoutMixin
from src.ui.gui.log import LogMixin
from src.ui.gui.menu import MenuMixin
from src.ui.gui.state import StateMixin
from src.ui.gui.theme import ThemeMixin
from src.ui.gui.utils import UtilsMixin


def get_asset_path(filename: str) -> str:
    meipass = getattr(sys, '_MEIPASS', '')
    if isinstance(meipass, str) and meipass:
        base_path = meipass
    else:
        current_file = str(__file__)
        # Этот файл - src/ui/gui/__init__.py, поэтому до корня проекта (где
        # лежит папка assets/) нужно подняться на три уровня. При сборке
        # через PyInstaller сюда не заходим - sys._MEIPASS уже указывает на
        # корень распакованных данных.
        base_path = os.path.abspath(os.path.join(os.path.dirname(current_file), "..", "..", ".."))
    return os.path.join(base_path, "assets", filename)


class AppGUI(MenuMixin, ThemeMixin, I18nMixin, LayoutMixin, StateMixin, UtilsMixin, LogMixin, ActionStubsMixin, tk.Tk):
    """Главное окно приложения: строит и переключает интерфейс (виджеты,
    тема, язык). Конкретные действия (поиск, скачивание и т.д.) реализует
    подкласс Rule34ArtistFinderApp в src/app/; см. action_stubs.py для
    контракта таких методов."""
    def __init__(self):
        super().__init__()
        self.geometry("1050x760")

        try:
            icon_path = get_asset_path("1.png")
            icon_img = tk.PhotoImage(file=icon_path)
            self.iconphoto(False, icon_img)
        except tk.TclError as e:
            applog.warning(f"Не удалось загрузить иконку приложения: {e}")

        self.font_main = ("Segoe UI", 10)
        self.font_bold = ("Segoe UI", 10, "bold")

        self.included_tags: set[str] = set()
        self.excluded_tags: set[str] = set()

        self.search_history: set[str] = set()
        self.copied_artists: list = []
        self.found_artists_data: list = []
        self.artist_marks: dict = {}
        self.grouped_history_data: dict = {}

        self.autocomplete_map_include: dict = {}
        self.autocomplete_map_exclude: dict = {}

        self.api_key_var = tk.StringVar(value="")
        self.user_id_var = tk.StringVar(value="")
        self.site_var = tk.StringVar(value="rule34.xxx")

        self.any_amount_var = tk.BooleanVar(value=False)
        self.min_posts_var = tk.StringVar(value="1000")
        self.dl_limit_var = tk.StringVar(value="0")
        self.skip_bad_marks_var = tk.BooleanVar(value=True)
        self.exclude_q_var = tk.BooleanVar(value=False)
        self.exclude_ai_var = tk.BooleanVar(value=False)
        self.auto_save_var = tk.BooleanVar(value=True)
        self.auto_exclude_copied_var = tk.BooleanVar(value=False)
        self.debug_var = tk.BooleanVar(value=False)
        self.dl_exclude_var = tk.StringVar(value="")
        self.show_ai_tab_var = tk.BooleanVar(value=False)
        self.show_hist_site_var = tk.BooleanVar(value=True)

        self.ai_provider_var = tk.StringVar(value="Ollama (Локально)")
        self.ai_api_key_var = tk.StringVar(value="")
        self.ai_model_var = tk.StringVar(value="llama3")

        self.check_updates_var = tk.BooleanVar(value=True)
        self.dl_workers_var = tk.StringVar(value="8")
        self.check_workers_var = tk.StringVar(value="32")
        self.tag_workers_var = tk.StringVar(value="4")
        self.http_proxy_var = tk.StringVar(value="")
        self.net_toggle_var = tk.BooleanVar(value=False)

        self.gal_base_dir: str = ""
        self.current_lang: str = "ru"
        self.current_theme: str = "dark"
        self.last_log_was_progress: bool = False

        self.is_searching: bool = False
        self.is_downloading: bool = False
        self.is_prompting_dl: bool = False

        self.menubar = None
        self.settings_menu = None
        self.lang_menu = None
        self.theme_menu = None
        self.help_menu = None

        self.left_frame = None
        self.left_bottom = None
        self.lbl_final_query = None
        self.query_preview_text = None
        self.btn_start = None
        self.btn_stop = None
        self.btn_clear = None
        self.btn_dl_query = None

        self.canvas = None
        self.scrollbar = None
        self.scrollable_frame = None
        self.canvas_window = None

        self.api_frame = None
        self.lbl_site = None
        self.site_combo = None
        self.lbl_api_key = None
        self.api_key_entry = None
        self.lbl_user_id = None
        self.user_id_entry = None
        self.btn_help_api = None

        self.filter_frame = None
        self.chk_any_amount = None
        self.min_posts_container = None
        self.lbl_min_posts = None
        self.min_posts_spin = None
        self.dl_container = None
        self.lbl_dl_limit = None
        self.dl_limit_spin = None
        self.chk_skip_bad = None
        self.chk_exclude_q = None
        self.chk_exclude_ai = None
        self.chk_auto_save = None
        self.chk_auto_exclude_copied = None
        self.chk_debug_mode = None
        self.lbl_dl_exclude = None
        self.dl_exclude_entry = None

        self.net_frame = None
        self.net_warning_lbl = None
        self.lbl_dl_workers = None
        self.dl_workers_spin = None
        self.lbl_check_workers = None
        self.check_workers_spin = None
        self.lbl_tag_workers = None
        self.tag_workers_spin = None
        self.lbl_http_proxy = None
        self.http_proxy_entry = None
        self.chk_check_updates = None

        self.lbl_add_tag = None
        self.entry_include = None
        self.listbox_include = None
        self.lbl_exclude_tag = None
        self.entry_exclude = None
        self.listbox_exclude = None

        self.right_frame = None
        self.notebook = None
        self.tab_logs = None
        self.btn_clear_log = None
        self.download_progress = None
        self.log_area = None

        self.tab_history = None
        self.hist_search_var = tk.StringVar()
        self.entry_hist_search = None
        self.btn_hist_search = None
        self.history_tree = None
        self.btn_hist_run = None
        self.btn_hist_copy = None
        self.btn_hist_delete = None
        self.btn_hist_clear = None
        self.btn_hist_export = None
        self.btn_hist_download = None

        self.tab_gallery = None

        self.tab_ai = None
        self.ai_settings = None
        self.lbl_ai_provider = None
        self.ai_provider_combo = None
        self.lbl_ai_api_key = None
        self.ai_api_key_entry = None
        self.btn_help_ai_keys = None
        self.lbl_ai_model = None
        self.btn_ai = None
        self.ai_text_area = None

        self.fix_hotkeys()
        self.bind_all("<Button-3>", self.global_context_menu)
        self.build_menu()

