import tkinter as tk
from tkinter import scrolledtext, ttk


class UtilsMixin:
    """Мелкие утилиты интерфейса: горячие клавиши, контекстное меню
    "Копировать", форматирование размера файла."""

    def fix_hotkeys(self):
        def _on_ctrl_key(event):
            key = event.keysym.lower() if event.keysym else ""
            if key in ('v', 'cyrillic_em') or event.keycode == 86:
                event.widget.event_generate("<<Paste>>")
                return "break"
            elif key in ('c', 'cyrillic_es') or event.keycode == 67:
                event.widget.event_generate("<<Copy>>")
                return "break"
            elif key in ('x', 'cyrillic_che') or event.keycode == 88:
                event.widget.event_generate("<<Cut>>")
                return "break"
            elif key in ('a', 'cyrillic_ef') or event.keycode == 65:
                event.widget.select_range(0, tk.END)
                event.widget.icursor(tk.END)
                return "break"
            return None

        self.bind_class("TEntry", "<Control-KeyPress>", _on_ctrl_key, add="+")
        self.bind_class("Entry", "<Control-KeyPress>", _on_ctrl_key, add="+")

    def global_context_menu(self, event):
        widget = event.widget
        if isinstance(widget, ttk.Treeview): return

        text_to_copy = ""
        try:
            if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
                if widget.select_present():
                    text_to_copy = widget.selection_get()
                else:
                    text_to_copy = widget.get()
            elif isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                try:
                    text_to_copy = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError:
                    if widget in (self.query_preview_text, self.ai_text_area): text_to_copy = widget.get(1.0, tk.END)
            elif isinstance(widget, tk.Listbox):
                sel = widget.curselection()
                if sel: text_to_copy = widget.get(sel[0])
            else:
                try:
                    t_var = widget.cget("textvariable")
                    if t_var:
                        text_to_copy = widget.getvar(t_var)
                    else:
                        text_to_copy = widget.cget("text")
                except tk.TclError:
                    pass
        except (tk.TclError, AttributeError):
            pass

        text_to_copy = str(text_to_copy).strip()
        if text_to_copy:
            menu = tk.Menu(self, tearoff=0, font=self.font_main)
            label_text = "📋 Скопировать текст" if self.current_lang == "ru" else "📋 Copy text"
            menu.add_command(label=label_text, command=lambda t=text_to_copy: self._perform_copy(t))
            menu.post(event.x_root, event.y_root)

    def _perform_copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    @staticmethod
    def format_size(size_bytes: float | int) -> str:
        size_f = float(size_bytes)
        if size_f == 0.0: return "0 B"
        names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_f >= 1024.0 and i < len(names) - 1:
            size_f /= 1024.0
            i += 1
        return f"{size_f:.2f} {names[i]}"

