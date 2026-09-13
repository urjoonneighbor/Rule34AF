"""Список авторов, миниатюры и пагинация локальной галереи."""
import math
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import ttk, filedialog
import tkinter as tk

from PIL import Image, ImageTk

from src.core.download.metadata_store import get_file_md5, load_artist_metadata, save_artist_metadata
from src.core.media_types import ALLOWED_EXTENSIONS

_VALID_EXTS_WITH_DOT = {f".{ext}" for ext in ALLOWED_EXTENSIONS}


class GridMixin:
    def create_widgets(self):
        gal_left = ttk.Frame(self, width=200)
        gal_left.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        self.btn_gal_load = ttk.Button(gal_left, command=self.load_gallery_folder)
        self.btn_gal_load.pack(fill=tk.X, pady=(0, 5))

        self.btn_gal_recover = ttk.Button(gal_left, command=self.recover_current_artist_meta)
        self.btn_gal_recover.pack(fill=tk.X, pady=(0, 10))

        self.listbox_gal_artists = tk.Listbox(gal_left, font=self.app.font_main, relief="flat", highlightthickness=1,
                                              selectmode=tk.EXTENDED)
        self.listbox_gal_artists.pack(fill=tk.BOTH, expand=True)
        self.listbox_gal_artists.bind("<<ListboxSelect>>", self.on_gal_artist_select)

        gal_right = ttk.Frame(self)
        gal_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        search_frame = ttk.Frame(gal_right)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        self.lbl_gal_search = ttk.Label(search_frame)
        self.lbl_gal_search.pack(side=tk.LEFT)
        self.entry_gal_search = ttk.Entry(search_frame, textvariable=self.gal_search_var)
        self.entry_gal_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_gal_search.bind("<Return>", lambda _e: self.on_gal_search())
        self.entry_gal_search.bind("<KeyRelease>", self.on_gal_search_key)
        self.btn_gal_search = ttk.Button(search_frame, command=self.on_gal_search)
        self.btn_gal_search.pack(side=tk.LEFT)

        self.gal_auto_frame = ttk.Frame(gal_right)
        self.gal_listbox_auto = tk.Listbox(self.gal_auto_frame, height=5, font=self.app.font_main)
        self.gal_listbox_auto.pack(fill=tk.X)
        self.gal_listbox_auto.bind("<Double-Button-1>", self.on_gal_auto_select)

        self.canvas_frame = ttk.Frame(gal_right)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.gal_canvas = tk.Canvas(self.canvas_frame, highlightthickness=0)
        self.gal_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.gal_canvas.yview)
        self.gal_scroll_frame = ttk.Frame(self.gal_canvas)

        self.gal_scroll_frame.bind(
            "<Configure>",
            lambda _e: self.gal_canvas.configure(scrollregion=self.gal_canvas.bbox("all"))
        )
        self.gal_canvas.create_window((0, 0), window=self.gal_scroll_frame, anchor="nw")
        self.gal_canvas.configure(yscrollcommand=self.gal_scrollbar.set)

        self.gal_canvas.bind('<Enter>', lambda _e: self.gal_canvas.bind_all("<MouseWheel>",
                                                                            lambda ev: self.gal_canvas.yview_scroll(
                                                                                int(-1 * (ev.delta / 120)), "units")))
        self.gal_canvas.bind('<Leave>', lambda _e: self.gal_canvas.unbind_all("<MouseWheel>"))

        self.gal_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.gal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        pagination_frame = ttk.Frame(gal_right)
        pagination_frame.pack(fill=tk.X, pady=(5, 0))

        self.btn_gal_first = ttk.Button(pagination_frame, text="⏮", command=self.gal_first_page, state=tk.DISABLED,
                                        width=3)
        self.btn_gal_first.pack(side=tk.LEFT, padx=2)

        self.btn_gal_prev = ttk.Button(pagination_frame, command=self.gal_prev_page, state=tk.DISABLED)
        self.btn_gal_prev.pack(side=tk.LEFT, expand=True, anchor=tk.E, padx=2)

        self.lbl_gal_page = ttk.Label(pagination_frame, font=self.app.font_main)
        self.lbl_gal_page.pack(side=tk.LEFT, expand=False, anchor=tk.CENTER)

        self.btn_gal_next = ttk.Button(pagination_frame, command=self.gal_next_page, state=tk.DISABLED)
        self.btn_gal_next.pack(side=tk.LEFT, expand=True, anchor=tk.W, padx=2)

        self.btn_gal_last = ttk.Button(pagination_frame, text="⏭", command=self.gal_last_page, state=tk.DISABLED,
                                       width=3)
        self.btn_gal_last.pack(side=tk.LEFT, padx=2)

    def update_texts(self):
        self.btn_gal_load.config(text=self.app.tr("gal_btn_load"))
        self.btn_gal_recover.config(text=self.app.tr("gal_btn_recover"))
        self.lbl_gal_search.config(text=self.app.tr("gal_search_hint"))
        self.btn_gal_search.config(text=self.app.tr("gal_btn_search"))
        self.btn_gal_prev.config(text=self.app.tr("gal_prev"))
        self.btn_gal_next.config(text=self.app.tr("gal_next"))

        total_pages = math.ceil(
            len(self.gal_filtered_files) / self.gal_items_per_page) if self.gal_filtered_files else 1
        self.lbl_gal_page.config(text=self.app.tr("gal_page").format(self.gal_current_page, total_pages))

    def apply_theme(self, bg_main, input_bg, fg_main, select_bg, border_col):
        self.gal_canvas.configure(bg=bg_main)
        self.listbox_gal_artists.configure(bg=input_bg, fg=fg_main, selectbackground=select_bg,
                                           selectforeground="#ffffff", highlightcolor=select_bg,
                                           highlightbackground=border_col)
        self.gal_listbox_auto.configure(bg=input_bg, fg=fg_main, selectbackground=select_bg,
                                        selectforeground="#ffffff", highlightcolor=select_bg,
                                        highlightbackground=border_col)

    def load_gallery_folder(self):
        if not self.gal_base_dir or not os.path.exists(self.gal_base_dir):
            initial_dir = os.getcwd()
        else:
            initial_dir = self.gal_base_dir

        selected_dir = filedialog.askdirectory(initialdir=initial_dir, title=self.app.tr("gal_btn_load"))
        if not selected_dir: return

        self.gal_base_dir = selected_dir
        if hasattr(self.app, 'save_settings'):
            self.app.save_settings()
        self._refresh_gallery_artists()

    def _start_folder_polling(self):
        if self.gal_base_dir and os.path.exists(self.gal_base_dir):
            try:
                current_count = len(
                    [d for d in os.listdir(self.gal_base_dir) if os.path.isdir(os.path.join(self.gal_base_dir, d))])
                if self.gal_last_folder_count != -1 and current_count != self.gal_last_folder_count:
                    self._refresh_gallery_artists(_silent=True)
                self.gal_last_folder_count = current_count
            except OSError:
                pass
        self.poll_timer = self.after(3000, self._start_folder_polling)

    def _refresh_gallery_artists(self, _silent=False):
        sel = self.listbox_gal_artists.curselection()
        sel_val = self.listbox_gal_artists.get(sel[0]) if sel else None

        self.listbox_gal_artists.delete(0, tk.END)
        if not self.gal_base_dir or not os.path.exists(self.gal_base_dir): return

        try:
            for item in os.listdir(self.gal_base_dir):
                full_path = os.path.join(self.gal_base_dir, item)
                if os.path.isdir(full_path):
                    self.listbox_gal_artists.insert(tk.END, item)
        except OSError:
            pass

        if sel_val:
            for i in range(self.listbox_gal_artists.size()):
                if self.listbox_gal_artists.get(i) == sel_val:
                    self.listbox_gal_artists.selection_set(i)
                    self.listbox_gal_artists.see(i)
                    break

    def recover_current_artist_meta(self):
        if not self.gal_base_dir: return
        selections = self.listbox_gal_artists.curselection()
        if not selections: return

        artists_to_recover = [self.listbox_gal_artists.get(i) for i in selections]

        self.app.clear_log()
        self.app.notebook.select(self.app.tab_logs)
        self.app.log(self.app.tr("log_start_recover"))

        def worker():
            api_key = self.app.api_key_var.get().strip()
            user_id = self.app.user_id_var.get().strip()

            for artist in artists_to_recover:
                artist_dir = os.path.join(self.gal_base_dir, artist)
                try:
                    local_files = [f for f in os.listdir(artist_dir) if
                                   f.split('.')[-1].lower() in ALLOWED_EXTENSIONS]
                except OSError:
                    continue

                if not local_files:
                    self.app.log(self.app.tr("log_folder_empty").format(artist))
                    continue

                current_meta = load_artist_metadata(artist_dir)

                missing_files = [f for f in local_files if f not in current_meta]
                if not missing_files:
                    self.app.log(self.app.tr("log_tags_exist").format(len(local_files), artist))
                    continue

                self.app.log(self.app.tr("log_fetching_tags").format(artist, len(missing_files)), is_progress=False)

                data_list = self.app.api.get_image_data(artist, api_key, user_id, 0)
                if not data_list:
                    self.app.log(self.app.tr("log_api_no_data").format(artist))
                    continue

                matched = 0
                safe_name = re.sub(r'[\\/*?:"<>|]', "", artist).strip() or "unknown_artist"

                local_md5_map = {}
                missing_bases = {}

                def hash_worker(worker_file: str):
                    return worker_file, get_file_md5(os.path.join(artist_dir, worker_file))

                with ThreadPoolExecutor(max_workers=8) as ex:
                    futures = [ex.submit(hash_worker, f) for f in missing_files]
                    for fut in as_completed(futures):
                        result_f_name, md5_val = fut.result()
                        if md5_val:
                            local_md5_map[md5_val] = result_f_name
                        missing_bases[os.path.splitext(result_f_name)[0].lower()] = result_f_name

                for idx, item in enumerate(data_list):
                    base_new = f"{safe_name}_{idx + 1:04d}".lower()
                    base_old = f"{safe_name}_{idx + 1}".lower()
                    tags = item.get("tags", "")
                    item_md5 = item.get("md5", "")

                    if item_md5 and item_md5 in local_md5_map:
                        actual_filename = local_md5_map[item_md5]
                        current_meta[actual_filename] = tags
                        matched += 1
                        del local_md5_map[item_md5]
                        base_key = os.path.splitext(actual_filename)[0].lower()
                        if base_key in missing_bases:
                            del missing_bases[base_key]

                    elif base_new in missing_bases:
                        actual_filename = missing_bases[base_new]
                        current_meta[actual_filename] = tags
                        matched += 1
                        del missing_bases[base_new]
                    elif base_old in missing_bases:
                        actual_filename = missing_bases[base_old]
                        current_meta[actual_filename] = tags
                        matched += 1
                        del missing_bases[base_old]

                if matched > 0:
                    try:
                        save_artist_metadata(artist_dir, current_meta)

                        self.app.log(self.app.tr("log_tags_updated").format(artist, matched))

                        if artist == self.gal_current_artist:
                            self.gal_artist_meta = current_meta

                            self.gal_local_tags.clear()
                            for t_str in self.gal_artist_meta.values():
                                self.gal_local_tags.update(t_str.lower().split())

                            # reset_page=False: обновили теги текущего автора - не
                            # нужно сбрасывать пользователя обратно на страницу 1.
                            self.after(0, lambda: self.on_gal_search(reset_page=False))
                    except (OSError, ValueError, TypeError) as e:
                        self.app.log(self.app.tr("err_dat_save").format(e))
                else:
                    self.app.log(self.app.tr("log_no_matches").format(artist))

                leftovers = list(missing_bases.values())
                if leftovers:
                    self.app.log(self.app.tr("log_not_on_server").format(len(leftovers), ", ".join(leftovers)))

            self.app.log(self.app.tr("log_recover_done"))

        threading.Thread(target=worker, daemon=True).start()

    def on_gal_artist_select(self, _event):
        sel = self.listbox_gal_artists.curselection()
        if not sel: return

        self.gal_stop_thumb_thread.set()

        self.gal_current_artist = self.listbox_gal_artists.get(sel[0])
        artist_dir = os.path.join(self.gal_base_dir, self.gal_current_artist)

        self.gal_artist_meta = load_artist_metadata(artist_dir)

        self.gal_local_tags.clear()
        for tags in self.gal_artist_meta.values():
            self.gal_local_tags.update(tags.lower().split())

        # reset_page=False: открываем автора на той странице, где остановились
        # в прошлый раз (см. gal_artist_positions), а не всегда с первой.
        self.on_gal_search(reset_page=False)

    def on_gal_search(self, reset_page=True):
        if not self.gal_current_artist: return

        artist_dir = os.path.join(self.gal_base_dir, self.gal_current_artist)
        search_query = self.gal_search_var.get().strip().lower()

        include_tags = set()
        exclude_tags = set()
        if search_query:
            for tag in search_query.split():
                if tag.startswith("-") and len(tag) > 1:
                    exclude_tags.add(tag[1:])
                else:
                    include_tags.add(tag)

        self.gal_stop_thumb_thread.set()
        self.gal_filtered_files = []
        valid_exts = _VALID_EXTS_WITH_DOT

        meta_lower_keys = {k.lower(): v.lower() for k, v in self.gal_artist_meta.items()}

        try:
            for filename in os.listdir(artist_dir):
                ext = os.path.splitext(filename)[1].lower()
                if ext not in valid_exts: continue

                if include_tags or exclude_tags:
                    file_tags_str = meta_lower_keys.get(filename.lower(), "")
                    file_tags = set(file_tags_str.split())

                    if exclude_tags:
                        has_exclude = False
                        for ex in exclude_tags:
                            if ex in file_tags or any(ex in t for t in file_tags):
                                has_exclude = True
                                break
                        if has_exclude:
                            continue

                    if include_tags:
                        missing_include = False
                        for inc in include_tags:
                            if inc not in file_tags and not any(inc in t for t in file_tags):
                                missing_include = True
                                break
                        if missing_include:
                            continue

                self.gal_filtered_files.append(os.path.join(artist_dir, filename))
        except OSError:
            pass

        if reset_page:
            self.gal_current_page = 1
        else:
            # Восстанавливаем сохранённую страницу этого автора, но не выходим
            # за пределы того, что реально есть после фильтрации (файлы могли
            # быть удалены, папка могла измениться и т.п.).
            total_pages = math.ceil(len(self.gal_filtered_files) / self.gal_items_per_page) or 1
            saved_page = self.gal_artist_positions.get(self.gal_current_artist, 1)
            self.gal_current_page = max(1, min(saved_page, total_pages))

        self._render_gallery_page()

    def gal_first_page(self):
        if self.gal_current_page > 1:
            self.gal_current_page = 1
            self._render_gallery_page()

    def gal_prev_page(self):
        if self.gal_current_page > 1:
            self.gal_current_page -= 1
            self._render_gallery_page()

    def gal_next_page(self):
        total_pages = math.ceil(len(self.gal_filtered_files) / self.gal_items_per_page)
        if self.gal_current_page < total_pages:
            self.gal_current_page += 1
            self._render_gallery_page()

    def gal_last_page(self):
        total_pages = math.ceil(len(self.gal_filtered_files) / self.gal_items_per_page)
        if total_pages == 0: total_pages = 1
        if self.gal_current_page < total_pages:
            self.gal_current_page = total_pages
            self._render_gallery_page()

    def jump_to_gallery_index(self, abs_idx: int):
        """Переключает сетку на страницу, содержащую файл с абсолютным
        индексом abs_idx (в gal_filtered_files), и прокручивает список к его
        миниатюре. Вызывается при закрытии полноэкранного просмотрщика, чтобы
        вернуться туда же, где пользователь остановился, даже если он
        пролистал там на другую картинку через стрелки."""
        if not self.gal_filtered_files:
            return

        abs_idx = max(0, min(abs_idx, len(self.gal_filtered_files) - 1))
        target_page = abs_idx // self.gal_items_per_page + 1

        self._gal_pending_scroll_idx = abs_idx

        if target_page != self.gal_current_page:
            self.gal_current_page = target_page
            self._render_gallery_page()
        else:
            # Страница та же самая - сетка уже отрендерена, просто прокручиваем.
            self._scroll_to_pending_thumb()

    def _scroll_to_pending_thumb(self):
        target_idx = self._gal_pending_scroll_idx
        if target_idx is None:
            return
        start_idx = (self.gal_current_page - 1) * self.gal_items_per_page
        for widget in self.gal_scroll_frame.winfo_children():
            if getattr(widget, "_gal_abs_idx", None) == target_idx:
                self._gal_pending_scroll_idx = None
                self._scroll_canvas_to_widget(widget)
                return
        # Миниатюра ещё не отрисована (страница только начала грузиться) -
        # _add_thumb_to_ui сама вызовет прокрутку, когда до неё дойдёт очередь.
        _ = start_idx

    def _scroll_canvas_to_widget(self, widget):
        try:
            if not widget.winfo_exists(): return
            self.gal_scroll_frame.update_idletasks()
            total_h = self.gal_scroll_frame.winfo_height()
            if total_h <= 0: return
            fraction = max(0.0, min(1.0, widget.winfo_y() / total_h))
            self.gal_canvas.yview_moveto(fraction)
        except tk.TclError:
            pass

    def _render_gallery_page(self):
        self.gal_stop_thumb_thread.set()

        if self.gal_current_artist:
            self.gal_artist_positions[self.gal_current_artist] = self.gal_current_page

        for widget in self.gal_scroll_frame.winfo_children():
            widget.destroy()
        self.gal_images_refs.clear()

        self.gal_stop_thumb_thread = threading.Event()
        current_stop_event = self.gal_stop_thumb_thread

        total_files = len(self.gal_filtered_files)
        total_pages = math.ceil(total_files / self.gal_items_per_page)
        if total_pages == 0: total_pages = 1

        self.lbl_gal_page.config(text=self.app.tr("gal_page").format(self.gal_current_page, total_pages))

        self.btn_gal_first.config(state=tk.NORMAL if self.gal_current_page > 1 else tk.DISABLED)
        self.btn_gal_prev.config(state=tk.NORMAL if self.gal_current_page > 1 else tk.DISABLED)
        self.btn_gal_next.config(state=tk.NORMAL if self.gal_current_page < total_pages else tk.DISABLED)
        self.btn_gal_last.config(state=tk.NORMAL if self.gal_current_page < total_pages else tk.DISABLED)

        if total_files == 0:
            lbl = ttk.Label(self.gal_scroll_frame, text=self.app.tr("gal_empty"), font=self.app.font_main)
            lbl.grid(row=0, column=0, padx=20, pady=20)
            return

        lbl_loading = ttk.Label(self.gal_scroll_frame, text=self.app.tr("gal_loading"), font=self.app.font_main)
        lbl_loading.grid(row=0, column=0, padx=20, pady=20)

        start_idx = (self.gal_current_page - 1) * self.gal_items_per_page
        end_idx = start_idx + self.gal_items_per_page
        page_files = self.gal_filtered_files[start_idx:end_idx]

        threading.Thread(target=self._thumb_worker, args=(page_files, start_idx, lbl_loading, current_stop_event),
                         daemon=True).start()

    def _thumb_worker(self, files, start_abs_idx, lbl_loading, stop_event):
        row, col = 0, 0
        max_cols = 5

        def safe_destroy_loading():
            if not stop_event.is_set() and lbl_loading.winfo_exists():
                lbl_loading.destroy()

        self.after(0, safe_destroy_loading)

        for i, filepath in enumerate(files):
            if stop_event.is_set(): break

            try:
                ext = filepath.split('.')[-1].lower()

                if ext in ['mp4', 'webm', 'avi', 'mkv']:
                    img = Image.new('RGB', (150, 150), color='#2C3E50')
                else:
                    img = Image.open(filepath)
                    img.thumbnail((150, 150), Image.Resampling.LANCZOS)

                abs_idx = start_abs_idx + i

                self.after(0, self._add_thumb_to_ui, img, row, col, ext, abs_idx, stop_event)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            except OSError:
                pass

    def _add_thumb_to_ui(self, img, row, col, ext, abs_idx, stop_event):
        if stop_event.is_set(): return

        photo = ImageTk.PhotoImage(img)
        self.gal_images_refs.append(photo)

        bg_color = "#e74c3c" if ext in ['mp4', 'webm'] else self.app.cget('bg')
        frame = tk.Frame(self.gal_scroll_frame, bg=bg_color, bd=2)
        frame._gal_abs_idx = abs_idx
        frame.grid(row=row, column=col, padx=5, pady=5)

        btn = tk.Button(frame, image=photo, relief="flat", command=lambda idx=abs_idx: self.open_media_viewer(idx))
        btn.pack()

        if ext in ['mp4', 'webm', 'avi']:
            tk.Label(frame, text=self.app.tr("gal_video_label"), fg="white", bg="#e74c3c",
                     font=("Segoe UI", 8, "bold")).pack(fill=tk.X)

        if abs_idx == getattr(self, "_gal_pending_scroll_idx", None):
            self._gal_pending_scroll_idx = None
            self.after(30, lambda f=frame: self._scroll_canvas_to_widget(f))

    def on_gal_search_key(self, event):
        if event.keysym in ("Return", "Up", "Down", "Left", "Right"): return
        if self.gal_auto_timer:
            self.after_cancel(self.gal_auto_timer)
        self.gal_auto_timer = self.after(300, self.show_gal_autocomplete)

    def show_gal_autocomplete(self):
        query = self.gal_search_var.get().lower()
        words = query.split()

        if not words or query.endswith(" "):
            self.gal_auto_frame.pack_forget()
            return

        current_word = words[-1]
        is_minus = current_word.startswith("-")
        search_word = current_word[1:] if is_minus else current_word

        if len(search_word) < 2:
            self.gal_auto_frame.pack_forget()
            return

        matches = [t for t in self.gal_local_tags if search_word in t]
        if not matches:
            self.gal_auto_frame.pack_forget()
            return

        self.gal_listbox_auto.delete(0, tk.END)
        for m in sorted(matches)[:15]:
            self.gal_listbox_auto.insert(tk.END, f"-{m}" if is_minus else m)

        self.gal_auto_frame.pack(fill=tk.X, before=self.canvas_frame)

    def on_gal_auto_select(self, _event):
        sel = self.gal_listbox_auto.curselection()
        if not sel: return
        tag = self.gal_listbox_auto.get(sel[0])

        query = self.gal_search_var.get()
        words = query.split()
        if words:
            words[-1] = tag
        else:
            words = [tag]

        self.gal_search_var.set(" ".join(words) + " ")
        self.gal_auto_frame.pack_forget()
        self.entry_gal_search.focus_set()
        self.entry_gal_search.icursor(tk.END)

        self.on_gal_search()

