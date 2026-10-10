import tkinter as tk

from src.ui.locales import TRANSLATIONS


class I18nMixin:
    """Локализация интерфейса (RU/EN)."""

    def tr(self, key: str) -> str:
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS.get("ru", {}))
        res = lang_dict.get(key)
        if res: return str(res)

        # Фолбэк на русский, если ключа нет в английском
        fallback_dict = TRANSLATIONS.get("ru", {})
        res_fb = fallback_dict.get(key)
        if res_fb: return str(res_fb)

        return str(key)

    def set_lang(self, lang: str):
        if self.current_lang == lang: return
        old_lang = self.current_lang
        self.current_lang = lang

        self._translate_log_area(old_lang, lang)
        self.update_ui_texts()
        self.save_settings()

    def _translate_log_area(self, old_lang: str, new_lang: str):
        """ Умный сканер: заменяет старые статические логи на новый язык """
        old_dict = TRANSLATIONS.get(old_lang, TRANSLATIONS.get("ru", {}))
        new_dict = TRANSLATIONS.get(new_lang, TRANSLATIONS.get("ru", {}))

        self.log_area.config(state=tk.NORMAL)
        content = self.log_area.get(1.0, tk.END)

        # Выбираем только те фразы, где нет динамического форматирования "{}"
        replacements = []
        for k, old_str in old_dict.items():
            if isinstance(old_str, str) and "{}" not in old_str:
                new_str = new_dict.get(k, "")
                if new_str and old_str != new_str:
                    replacements.append((old_str, new_str))

        # Сортируем по длине фразы, чтобы сначала менять длинные (иначе короткие сломают текст)
        replacements.sort(key=lambda x: len(x[0]), reverse=True)

        for old_str, new_str in replacements:
            content = content.replace(old_str, new_str)

        self.log_area.delete(1.0, tk.END)
        # Tkinter при get() добавляет технический \n, срезаем его при возврате
        if content.endswith("\n"):
            content = content[:-1]
        self.log_area.insert(1.0, content)
        self.log_area.config(state=tk.DISABLED)

    def update_ui_texts(self):
        self.title(self.tr("app_title"))
        try:
            self.menubar.entryconfig(0, label=self.tr("menu_settings"))
            self.menubar.entryconfig(1, label=self.tr("menu_help"))
        except tk.TclError:
            self.menubar.entryconfig(1, label=self.tr("menu_settings"))
            self.menubar.entryconfig(2, label=self.tr("menu_help"))

        self.settings_menu.entryconfig(0, label=self.tr("menu_lang"))
        self.settings_menu.entryconfig(1, label=self.tr("menu_theme"))
        self.theme_menu.entryconfig(0, label=self.tr("menu_theme_dark"))
        self.theme_menu.entryconfig(1, label=self.tr("menu_theme_light"))
        self.settings_menu.entryconfig(4, label=self.tr("menu_check_updates"))
        self.settings_menu.entryconfig(5, label=self.tr("net_toggle"))
        self.help_menu.entryconfig(0, label=self.tr("menu_help_app"))
        self.help_menu.entryconfig(1, label=self.tr("menu_about"))

        self.api_frame.config(text=self.tr("auth_frame"))
        self.lbl_site.config(text=self.tr("site_source"))
        self.btn_help_api.config(text=self.tr("btn_help_api"))

        self.filter_frame.config(text=self.tr("filter_frame"))
        self.chk_any_amount.config(text=self.tr("any_amount"))
        self.lbl_min_posts.config(text=self.tr("min_posts"))
        self.lbl_dl_limit.config(text=self.tr("dl_limit"))
        self.chk_skip_bad.config(text=self.tr("skip_bad_marks"))
        self.chk_exclude_q.config(text=self.tr("exclude_q"))
        self.chk_exclude_ai.config(text=self.tr("exclude_ai"))
        self.auto_save_var.set(self.auto_save_var.get())
        self.chk_auto_save.config(text=self.tr("auto_save"))
        self.chk_auto_exclude_copied.config(text=self.tr("auto_exclude_copied"))
        self.chk_debug_mode.config(text=self.tr("debug_mode"))

        self.lbl_dl_exclude.config(text=self.tr("dl_exclude_tags"))

        self.net_warning_lbl.config(text=self.tr("net_warning"))
        self.net_frame.config(text=self.tr("net_frame"))
        self.lbl_dl_workers.config(text=self.tr("net_dl_workers"))
        self.lbl_check_workers.config(text=self.tr("net_check_workers"))
        self.lbl_tag_workers.config(text=self.tr("net_tag_workers"))
        self.lbl_http_proxy.config(text=self.tr("net_http_proxy"))

        self.lbl_add_tag.config(text=self.tr("add_tag"))
        self.lbl_exclude_tag.config(text=self.tr("exclude_tag"))
        self.lbl_final_query.config(text=self.tr("final_query"))

        self.btn_start.config(text=self.tr("btn_search"))
        self.btn_stop.config(text=self.tr("btn_stop"))
        self.btn_clear.config(text=self.tr("btn_clear"))
        self.btn_dl_query.config(text=self.tr("btn_dl_query"))

        self.notebook.tab(self.tab_logs, text=self.tr("tab_logs"))
        self.notebook.tab(self.tab_history, text=self.tr("tab_history"))

        if hasattr(self, "tab_gallery") and self.tab_gallery:
            try:
                self.notebook.tab(self.tab_gallery, text=self.tr("tab_gallery"))
                self.tab_gallery.update_texts()
            except tk.TclError:
                pass
        try:
            self.notebook.tab(self.tab_ai, text=self.tr("tab_ai"))
        except tk.TclError:
            pass

        self.btn_clear_log.config(text=self.tr("btn_clear_log"))

        self.lbl_hist_search.config(text=self.tr("hist_search_hint"))
        self.btn_hist_search.config(text=self.tr("btn_hist_search"))
        self.history_tree.heading("#0", text=self.tr("tree_query_artist"))
        self.history_tree.heading("count", text=self.tr("tree_count"))
        self.history_tree.heading("mark", text=self.tr("tree_mark"))
        self.history_tree.heading("site", text=self.tr("tree_site"))
        self.chk_hist_show_site.config(text=self.tr("chk_hist_show_site"))
        self.btn_hist_run.config(text=self.tr("btn_hist_run"))
        self.btn_hist_copy.config(text=self.tr("btn_hist_copy"))
        self.btn_hist_delete.config(text=self.tr("btn_hist_delete"))
        self.btn_hist_clear.config(text=self.tr("btn_hist_clear"))
        self.btn_hist_export.config(text=self.tr("btn_hist_export"))
        self.btn_hist_download.config(text=self.tr("btn_hist_download"))

        self.ai_settings.config(text=self.tr("ai_settings"))
        self.lbl_ai_provider.config(text=self.tr("ai_provider"))
        self.lbl_ai_api_key.config(text=self.tr("api_key"))
        self.lbl_ai_model.config(text=self.tr("ai_model"))
        self.btn_ai.config(text=self.tr("btn_ai_run"))
        self.btn_help_ai_keys.config(text=self.tr("btn_help_ai_keys"))

        current_ai_text = self.ai_text_area.get(1.0, tk.END).strip()
        hints = [
            "Нейросеть проанализирует историю твоих любимых авторов и предложит похожих художников.\nДобавляй авторов в историю (ставь им хорошие оценки), а затем жми старт.",
            "The AI will analyze your saved artists and suggest similar ones.\nRate artists as 'Excellent' in the History tab, then click Run."
        ]
        if not current_ai_text or current_ai_text in hints:
            self.ai_text_area.config(state=tk.NORMAL)
            self.ai_text_area.delete(1.0, tk.END)
            self.ai_text_area.insert(tk.END, self.tr("ai_hint"))
            self.ai_text_area.config(state=tk.DISABLED)

