import os
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox, filedialog

from src.core import applog
from src.core.download import queue_store
from src.core.download.metadata_store import get_file_md5, load_artist_metadata, save_artist_metadata
from src.core.media_types import ALLOWED_EXTENSIONS


class DownloadManager:
    def __init__(self, app):
        self.app = app

    def _persist_queue(self) -> None:
        """Сохраняет на диск то, что ещё не скачано: задачу, которая прямо
        сейчас в работе (она уже вынута из очереди), плюс всю остальную
        очередь. Вызывается на каждом изменении состояния, чтобы после
        внезапного закрытия приложения было с чего продолжить."""
        tasks = []
        current = getattr(self.app, "current_download_task", None)
        if current:
            tasks.append(current)
        tasks.extend(getattr(self.app, "download_queue", []))
        queue_store.save_queue(tasks)

    def resume_saved_queue(self, tasks: list) -> None:
        """Ставит в очередь сохранённые с прошлого запуска задачи и сразу
        запускает скачивание. Уже скачанные файлы внутри задачи отсеются
        сами (см. _download_task в download_worker_loop)."""
        if not tasks:
            return

        self.app.download_queue.extend(tasks)
        self.app.log(self.app.tr("log_dl_resumed").format(queue_store.count_files(tasks), len(tasks)))

        if not self.app.is_downloading:
            self.app.stop_event.clear()
            # Как и в остальных местах, откуда стартует download_worker_loop
            # (prepare_download_worker, prepare_query_download_worker,
            # _ask_mass_download_confirmation) - блокируем интерфейс на время
            # скачивания. Раньше этот вызов тут отсутствовал, и после
            # возобновления скачивания при старте все поля и кнопки
            # оставались доступны для редактирования, хотя скачивание уже
            # шло в фоне.
            self.app.after(0, lambda: getattr(self.app, "_set_ui_state")(is_working=True))
            threading.Thread(target=self.download_worker_loop, daemon=True).start()

    def _get_worker_count(self, var_name: str, default: int) -> int:
        """Читает настраиваемое число потоков из UI (см. gui.py), с безопасным откатом
        на значение по умолчанию, если переменной ещё нет или введено что-то не то."""
        var = getattr(self.app, var_name, None)
        if var is None:
            return default
        try:
            val = int(str(var.get()).strip())
            return val if val > 0 else default
        except (ValueError, TypeError, AttributeError):
            return default

    def _resolve_artist_site(self, artist: str) -> str:
        """Сайт, на котором artist был найден (сохраняется в grouped_history_data
        при поиске, см. src.core.search.engine). Для записей без этого поля
        (например, старых, до появления поля site) - сайт, выбранный сейчас
        в интерфейсе, как разумное значение по умолчанию."""
        for items in self.app.grouped_history_data.values():
            for item in items:
                if str(item.get("artist", "")) == artist:
                    site = item.get("site", "")
                    if site:
                        return site
                    break
        return self.app.site_var.get()

    def _resolve_site_credentials(self, site: str) -> tuple[str, str]:
        """(api_key, user_id) для сайта. Если это сайт, выбранный сейчас в
        интерфейсе, берём значения прямо из полей ввода (могли ещё не
        попасть в site_credentials - см. on_site_change/save_settings),
        иначе - последние сохранённые учётные данные для этого сайта."""
        if site == self.app.site_var.get():
            return self.app.api_key_var.get().strip(), self.app.user_id_var.get().strip()
        creds = getattr(self.app, "site_credentials", {}).get(site, {})
        return creds.get("api_key", ""), creds.get("user_id", "")

    def _check_unknown_sizes(self, data_list: list) -> int:
        """Досчитывает размер файлов с неизвестным (0) размером через HEAD-запросы,
        в несколько потоков, с прогрессом в лог. Возвращает суммарный известный размер."""
        known_bytes = sum(f["size"] for f in data_list)
        unknown_files = [f for f in data_list if f["size"] == 0]
        if not unknown_files:
            return known_bytes

        self.app.log(self.app.tr("log_calc_size").format(len(unknown_files)))
        checked = 0

        def check_size(file_item):
            sz = self.app.api.get_file_size(file_item["url"])
            file_item["size"] = sz
            return sz

        with ThreadPoolExecutor(max_workers=self._get_worker_count("check_workers_var", 32)) as ex:
            futures = [ex.submit(check_size, f) for f in unknown_files]
            for fut in as_completed(futures):
                if self.app.stop_event.is_set(): break
                known_bytes += fut.result()
                checked += 1
                if checked % 5 == 0 or checked == len(unknown_files):
                    self.app.log(self.app.tr("log_calc_progress").format(checked, len(unknown_files)),
                                 is_progress=True)

        return known_bytes

    def download_by_query(self):
        if self.app.is_searching or getattr(self.app, "is_prompting_dl", False) or self.app.is_downloading:
            return

        if not self.app.included_tags:
            messagebox.showerror("Ошибка", "Добавьте хотя бы один тег в выборку перед скачиванием!")
            return

        final_query = self.app.update_preview()

        save_dir = filedialog.askdirectory(title=self.app.tr("dir_select"))
        if not save_dir: return

        limit_val = self.app.dl_limit_var.get()
        limit = int(limit_val) if limit_val.isdigit() else 0

        self.app.clear_log()
        self.app.log("▶ Запуск подготовки скачивания по тегам...")
        self.app.stop_event.clear()

        threading.Thread(target=self.prepare_query_download_worker, args=(final_query, limit, save_dir),
                         daemon=True).start()

    def prepare_query_download_worker(self, query, limit, base_dir):
        try:
            # Используем getattr, чтобы линтер не ругался на вызов protected методов
            self.app.after(0, lambda: getattr(self.app, "_set_ui_state")(is_working=True))
            self.app.after(0, lambda: self.app.notebook.select(self.app.tab_logs))
            api_key = self.app.api_key_var.get().strip()
            user_id = self.app.user_id_var.get().strip()

            local_exclude_set = set()
            for word in query.split():
                if word.startswith("-") and len(word) > 1:
                    local_exclude_set.add(word[1:].lower())

            self.app.log(f"🔍 Сбор данных по запросу: {query}...", is_progress=True)
            data_list = self.app.api.get_image_data(query, api_key, user_id, limit, exclude_tags=local_exclude_set)

            if self.app.stop_event.is_set() or not data_list:
                self.app.log("❌ Ничего не найдено по этому запросу.")
                self.app.after(0, getattr(self.app, "_check_unlock_ui"))
                return

            known_bytes = self._check_unknown_sizes(data_list)

            if self.app.stop_event.is_set():
                self.app.after(0, getattr(self.app, "_check_unlock_ui"))
                return

            total_str = self.app.format_size(known_bytes)
            file_count = len(data_list)

            safe_tags = re.sub(r'[\\/*?:"<>|]', "", query).strip()
            short_name = "_".join(safe_tags.split()[:3])
            if not short_name: short_name = "query_download"
            folder_name = f"Tags_{short_name}"

            temp_queue = [{"artist": folder_name, "dir": base_dir, "data_list": data_list, "custom_name": ""}]

            if self.app.is_downloading or getattr(self.app, "is_prompting_dl", False):
                self.app.download_queue.extend(temp_queue)
                self._persist_queue()
                self.app.log(self.app.tr("log_queue_added").format(file_count, total_str))
            else:
                self.app.is_prompting_dl = True
                self.app.after(0, self._ask_mass_download_confirmation, file_count, total_str, temp_queue)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as err:
            self.app.log(f"Ошибка подготовки: {err}")
            applog.exception("Ошибка подготовки скачивания")
            self.app.after(0, getattr(self.app, "_check_unlock_ui"))

    def recover_metadata_worker(self, artists, base_dir):
        self.app.after(0, lambda: getattr(self.app, "_set_ui_state")(is_working=True))
        self.app.after(0, lambda: self.app.notebook.select(self.app.tab_logs))

        # Как и в prepare_download_worker: запрашиваем теги с сайта, на
        # котором автор был найден, и в конце возвращаем клиент на сайт,
        # видимый в интерфейсе.
        ui_site = self.app.site_var.get()
        try:
            for artist in artists:
                if self.app.stop_event.is_set(): break

                safe_name = re.sub(r'[\\/*?:"<>|]', "", artist).strip() or "unknown_artist"
                artist_dir = os.path.join(base_dir, safe_name)

                if not os.path.exists(artist_dir):
                    self.app.log(f"⏭ Папка для {artist} не найдена, пропускаем.")
                    continue

                local_files = [f for f in os.listdir(artist_dir) if
                               f.split('.')[-1].lower() in ALLOWED_EXTENSIONS]
                if not local_files:
                    self.app.log(f"⚠️ Папка пуста: {artist}.")
                    continue

                artist_meta = load_artist_metadata(artist_dir)

                missing_files = [f for f in local_files if f not in artist_meta]
                if not missing_files:
                    self.app.log(f"✅ Теги для всех {len(local_files)} файлов {artist} уже существуют. Пропускаем.")
                    continue

                self.app.log(f"🔄 Догрузка тегов для {artist} (не хватает для {len(missing_files)} файлов)...")
                artist_site = self._resolve_artist_site(artist)
                api_key, user_id = self._resolve_site_credentials(artist_site)
                self.app.api.set_site(artist_site)
                data_list = self.app.api.get_image_data(artist, api_key, user_id, 0)

                if not data_list:
                    self.app.log(f"❌ API не вернуло данных для {artist}.")
                    continue

                matched = 0
                local_md5_map = {}
                missing_bases = {}

                def hash_worker(worker_file):
                    return worker_file, get_file_md5(os.path.join(artist_dir, worker_file))

                with ThreadPoolExecutor(max_workers=8) as ex:
                    futures = [ex.submit(hash_worker, f) for f in missing_files]
                    for fut in as_completed(futures):
                        res_f_name, md5_val = fut.result()
                        if md5_val:
                            local_md5_map[md5_val] = res_f_name
                        missing_bases[os.path.splitext(res_f_name)[0].lower()] = res_f_name

                for idx, item in enumerate(data_list):
                    base_new = f"{safe_name}_{idx + 1:04d}".lower()
                    base_old = f"{safe_name}_{idx + 1}".lower()
                    tags = item.get("tags", "")
                    item_md5 = item.get("md5", "")

                    if item_md5 and item_md5 in local_md5_map:
                        actual_filename = local_md5_map[item_md5]
                        artist_meta[actual_filename] = tags
                        matched += 1

                        del local_md5_map[item_md5]
                        base_key = os.path.splitext(actual_filename)[0].lower()
                        if base_key in missing_bases:
                            del missing_bases[base_key]

                    elif base_new in missing_bases:
                        actual_filename = missing_bases[base_new]
                        artist_meta[actual_filename] = tags
                        matched += 1
                        del missing_bases[base_new]
                    elif base_old in missing_bases:
                        actual_filename = missing_bases[base_old]
                        artist_meta[actual_filename] = tags
                        matched += 1
                        del missing_bases[base_old]

                if matched > 0:
                    try:
                        save_artist_metadata(artist_dir, artist_meta)
                        self.app.log(f"✅ Успешно обновлено тегов для {artist}: {matched} файлов.")
                    except (OSError, ValueError, TypeError) as err:
                        self.app.log(f"❌ Ошибка записи .dat: {err}")
                else:
                    self.app.log(f"⚠️ Нет совпадений файлов для {artist}.")

                leftovers = list(missing_bases.values())
                if leftovers:
                    self.app.log(f"👻 Не найдено на сервере ({len(leftovers)} шт.):\n" + ", ".join(leftovers))
        finally:
            self.app.api.set_site(ui_site)

        self.app.log("✅ Процесс догрузки завершен.")
        self.app.after(0, getattr(self.app, "_check_unlock_ui"))

    def start_download_prep(self, artists, custom_name=""):
        for a in artists:
            self.app.search_history.add(a)

            # Добавляем в новую структуру дерева, если автора там еще нет
            is_found = False
            for group, items in self.app.grouped_history_data.items():
                if any(str(item.get("artist", "")) == a for item in items):
                    is_found = True
                    break

            if not is_found:
                group_name = f"⭐ {self.app.tr('tab_history')}"
                if group_name not in self.app.grouped_history_data:
                    self.app.grouped_history_data[group_name] = []
                self.app.grouped_history_data[group_name].append(
                    {"artist": a, "count": "?", "tags": [], "site": self.app.site_var.get()})

        if hasattr(self.app, "update_history_tree"):
            self.app.update_history_tree()

        self.app.save_settings()

        save_dir = filedialog.askdirectory(title=self.app.tr("dir_select"))
        if not save_dir: return
        limit_val = self.app.dl_limit_var.get()
        limit = int(limit_val) if limit_val.isdigit() else 0

        self.app.clear_log()
        self.app.log(self.app.tr("log_start_dl_prep"))
        threading.Thread(target=self.prepare_download_worker, args=(artists, limit, save_dir, custom_name),
                         daemon=True).start()

    def prepare_download_worker(self, artists, limit, base_dir, custom_name=""):
        try:
            self.app.after(0, lambda: getattr(self.app, "_set_ui_state")(is_working=True))
            self.app.after(0, lambda: self.app.notebook.select(self.app.tab_logs))
            temp_queue = []
            all_files = []

            dl_exclude_str = self.app.dl_exclude_var.get().strip().lower()
            raw_exclude_set = set(dl_exclude_str.split()) if dl_exclude_str else set()
            raw_exclude_set.update({t.lower() for t in self.app.excluded_tags})

            if self.app.exclude_q_var.get(): raw_exclude_set.add("rating:questionable")
            if self.app.exclude_ai_var.get(): raw_exclude_set.update(["ai_generated", "ai-generated"])

            local_exclude_set = set()
            for t in raw_exclude_set:
                t = t.lstrip('-')
                if t: local_exclude_set.add(t)

            # Каждого автора качаем с того сайта, на котором он был найден
            # (сохранено в истории), а не с того, что сейчас выбран в
            # интерфейсе - поэтому переключаем API-клиент прямо здесь, а не
            # через self.app.site_var/on_site_change (это дёрнуло бы UI).
            # В конце обязательно возвращаем клиент на сайт, видимый в
            # интерфейсе, чтобы не путать остальные части приложения.
            ui_site = self.app.site_var.get()
            try:
                for artist in artists:
                    if self.app.stop_event.is_set(): break
                    if self.app.skip_bad_marks_var.get() and self.app.artist_marks.get(artist) == "bad":
                        self.app.log(self.app.tr("log_skip_bad").format(artist))
                        continue

                    artist_site = self._resolve_artist_site(artist)
                    api_key, user_id = self._resolve_site_credentials(artist_site)
                    self.app.api.set_site(artist_site)

                    full_query = artist
                    data_list = self.app.api.get_image_data(full_query, api_key, user_id, limit,
                                                            exclude_tags=local_exclude_set)

                    if data_list:
                        # Передаем custom_name в очередь задач
                        temp_queue.append(
                            {"artist": artist, "dir": base_dir, "data_list": data_list, "custom_name": custom_name})
                        all_files.extend(data_list)
                        self.app.log(
                            self.app.tr("log_dl_progress").format(len(all_files), "?", f"Сбор данных ({artist})"),
                            is_progress=True)
            finally:
                self.app.api.set_site(ui_site)

            if self.app.stop_event.is_set() or not all_files:
                self.app.log(self.app.tr("log_not_found"))
                self.app.after(0, getattr(self.app, "_check_unlock_ui"))
                return

            known_bytes = self._check_unknown_sizes(all_files)

            if self.app.stop_event.is_set():
                self.app.after(0, getattr(self.app, "_check_unlock_ui"))
                return

            total_str = self.app.format_size(known_bytes)
            file_count = len(all_files)

            if self.app.is_downloading or getattr(self.app, "is_prompting_dl", False):
                self.app.download_queue.extend(temp_queue)
                self._persist_queue()
                self.app.log(self.app.tr("log_queue_added").format(file_count, total_str))
            else:
                self.app.is_prompting_dl = True
                self.app.after(0, self._ask_mass_download_confirmation, file_count, total_str, temp_queue)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as err:
            self.app.log(f"Ошибка подготовки: {err}")
            applog.exception("Ошибка подготовки скачивания")
            self.app.after(0, getattr(self.app, "_check_unlock_ui"))

    def _ask_mass_download_confirmation(self, file_count, total_str, temp_queue):
        msg = self.app.tr("msg_confirm_dl").format(file_count, total_str)
        ans = messagebox.askyesno(self.app.tr("msg_confirm_dl_title"), msg)
        self.app.is_prompting_dl = False

        if ans:
            self.app.download_queue.extend(temp_queue)
            self._persist_queue()
            self.app.log("✅ Подтверждено, начинаем скачивание...")
            threading.Thread(target=self.download_worker_loop, daemon=True).start()
        else:
            self.app.log("❌ Скачивание отменено пользователем.")
            getattr(self.app, "_check_unlock_ui")()

    def download_worker_loop(self):
        try:
            self.app.is_downloading = True
            while self.app.download_queue:
                if self.app.stop_event.is_set():
                    # Что делать с недоделанным - решается в finally: при
                    # закрытии приложения очередь сохраняется, при остановке
                    # пользователем выбрасывается.
                    break

                # Задача уходит из очереди в работу, но из сохранённого
                # состояния не пропадает - иначе закрытие приложения прямо
                # во время её скачивания потеряло бы её целиком.
                task = self.app.download_queue.pop(0)
                self.app.current_download_task = task
                self._persist_queue()

                artist = task["artist"]
                base_dir = task["dir"]
                data_list = task["data_list"]
                custom_name = task.get("custom_name", "")

                # --- ЛОГИКА КАСТОМНОГО ИМЕНИ ---
                if custom_name:
                    folder_name = re.sub(r'[\\/*?:"<>|]', "", custom_name).strip() or "Custom_DL"
                    file_prefix = folder_name
                else:
                    folder_name = re.sub(r'[\\/*?:"<>|]', "", artist).strip() or "unknown_artist"
                    file_prefix = folder_name
                # -------------------------------

                self.app.log(self.app.tr("log_dl_start").format(artist))
                artist_dir = os.path.join(base_dir, folder_name)
                os.makedirs(artist_dir, exist_ok=True)

                artist_meta = load_artist_metadata(artist_dir)

                downloaded = 0
                total_to_dl = len(data_list)
                self.app.after(0, lambda t=total_to_dl: getattr(self.app, "_progress_start", lambda *_a: None)(t))

                def _download_task(idx, item):
                    if self.app.stop_event.is_set(): return None
                    dl_url = item["url"]
                    tags = item.get("tags", "")
                    expected_md5 = str(item.get("md5", "")).lower()

                    if dl_url.startswith("//"): dl_url = "https:" + dl_url
                    # Расширение сохраняем только из белого списка известных
                    # типов изображений/видео - иначе сервер (или подменённая
                    # ссылка) мог бы навязать произвольное расширение файлу,
                    # который пользователь потом открывает через os.startfile().
                    ext = dl_url.split(".")[-1].split("?")[0].lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        ext = "jpg"

                    # Применяем кастомное имя файла
                    res_filename = f"{file_prefix}_{idx + 1:04d}.{ext}"
                    filepath = os.path.join(artist_dir, res_filename)

                    # Файл на месте - значит он уже был скачан (возможно, в
                    # прошлый запуск, до того как скачивание прервали).
                    # Недокачанные файлы под нормальным именем не лежат:
                    # download_file пишет в .part и переименовывает только
                    # после полной загрузки. Если сайт сообщил MD5 - лишний
                    # раз убеждаемся, что на диске именно то, что нужно.
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        if not expected_md5 or get_file_md5(filepath) == expected_md5:
                            artist_meta[res_filename] = tags
                            return res_filename

                    if self.app.api.download_file(dl_url, filepath):
                        if expected_md5:
                            actual_md5 = get_file_md5(filepath)
                            if actual_md5 and actual_md5 != expected_md5:
                                applog.warning(
                                    f"MD5 скачанного файла {res_filename} не совпадает с ожидаемым "
                                    f"(ожидали {expected_md5}, получили {actual_md5}) - файл может быть повреждён."
                                )
                        artist_meta[res_filename] = tags
                        return res_filename
                    return None

                with ThreadPoolExecutor(max_workers=self._get_worker_count("dl_workers_var", 8)) as dl_executor:
                    futures = [dl_executor.submit(_download_task, i, item) for i, item in enumerate(data_list)]
                    for future in as_completed(futures):
                        if self.app.stop_event.is_set(): break
                        res_filename = future.result()
                        if res_filename:
                            downloaded += 1
                            self.app.log(self.app.tr("log_dl_progress").format(downloaded, total_to_dl, res_filename),
                                         is_progress=True)
                            self.app.after(0, lambda d=downloaded: getattr(self.app, "_progress_update",
                                                                            lambda *_a: None)(d))

                try:
                    save_artist_metadata(artist_dir, artist_meta)
                except (OSError, ValueError, TypeError) as err:
                    self.app.log(f"Не удалось сохранить теги для {artist}: {err}")

                # Задача доведена до конца (или прервана - тогда ниже, в
                # finally, состояние всё равно пересохранится с учётом того,
                # что осталось).
                if not self.app.stop_event.is_set():
                    self.app.current_download_task = None
                    self._persist_queue()

                self.app.log(self.app.tr("log_dl_done").format(artist))
                if self.app.download_queue:
                    self.app.log(self.app.tr("log_dl_queue_left").format(len(self.app.download_queue)))
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as err:
            self.app.log(f"Ошибка скачивания: {err}")
            self.app.log(traceback.format_exc())
            applog.exception("Ошибка в download_worker_loop")
        finally:
            self.app.is_downloading = False

            if self.app.stop_event.is_set() and not getattr(self.app, "is_closing", False):
                # Пользователь сам нажал "Стоп" - продолжать нечего,
                # сохранённое состояние выбрасываем (как и раньше).
                self.app.download_queue.clear()
                self.app.current_download_task = None

            # Очередь опустела -> сохранённого состояния быть не должно.
            # Закрыли приложение на середине -> в файле остаётся недоделанное.
            self._persist_queue()
            self.app.after(0, getattr(self.app, "_progress_stop", lambda: None))
            self.app.after(0, getattr(self.app, "_check_unlock_ui"))
