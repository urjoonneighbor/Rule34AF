import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.core import applog
from src.core.storage import blob_codec
from src.core.storage.paths import DEBUG_LOG_FILENAME, FOUND_ARTISTS_FILENAME, resolve_data_file


class SearchEngine:
    def __init__(self, app):
        self.app = app

    def search_worker(self, query_string, min_posts, any_amount, auto_save, debug_mode):
        app = self.app
        try:
            # Запоминаем сайт на момент запуска поиска (а не читаем его повторно
            # ниже) - чтобы в истории у найденных авторов сохранился именно тот
            # сайт, на котором их реально нашли, даже если пользователь успеет
            # переключить сайт в интерфейсе, пока поиск ещё идёт в фоне.
            site_used = app.site_var.get()
            if site_used == "rule34.paheal.net":
                app.log(app.tr("paheal_warning"))

            api_key = app.api_key_var.get().strip()
            user_id = app.user_id_var.get().strip()
            posts = app.api.get_all_posts(query_string, api_key, user_id, app.stop_event,
                                          log_callback=lambda msg: app.log(msg, is_progress=True))

            if app.stop_event.is_set(): return
            if not posts:
                app.log(app.tr("log_not_found"))
                return

            bad_post_tags = set()
            if app.exclude_q_var.get() and "rating:questionable" not in app.included_tags: bad_post_tags.add(
                "rating:questionable")
            if app.exclude_ai_var.get(): bad_post_tags.update(["ai_generated", "ai-generated"])

            for ex_tag in app.excluded_tags:
                bad_post_tags.add(ex_tag.lower())

            raw_unique_tags = set()
            banned_posts_indices = set()

            for i, post in enumerate(posts):
                post_tags = set(post.get("tags", "").lower().split())
                raw_unique_tags.update(post_tags)
                if bad_post_tags & post_tags:
                    banned_posts_indices.add(i)

            tags_to_exclude = app.excluded_tags.copy()
            if app.auto_exclude_copied_var.get():
                for artist in app.copied_artists:
                    name = artist.get("name") if isinstance(artist, dict) else str(artist)
                    tags_to_exclude.add(name)

            for t in tags_to_exclude:
                if t in raw_unique_tags: raw_unique_tags.remove(t)
                if t.startswith("-") and t[1:] in raw_unique_tags: raw_unique_tags.remove(t[1:])

            pre_tags_list = []
            for t in raw_unique_tags:
                if app.exclude_ai_var.get() and any(x in t.lower() for x in
                                                    ["ai_generator", "ai-generator", "ai_artist", "ai-artist",
                                                     "ai_generated", "ai-generated"]): continue
                pre_tags_list.append(t)

            tags_list = pre_tags_list

            total_tags = len(tags_list)
            app.log(app.tr("log_found_tags").format(total_tags))

            valid_artists = []
            checked = 0

            debug_log_lines = []
            if debug_mode:
                debug_log_lines.append(f"=== ОТЧЕТ ПО ИСКЛЮЧЕНИЮ ТЕГОВ (ЗАПРОС: {query_string}) ===\n")
                debug_log_lines.append(f"{'НАЗВАНИЕ ТЕГА':<40} | {'ХУДОЖНИК?':<12} | {'КОЛ-ВО ПОСТОВ'}")
                debug_log_lines.append("-" * 75)

            tag_workers = app.MAX_WORKERS
            try:
                if hasattr(app, "tag_workers_var"):
                    tag_workers = int(str(app.tag_workers_var.get()).strip())
            except (ValueError, TypeError, AttributeError):
                tag_workers = app.MAX_WORKERS
            if tag_workers <= 0:
                tag_workers = app.MAX_WORKERS

            with ThreadPoolExecutor(max_workers=tag_workers) as executor:
                future_to_tag = {
                    executor.submit(app.api.check_tag_global_stats, tag, api_key, user_id, app.stop_event): tag for tag
                    in tags_list}
                for future in as_completed(future_to_tag):
                    if app.stop_event.is_set(): break
                    tag_name, is_artist, global_count = future.result()
                    checked += 1

                    if debug_mode:
                        status = "ДА" if is_artist else "НЕТ"
                        debug_log_lines.append(f"{tag_name:<40} | {status:<12} | {global_count}")

                    if is_artist and (any_amount or global_count >= min_posts):
                        valid_artists.append((tag_name, global_count))

                    if checked % 50 == 0 or checked == total_tags:
                        app.log(app.tr("log_progress").format(checked, total_tags, len(valid_artists)),
                                is_progress=True)

            if debug_mode:
                debug_path = resolve_data_file(DEBUG_LOG_FILENAME)
                try:
                    with open(debug_path, "w", encoding="utf-8") as df:
                        df.write("\n".join(debug_log_lines))
                    app.log(app.tr("log_debug_saved").format(debug_path))
                except OSError as e:
                    app.log(app.tr("err_debug_save").format(e))
                    applog.warning(f"Не удалось сохранить дебаг-лог в {debug_path}: {e}")

            if app.stop_event.is_set(): return
            if valid_artists:
                banned_artists = set()
                artist_names = {a[0] for a in valid_artists}

                for i, post in enumerate(posts):
                    if i in banned_posts_indices:
                        p_tags = set(post.get("tags", "").lower().split())
                        banned_artists.update(artist_names.intersection(p_tags))

                valid_artists = [a for a in valid_artists if a[0] not in banned_artists]
                valid_artists.sort(key=lambda x: x[1], reverse=True)

                if not valid_artists:
                    app.log("⚠️ Все найденные авторы были исключены фильтром.")
                    app.after(0, app._check_unlock_ui)
                    return

                final_artist_names = {a[0] for a in valid_artists}
                artist_tags_map = {a: set() for a in final_artist_names}
                for i, post in enumerate(posts):
                    if i not in banned_posts_indices:
                        p_tags = set(post.get("tags", "").lower().split())
                        for a in final_artist_names.intersection(p_tags):
                            artist_tags_map[a].update(p_tags)

                new_data = []
                for artist, count in valid_artists:
                    new_data.append({
                        "artist": artist,
                        "count": count,
                        # sorted(...): grouped_history_data сохраняется целиком
                        # через json.dumps (см. ConfigManager.save_settings),
                        # а set в него класть нельзя - это не JSON-тип.
                        "tags": sorted(artist_tags_map[artist]),
                        "site": site_used,
                    })

                if auto_save:
                    self._save_to_found_artists_dat(query_string, valid_artists)

                # --- ФИЛЬТРАЦИЯ УЖЕ ИЗВЕСТНЫХ АВТОРОВ ---
                # Один и тот же тег на разных сайтах - это разные авторы
                # (namespace тегов у каждого сайта свой), поэтому сравниваем
                # пару (имя, сайт), а не только имя. Для старых записей без
                # поля site (сохранены до его появления - сайт неизвестен)
                # сайт не проверяем и блокируем повтор на любом сайте, как
                # раньше, пока пользователь не проставит сайт вручную
                # (см. HistoryMixin.set_history_artists_site).
                known_artists_by_site = set()
                known_artists_any_site = set()
                for group_items in app.grouped_history_data.values():
                    for item in group_items:
                        name_lower = str(item.get("artist", "")).lower()
                        item_site = item.get("site", "")
                        if item_site:
                            known_artists_by_site.add((name_lower, item_site))
                        else:
                            known_artists_any_site.add(name_lower)

                def _already_known(item):
                    name_lower = str(item.get("artist", "")).lower()
                    return name_lower in known_artists_any_site or (name_lower, site_used) in known_artists_by_site

                filtered_data = [item for item in new_data if not _already_known(item)]
                # --------------------------------------------------------

                def _finalize(data=filtered_data):
                    app.found_artists_data = data
                    
                    if data:
                        # Если нашли кого-то нового, создаем папку
                        group_name = f"🔍 Поиск: {query_string}"
                        app.grouped_history_data[group_name] = data
                    else:
                        # Используем ключ локализации, который мы уже добавили в locales.py
                        app.log(app.tr("log_all_excluded")) 
                    
                    if hasattr(app, "update_history_tree"):
                        app.update_history_tree()
                        
                    app.notebook.select(app.tab_history)
                    app.save_settings()

                app.after(0, _finalize)
                
                # Пишем в лог количество именно НОВЫХ авторов
                app.log(app.tr("log_success").format(len(filtered_data)))
                
        except Exception as e:
            app.log(app.tr("err_critical").format(e))
            app.log(traceback.format_exc())
            applog.exception("Критическая ошибка в search_worker")
        finally:
            app.is_searching = False
            app.after(0, getattr(app, "_check_unlock_ui"))

    def _save_to_found_artists_dat(self, query_string, valid_artists):
        txt_file = "found_artists.txt"  # старый (ещё более старый) legacy-формат, только для однократной миграции
        dat_file = resolve_data_file(FOUND_ARTISTS_FILENAME)
        content = ""

        if os.path.exists(txt_file):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    content += f.read()
                os.remove(txt_file)
            except OSError as e:
                applog.debug(f"Не удалось перенести старый found_artists.txt: {e}")

        if os.path.exists(dat_file):
            try:
                with open(dat_file, "rb") as f:
                    decoded = blob_codec.decode_text(f.read())
                if decoded is not None:
                    content += decoded
            except OSError as e:
                applog.warning(f"Не удалось прочитать {dat_file}: {e}")

        content += f"\n--- Поиск: {query_string} ---\n"
        for artist, count in valid_artists:
            m_type = self.app.artist_marks.get(artist, "")
            m_txt = f" [{self.app.tr('mark_' + m_type)}]" if m_type else ""
            content += f"Автор: {artist} | Постов: {count}{m_txt}\n"

        try:
            with open(dat_file, "wb") as f:
                f.write(blob_codec.encode_text(content))
        except OSError as e:
            self.app.log(self.app.tr("err_autosave").format(e))
            applog.error(f"Не удалось сохранить {dat_file}: {e}")
