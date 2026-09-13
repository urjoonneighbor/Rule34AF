import json
import os
from typing import Any

from src.core import applog
from src.core.storage import blob_codec, paths, secure_store


class ConfigManager:
    def __init__(self, app: Any):
        self.app = app
        # Настройки (без чувствительных данных) - обычный кодированный файл,
        # его нет смысла шифровать: там нет ничего секретного.
        self.settings_file: str = paths.resolve_data_file(paths.SETTINGS_FILENAME)
        self.old_settings_file: str = paths.resolve_data_file(paths.OLD_SETTINGS_FILENAME)
        # Учётные данные (API-ключи, User ID/логины) - отдельный файл,
        # который шифруется через src.core.storage.secure_store.
        self.credentials_file: str = paths.resolve_data_file(paths.CREDENTIALS_FILENAME)

    # ------------------------------------------------------------------
    # Учётные данные (шифруются отдельно от остальных настроек)
    # ------------------------------------------------------------------
    def _load_credentials(self) -> dict | None:
        if not os.path.exists(self.credentials_file):
            return None
        try:
            with open(self.credentials_file, "rb") as f:
                payload = f.read()
            raw = secure_store.decrypt(payload)
            if raw is None:
                return None
            return json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, TypeError) as e:
            applog.warning(f"Не удалось прочитать файл учётных данных: {e}")
            return None

    def _save_credentials(self, creds: dict) -> None:
        try:
            raw = json.dumps(creds, ensure_ascii=False).encode("utf-8")
            payload = secure_store.encrypt(raw)
            with open(self.credentials_file, "wb") as f:
                f.write(payload)
        except (OSError, ValueError, TypeError) as e:
            applog.error(f"Не удалось сохранить учётные данные: {e}")

    # ------------------------------------------------------------------
    # Основные настройки
    # ------------------------------------------------------------------
    def load_settings(self) -> None:
        data = None

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "rb") as f:
                    data = blob_codec.decode_json(f.read())
            except OSError as e:
                applog.warning(f"Не удалось прочитать файл настроек ({self.settings_file}): {e}")
        elif os.path.exists(self.old_settings_file):
            try:
                with open(self.old_settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                applog.warning(f"Не удалось прочитать старый файл настроек: {e}")

        # Учётные данные (API-ключи/User ID) сначала пробуем прочитать из
        # нового зашифрованного файла. Если его нет (первый запуск после
        # обновления со старой версии) - мигрируем их из основного файла
        # настроек, где они раньше хранились в открытом виде.
        creds = self._load_credentials()
        migrate_credentials_from_legacy = creds is None

        if isinstance(data, dict):
            try:
                if creds is None:
                    old_api = str(data.get("api_key", ""))
                    old_user = str(data.get("user_id", ""))

                    legacy_creds = data.get("credentials")
                    if isinstance(legacy_creds, dict):
                        creds = legacy_creds
                    else:
                        creds = {
                            "rule34.xxx": {"api_key": old_api, "user_id": old_user},
                            "allthefallen.moe": {"api_key": "", "user_id": ""},
                            "rule34.paheal.net": {"api_key": "", "user_id": ""}
                        }

                self.app.site_credentials = creds

                loaded_site = str(data.get("site", "rule34.xxx"))
                self.app.site_var.set(loaded_site)
                self.app._current_site_internal = loaded_site

                current_creds = self.app.site_credentials.get(loaded_site, {})
                if not isinstance(current_creds, dict): current_creds = {"api_key": "", "user_id": ""}

                self.app.api_key_var.set(str(current_creds.get("api_key", "")))
                self.app.user_id_var.set(str(current_creds.get("user_id", "")))

                self.app.any_amount_var.set(bool(data.get("any_amount", False)))
                self.app.min_posts_var.set(str(data.get("min_posts", 1000)))
                self.app.dl_limit_var.set(str(data.get("dl_limit", 0)))
                self.app.skip_bad_marks_var.set(bool(data.get("skip_bad_marks", True)))
                self.app.exclude_q_var.set(bool(data.get("exclude_questionable", False)))
                self.app.exclude_ai_var.set(bool(data.get("exclude_ai", False)))
                self.app.auto_save_var.set(bool(data.get("auto_save", True)))
                self.app.auto_exclude_copied_var.set(bool(data.get("auto_exclude_copied", False)))
                self.app.debug_var.set(bool(data.get("debug_mode", False)))

                inc_tags = data.get("included_tags", [])
                self.app.included_tags = set(inc_tags) if isinstance(inc_tags, list) else set()

                exc_tags = data.get("excluded_tags", [])
                self.app.excluded_tags = set(exc_tags) if isinstance(exc_tags, list) else set()

                self.app.artist_marks = data.get("artist_marks", {})
                self.app.dl_exclude_var.set(str(data.get("dl_exclude_tags", "")))
                self.app.show_ai_tab_var.set(bool(data.get("show_ai_tab", False)))
                self.app.show_hist_site_var.set(bool(data.get("show_hist_site", True)))

                self.app.gal_base_dir = str(data.get("gal_base_dir", ""))
                if getattr(self.app, "tab_gallery", None):
                    self.app.tab_gallery.gal_base_dir = self.app.gal_base_dir

                # На какой странице пользователь остановился у каждого автора
                # в локальной галерее (имя автора -> номер страницы). tab_gallery
                # на момент load_settings() обычно ещё не создан - значение
                # подхватывается конструктором GalleryTab (см. gui/layout.py).
                raw_positions = data.get("gal_artist_positions", {})
                self.app.gal_artist_positions = raw_positions if isinstance(raw_positions, dict) else {}
                if getattr(self.app, "tab_gallery", None):
                    self.app.tab_gallery.gal_artist_positions = self.app.gal_artist_positions

                self.app.current_lang = str(data.get("language", "ru"))
                self.app.current_theme = str(data.get("theme", "dark"))

                # --- Настройки обновлений и производительности (могут отсутствовать у старых профилей) ---
                if hasattr(self.app, "check_updates_var"):
                    self.app.check_updates_var.set(bool(data.get("check_updates", True)))
                if hasattr(self.app, "dl_workers_var"):
                    self.app.dl_workers_var.set(str(data.get("dl_workers", 8)))
                if hasattr(self.app, "check_workers_var"):
                    self.app.check_workers_var.set(str(data.get("check_workers", 32)))
                if hasattr(self.app, "tag_workers_var"):
                    self.app.tag_workers_var.set(str(data.get("tag_workers", 4)))
                if hasattr(self.app, "http_proxy_var"):
                    self.app.http_proxy_var.set(str(data.get("http_proxy", "")))
                if hasattr(self.app, "net_toggle_var"):
                    self.app.net_toggle_var.set(bool(data.get("net_toggle", False)))

                # --- НОВАЯ СИСТЕМА ИСТОРИИ (С миграцией старой) ---
                self.app.grouped_history_data = data.get("grouped_history", {})

                # Если новая структура пустая, пытаемся спасти старые данные
                if not self.app.grouped_history_data:
                    manual_group = "⭐ Сохраненные авторы"

                    old_results = data.get("search_results", [])
                    if isinstance(old_results, list) and old_results:
                        self.app.grouped_history_data["Последний поиск"] = []
                        for item in old_results:
                            if isinstance(item, (list, tuple)) and len(item) >= 3:
                                artist = item[0]
                                count = item[1]
                                tags = item[3] if len(item) == 4 else []
                                self.app.grouped_history_data["Последний поиск"].append({
                                    "artist": str(artist), "count": count,
                                    "tags": list(tags) if isinstance(tags, list) else []
                                })

                    old_history = data.get("search_history", [])
                    old_copied = data.get("copied_artists", [])
                    if old_history or old_copied:
                        self.app.grouped_history_data[manual_group] = []
                        for h in old_history:
                            self.app.grouped_history_data[manual_group].append(
                                {"artist": str(h), "count": "?", "tags": []})
                        for c in old_copied:
                            name = c.get("name", "") if isinstance(c, dict) else str(c)
                            if name: self.app.grouped_history_data[manual_group].append(
                                {"artist": name, "count": "?", "tags": []})

            except (TypeError, ValueError, AttributeError) as e:
                applog.warning(f"Не удалось разобрать файл настроек, использую значения по умолчанию: {e}")
                self.app.api_key_var.set("")
                self.app.user_id_var.set("")
        else:
            if creds is not None:
                # Основного файла настроек нет/он битый, но зашифрованные
                # учётные данные есть - подставляем хотя бы их.
                self.app.site_credentials = creds
                current_creds = creds.get(self.app.site_var.get(), {})
                self.app.api_key_var.set(str(current_creds.get("api_key", "")))
                self.app.user_id_var.set(str(current_creds.get("user_id", "")))
            else:
                self.app.api_key_var.set("")
                self.app.user_id_var.set("")

        self.app.api.set_site(self.app.site_var.get())

        # Если учётные данные до этого жили только в старом (незащищённом)
        # файле настроек - сразу переносим их в новый зашифрованный файл.
        app_site_credentials = getattr(self.app, "site_credentials", None)
        if migrate_credentials_from_legacy and isinstance(app_site_credentials, dict):
            self._save_credentials(app_site_credentials)

        if hasattr(self.app, "http_proxy_var"):
            try:
                self.app.api.set_proxy(self.app.http_proxy_var.get().strip())
            except Exception as e:
                applog.debug(f"Не удалось применить настройки прокси: {e}")

    def save_settings(self) -> None:
        # Синхронизируем текущий выбранный сайт в общий словарь учётных данных
        # перед сохранением (аналогично тому, что делает on_site_change).
        site_credentials = getattr(self.app, "site_credentials", {})
        if isinstance(site_credentials, dict):
            current_site = self.app.site_var.get()
            site_credentials[current_site] = {
                "api_key": self.app.api_key_var.get(),
                "user_id": self.app.user_id_var.get(),
            }
            self._save_credentials(site_credentials)

        data: dict[str, Any] = {
            "site": self.app.site_var.get(),
            # ВНИМАНИЕ: реальные ключи/логины теперь хранятся отдельно и
            # зашифрованно (см. _save_credentials) - здесь их больше нет.
            "any_amount": self.app.any_amount_var.get(),
            "min_posts": self.app.min_posts_var.get(),
            "dl_limit": self.app.dl_limit_var.get(),
            "skip_bad_marks": self.app.skip_bad_marks_var.get(),
            "exclude_questionable": self.app.exclude_q_var.get(),
            "exclude_ai": self.app.exclude_ai_var.get(),
            "auto_save": self.app.auto_save_var.get(),
            "auto_exclude_copied": self.app.auto_exclude_copied_var.get(),
            "debug_mode": self.app.debug_var.get(),
            "included_tags": list(getattr(self.app, "included_tags", set())),
            "excluded_tags": list(getattr(self.app, "excluded_tags", set())),
            "artist_marks": getattr(self.app, "artist_marks", {}),
            "dl_exclude_tags": self.app.dl_exclude_var.get(),
            "show_ai_tab": self.app.show_ai_tab_var.get(),
            "show_hist_site": self.app.show_hist_site_var.get(),
            "gal_base_dir": getattr(self.app, "gal_base_dir", ""),
            # Источник истины - сам tab_gallery (пользователь мог полистать
            # галерею уже после старта), а не то, что было в момент load_settings().
            "gal_artist_positions": getattr(
                getattr(self.app, "tab_gallery", None), "gal_artist_positions",
                getattr(self.app, "gal_artist_positions", {}),
            ),
            "language": getattr(self.app, "current_lang", "ru"),
            "theme": getattr(self.app, "current_theme", "dark"),

            # Сохраняем ТОЛЬКО новую историю (старые списки больше не нужны)
            "grouped_history": getattr(self.app, "grouped_history_data", {})
        }

        if hasattr(self.app, "check_updates_var"):
            data["check_updates"] = self.app.check_updates_var.get()
        if hasattr(self.app, "dl_workers_var"):
            data["dl_workers"] = self.app.dl_workers_var.get()
        if hasattr(self.app, "check_workers_var"):
            data["check_workers"] = self.app.check_workers_var.get()
        if hasattr(self.app, "tag_workers_var"):
            data["tag_workers"] = self.app.tag_workers_var.get()
        if hasattr(self.app, "http_proxy_var"):
            data["http_proxy"] = self.app.http_proxy_var.get()
        if hasattr(self.app, "net_toggle_var"):
            data["net_toggle"] = self.app.net_toggle_var.get()

        try:
            with open(self.settings_file, "wb") as f:
                f.write(blob_codec.encode_json(data))

            if os.path.exists(self.old_settings_file):
                try:
                    os.remove(self.old_settings_file)
                except OSError:
                    pass
        except (OSError, ValueError, TypeError) as e:
            applog.error(f"Не удалось сохранить настройки: {e}")
