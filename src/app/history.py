import threading
import tkinter as tk
from tkinter import filedialog, messagebox


class HistoryMixin:
    """Дерево истории найденных авторов: фильтр, папки, оценки, экспорт,
    повторное скачивание и подгрузка тегов."""

    def update_history_tree(self, filter_text=""):
        if not hasattr(self, "history_tree") or not self.history_tree: return
        self.history_tree.delete(*self.history_tree.get_children())
        filter_text = filter_text.lower().strip()

        unique_artists = {}
        for artists in self.grouped_history_data.values():
            for a in artists:
                unique_artists[str(a.get("artist", ""))] = a

        rated_groups = {
            self.tr("group_good"): [],
            self.tr("group_neutral"): [],
            self.tr("group_bad"): [],
            self.tr("group_unrated"): []
        }

        for name, a in unique_artists.items():
            mark = self.artist_marks.get(name, "")
            if mark == "good":
                rated_groups[self.tr("group_good")].append(a)
            elif mark == "neutral":
                rated_groups[self.tr("group_neutral")].append(a)
            elif mark == "bad":
                rated_groups[self.tr("group_bad")].append(a)
            else:
                rated_groups[self.tr("group_unrated")].append(a)

        render_data = {}
        for g_name, g_artists in rated_groups.items():
            if g_artists:
                render_data[f"__default__{g_name}"] = sorted(g_artists, key=lambda x: str(x.get("artist", "")).lower())

        for g_name, g_artists in self.grouped_history_data.items():
            render_data[f"__history__{g_name}"] = g_artists

        for full_group_name, artists in render_data.items():
            filtered_artists = []
            for a in artists:
                artist_name = str(a.get("artist", "")).lower()
                tags_str = " ".join(a.get("tags", [])).lower()
                if filter_text in artist_name or filter_text in tags_str:
                    filtered_artists.append(a)

            is_default = full_group_name.startswith("__default__")
            display_group_name = full_group_name.split("__", 2)[-1]

            if filtered_artists or (filter_text in display_group_name.lower()):
                folder_icon = "⭐" if is_default else "📁"
                parent_id = self.history_tree.insert("", tk.END, text=f"{folder_icon} {display_group_name}",
                                                     values=(f"[{len(artists)} шт.]", "", "", ""), open=is_default)

                artists_to_show = filtered_artists if filtered_artists else artists
                for a in artists_to_show:
                    artist_name = str(a.get("artist", ""))
                    count = str(a.get("count", "?"))
                    mark = self.artist_marks.get(artist_name, "")

                    tag_name = ""
                    if mark == "good":
                        tag_name = "mark_good"
                    elif mark == "bad":
                        tag_name = "mark_bad"
                    elif mark == "neutral":
                        tag_name = "mark_neutral"

                    mark_text = "💚" if mark == "good" else "🔴" if mark == "bad" else "🟡" if mark == "neutral" else ""
                    site_text = str(a.get("site", ""))
                    # artist_name - 4-е (скрытое, не входит в displaycolumns)
                    # значение: настоящее имя автора без иконок/декораций для
                    # _get_selected_history_artists и т.п. Колонка site видна
                    # или скрыта через displaycolumns (см. toggle_hist_site_column) -
                    # само значение хранится всегда, независимо от переключателя.
                    self.history_tree.insert(parent_id, tk.END, text=f"  👤 {artist_name}",
                                             values=(count, mark_text, site_text, artist_name), tags=(tag_name,))

        self.notebook.tab(self.tab_history, text=f"{self.tr('tab_history')} ({len(unique_artists)})")

    def apply_history_filter(self):
        self.update_history_tree(self.hist_search_var.get())

    def toggle_hist_site_column(self):
        """Переключатель на тулбаре истории: показать/скрыть колонку с сайтом.
        Значения сайта в дереве хранятся всегда - меняется только видимость
        колонки (displaycolumns), перестраивать дерево не нужно."""
        cols = ("count", "mark", "site") if self.show_hist_site_var.get() else ("count", "mark")
        self.history_tree["displaycolumns"] = cols
        self.save_settings()

    def _get_selected_history_artists(self):
        sel = self.history_tree.selection()
        if not sel: return []
        artists = []
        for item_id in sel:
            vals = self.history_tree.item(item_id, "values")
            if len(vals) >= 4 and vals[3]:
                artists.append(vals[3])
            else:
                for child_id in self.history_tree.get_children(item_id):
                    c_vals = self.history_tree.item(child_id, "values")
                    if len(c_vals) >= 4 and c_vals[3]:
                        artists.append(c_vals[3])
        return list(dict.fromkeys(artists))

    def on_history_double_click(self, event=None):
        artists = self._get_selected_history_artists()
        if artists:
            self.query_preview_text.config(state=tk.NORMAL)
            self.query_preview_text.delete(1.0, tk.END)
            self.query_preview_text.insert(tk.END, artists[0])
            self.query_preview_text.config(state=tk.DISABLED)

            self.included_tags.clear()
            self.included_tags.add(artists[0])
            self.listbox_include.delete(0, tk.END)
            self.listbox_include.insert(tk.END, artists[0])
            self.update_preview()

    def show_history_context_menu(self, event):
        item_id = self.history_tree.identify_row(event.y)
        menu = tk.Menu(self, tearoff=0, font=self.font_main)

        # Если кликнули по элементу (автор или папка)
        if item_id:
            if item_id not in self.history_tree.selection():
                self.history_tree.selection_set(item_id)

            vals = self.history_tree.item(item_id, "values")
            if len(vals) >= 4 and vals[3]:
                artist = vals[3]
                menu.add_command(label=self.tr("btn_hist_run"), command=self.run_history_item)
                menu.add_command(label=self.tr("btn_hist_copy"), command=self.copy_history_item)
                menu.add_command(label=self.tr("menu_exclude_selected"), command=self.exclude_history_item)
                
                # --- Подменю для перемещения в папки ---
                if self.grouped_history_data:
                    move_menu = tk.Menu(menu, tearoff=0, font=self.font_main)
                    for folder_name in self.grouped_history_data.keys():
                        move_menu.add_command(label=folder_name, command=lambda f=folder_name: self.move_history_item(f))
                    menu.add_cascade(label=self.tr("menu_move_to"), menu=move_menu)
                # ---------------------------------------
                
                menu.add_separator()
                menu.add_command(label=self.tr("btn_hist_download"), command=self.download_from_history)
                menu.add_command(label=self.tr("menu_recover_meta"), command=self.recover_history_meta)

                # --- Подменю для ручной простановки сайта (в т.ч. для записей,
                # сохранённых до появления поля site) ---
                from src.core.network.client import SITE_ENGINES
                site_menu = tk.Menu(menu, tearoff=0, font=self.font_main)
                for site_name in SITE_ENGINES.keys():
                    site_menu.add_command(label=site_name, command=lambda s=site_name: self.set_history_artists_site(s))
                menu.add_cascade(label=self.tr("menu_set_site"), menu=site_menu)
                # ------------------------------------------------------------

                menu.add_separator()
                menu.add_command(label=self.tr("mark_good"), command=lambda a=artist: self._mark_artist(a, "good"))
                menu.add_command(label=self.tr("mark_neutral"), command=lambda a=artist: self._mark_artist(a, "neutral"))
                menu.add_command(label=self.tr("mark_bad"), command=lambda a=artist: self._mark_artist(a, "bad"))
                menu.add_command(label=self.tr("mark_clear"), command=lambda a=artist: self._mark_artist(a, "clear"))
                menu.add_separator()
                menu.add_command(label=self.tr("btn_hist_delete"), command=self.delete_history_item)
            else:
                menu.add_command(label=self.tr("menu_download_selected"), command=self.download_from_history)
                menu.add_command(label=self.tr("btn_hist_delete"), command=self.delete_history_item)
                
            menu.add_separator()

        # Пункт "Создать папку" доступен всегда (даже если кликнули по пустому месту)
        menu.add_command(label=self.tr("menu_create_folder"), command=self.create_history_folder)
        menu.post(event.x_root, event.y_root)

    def create_history_folder(self):
        from tkinter import simpledialog
        folder_name = simpledialog.askstring(
            self.tr("msg_new_folder_title"),
            self.tr("msg_new_folder_prompt"),
            parent=self
        )
        if not folder_name: return
        folder_name = folder_name.strip()
        if not folder_name: return
        
        if folder_name not in self.grouped_history_data:
            self.grouped_history_data[folder_name] = []
            self.update_history_tree(self.hist_search_var.get())
            self.save_settings()

    def move_history_item(self, target_folder):
        artists = self._get_selected_history_artists()
        if not artists: return
        
        extracted_artists_data = {}
        # Удаляем авторов из всех старых папок и сохраняем их данные (теги, посты)
        for group, items in self.grouped_history_data.items():
            new_items = []
            for item in items:
                a_name = str(item.get("artist", ""))
                if a_name in artists:
                    extracted_artists_data[a_name] = item 
                else:
                    new_items.append(item)
            self.grouped_history_data[group] = new_items
            
        # Помещаем в новую папку
        if target_folder in self.grouped_history_data:
            for a_name in artists:
                item_data = extracted_artists_data.get(
                    a_name, {"artist": a_name, "count": "?", "tags": [], "site": self.site_var.get()})
                self.grouped_history_data[target_folder].append(item_data)
                
        self.update_history_tree(self.hist_search_var.get())
        self.save_settings()

    def delete_history_item(self):
        sel = self.history_tree.selection()
        if not sel: return

        for item_id in sel:
            vals = self.history_tree.item(item_id, "values")
            if len(vals) >= 4 and vals[3]:
                artist_name = vals[3]
                for group, artists in self.grouped_history_data.items():
                    self.grouped_history_data[group] = [a for a in artists if str(a.get("artist", "")) != artist_name]
            else:
                text = self.history_tree.item(item_id, "text")
                if text.startswith("📁 ") or text.startswith("⭐ "):
                    # Отрезаем иконку папки и пробел, чтобы получить чистое имя
                    group_name = text.split(" ", 1)[-1]
                    if group_name in self.grouped_history_data:
                        del self.grouped_history_data[group_name]

        # Автоматически удаляем ТОЛЬКО пустые папки из поиска. 
        # Пустые пользовательские папки теперь остаются нетронутыми.
        empty_groups = [g for g, a in self.grouped_history_data.items() if not a and g.startswith("🔍 Поиск:")]
        for g in empty_groups:
            del self.grouped_history_data[g]

        self.update_history_tree(self.hist_search_var.get())
        self.save_settings()

    def export_history(self):
        items = self.history_tree.get_children()
        if not items:
            messagebox.showinfo(self.tr("error"), self.tr("msg_export_empty"))
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                                                title=self.tr("btn_hist_export"))
        if not filepath: return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"--- {self.tr('tab_history')} ---\n\n")
                
                unique_artists = {}
                for artists in self.grouped_history_data.values():
                    for a in artists:
                        unique_artists[str(a.get("artist", ""))] = a.get("count", "?")

                for artist, count in sorted(unique_artists.items()):
                    mark_type = self.artist_marks.get(artist, "")
                    mark_str = f" [{self.tr('mark_' + mark_type)}]" if mark_type else ""
                    f.write(f"Автор: {artist} | Постов: {count}{mark_str}\n")

            messagebox.showinfo(self.tr("msg_success"), self.tr("msg_exported").format(filepath))
        except Exception as e:
            messagebox.showerror(self.tr("error"), str(e))

    def recover_history_meta(self):
        artists = self._get_selected_history_artists()
        if not artists: return
        
        save_dir = getattr(self.tab_gallery, "gal_base_dir", "") if hasattr(self, "tab_gallery") else ""
        import os
        if not save_dir or not os.path.exists(save_dir):
            save_dir = filedialog.askdirectory(title=self.tr("dir_select"))
        if not save_dir: return
        
        self.clear_log()
        self.log(self.tr("log_start_recover"))
        self.stop_event.clear()
        import threading
        threading.Thread(target=self.downloader.recover_metadata_worker, args=(artists, save_dir), daemon=True).start()

    def exclude_history_item(self):
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return
        artists = self._get_selected_history_artists()
        if not artists: return
        added = 0
        for artist in artists:
            if artist not in self.excluded_tags:
                self.excluded_tags.add(artist)
                added += 1

        if added > 0:
            self.update_preview()
            self.log(self.tr("log_excluded_added").format(added))
        self.save_settings()

    def _mark_artist(self, artist: str, mark: str):
        if mark == "clear":
            self.artist_marks.pop(artist, None)
        else:
            self.artist_marks[artist] = mark

        self.update_history_tree(self.hist_search_var.get())
        self.save_settings()

    def set_history_artists_site(self, site: str):
        """Проставляет сайт вручную для выбранных авторов - нужно для записей,
        сохранённых до появления автоматического сохранения сайта, а также
        на случай, если сайт определился неверно."""
        artists = self._get_selected_history_artists()
        if not artists: return

        updated = 0
        for items in self.grouped_history_data.values():
            for item in items:
                if str(item.get("artist", "")) in artists:
                    item["site"] = site
                    updated += 1

        if updated:
            self.update_history_tree(self.hist_search_var.get())
            self.save_settings()
            self.log(self.tr("log_site_set").format(site, updated))

    def download_from_history(self):
        from tkinter import simpledialog
        artists = self._get_selected_history_artists()
        if not artists: return

        custom_name = simpledialog.askstring(
            self.tr("msg_custom_name_title"),
            self.tr("msg_custom_name_prompt"),
            parent=self
        )

        if custom_name is None: return
        custom_name = custom_name.strip()

        if hasattr(self.downloader, 'start_download_prep'):
            self.downloader.start_download_prep(artists, custom_name=custom_name)

    def run_history_item(self):
        self.on_history_double_click()
        self.start_search()

    def copy_history_item(self):
        artists = self._get_selected_history_artists()
        if artists: self._perform_copy(", ".join(artists))

    def clear_history_list(self):
        if messagebox.askyesno(self.tr("msg_clear_history_title"), self.tr("msg_clear_history_prompt")):
            self.grouped_history_data.clear()
            self.update_history_tree()
            self.save_settings()

