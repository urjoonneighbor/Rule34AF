import tkinter as tk
from tkinter import messagebox


class MenuMixin:
    """Меню приложения и связанные с ним переключатели."""

    def build_menu(self):
        self.menubar = tk.Menu(self, font=self.font_main)
        self.config(menu=self.menubar)

        self.settings_menu = tk.Menu(self.menubar, tearoff=0, font=self.font_main)
        self.lang_menu = tk.Menu(self.settings_menu, tearoff=0, font=self.font_main)
        self.lang_menu.add_command(label="Русский", command=lambda: self.set_lang("ru"))
        self.lang_menu.add_command(label="English", command=lambda: self.set_lang("en"))
        self.settings_menu.add_cascade(label="Language", menu=self.lang_menu)

        self.theme_menu = tk.Menu(self.settings_menu, tearoff=0, font=self.font_main)
        self.theme_menu.add_command(label="Dark", command=lambda: self.set_theme("dark"))
        self.theme_menu.add_command(label="Light", command=lambda: self.set_theme("light"))
        self.settings_menu.add_cascade(label="Theme", menu=self.theme_menu)

        self.settings_menu.add_separator()
        self.settings_menu.add_checkbutton(label="🤖 ИИ-Аналитика", variable=self.show_ai_tab_var,
                                           command=self.toggle_ai_tab)
        self.settings_menu.add_checkbutton(label=self.tr("menu_check_updates"), variable=self.check_updates_var,
                                           command=self.save_settings)
        self.settings_menu.add_checkbutton(label=self.tr("net_toggle"), variable=self.net_toggle_var,
                                           command=self.toggle_net_frame)

        self.menubar.add_cascade(label="Настройки", menu=self.settings_menu)
        self.help_menu = tk.Menu(self.menubar, tearoff=0, font=self.font_main)
        self.help_menu.add_command(label=self.tr("menu_help_app"), command=self.show_help)
        self.help_menu.add_command(label=self.tr("menu_about"), command=self.show_about)
        self.menubar.add_cascade(label="Справка", menu=self.help_menu)

    def toggle_net_frame(self):
        self._apply_net_frame_visibility()
        self.save_settings()

    def _apply_net_frame_visibility(self):
        """Показывает/прячет блок "Сеть и производительность" без записи настроек -
        используется как при клике на переключатель (см. toggle_net_frame), так
        и один раз при старте, чтобы применить значение, загруженное из настроек."""
        if self.net_toggle_var.get():
            # before=self.lbl_add_tag держит блок на исходном месте в раскладке,
            # даже если pack() вызывается позже, чем виджеты под ним.
            self.net_frame.pack(fill=tk.X, pady=(0, 15), before=self.lbl_add_tag)
        else:
            self.net_frame.pack_forget()

    def toggle_ai_tab(self):
        if self.show_ai_tab_var.get():
            self.notebook.add(self.tab_ai, text=self.tr("tab_ai"))
        else:
            self.notebook.forget(self.tab_ai)
        self.save_settings()

    def show_help(self):
        messagebox.showinfo(self.tr("help_title"), self.tr("help_text"))

    def show_about(self):
        from src.core.version import __version__
        messagebox.showinfo(self.tr("about_title"), self.tr("about_text").format(__version__))

