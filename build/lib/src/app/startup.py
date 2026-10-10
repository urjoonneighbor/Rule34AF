import threading
import webbrowser
from tkinter import messagebox

from src.core.download import queue_store
from src.core.network.updater import check_for_updates_async


class StartupMixin:
    """Автообновление, проверка доступности серверов и статуса учётных
    данных при старте, закрытие приложения."""

    def _check_for_updates(self):
        if not self.check_updates_var.get():
            return

        def on_new_version(tag, html_url):
            self.after(0, lambda: self._show_update_notice(tag, html_url))

        check_for_updates_async(on_new_version)

    def _show_update_notice(self, tag, html_url):
        self.log(self.tr("log_update_available").format(tag))
        if messagebox.askyesno(self.tr("msg_update_title"), self.tr("msg_update_prompt").format(tag)):
            webbrowser.open(html_url)

    def _has_saved_credentials(self, site: str) -> str:
        """Возвращает ключ локализации со статусом сохранённых учётных данных сайта.

        Для текущего выбранного сайта смотрим на живые значения полей ввода
        (они попадают в self.site_credentials только при переключении сайта,
        см. on_site_change), для остальных - на уже сохранённый словарь.
        """
        if site == "rule34.paheal.net":
            # У paheal нет API-ключа/User ID - поля отключены в on_site_change.
            return "cred_status_not_required"

        if site == getattr(self, "_current_site_internal", None):
            api_key = self.api_key_var.get().strip()
            user_id = self.user_id_var.get().strip()
        else:
            creds = self.site_credentials.get(site, {})
            api_key = str(creds.get("api_key", "")).strip()
            user_id = str(creds.get("user_id", "")).strip()

        return "cred_status_saved" if (api_key or user_id) else "cred_status_missing"

    def run_startup_checks(self):
        self.log(self.tr("log_check_servers"))

        sites = ["rule34.xxx", "allthefallen.moe", "rule34.paheal.net"]
        # Статус сохранённых кредов читаем на UI-потоке (это tkinter-переменные),
        # а не внутри worker() ниже, который выполняется в фоновом потоке.
        cred_statuses = {site: self.tr(self._has_saved_credentials(site)) for site in sites}

        def worker():
            results = self.api.check_servers_bulk(sites)

            log_lines = [self.tr("log_server_status")]
            for site in sites:
                is_ok = results.get(site, False)
                status = self.tr("log_server_ok") if is_ok else self.tr("log_server_fail")
                log_lines.append(f"  • {site}: {status} ({cred_statuses[site]})")

            self.after(0, lambda: self.log("\n".join(log_lines)))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _pending_download_files(self) -> int:
        """Сколько файлов осталось скачать: задача в работе плюс очередь."""
        tasks = []
        current = getattr(self, "current_download_task", None)
        if current:
            tasks.append(current)
        tasks.extend(getattr(self, "download_queue", []))
        return queue_store.count_files(tasks)

    def check_unfinished_downloads(self):
        """Спрашивает при запуске, продолжать ли скачивание, прерванное в
        прошлый раз. Вызывается уже после отрисовки интерфейса (см.
        Rule34ArtistFinderApp.__init__), чтобы диалог не опередил окно."""
        tasks = queue_store.load_queue()
        if not tasks:
            return

        files_left = queue_store.count_files(tasks)
        if messagebox.askyesno(
            self.tr("msg_resume_dl_title"),
            self.tr("msg_resume_dl_prompt").format(files_left, len(tasks)),
        ):
            self.downloader.resume_saved_queue(tasks)
        else:
            queue_store.clear_queue()
            self.log(self.tr("log_dl_resume_declined"))

    def on_closing(self):
        # Скачивание в процессе - предупреждаем и даём передумать. Само
        # состояние очереди сохраняем до destroy(): поток скачивания
        # daemon-овый, после выхода из mainloop он может не успеть
        # доработать свой finally.
        pending = self._pending_download_files()
        if (self.is_downloading or pending) and not messagebox.askyesno(
            self.tr("msg_exit_dl_title"),
            self.tr("msg_exit_dl_prompt").format(pending),
        ):
            return

        self.is_closing = True
        if pending:
            self.downloader._persist_queue()

        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): self.stop_event.set()
        if hasattr(self, "tab_gallery"):
            self.tab_gallery.gal_stop_thumb_thread.set()
        self.save_settings()
        self.destroy()

