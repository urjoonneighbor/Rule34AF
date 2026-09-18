import threading
import tkinter as tk
from tkinter import ttk

from src.ui.gallery.grid import GridMixin
from src.ui.gallery.viewer import ViewerMixin


class GalleryTab(GridMixin, ViewerMixin, ttk.Frame):
    """Вкладка "Локальная Галерея": список авторов, сетка миниатюр с
    пагинацией (GridMixin, grid.py) и полноэкранный просмотрщик с зумом
    (ViewerMixin, viewer.py)."""

    def __init__(self, notebook, app, initial_dir="", initial_positions=None, initial_solo_only=False):
        super().__init__(notebook)
        self.viewer_img_id = None
        self.app = app

        self.gal_base_dir: str = initial_dir
        self.gal_current_artist: str = ""
        self.gal_artist_meta: dict = {}
        self.gal_filtered_files: list[str] = []
        self.gal_current_page: int = 1
        self.gal_items_per_page: int = 50
        self.gal_stop_thumb_thread = threading.Event()
        self.gal_images_refs: list = []

        # Страница, на которой пользователь остановился у каждого автора
        # (имя автора -> номер страницы) - чтобы при повторном выборе автора
        # (в т.ч. после перезапуска программы, см. ConfigManager) открывать
        # сразу то же место, а не всегда страницу 1. initial_positions
        # приходит из сохранённых настроек (см. src/ui/gui/layout.py).
        self.gal_artist_positions: dict[str, int] = (
            dict(initial_positions) if isinstance(initial_positions, dict) else {}
        )
        # Абсолютный индекс миниатюры (в gal_filtered_files), к которой нужно
        # прокрутить сетку после того, как страница с ней отрендерится - см.
        # jump_to_gallery_index() в grid.py, вызывается при закрытии
        # полноэкранного просмотрщика.
        self._gal_pending_scroll_idx: int | None = None

        self.gal_local_tags: set[str] = set()
        self.gal_auto_timer = None

        # "Только сольные": прячет файлы, на которых кроме текущего автора
        # висит тег другого известного автора (коллаборации). Известные авторы
        # берутся локально - из папок галереи и истории поисков, см.
        # _get_other_artist_names() в grid.py.
        self.gal_solo_only_var = tk.BooleanVar(value=bool(initial_solo_only))
        self.chk_gal_solo_only = None

        self.btn_gal_load = None
        self.btn_gal_recover = None
        self.listbox_gal_artists = None
        self.lbl_gal_search = None
        self.gal_search_var = tk.StringVar()
        self.entry_gal_search = None
        self.btn_gal_search = None
        self.gal_auto_frame = None
        self.gal_listbox_auto = None
        self.canvas_frame = None
        self.gal_canvas = None
        self.gal_scrollbar = None
        self.gal_scroll_frame = None
        self.btn_gal_first = None
        self.btn_gal_prev = None
        self.lbl_gal_page = None
        self.btn_gal_next = None
        self.btn_gal_last = None

        self.viewer_window = None
        self.viewer_idx = 0
        self.viewer_canvas = None
        self.video_lbl = None
        self.btn_open_video = None
        self.current_viewer_img = None
        self.current_photo = None
        self.resize_timer = None

        # Переменные для зума и панорамирования
        self.v_zoom = 1.0
        self.v_pan_x = 0
        self.v_pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0

        # Раскрытие просмотрщика на весь экран (F11) - см. viewer.py
        self._viewer_fullscreen = False
        self._viewer_geom_before_fullscreen = None

        self.create_widgets()
        if self.gal_base_dir:
            self._refresh_gallery_artists()

        self.gal_last_folder_count = -1
        self._start_folder_polling()
