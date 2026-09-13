import tkinter as tk
from tkinter import scrolledtext, ttk

from src.ui.gallery import GalleryTab


class LayoutMixin:
    """Построение виджетов главного окна: вкладки, поля ввода, кнопки."""

    def create_widgets(self):
        self.left_frame = ttk.Frame(self, padding="15")
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)

        self.left_bottom = ttk.Frame(self.left_frame)
        self.left_bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        self.lbl_final_query = ttk.Label(self.left_bottom, font=self.font_bold)
        self.lbl_final_query.pack(anchor=tk.W, pady=(0, 2))
        self.query_preview_text = scrolledtext.ScrolledText(self.left_bottom, height=4, wrap=tk.WORD,
                                                            font=self.font_main)
        self.query_preview_text.pack(fill=tk.X, pady=(0, 15))
        self.query_preview_text.insert(tk.END, "[Пусто]")
        self.query_preview_text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(self.left_bottom)
        btn_frame.pack(fill=tk.X)
        self.btn_start = ttk.Button(btn_frame, command=self.start_search)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        self.btn_stop = ttk.Button(btn_frame, command=self.stop_search, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        self.btn_clear = ttk.Button(btn_frame, command=self.clear_all)
        self.btn_clear.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_dl_query = ttk.Button(self.left_bottom, command=self.download_by_query)
        self.btn_dl_query.pack(fill=tk.X, pady=(5, 0))

        self.canvas = tk.Canvas(self.left_frame, highlightthickness=0, width=330)
        self.scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        def _on_frame_configure(_event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            if self.canvas.winfo_height() >= self.scrollable_frame.winfo_reqheight(): self.canvas.yview_moveto(0)

        def _on_canvas_configure(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            if self.canvas.winfo_height() >= self.scrollable_frame.winfo_reqheight(): self.canvas.yview_moveto(0)

        self.scrollable_frame.bind("<Configure>", _on_frame_configure)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', _on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            if self.scrollable_frame.winfo_reqheight() > self.canvas.winfo_height():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind('<Enter>', lambda _e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind('<Leave>', lambda _e: self.canvas.unbind_all("<MouseWheel>"))

        self.api_frame = ttk.LabelFrame(self.scrollable_frame, padding="10")
        self.api_frame.pack(fill=tk.X, pady=(0, 15))
        self.lbl_site = ttk.Label(self.api_frame, font=self.font_bold)
        self.lbl_site.pack(anchor=tk.W)
        self.site_combo = ttk.Combobox(self.api_frame, textvariable=self.site_var,
                                       values=["rule34.xxx", "allthefallen.moe", "rule34.paheal.net"], state="readonly",
                                       font=self.font_main)
        self.site_combo.pack(anchor=tk.W, fill=tk.X, pady=(2, 10))
        self.site_combo.bind("<<ComboboxSelected>>", self.on_site_change)
        self.lbl_api_key = ttk.Label(self.api_frame)
        self.lbl_api_key.pack(anchor=tk.W)
        self.api_key_entry = ttk.Entry(self.api_frame, textvariable=self.api_key_var)
        self.api_key_entry.pack(anchor=tk.W, fill=tk.X, pady=(2, 10))
        self.lbl_user_id = ttk.Label(self.api_frame)
        self.lbl_user_id.pack(anchor=tk.W)
        self.user_id_entry = ttk.Entry(self.api_frame, textvariable=self.user_id_var)
        self.user_id_entry.pack(anchor=tk.W, fill=tk.X, pady=(2, 10))
        self.btn_help_api = ttk.Button(self.api_frame, command=self.show_api_help)
        self.btn_help_api.pack(fill=tk.X)

        self.filter_frame = ttk.LabelFrame(self.scrollable_frame, padding="10")
        self.filter_frame.pack(fill=tk.X, pady=(0, 15))
        self.chk_any_amount = ttk.Checkbutton(self.filter_frame, variable=self.any_amount_var,
                                              command=self.toggle_min_posts_state)
        self.chk_any_amount.pack(anchor=tk.W, pady=(0, 5))

        self.min_posts_container = ttk.Frame(self.filter_frame)
        self.min_posts_container.pack(anchor=tk.W, pady=(0, 5))
        self.lbl_min_posts = ttk.Label(self.min_posts_container)
        self.lbl_min_posts.pack(side=tk.LEFT)
        vcmd = (self.register(self.validate_spinbox), '%P')
        self.min_posts_spin = ttk.Spinbox(self.min_posts_container, from_=1, to=9999999,
                                          textvariable=self.min_posts_var, width=12, validate='key',
                                          validatecommand=vcmd)
        self.min_posts_spin.pack(side=tk.LEFT, padx=(10, 0))
        self.toggle_min_posts_state()

        self.dl_container = ttk.Frame(self.filter_frame)
        self.dl_container.pack(anchor=tk.W, pady=(0, 5))
        self.lbl_dl_limit = ttk.Label(self.dl_container)
        self.lbl_dl_limit.pack(side=tk.LEFT)
        self.dl_limit_spin = ttk.Spinbox(self.dl_container, from_=0, to=999999, textvariable=self.dl_limit_var,
                                         width=12, validate='key', validatecommand=vcmd)
        self.dl_limit_spin.pack(side=tk.LEFT, padx=(10, 0))

        self.chk_skip_bad = ttk.Checkbutton(self.filter_frame, variable=self.skip_bad_marks_var)
        self.chk_skip_bad.pack(anchor=tk.W, pady=(0, 5))
        self.chk_exclude_q = ttk.Checkbutton(self.filter_frame, variable=self.exclude_q_var,
                                             command=self.update_preview)
        self.chk_exclude_q.pack(anchor=tk.W, pady=(0, 5))
        self.chk_exclude_ai = ttk.Checkbutton(self.filter_frame, variable=self.exclude_ai_var,
                                              command=self.update_preview)
        self.chk_exclude_ai.pack(anchor=tk.W, pady=(0, 5))
        self.chk_auto_save = ttk.Checkbutton(self.filter_frame, variable=self.auto_save_var)
        self.chk_auto_save.pack(anchor=tk.W, pady=(0, 5))
        self.chk_auto_exclude_copied = ttk.Checkbutton(self.filter_frame, variable=self.auto_exclude_copied_var,
                                                       command=self.update_preview)
        self.chk_auto_exclude_copied.pack(anchor=tk.W, pady=(0, 5))
        self.chk_debug_mode = ttk.Checkbutton(self.filter_frame, variable=self.debug_var)
        self.chk_debug_mode.pack(anchor=tk.W, pady=(0, 5))

        self.lbl_dl_exclude = ttk.Label(self.filter_frame, font=self.font_main)
        self.lbl_dl_exclude.pack(anchor=tk.W, pady=(5, 2))
        self.dl_exclude_entry = ttk.Entry(self.filter_frame, textvariable=self.dl_exclude_var)
        self.dl_exclude_entry.pack(anchor=tk.W, fill=tk.X, pady=(0, 5))

        # Сеть и производительность: обычному пользователю почти никогда не
        # нужны, поэтому по умолчанию блок свёрнут и включается через пункт
        # меню "Настройки" (см. build_menu/toggle_net_frame), чтобы не
        # загромождать вкладку настроек.
        self.net_frame = ttk.LabelFrame(self.scrollable_frame, padding="10")
        # Намеренно НЕ .pack() здесь - блок скрыт, пока пользователь сам не
        # включит его через меню "Настройки" (см. toggle_net_frame).

        self.net_warning_lbl = ttk.Label(self.net_frame, foreground="#e67e22", wraplength=280, justify=tk.LEFT)
        self.net_warning_lbl.pack(anchor=tk.W, fill=tk.X, pady=(0, 10))

        workers_row = ttk.Frame(self.net_frame)
        workers_row.pack(anchor=tk.W, fill=tk.X, pady=(0, 5))
        self.lbl_dl_workers = ttk.Label(workers_row)
        self.lbl_dl_workers.pack(side=tk.LEFT)
        self.dl_workers_spin = ttk.Spinbox(workers_row, from_=1, to=64, textvariable=self.dl_workers_var, width=6,
                                          validate='key', validatecommand=vcmd)
        self.dl_workers_spin.pack(side=tk.LEFT, padx=(10, 15))

        self.lbl_check_workers = ttk.Label(workers_row)
        self.lbl_check_workers.pack(side=tk.LEFT)
        self.check_workers_spin = ttk.Spinbox(workers_row, from_=1, to=128, textvariable=self.check_workers_var,
                                             width=6, validate='key', validatecommand=vcmd)
        self.check_workers_spin.pack(side=tk.LEFT, padx=(10, 15))

        self.lbl_tag_workers = ttk.Label(workers_row)
        self.lbl_tag_workers.pack(side=tk.LEFT)
        self.tag_workers_spin = ttk.Spinbox(workers_row, from_=1, to=32, textvariable=self.tag_workers_var, width=6,
                                           validate='key', validatecommand=vcmd)
        self.tag_workers_spin.pack(side=tk.LEFT, padx=(10, 0))

        self.lbl_http_proxy = ttk.Label(self.net_frame)
        self.lbl_http_proxy.pack(anchor=tk.W, pady=(5, 2))
        self.http_proxy_entry = ttk.Entry(self.net_frame, textvariable=self.http_proxy_var)
        self.http_proxy_entry.pack(anchor=tk.W, fill=tk.X)
        self.http_proxy_entry.bind("<FocusOut>", lambda _e: self.apply_network_settings())

        self.lbl_add_tag = ttk.Label(self.scrollable_frame, font=self.font_bold)
        self.lbl_add_tag.pack(anchor=tk.W, pady=(5, 2))
        self.entry_include = ttk.Entry(self.scrollable_frame)
        self.entry_include.pack(anchor=tk.W, fill=tk.X)
        self.entry_include.bind("<KeyRelease>", lambda e: self.schedule_autocomplete(e, "include"))
        self.entry_include.bind("<Return>", lambda _e: self.add_tag("include", from_enter=True))

        self.listbox_include = tk.Listbox(self.scrollable_frame, height=3, relief="flat", highlightthickness=1,
                                          font=self.font_main)
        self.listbox_include.pack(anchor=tk.W, fill=tk.X, pady=(2, 15))
        self.listbox_include.bind("<Double-Button-1>", lambda _e: self.add_tag("include"))

        self.lbl_exclude_tag = ttk.Label(self.scrollable_frame, font=self.font_bold)
        self.lbl_exclude_tag.pack(anchor=tk.W, pady=(0, 2))
        self.entry_exclude = ttk.Entry(self.scrollable_frame)
        self.entry_exclude.pack(anchor=tk.W, fill=tk.X)
        self.entry_exclude.bind("<KeyRelease>", lambda e: self.schedule_autocomplete(e, "exclude"))
        self.entry_exclude.bind("<Return>", lambda _e: self.add_tag("exclude", from_enter=True))

        self.listbox_exclude = tk.Listbox(self.scrollable_frame, height=3, relief="flat", highlightthickness=1,
                                          font=self.font_main)
        self.listbox_exclude.pack(anchor=tk.W, fill=tk.X, pady=(2, 10))
        self.listbox_exclude.bind("<Double-Button-1>", lambda _e: self.add_tag("exclude"))

        self.right_frame = ttk.Frame(self, padding="15")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 1. ВКЛАДКА ЛОГОВ
        self.tab_logs = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_logs, text="")
        log_btn_frame = ttk.Frame(self.tab_logs)
        log_btn_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        self.btn_clear_log = ttk.Button(log_btn_frame, command=self.clear_log)
        self.btn_clear_log.pack(side=tk.RIGHT)
        # Прогресс-бар скачивания: скрыт, пока не начнётся реальная загрузка (см. _progress_start/_progress_stop)
        self.download_progress = ttk.Progressbar(log_btn_frame, mode="determinate", length=220)
        self.log_area = scrolledtext.ScrolledText(self.tab_logs, wrap=tk.WORD, state=tk.DISABLED, relief="flat",
                                                  font=self.font_main)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 2. ИСТОРИЯ
        self.tab_history = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_history, text="")

        hist_search_frame = ttk.Frame(self.tab_history)
        hist_search_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        self.lbl_hist_search = ttk.Label(hist_search_frame)
        self.lbl_hist_search.pack(side=tk.LEFT)
        self.entry_hist_search = ttk.Entry(hist_search_frame, textvariable=self.hist_search_var)
        self.entry_hist_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_hist_search.bind("<Return>", lambda _e: self.apply_history_filter())
        self.entry_hist_search.bind("<KeyRelease>", self.on_hist_search_key)
        self.btn_hist_search = ttk.Button(hist_search_frame, command=self.apply_history_filter)
        self.btn_hist_search.pack(side=tk.LEFT)

        self.history_tree = ttk.Treeview(self.tab_history, columns=("count", "mark", "site"), show="tree headings",
                                         selectmode="extended")
        self.history_tree.column("#0", width=350, anchor=tk.W)
        self.history_tree.column("count", width=100, anchor=tk.CENTER)
        self.history_tree.column("mark", width=120, anchor=tk.CENTER)
        self.history_tree.column("site", width=130, anchor=tk.CENTER)
        # Колонку site можно скрыть переключателем на тулбаре (chk_hist_show_site)
        # ниже - настоящее значение всегда хранится в values, скрывается только
        # отображение через displaycolumns.
        self.history_tree["displaycolumns"] = (
            ("count", "mark", "site") if self.show_hist_site_var.get() else ("count", "mark"))

        scrollbar_hist = ttk.Scrollbar(self.tab_history, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar_hist.set)
        scrollbar_hist.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.history_tree.bind("<Double-1>", self.on_history_double_click)
        self.history_tree.bind("<Button-3>", self.show_history_context_menu)

        hist_controls = ttk.Frame(self.tab_history)
        hist_controls.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.btn_hist_run = ttk.Button(hist_controls, command=self.run_history_item)
        self.btn_hist_run.pack(side=tk.LEFT, padx=2)
        self.btn_hist_copy = ttk.Button(hist_controls, command=self.copy_history_item)
        self.btn_hist_copy.pack(side=tk.LEFT, padx=2)
        self.btn_hist_delete = ttk.Button(hist_controls, command=self.delete_history_item)
        self.btn_hist_delete.pack(side=tk.LEFT, padx=2)
        self.btn_hist_clear = ttk.Button(hist_controls, command=self.clear_history_list)
        self.btn_hist_clear.pack(side=tk.LEFT, padx=2)
        self.chk_hist_show_site = ttk.Checkbutton(hist_controls, variable=self.show_hist_site_var,
                                                  command=self.toggle_hist_site_column)
        self.chk_hist_show_site.pack(side=tk.LEFT, padx=(10, 2))

        self.btn_hist_export = ttk.Button(hist_controls, command=self.export_history)
        self.btn_hist_export.pack(side=tk.RIGHT, padx=2)
        self.btn_hist_download = ttk.Button(hist_controls, command=self.download_from_history)
        self.btn_hist_download.pack(side=tk.RIGHT, padx=2)

        # 3. ГАЛЕРЕЯ
        self.tab_gallery = GalleryTab(
            self.notebook, self,
            getattr(self, "gal_base_dir", ""),
            getattr(self, "gal_artist_positions", {}),
        )
        self.notebook.add(self.tab_gallery, text="")

        # 4. ИИ АНАЛИТИКА
        self.tab_ai = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_ai, text="")
        self.ai_settings = ttk.LabelFrame(self.tab_ai, padding=15)
        self.ai_settings.pack(fill=tk.X, padx=10, pady=10)
        self.lbl_ai_provider = ttk.Label(self.ai_settings)
        self.lbl_ai_provider.grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.ai_provider_combo = ttk.Combobox(self.ai_settings, textvariable=self.ai_provider_var, state="readonly",
                                              values=["Ollama (Локально)", "LM Studio (Локально)", "Gemini API",
                                                      "OpenAI API", "Qwen API"],
                                              font=self.font_main)
        self.ai_provider_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5, columnspan=2)
        self.ai_provider_combo.bind("<<ComboboxSelected>>", self.on_ai_provider_change)
        self.lbl_ai_api_key = ttk.Label(self.ai_settings)
        self.lbl_ai_api_key.grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.ai_api_key_entry = ttk.Entry(self.ai_settings, textvariable=self.ai_api_key_var)
        self.ai_api_key_entry.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        self.ai_api_key_entry.config(state=tk.DISABLED)
        self.btn_help_ai_keys = ttk.Button(self.ai_settings, command=self.show_ai_help)
        self.btn_help_ai_keys.grid(row=1, column=2, padx=5, sticky=tk.W)
        self.lbl_ai_model = ttk.Label(self.ai_settings)
        self.lbl_ai_model.grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ttk.Entry(self.ai_settings, textvariable=self.ai_model_var).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=5,
                                                                         columnspan=2)
        self.ai_settings.columnconfigure(1, weight=1)

        ai_controls = ttk.Frame(self.tab_ai)
        ai_controls.pack(fill=tk.X, padx=10, pady=5)
        self.btn_ai = ttk.Button(ai_controls, command=self.run_ai_analysis)
        self.btn_ai.pack(side=tk.RIGHT)
        self.ai_text_area = scrolledtext.ScrolledText(self.tab_ai, wrap=tk.WORD, font=self.font_main, relief="flat")
        self.ai_text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.ai_text_area.config(state=tk.DISABLED)

        if not getattr(self, "show_ai_tab_var", tk.BooleanVar(value=False)).get():
            try:
                self.notebook.forget(self.tab_ai)
            except tk.TclError:
                pass

    def toggle_min_posts_state(self):
        if self.any_amount_var.get():
            self.min_posts_spin.config(state=tk.DISABLED)
        else:
            self.min_posts_spin.config(state=tk.NORMAL)
            val = self.min_posts_var.get()
            if val == "0" or val == "": self.min_posts_var.set("1000")

