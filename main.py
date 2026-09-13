import sys
import traceback


def _crash_log_path() -> str:
    """Каталог данных приложения, а не CWD - иначе при установке в
    Program Files/на многопользовательской машине запись может не удаться,
    и лог об ошибке импорта потеряется вместе с самой ошибкой."""
    try:
        from src.core.storage.paths import CRASH_LOG_FILENAME, resolve_data_file
        return resolve_data_file(CRASH_LOG_FILENAME)
    except Exception:
        return "crash_log.txt"


def _show_crash_dialog(title: str, message: str) -> None:
    """Показывает сообщение об ошибке всеми доступными способами. В
    консольном режиме используются print/input, но в --windowed сборке
    (PyInstaller) sys.stdout/stdin/stderr равны None, и обращение к ним
    само по себе кидает исключение - поэтому основной канал здесь
    диалоговое окно tkinter, а консоль используется только если она
    реально есть."""
    if sys.stdout is not None:
        try:
            print(f"{title}\n\n{message}")
        except Exception:
            pass

    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass

    if sys.stdin is not None and sys.stdout is not None:
        try:
            input("\nНажмите Enter, чтобы закрыть окно...")
        except Exception:
            pass


# Ловим ошибки на этапе чтения файлов и папок
try:
    from src.app import Rule34ArtistFinderApp
except Exception:
    error_msg = traceback.format_exc()
    crash_path = _crash_log_path()
    try:
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write("ОШИБКА ИМПОРТА (Проверь файлы в папке src):\n\n" + error_msg)
    except OSError:
        pass
    _show_crash_dialog(
        "Ошибка при запуске",
        f"Не удалось запустить приложение.\nЛог сохранён: {crash_path}\n\n{error_msg}",
    )
    exit()

# Ловим ошибки во время работы самой программы
if __name__ == "__main__":
    try:
        app = Rule34ArtistFinderApp()
        app.mainloop()
    except Exception:
        error_msg = traceback.format_exc()
        crash_path = _crash_log_path()
        try:
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write("ПРИЛОЖЕНИЕ УПАЛО С ОШИБКОЙ:\n\n" + error_msg)
        except OSError:
            pass
        _show_crash_dialog(
            "Приложение упало с ошибкой",
            f"Лог сохранён: {crash_path}\n\n{error_msg}",
        )
