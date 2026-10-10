import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from src.core.ai import LOCAL_AI_PROVIDER, run_ai_analysis_request


class AiMixin:
    """Вкладка "AI Аналитика": выбор провайдера, запуск анализа в фоне."""

    _AI_DEFAULT_MODELS = {
        "Ollama (Локально)": "llama3",
        "LM Studio (Локально)": "local-model",
        "Gemini API": "gemini-1.5-flash",
        "OpenAI API": "gpt-3.5-turbo",
        "Qwen API": "qwen-plus",
        LOCAL_AI_PROVIDER: LOCAL_AI_PROVIDER,
    }

    def _sync_ai_widget_states(self, prov):
        """Включает/выключает поля "модель" и "API-ключ" под конкретного
        провайдера, не трогая при этом сохранённое значение модели. Нужен
        отдельно от on_ai_provider_change() для вызова при старте программы:
        там provider/model только что подхватились из настроек (см.
        src/core/storage/config.py), и on_ai_provider_change() затёр бы
        загруженную модель дефолтной для этого провайдера."""
        # Поле модели редактируемо только там, где выбор модели вообще имеет
        # смысл (Ollama/LM Studio - у пользователя может быть своя). У
        # встроенной модели файл всего один, менять там нечего.
        if hasattr(self, "ai_model_entry") and self.ai_model_entry is not None:
            self.ai_model_entry.config(state=tk.DISABLED if prov == LOCAL_AI_PROVIDER else tk.NORMAL)

        needs_api_key = prov in ("Gemini API", "OpenAI API", "Qwen API")
        self.ai_api_key_entry.config(state=tk.NORMAL if needs_api_key else tk.DISABLED)

    def on_ai_provider_change(self, _event=None):
        """Обработчик реального переключения провайдера пользователем
        (событие комбобокса) - в отличие от _sync_ai_widget_states(),
        которую вызывают и при старте программы, здесь модель осознанно
        сбрасывается на разумный дефолт для новой выбранной вкладки."""
        prov = self.ai_provider_var.get()
        self._sync_ai_widget_states(prov)
        self.ai_model_var.set(self._AI_DEFAULT_MODELS.get(prov, self.ai_model_var.get()))

    def show_ai_help(self):
        prov = self.ai_provider_var.get()
        if prov == "Gemini API":
            webbrowser.open("https://aistudio.google.com/app/apikey")
        elif prov == "OpenAI API":
            webbrowser.open("https://platform.openai.com/api-keys")
        elif prov == "Qwen API":
            webbrowser.open("https://bailian.console.alibabacloud.com/")
        elif prov == "Ollama (Локально)":
            messagebox.showinfo(self.tr("ollama_title"), self.tr("ollama_msg"))
        elif prov == LOCAL_AI_PROVIDER:
            messagebox.showinfo(self.tr("local_ai_title"), self.tr("local_ai_msg"))

    def _get_rated_good_artist_records(self):
        """Записи (имя + РЕАЛЬНЫЕ теги содержимого, объединённые по всем
        группам истории, где встречается автор) авторов с оценкой "хорошо" -
        именно про них говорит подсказка под этой вкладкой ("ставь им
        хорошие оценки, а затем жми старт"). Логика отбора повторяет
        update_history_tree() (src/app/history.py). Источник данных для
        SearchEngine.build_taste_profile - записи без тегов (например, автор
        попал в историю не через поиск, а другим путём) просто дадут пустой
        список тегов, build_taste_profile их пропустит.

        Раньше здесь ошибочно использовался self.search_history - другой,
        временный набор, который пополняется только во время реальной
        закачки в ТЕКУЩЕМ сеансе (см. start_download_prep в
        src/core/download/manager.py) и никогда не сохраняется на диск. Из-за
        этого ИИ-анализ считал историю пустой даже у пользователей с
        десятками оценённых авторов, накопленными за много сеансов, если они
        просто не успели ничего скачать в этом конкретном запуске."""
        records = {}
        for artists in self.grouped_history_data.values():
            for a in artists:
                name = str(a.get("artist", ""))
                if self.artist_marks.get(name) != "good":
                    continue
                rec = records.setdefault(name, {"artist": name, "tags": set()})
                rec["tags"].update(a.get("tags", []) or [])
        return [{"artist": r["artist"], "tags": sorted(r["tags"])} for r in records.values()]

    def _get_all_known_artist_names(self):
        """Все имена авторов, когда-либо встречавшиеся в истории - независимо
        от оценки ("хорошо"/"нейтрально"/"плохо"). Похожих авторов ищем
        исключая этот набор целиком, чтобы не предлагать того, кто уже есть
        в списке хоть в каком-то качестве."""
        names = set()
        for artists in self.grouped_history_data.values():
            for a in artists:
                names.add(str(a.get("artist", "")))
        return names

    def run_ai_analysis(self):
        # Пока идёт поиск/скачивание - молча ничего не делаем, это состояние
        # и так видно по остальному интерфейсу (поля заблокированы). А вот
        # пустую историю и отсутствующий API-ключ ниже нужно показать явно -
        # иначе нажатие "Запустить" выглядит так, будто кнопка не работает.
        if self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl", False): return
        provider = self.ai_provider_var.get()
        ai_api_key = self.ai_api_key_var.get().strip()
        # Значения Tk-переменных читаем здесь, в основном потоке - Tkinter не
        # потокобезопасен, а обращение к нему из фонового потока (как раньше
        # делал _ai_worker с ai_model_var) может упасть с "main thread is not
        # in main loop". В .exe-сборке без консоли (--windowed) это исключение
        # никто не увидит - снаружи это выглядит так, будто кнопка "Запустить"
        # вообще ничего не делает. Тот же приём уже используется для поиска и
        # автодополнения (см. src/app/search.py).
        model = self.ai_model_var.get().strip()
        # Учётные данные буру-сайта (НЕ путать с ai_api_key выше - это ключ
        # AI-провайдера) - нужны, чтобы искать похожих авторов через тот же
        # API, что и обычный поиск (см. SearchEngine.find_similar_artists).
        site_api_key = self.api_key_var.get().strip()
        site_user_id = self.user_id_var.get().strip()

        good_records = self._get_rated_good_artist_records()
        known_names = self._get_all_known_artist_names()

        if not good_records:
            self._show_ai_text(self.tr("ai_empty_history"))
            return
        if provider in ("Gemini API", "OpenAI API", "Qwen API") and not ai_api_key:
            self._show_ai_text(self.tr("ai_err_no_api_key"))
            return

        self.btn_ai.config(state=tk.DISABLED)
        self._show_ai_text(self.tr("ai_req_sending").format(provider))
        self.update_idletasks()
        threading.Thread(
            target=self._ai_worker,
            args=(provider, ai_api_key, model, good_records, known_names, site_api_key, site_user_id),
            daemon=True,
        ).start()

    def _ai_worker(self, provider, api_key, model, good_records, known_names, site_api_key, site_user_id):
        # Встроенная модель может минуту-другую качаться при первом
        # использовании - показываем прогресс вместо "зависшего" окна.
        def progress_cb(text):
            self.after(0, self._update_ai_progress, text)

        profile_tags = self.search_engine.build_taste_profile(good_records, known_names)

        similar = []
        if profile_tags:
            progress_cb(self.tr("ai_finding_similar"))
            try:
                similar = self.search_engine.find_similar_artists(
                    profile_tags, site_api_key, site_user_id, known_names,
                    log_callback=lambda q: progress_cb(f"{self.tr('ai_finding_similar')} ({q})"),
                )
            except Exception:
                similar = []

        progress_cb(self.tr("ai_req_sending").format(provider))
        style_text = run_ai_analysis_request(provider, api_key, model, profile_tags, self.current_lang, self.tr,
                                             progress_callback=progress_cb)

        result = self._format_ai_result(style_text, similar)
        self.after(0, self._update_ai_ui, result)

    def _format_ai_result(self, style_text, similar):
        """Собирает финальный текст результата из двух независимых частей:
        текстового описания стиля от LLM (style_text) и детерминированного,
        найденного прямо на сайте списка похожих авторов (similar, список
        пар (имя, число_постов) - см. SearchEngine.find_similar_artists).
        Форматирование одинаковое для всех провайдеров, включая встроенную
        модель - раньше только она сама оборачивала свой ответ в заголовки."""
        lines = [f"{i}. {name} ({count})" for i, (name, count) in enumerate(similar, start=1)]
        similar_block = "\n".join(lines) if lines else self.tr("ai_no_similar_found")
        return f"{self.tr('ai_header_style')}\n{style_text}\n\n{self.tr('ai_header_similar')}\n{similar_block}"

    def _show_ai_text(self, text):
        self.ai_text_area.config(state=tk.NORMAL)
        self.ai_text_area.delete(1.0, tk.END)
        self.ai_text_area.insert(tk.END, text)
        self.ai_text_area.config(state=tk.DISABLED)

    def _update_ai_progress(self, text):
        self._show_ai_text(text)

    def _update_ai_ui(self, text):
        self._show_ai_text(text)
        if not self.is_searching and not self.is_downloading and not getattr(self, "is_prompting_dl", False):
            self.btn_ai.config(state=tk.NORMAL)

