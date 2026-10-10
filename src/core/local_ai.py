"""Встроенная локальная AI-модель (Qwen2.5 0.5B Instruct, GGUF).

Работает полностью офлайн прямо в процессе приложения - в отличие от
провайдеров "Ollama"/"LM Studio", не требует отдельно установленной и
запущенной программы, а в отличие от облачных API - не требует ключа.
Единственная "настройка" - один раз скачать файл модели (~490 МБ), это
происходит автоматически при первом использовании этого провайдера.

Инференс идёт через llama-cpp-python - опциональную зависимость (extra
"local-ai" в pyproject.toml), т.к. PyPI не публикует под неё готовые
wheel'ы и обычная установка компилирует пакет из исходников. В сборках,
которые публикуются на GitHub Releases, она ставится через готовый
CPU-wheel (см. .github/workflows/release.yml) и доступна "из коробки". Если
её всё же нет (например, при запуске из исходников без этого extra) -
run_local_analysis возвращает понятное сообщение об ошибке вместо падения
всего приложения; сам факт отсутствия пакета не мешает работе остальных
AI-провайдеров и приложения в целом (импорт llama_cpp - только внутри
функций, не на уровне модуля)."""
from __future__ import annotations

import os
import threading

import requests

from src.core import applog
from src.core.storage.paths import get_app_data_dir

MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
MODEL_URL = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILENAME}"
# Реальный размер файла на HuggingFace - ориентир для прогресс-бара на
# случай, если сервер не пришлёт Content-Length.
MODEL_SIZE_BYTES = 491_000_000

_llm_lock = threading.Lock()
_llm_instance = None


def model_path() -> str:
    models_dir = os.path.join(get_app_data_dir(), "models")
    os.makedirs(models_dir, exist_ok=True)
    return os.path.join(models_dir, MODEL_FILENAME)


def is_model_downloaded() -> bool:
    path = model_path()
    return os.path.exists(path) and os.path.getsize(path) > 0


def is_available() -> bool:
    """Установлен ли в этой сборке llama-cpp-python (опциональная
    зависимость - см. docstring модуля)."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


def download_model(progress_callback=None) -> bool:
    """Скачивает файл модели во временный .part и переименовывает только
    после полной загрузки - как основные скачивания артов (см.
    src.core.network.client.Rule34API.download_file), чтобы обрыв связи
    посреди скачивания не оставил битый файл под нормальным именем (иначе
    is_model_downloaded() навсегда считала бы его готовым)."""
    path = model_path()
    temp_path = path + ".part"

    try:
        resp = requests.get(MODEL_URL, stream=True, timeout=30)
        if resp.status_code != 200:
            applog.warning(f"Не удалось скачать встроенную AI-модель: HTTP {resp.status_code}")
            return False

        total = int(resp.headers.get("Content-Length", 0)) or MODEL_SIZE_BYTES
        downloaded = 0

        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)

        os.replace(temp_path, path)
        return True
    except (OSError, requests.RequestException) as e:
        applog.warning(f"Не удалось скачать встроенную AI-модель: {e}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False


def _get_llm():
    """Модель грузится в память один раз за сессию приложения и переиспользуется -
    инициализация занимает заметное время, а повторный AI-анализ должен
    отвечать быстро."""
    global _llm_instance
    with _llm_lock:
        if _llm_instance is None:
            from llama_cpp import Llama
            _llm_instance = Llama(
                model_path=model_path(),
                n_ctx=2048,
                n_threads=max(1, (os.cpu_count() or 4) - 1),
                chat_format="chatml",
                verbose=False,
            )
        return _llm_instance


def _chat(llm, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    result = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        # У маленькой модели заметно выше риск зациклиться на повторах одной
        # и той же формулировки - штраф за повтор снижает это (0.5B без него
        # временами повторял один и тот же оборот раз за разом до конца лимита
        # токенов).
        repeat_penalty=1.15,
    )
    return result["choices"][0]["message"]["content"].strip()


def run_local_analysis(tags_str: str, lang: str = "ru", tr_func=None, progress_callback=None) -> str:
    """progress_callback(text) вызывается синхронно во время скачивания
    модели (может занять минуты), перед загрузкой её в память и во время
    самого запроса - вызывающий код сам решает, как показать это
    пользователю (см. src/app/ai.py).

    Модель отвечает ТОЛЬКО за описание стиля - и делает это по агрегированным
    реальным тегам контента (переданным в tags_str), а не по именам авторов.
    Раньше здесь также был второй запрос "предложи похожих авторов", но он
    оказался в принципе нерабочей задачей для любой модели, даже крупной: ни
    у одной LLM нет доступа к живому интернету, чтобы реально знать, как
    рисуют конкретные (часто уникальные и 18+) псевдонимы буру-сайтов -
    на практике модель либо выдумывала факты про них, либо просто повторяла
    те же имена, что были на входе. Список похожих авторов теперь строится
    детерминированно, поиском по самому сайту (см.
    src/core/search/engine.py: build_taste_profile/find_similar_artists) и
    комбинируется с этим текстом уже в src/app/ai.py."""
    if not is_available():
        return (tr_func("ai_err_local_unavailable") if tr_func
                else "The built-in local model isn't available in this build (llama-cpp-python is not installed).")

    if not is_model_downloaded():
        def _report(done: int, total: int):
            if not progress_callback:
                return
            done_mb, total_mb = done // (1024 * 1024), total // (1024 * 1024)
            pct = int(done * 100 / total) if total else 0
            progress_callback(
                tr_func("ai_local_downloading").format(done_mb, total_mb, pct) if tr_func
                else f"Downloading built-in model: {done_mb} / {total_mb} MB ({pct}%)..."
            )

        if not download_model(_report):
            return (tr_func("ai_err_local_download") if tr_func
                    else "Failed to download the built-in model. Check your internet connection and try again.")

    if progress_callback:
        progress_callback(tr_func("ai_local_loading") if tr_func else "Loading the model into memory...")

    if lang == "en":
        system_style = ("You are a concise art critic. Reply only in English, in 2-4 short sentences, with no "
                         "preamble, no headers and no repetition.")
        user_style = (f"These are the most common content tags across a collection of favorite artwork: "
                      f"{tags_str}. In 2-4 sentences, describe the shared art style, genre or theme these tags "
                      f"suggest. Do not invent or mention any specific artist names - you only know the tags, "
                      f"not who drew what.")
    else:
        system_style = ("Ты лаконичный арт-критик. Отвечай только на русском языке, 2-4 короткими предложениями, "
                        "без вступлений, заголовков и повторов.")
        user_style = (f"Вот самые частые теги содержимого в подборке любимых работ: {tags_str}. Опиши в "
                      f"2-4 предложениях, какой стиль, жанр или тематику объединяют эти теги. Не придумывай и "
                      f"не называй конкретных имён авторов - тебе известны только теги, а не то, кто именно это "
                      f"рисовал.")

    try:
        llm = _get_llm()
        return _chat(llm, system_style, user_style, max_tokens=220, temperature=0.5)
    except Exception as e:
        applog.exception("Ошибка локального AI-анализа")
        return (tr_func("ai_err_api").format("Local model", str(e)) if tr_func
                else f"Local model error: {e}")
