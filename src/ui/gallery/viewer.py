"""Полноэкранный просмотрщик изображений/видео: зум колесом мыши от курсора,
панорамирование, копирование в буфер обмена. При закрытии (крестиком или
Escape) сетка переключается на страницу с текущей картинкой."""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from src.core import applog


def _get_window_monitor_rect(window):
    """Возвращает (x, y, width, height) монитора, на котором СЕЙЧАС стоит
    окно (только Windows, иначе None). На мультимониторных системах
    штатный wm_attributes('-fullscreen', 1) в Tk на Windows разворачивает
    окно по размеру ГЛАВНОГО монитора, а не того, где оно физически
    находится - см. toggle_fullscreen() в open_media_viewer, которая для
    Windows вместо этого сама убирает рамку окна и явно ставит геометрию
    нужного монитора, посчитанную здесь через Win32 API. На других ОС
    штатный fullscreen-атрибут Tk уже корректно учитывает текущий монитор."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        MONITOR_DEFAULTTONEAREST = 2

        user32 = ctypes.windll.user32

        monitor_from_window = user32.MonitorFromWindow
        monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
        monitor_from_window.restype = wintypes.HANDLE

        get_monitor_info = user32.GetMonitorInfoW
        get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        get_monitor_info.restype = wintypes.BOOL

        window.update_idletasks()
        hwnd = wintypes.HWND(window.winfo_id())
        monitor = monitor_from_window(hwnd, MONITOR_DEFAULTTONEAREST)

        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not get_monitor_info(monitor, ctypes.byref(info)):
            return None

        r = info.rcMonitor
        return r.left, r.top, r.right - r.left, r.bottom - r.top
    except (OSError, AttributeError, ValueError, TypeError):
        return None


class ViewerMixin:
    def open_media_viewer(self, start_idx):
        if getattr(self, "resize_timer", None):
            try:
                self.after_cancel(self.resize_timer)
            except (ValueError, TypeError):
                pass

        if self.viewer_window and self.viewer_window.winfo_exists():
            self.viewer_window.destroy()

        self.viewer_window = tk.Toplevel(self)
        self.viewer_window.geometry("900x800")
        self.viewer_window.configure(bg="#1e1e1e")
        self.viewer_idx = start_idx

        self.v_zoom = 1.0
        self.v_pan_x = 0
        self.v_pan_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        # Раскрытие просмотрщика на весь экран (F11) - запоминаем размер/позицию
        # окна до раскрытия, чтобы вернуть их при выходе из полноэкранного режима.
        self._viewer_fullscreen = False
        self._viewer_geom_before_fullscreen = None
        # Счётчик "поколений" ресайза: асинхронный (в фоновом потоке) качественный
        # ресайз применяется только если к моменту готовности он всё ещё актуален -
        # иначе более старый результат мог бы перезаписать более новый и вызвать "мигание".
        self._resize_generation = 0

        self.viewer_window.focus_force()

        self.viewer_canvas = tk.Canvas(self.viewer_window, bg="#1e1e1e", highlightthickness=0)
        self.viewer_canvas.pack(fill=tk.BOTH, expand=True)

        self.video_lbl = tk.Label(self.viewer_window, bg="#1e1e1e", fg="white", font=("Segoe UI", 14))
        self.btn_open_video = ttk.Button(self.viewer_window, text=self.app.tr("gal_btn_open_video"))

        self.current_viewer_img = None
        self.current_photo = None
        self.resize_timer = None
        self.viewer_img_id = None

        def show_toast(text: str):
            """Короткое сообщение поверх картинки. Раньше результат копирования
            показывался в заголовке окна, но в полноэкранном режиме заголовка
            не видно вообще - поэтому подтверждение рисуется на самом холсте."""
            if not self.viewer_canvas.winfo_exists(): return

            self.viewer_canvas.delete("toast")
            w = self.viewer_canvas.winfo_width()
            text_id = self.viewer_canvas.create_text(
                w // 2, 32, text=text, fill="white", justify=tk.CENTER,
                font=("Segoe UI", 12, "bold"), tags="toast"
            )

            bbox = self.viewer_canvas.bbox(text_id)
            if bbox:
                pad = 10
                bg_id = self.viewer_canvas.create_rectangle(
                    bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad,
                    fill="#1e1e1e", outline="#555555", tags="toast"
                )
                self.viewer_canvas.tag_lower(bg_id, text_id)

            self.viewer_canvas.after(
                2500,
                lambda: self.viewer_canvas.delete("toast") if self.viewer_canvas.winfo_exists() else None
            )

        def draw_image(fast: bool = False):
            if not getattr(self, "current_viewer_img", None): return
            if not self.viewer_canvas.winfo_exists(): return

            self.viewer_window.update_idletasks()
            w = self.viewer_canvas.winfo_width()
            h = self.viewer_canvas.winfo_height()

            if w < 10 or h < 10:
                if self.resize_timer:
                    self.viewer_window.after_cancel(self.resize_timer)
                self.resize_timer = self.viewer_window.after(50, draw_image)
                return

            try:
                img_w, img_h = self.current_viewer_img.size
                img_w_f, img_h_f = float(img_w), float(img_h)
                w_f, h_f = float(w), float(h)

                ratio_w = w_f / img_w_f
                ratio_h = h_f / img_h_f
                base_ratio = ratio_w if ratio_w < ratio_h else ratio_h
                final_ratio = base_ratio * float(self.v_zoom)

                new_w = int(img_w_f * final_ratio)
                new_h = int(img_h_f * final_ratio)

                if new_w < 1: new_w = 1
                if new_h < 1: new_h = 1

                if new_w > 8000 or new_h > 8000:
                    max_dim = float(new_w if new_w > new_h else new_h)
                    scale = 8000.0 / max_dim
                    new_w = int(new_w * scale)
                    new_h = int(new_h * scale)

                pan_x, pan_y = self.v_pan_x, self.v_pan_y
                self._resize_generation += 1
                my_generation = self._resize_generation

                def apply_photo(img_copy):
                    # Если пользователь успел покрутить колесо ещё раз, пока этот
                    # (более медленный, качественный) ресайз считался - результат
                    # уже устарел, и его нужно просто отбросить, а не показывать -
                    # иначе картинка на секунду "мигает" назад к старому масштабу.
                    if my_generation != self._resize_generation: return
                    if not self.viewer_canvas.winfo_exists(): return

                    self.current_photo = ImageTk.PhotoImage(img_copy, master=self.viewer_canvas)
                    if self.viewer_img_id is None:
                        self.viewer_canvas.delete("all")
                        self.viewer_img_id = self.viewer_canvas.create_image(
                            w // 2 + pan_x, h // 2 + pan_y,
                            anchor=tk.CENTER, image=self.current_photo
                        )
                    else:
                        self.viewer_canvas.coords(self.viewer_img_id, w // 2 + pan_x, h // 2 + pan_y)
                        self.viewer_canvas.itemconfig(self.viewer_img_id, image=self.current_photo)
                    self.viewer_canvas.image = self.current_photo

                if fast:
                    # Быстрый черновой ресайз (NEAREST) прямо в основном потоке -
                    # почти бесплатный по CPU, даёт мгновенный отклик на каждый
                    # щелчок колеса мыши, даже если итоговое изображение огромное.
                    quick = self.current_viewer_img.resize((new_w, new_h), Image.Resampling.NEAREST)
                    apply_photo(quick)
                else:
                    # Качественный ресайз (LANCZOS) считаем в фоновом потоке, чтобы
                    # не подвешивать интерфейс на крупных изображениях, и применяем
                    # результат через after(), только если он ещё актуален.
                    src_img = self.current_viewer_img

                    def worker():
                        try:
                            hq = src_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        except (OSError, ValueError, MemoryError) as werr:
                            applog.debug(f"Фоновый ресайз изображения не удался: {werr}")
                            return
                        # self.viewer_window обнуляется при закрытии просмотрщика
                        # (см. on_close ниже) - к моменту, когда этот фоновый
                        # ресайз досчитается, окно уже вполне может быть закрыто.
                        if self.viewer_window and self.viewer_window.winfo_exists():
                            self.viewer_window.after(0, apply_photo, hq)

                    threading.Thread(target=worker, daemon=True).start()

            except (OSError, ValueError, TypeError, MemoryError, RuntimeError) as err:
                self.viewer_canvas.delete("all")
                self.viewer_img_id = None
                self.viewer_canvas.create_text(
                    w // 2, h // 2,
                    text=self.app.tr("gal_err_render").format(err), fill="red", font=("Segoe UI", 12), justify=tk.CENTER
                )

        def on_mousewheel(event):
            if not getattr(self, "current_viewer_img", None): return
            old_zoom = self.v_zoom
            if event.num == 5 or event.delta < 0:
                self.v_zoom /= 1.1
            elif event.num == 4 or event.delta > 0:
                self.v_zoom *= 1.1

            if self.v_zoom < 0.1: self.v_zoom = 0.1
            if self.v_zoom > 8.0: self.v_zoom = 8.0

            ratio = self.v_zoom / old_zoom
            if ratio != 1.0:
                # Зумируем "от курсора": пересчитываем смещение картинки так,
                # чтобы точка изображения под мышью осталась на том же месте
                # экрана, а не "прыгала" к центру canvas при каждом шаге колеса.
                w = self.viewer_canvas.winfo_width()
                h = self.viewer_canvas.winfo_height()
                vx = event.x - (w // 2 + self.v_pan_x)
                vy = event.y - (h // 2 + self.v_pan_y)
                self.v_pan_x = (event.x - w // 2) - vx * ratio
                self.v_pan_y = (event.y - h // 2) - vy * ratio

            # Мгновенный черновой рендер на каждый тик колеса...
            draw_image(fast=True)

            # ...а через короткую паузу - один качественный ресайз в фоне.
            if self.resize_timer: self.viewer_window.after_cancel(self.resize_timer)
            self.resize_timer = self.viewer_window.after(120, draw_image)

        def on_pan_start(event):
            self.drag_start_x = event.x
            self.drag_start_y = event.y

        def on_pan_motion(event):
            if not getattr(self, "current_viewer_img", None) or not self.viewer_img_id: return
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            self.v_pan_x += dx
            self.v_pan_y += dy
            self.drag_start_x = event.x
            self.drag_start_y = event.y

            w = self.viewer_canvas.winfo_width()
            h = self.viewer_canvas.winfo_height()
            self.viewer_canvas.coords(self.viewer_img_id, w // 2 + self.v_pan_x, h // 2 + self.v_pan_y)

        def copy_image(_event=None):
            if not getattr(self, "current_viewer_img", None):
                # Видео или картинка, которая не открылась - копировать нечего.
                # Раньше здесь просто ничего не происходило, без объяснений.
                applog.debug("Копирование в буфер обмена: текущий файл не изображение, копировать нечего.")
                show_toast(self.app.tr("gal_toast_nothing"))
                return

            filepath = self.gal_filtered_files[self.viewer_idx]
            filepath_abs = os.path.abspath(filepath)

            success = False
            import sys
            import time
            import subprocess  # Вынесли импорт сюда, чтобы он был доступен во всех блоках

            if sys.platform == "win32":
                try:
                    import ctypes
                    from ctypes import wintypes
                    from io import BytesIO

                    kernel32 = ctypes.windll.kernel32
                    user32 = ctypes.windll.user32

                    global_alloc = getattr(kernel32, "GlobalAlloc")
                    global_lock = getattr(kernel32, "GlobalLock")
                    global_unlock = getattr(kernel32, "GlobalUnlock")
                    global_free = getattr(kernel32, "GlobalFree")
                    open_cb = getattr(user32, "OpenClipboard")
                    empty_cb = getattr(user32, "EmptyClipboard")
                    set_cb_data = getattr(user32, "SetClipboardData")
                    close_cb = getattr(user32, "CloseClipboard")

                    global_alloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
                    global_alloc.restype = wintypes.HGLOBAL
                    global_lock.argtypes = [wintypes.HGLOBAL]
                    global_lock.restype = wintypes.LPVOID
                    global_unlock.argtypes = [wintypes.HGLOBAL]
                    global_unlock.restype = wintypes.BOOL
                    global_free.argtypes = [wintypes.HGLOBAL]
                    global_free.restype = wintypes.HGLOBAL

                    open_cb.argtypes = [wintypes.HWND]
                    open_cb.restype = wintypes.BOOL
                    empty_cb.argtypes = []
                    empty_cb.restype = wintypes.BOOL
                    set_cb_data.argtypes = [wintypes.UINT, wintypes.HANDLE]
                    set_cb_data.restype = wintypes.HANDLE
                    close_cb.argtypes = []
                    close_cb.restype = wintypes.BOOL

                    output = BytesIO()
                    self.current_viewer_img.convert("RGB").save(output, "BMP")
                    data = output.getvalue()[14:]
                    output.close()

                    cf_dib = 8
                    gmem_moveable = 0x0002

                    h_global_mem = global_alloc(gmem_moveable, len(data))
                    if not h_global_mem:
                        applog.debug("Копирование в буфер обмена: GlobalAlloc не выделил память под картинку.")
                    else:
                        lp_global_mem = global_lock(h_global_mem)
                        if not lp_global_mem:
                            applog.debug("Копирование в буфер обмена: GlobalLock не отдал указатель на память.")
                            global_free(h_global_mem)
                        else:
                            ctypes.memmove(lp_global_mem, data, len(data))
                            global_unlock(h_global_mem)

                            # Буфер обмена - разделяемый ресурс на всю систему, и в
                            # момент запроса его вполне может держать открытым другое
                            # приложение (менеджеры буфера обмена, Punto Switcher,
                            # история буфера Windows). Тогда OpenClipboard просто
                            # возвращает 0 - раньше копирование в этом случае молча
                            # не срабатывало. Поэтому даём несколько коротких попыток.
                            opened = False
                            for _attempt in range(10):
                                if open_cb(0):
                                    opened = True
                                    break
                                time.sleep(0.05)

                            if not opened:
                                applog.debug("Копирование в буфер обмена: не удалось открыть буфер, "
                                             "его удерживает другое приложение.")
                                global_free(h_global_mem)
                            else:
                                empty_cb()
                                handle = set_cb_data(cf_dib, h_global_mem)
                                last_error = 0 if handle else ctypes.GetLastError()
                                close_cb()

                                if handle:
                                    # Память с картинкой теперь принадлежит системе -
                                    # освобождать её самим нельзя.
                                    success = True
                                else:
                                    applog.debug("Копирование в буфер обмена: SetClipboardData не принял "
                                                 f"данные (GetLastError={last_error}).")
                                    global_free(h_global_mem)
                except (OSError, AttributeError, TypeError, ValueError, ImportError) as e:
                    applog.debug(f"Не удалось скопировать изображение через Windows Clipboard API: {e}")

            elif sys.platform == "darwin":
                try:
                    # Экранируем путь перед вставкой в строку AppleScript: без этого
                    # имя файла/автора с обратным слэшем или двойной кавычкой могло бы
                    # исказить или "вырваться" за пределы строкового литерала AppleScript.
                    safe_path = filepath_abs.replace("\\", "\\\\").replace('"', '\\"')
                    apple_script = f'set the clipboard to (read (POSIX file "{safe_path}") as JPEG picture)'
                    subprocess.run(["osascript", "-e", apple_script], check=True)
                    success = True
                except (OSError, subprocess.SubprocessError) as e:
                    applog.debug(f"Не удалось скопировать изображение через AppleScript: {e}")

            else:
                try:
                    subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", filepath_abs],
                                   check=True)
                    success = True
                except (OSError, subprocess.SubprocessError) as e:
                    applog.debug(f"Не удалось скопировать изображение через xclip: {e}")

            if self.viewer_window and self.viewer_window.winfo_exists():
                if success:
                    applog.debug("Картинка скопирована в буфер обмена.")
                    show_toast(self.app.tr("gal_toast_copied"))
                else:
                    # Картинку скопировать не вышло - кладём хотя бы путь к файлу.
                    self.app.clipboard_clear()
                    self.app.clipboard_append(filepath)
                    show_toast(self.app.tr("gal_toast_copied_path"))

        def on_viewer_ctrl_key(event):
            key = event.keysym.lower() if event.keysym else ""
            if key in ('c', 'cyrillic_es') or event.keycode == 67:
                copy_image()
                return "break"
            return None

        self.viewer_canvas.bind("<MouseWheel>", on_mousewheel)
        self.viewer_canvas.bind("<Button-4>", on_mousewheel)
        self.viewer_canvas.bind("<Button-5>", on_mousewheel)

        self.viewer_canvas.bind("<ButtonPress-1>", on_pan_start)
        self.viewer_canvas.bind("<B1-Motion>", on_pan_motion)

        self.viewer_window.bind("<Control-KeyPress>", on_viewer_ctrl_key)

        def check_resize(e):
            if e.widget == self.viewer_canvas:
                if self.resize_timer:
                    self.viewer_window.after_cancel(self.resize_timer)
                self.resize_timer = self.viewer_window.after(100, draw_image)

        self.viewer_canvas.bind("<Configure>", check_resize)

        def update_view(_event=None):
            filepath = self.gal_filtered_files[self.viewer_idx]
            filename = os.path.basename(filepath)
            total = len(self.gal_filtered_files)

            try:
                self.viewer_window.title(f"[{self.viewer_idx + 1}/{total}] {filename}")
            except tk.TclError:
                return

            self.v_zoom = 1.0
            self.v_pan_x = 0
            self.v_pan_y = 0

            ext = filepath.split('.')[-1].lower()

            if ext in ['mp4', 'webm', 'avi', 'mkv']:
                self.current_viewer_img = None
                self.viewer_img_id = None
                self.viewer_canvas.delete("all")
                self.viewer_canvas.pack_forget()
                self.video_lbl.config(text=self.app.tr("gal_video_hint"))
                self.video_lbl.pack(expand=True)
                self.btn_open_video.pack(pady=10)
                self.btn_open_video.config(command=lambda: os.startfile(filepath))
            else:
                self.video_lbl.pack_forget()
                self.btn_open_video.pack_forget()
                self.viewer_canvas.pack(fill=tk.BOTH, expand=True)

                try:
                    with Image.open(filepath) as img:
                        if img.mode not in ("RGB", "RGBA"):
                            img = img.convert("RGBA")
                        self.current_viewer_img = img.copy()
                    draw_image()
                except (OSError, ValueError, MemoryError, TypeError) as err:
                    self.current_viewer_img = None
                    self.viewer_img_id = None
                    self.viewer_canvas.delete("all")
                    try:
                        self.viewer_canvas.create_text(
                            self.viewer_canvas.winfo_width() // 2,
                            self.viewer_canvas.winfo_height() // 2,
                            text=self.app.tr("gal_err_load_img").format(err), fill="red", font=("Segoe UI", 12),
                            justify=tk.CENTER
                        )
                    except tk.TclError:
                        pass

        def toggle_fullscreen(_event=None):
            self._viewer_fullscreen = not self._viewer_fullscreen
            if self._viewer_fullscreen:
                self._viewer_geom_before_fullscreen = self.viewer_window.geometry()
                monitor_rect = _get_window_monitor_rect(self.viewer_window)
                if monitor_rect:
                    # Windows: сами убираем рамку окна и растягиваем его по
                    # монитору, на котором оно сейчас стоит (см. причину в
                    # docstring _get_window_monitor_rect выше).
                    x, y, w, h = monitor_rect
                    self.viewer_window.overrideredirect(True)
                    self.viewer_window.geometry(f"{w}x{h}+{x}+{y}")
                else:
                    self.viewer_window.attributes("-fullscreen", True)
            else:
                if self.viewer_window.overrideredirect():
                    self.viewer_window.overrideredirect(False)
                else:
                    self.viewer_window.attributes("-fullscreen", False)
                if self._viewer_geom_before_fullscreen:
                    self.viewer_window.geometry(self._viewer_geom_before_fullscreen)

            # Окно без рамки (overrideredirect) не управляется оконным менеджером и
            # легко теряет фокус клавиатуры - без этого после F11 переставали
            # работать стрелки, Escape и Ctrl+C (копирование картинки).
            self.viewer_window.lift()
            self.viewer_window.focus_force()

        def on_key(event):
            if event.keysym == 'Right':
                if self.viewer_idx < len(self.gal_filtered_files) - 1:
                    self.viewer_idx += 1
                    update_view()
            elif event.keysym == 'Left':
                if self.viewer_idx > 0:
                    self.viewer_idx -= 1
                    update_view()
            elif event.keysym == 'Return':
                filepath = self.gal_filtered_files[self.viewer_idx]
                ext = filepath.split('.')[-1].lower()
                if ext in ['mp4', 'webm', 'avi', 'mkv']:
                    os.startfile(filepath)
            elif event.keysym == 'F11':
                toggle_fullscreen()

        self.viewer_window.bind("<Key>", on_key)

        def on_close():
            # Запоминаем, на какой картинке остановились (пользователь мог
            # пролистать её стрелками, отличается от той, с которой открыли
            # просмотрщик) - используется, чтобы вернуться в сетку туда же.
            last_idx = self.viewer_idx

            if getattr(self, "resize_timer", None):
                try:
                    self.viewer_window.after_cancel(self.resize_timer)
                except (ValueError, tk.TclError):
                    pass
                self.resize_timer = None

            self.viewer_window.destroy()
            self.viewer_window = None
            self.viewer_img_id = None

            self.jump_to_gallery_index(last_idx)

        def on_escape(_e=None):
            # Если просмотрщик сейчас на весь экран - Escape сначала просто
            # сворачивает его обратно в обычное окно, а не закрывает.
            if self._viewer_fullscreen:
                toggle_fullscreen()
            else:
                on_close()

        self.viewer_window.protocol("WM_DELETE_WINDOW", on_close)
        self.viewer_window.bind("<Escape>", on_escape)

        update_view()

