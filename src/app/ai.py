import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from src.core.ai import run_ai_analysis_request


class AiMixin:
    """Вкладка "AI Аналитика": выбор провайдера, запуск анализа в фоне."""

    def on_ai_provider_change(self, _event=None):
        prov = self.ai_provider_var.get()
        if prov == "Ollama (Локально)":
            self.ai_api_key_entry.config(state=tk.DISABLED)
            self.ai_model_var.set("llama3")
        elif prov == "LM Studio (Локально)":
            self.ai_api_key_entry.config(state=tk.DISABLED)
            self.ai_model_var.set("local-model")
        elif prov == "Gemini API":
            self.ai_api_key_entry.config(state=tk.NORMAL)
            self.ai_model_var.set("gemini-1.5-flash")
        elif prov == "OpenAI API":
            self.ai_api_key_entry.config(state=tk.NORMAL)
            self.ai_model_var.set("gpt-3.5-turbo")
        elif prov == "Qwen API":
            self.ai_api_key_entry.config(state=tk.NORMAL)
            self.ai_model_var.set("qwen-plus")

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

    def run_ai_analysis(self):
        if not self.search_history or self.is_searching or self.is_downloading or getattr(self, "is_prompting_dl",
                                                                                          False): return
        provider = self.ai_provider_var.get()
        api_key = self.ai_api_key_var.get().strip()
        if provider in ("Gemini API", "OpenAI API", "Qwen API") and not api_key: return
        self.btn_ai.config(state=tk.DISABLED)
        self.ai_text_area.config(state=tk.NORMAL)
        self.ai_text_area.delete(1.0, tk.END)
        self.ai_text_area.insert(tk.END, self.tr("ai_req_sending").format(provider))
        self.ai_text_area.config(state=tk.DISABLED)
        self.update_idletasks()
        threading.Thread(target=self._ai_worker, args=(provider, api_key), daemon=True).start()

    def _ai_worker(self, provider, api_key):
        model = self.ai_model_var.get().strip()
        result = run_ai_analysis_request(provider, api_key, model, self.search_history, self.current_lang, self.tr)
        self.after(0, self._update_ai_ui, result)

    def _update_ai_ui(self, text):
        self.ai_text_area.config(state=tk.NORMAL)
        self.ai_text_area.delete(1.0, tk.END)
        self.ai_text_area.insert(tk.END, text)
        self.ai_text_area.config(state=tk.DISABLED)
        if not self.is_searching and not self.is_downloading and not getattr(self, "is_prompting_dl", False):
            self.btn_ai.config(state=tk.NORMAL)

