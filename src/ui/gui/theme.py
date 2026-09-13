from tkinter import ttk


class ThemeMixin:
    """Оформление интерфейса: тёмная и светлая тема."""

    def set_theme(self, theme: str):
        self.current_theme = theme
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names(): style.theme_use("clam")

        if self.current_theme == "dark":
            bg_main, fg_main, input_bg, select_bg, log_fg = "#202124", "#e8eaed", "#28292c", "#8ab4f8", "#81c995"
            border_col, caret_col = "#3c4043", "#ffffff"
            c_good, c_bad, c_neutral = "#81c995", "#f28b82", "#fdd663"
            dis_bg, dis_fg = "#2d2f31", "#7f8c8d"
        else:
            bg_main, fg_main, input_bg, select_bg, log_fg = "#f8f9fa", "#202124", "#ffffff", "#1a73e8", "#1e8e3e"
            border_col, caret_col = "#dadce0", "#000000"
            c_good, c_bad, c_neutral = "#137333", "#c5221f", "#ea8600"
            dis_bg, dis_fg = "#e0e0e0", "#7f8c8d"

        self.configure(bg=bg_main)
        self.canvas.configure(bg=bg_main)

        if hasattr(self, "tab_gallery") and self.tab_gallery:
            self.tab_gallery.apply_theme(bg_main, input_bg, fg_main, select_bg, border_col)

        style.configure(".", background=bg_main, foreground=fg_main, font=self.font_main)
        style.configure("TLabel", background=bg_main, foreground=fg_main)

        style.configure("TCheckbutton", background=bg_main, foreground=fg_main, focuscolor=bg_main)
        style.map("TCheckbutton", background=[("active", bg_main), ("pressed", bg_main)],
                  foreground=[("active", fg_main), ("pressed", fg_main)])

        style.configure("TLabelframe", background=bg_main, borderwidth=1, bordercolor=border_col)
        style.configure("TLabelframe.Label", background=bg_main, foreground=fg_main, font=self.font_bold)

        style.configure("TNotebook", background=bg_main, borderwidth=0)
        style.configure("TNotebook.Tab", background=input_bg, foreground=fg_main, padding=[15, 5], font=self.font_bold)
        style.map("TNotebook.Tab", background=[("selected", select_bg)], foreground=[("selected", "#ffffff")])

        style.configure("TButton", background=input_bg, foreground=fg_main, borderwidth=1, bordercolor=border_col,
                        padding=5)
        style.map("TButton", background=[("active", select_bg)], foreground=[("active", "#ffffff")])

        style.configure("TEntry", fieldbackground=input_bg, foreground=fg_main, borderwidth=1, bordercolor=border_col,
                        padding=5, insertcolor=caret_col)
        style.map("TEntry", fieldbackground=[("disabled", dis_bg)], foreground=[("disabled", dis_fg)])

        style.configure("TCombobox", fieldbackground=input_bg, foreground=fg_main, borderwidth=1,
                        bordercolor=border_col, padding=5, insertcolor=caret_col)
        style.map("TCombobox", fieldbackground=[("readonly", input_bg), ("disabled", dis_bg)],
                  foreground=[("readonly", fg_main), ("disabled", dis_fg)])

        style.configure("TSpinbox", fieldbackground=input_bg, foreground=fg_main, borderwidth=1, bordercolor=border_col,
                        padding=5, insertcolor=caret_col)
        style.map("TSpinbox", fieldbackground=[("disabled", dis_bg)], foreground=[("disabled", dis_fg)])

        style.configure("Treeview", background=input_bg, foreground=fg_main, fieldbackground=input_bg, borderwidth=0,
                        font=self.font_main, rowheight=25)
        style.map("Treeview", background=[("selected", select_bg)], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=bg_main, foreground=fg_main, font=self.font_bold, borderwidth=1)

        self.history_tree.tag_configure("mark_good", foreground=c_good)
        self.history_tree.tag_configure("mark_bad", foreground=c_bad)
        self.history_tree.tag_configure("mark_neutral", foreground=c_neutral)

        for widget in [self.listbox_include, self.listbox_exclude]:
            widget.configure(bg=input_bg, fg=fg_main, selectbackground=select_bg, selectforeground="#ffffff",
                             highlightcolor=select_bg, highlightbackground=border_col)

        self.log_area.configure(bg=input_bg, fg=log_fg, insertbackground=caret_col, highlightbackground=border_col)
        self.ai_text_area.configure(bg=input_bg, fg=fg_main, insertbackground=caret_col, highlightbackground=border_col)
        self.query_preview_text.configure(bg=input_bg, fg="#3498db", highlightbackground=border_col, borderwidth=1)

