import tkinter as tk


class LogMixin:
    """Отрисовка итогового запроса и лога процесса в текстовых полях."""

    def update_preview(self) -> str:
        try:
            query_parts = list(self.included_tags)
            clean_excludes = [t.lstrip('-') for t in self.excluded_tags if isinstance(t, str)]

            for t in clean_excludes: query_parts.append(f"-{t}")

            if self.exclude_q_var.get() and "rating:questionable" not in self.included_tags and "rating:questionable" not in clean_excludes:
                query_parts.append("-rating:questionable")

            if self.exclude_ai_var.get():
                ai_tags = {"ai_generated", "ai-generated"}
                if not (ai_tags & self.included_tags) and not (ai_tags & set(clean_excludes)):
                    if self.site_var.get() == "allthefallen.moe":
                        query_parts.append("-ai-generated")
                    else:
                        query_parts.append("-ai_generated")

            final_query = " ".join(query_parts)
            self.query_preview_text.config(state=tk.NORMAL)
            self.query_preview_text.delete(1.0, tk.END)
            self.query_preview_text.insert(tk.END, final_query if final_query else "[Пусто]")
            self.query_preview_text.config(state=tk.DISABLED)
            return final_query
        except (tk.TclError, AttributeError) as e:
            self.log(f"Ошибка в update_preview: {e}")
            return ""

    def clear_log(self):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.last_log_was_progress = False
        self.update_idletasks()

    def log(self, message: str, is_progress: bool = False):
        self.log_area.config(state=tk.NORMAL)
        if is_progress and getattr(self, "last_log_was_progress", False):
            self.log_area.delete("end-2l", "end-1c")
            self.log_area.insert("end-1c", message)
        else:
            self.log_area.insert(tk.END, message + "\n")
        self.last_log_was_progress = is_progress
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.update_idletasks()

