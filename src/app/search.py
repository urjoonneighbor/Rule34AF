import re
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox


class SearchMixin:
    """Поиск/фильтры и автодополнение тегов, запуск и остановка поиска."""

    def on_site_change(self, _event=None, force_update_labels=False):
        new_site = self.site_var.get()
        if not force_update_labels and getattr(self, "_current_site_internal", None) != new_site:
            old_site = self._current_site_internal
            self.site_credentials[old_site] = {"api_key": self.api_key_var.get(), "user_id": self.user_id_var.get()}
            creds = self.site_credentials.get(new_site, {"api_key": "", "user_id": ""})
            self.api_key_var.set(creds.get("api_key", ""))
            self.user_id_var.set(creds.get("user_id", ""))
            self._current_site_internal = new_site

        self.api.set_site(new_site)
        if new_site == "rule34.xxx" or new_site == "allthefallen.moe":
            self.lbl_api_key.config(
                text=self.tr("auth_r34_key") if new_site == "rule34.xxx" else self.tr("auth_atf_key"))
            self.lbl_user_id.config(
                text=self.tr("auth_r34_user") if new_site == "rule34.xxx" else self.tr("auth_atf_user"))
            state = tk.NORMAL if not self.is_searching and not self.is_downloading else tk.DISABLED
            self.api_key_entry.config(state=state)
            self.user_id_entry.config(state=state)
            self.btn_help_api.config(state=state)
        elif new_site == "rule34.paheal.net":
            self.lbl_api_key.config(text=self.tr("auth_paheal_key"))
            self.lbl_user_id.config(text=self.tr("auth_paheal_user"))
            self.api_key_entry.config(state=tk.DISABLED)
            self.user_id_entry.config(state=tk.DISABLED)
            self.btn_help_api.config(state=tk.DISABLED)

        self.update_preview()

    def show_api_help(self):
        site = self.site_var.get()
        if site == "rule34.xxx":
            webbrowser.open("https://rule34.xxx/index.php?page=account&s=options")
        elif site == "allthefallen.moe":
            webbrowser.open("https://allthefallen.moe/profile")

    def download_by_query(self):
        self.downloader.download_by_query()

    def schedule_autocomplete(self, event, tag_type):
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return
        if event.keysym in ("Up", "Down", "Left", "Right", "Return"): return
        if self.timer_id is not None: self.after_cancel(self.timer_id)
        self.timer_id = self.after(350, lambda: self.fetch_autocomplete(tag_type))

    def fetch_autocomplete(self, tag_type):
        entry = self.entry_include if tag_type == "include" else self.entry_exclude
        listbox = self.listbox_include if tag_type == "include" else self.listbox_exclude
        query = entry.get().strip()
        listbox.delete(0, tk.END)
        if len(query) < 2: return
        api_key = self.api_key_var.get().strip()
        user_id = self.user_id_var.get().strip()

        def task():
            data = self.api.fetch_autocomplete(query, api_key, user_id)
            if data: self.after(0, lambda: self.update_listbox(listbox, data, tag_type))

        threading.Thread(target=task, daemon=True).start()

    def update_listbox(self, listbox, data, tag_type):
        listbox.delete(0, tk.END)
        mapping = self.autocomplete_map_include if tag_type == "include" else self.autocomplete_map_exclude
        mapping.clear()
        for item in data:
            label = item.get("label", item.get("value"))
            value = item.get("value")
            mapping[label] = value
            listbox.insert(tk.END, label)

    def add_tag(self, tag_type, from_enter=False):
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return
        listbox = self.listbox_include if tag_type == "include" else self.listbox_exclude
        entry = self.entry_include if tag_type == "include" else self.entry_exclude
        target_set = self.included_tags if tag_type == "include" else self.excluded_tags

        tag = ""
        selection = listbox.curselection()
        if selection:
            display_text = listbox.get(selection[0])
            mapping = self.autocomplete_map_include if tag_type == "include" else self.autocomplete_map_exclude
            tag = mapping.get(display_text, display_text)
        elif from_enter:
            if listbox.size() > 0:
                display_text = listbox.get(0)
                mapping = self.autocomplete_map_include if tag_type == "include" else self.autocomplete_map_exclude
                tag = mapping.get(display_text, display_text)
            else:
                tag = entry.get().strip()

        if not tag: return

        if re.search(r'\(\d+\)$', tag):
            tag = re.sub(r'\s*\(\d+\)$', '', tag).strip()

        target_set.add(tag)
        entry.delete(0, tk.END)
        listbox.delete(0, tk.END)
        self.update_preview()

    def clear_all(self):
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return
        self.included_tags.clear()
        self.excluded_tags.clear()
        self.update_preview()
        self.entry_include.delete(0, tk.END)
        self.entry_exclude.delete(0, tk.END)
        self.listbox_include.delete(0, tk.END)
        self.listbox_exclude.delete(0, tk.END)
        self.clear_log()

    def stop_search(self):
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False):
            self.log(self.tr("log_stop"))
            self.download_queue.clear()
            self.stop_event.set()
            self.btn_stop.config(state=tk.DISABLED)

    def start_search(self):
        try:
            if not self.included_tags:
                messagebox.showerror(self.tr("error"), self.tr("err_no_tag"))
                return
            final_query = self.update_preview()
            if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return

            self.clear_log()

            self.is_searching = True
            self.stop_event.clear()
            self._set_ui_state(is_working=True)
            self.notebook.select(self.tab_logs)
            self.log(self.tr('log_start').format(final_query))

            min_posts_val = self.min_posts_var.get()
            min_posts = int(min_posts_val) if min_posts_val.isdigit() else 0
            any_amount = self.any_amount_var.get()
            auto_save = self.auto_save_var.get()
            debug_mode = self.debug_var.get()

            threading.Thread(target=self.search_engine.search_worker,
                             args=(final_query, min_posts, any_amount, auto_save, debug_mode), daemon=True).start()
        except Exception as e:
            self.log(self.tr("err_start_search").format(e))
            self.is_searching = False
            self._set_ui_state(is_working=False)

