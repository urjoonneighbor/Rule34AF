import tkinter as tk


class StateMixin:
    """Блокировка/разблокировка интерфейса во время поиска и скачивания,
    плюс прогресс-бар скачивания."""

    def _progress_start(self, maximum: int):
        if not self.download_progress: return
        self.download_progress.pack(side=tk.LEFT, padx=(0, 10))
        self.download_progress.config(maximum=max(1, maximum), value=0)

    def _progress_update(self, value: int):
        if not self.download_progress: return
        self.download_progress.config(value=value)

    def _progress_stop(self):
        if not self.download_progress: return
        self.download_progress.pack_forget()

    @staticmethod
    def validate_spinbox(p_str: str) -> bool:
        if p_str == "" or p_str.isdigit(): return True
        return False

    def _set_ui_state(self, is_working: bool):
        state = tk.DISABLED if is_working else tk.NORMAL

        self.btn_start.config(state=state)
        self.btn_clear.config(state=state)
        self.btn_stop.config(state=tk.NORMAL if is_working else tk.DISABLED)
        self.btn_dl_query.config(state=state)

        self.site_combo.config(state=state if is_working else "readonly")
        self.api_key_entry.config(state=state)
        self.user_id_entry.config(state=state)
        self.btn_help_api.config(state=state)

        self.chk_any_amount.config(state=state)
        if not is_working:
            self.toggle_min_posts_state()
        else:
            self.min_posts_spin.config(state=state)

        self.dl_limit_spin.config(state=state)
        self.dl_exclude_entry.config(state=state)
        self.dl_workers_spin.config(state=state)
        self.check_workers_spin.config(state=state)
        self.tag_workers_spin.config(state=state)
        self.http_proxy_entry.config(state=state)
        self.chk_exclude_q.config(state=state)
        self.chk_exclude_ai.config(state=state)
        self.chk_auto_save.config(state=state)
        self.chk_auto_exclude_copied.config(state=state)
        self.chk_skip_bad.config(state=state)
        self.chk_debug_mode.config(state=state)

        self.entry_include.config(state=state)
        self.entry_exclude.config(state=state)
        self.btn_clear_log.config(state=state)

        self.ai_provider_combo.config(state=state if is_working else "readonly")
        self.ai_api_key_entry.config(state=state)
        self.btn_ai.config(state=state)
        self.btn_help_ai_keys.config(state=state)

        self.btn_hist_run.config(state=state)
        self.btn_hist_delete.config(state=state)
        self.btn_hist_clear.config(state=state)
        self.btn_hist_download.config(state=state)

    def _check_unlock_ui(self):
        if not self.is_searching and not self.is_downloading and not self.is_prompting_dl:
            self._set_ui_state(is_working=False)

