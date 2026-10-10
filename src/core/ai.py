import requests

from src.core.local_ai import run_local_analysis

LOCAL_AI_PROVIDER = "Qwen2.5 0.5B (Встроенная)"


def run_ai_analysis_request(provider, api_key, model, profile_tags, lang="ru", tr_func=None, progress_callback=None):
    """profile_tags: агрегированные РЕАЛЬНЫЕ теги содержимого (не имена
    авторов!) у оценённых "хорошо" авторов - см.
    SearchEngine.build_taste_profile в src/core/search/engine.py. Модель
    отвечает только за текстовое описание стиля по этим тегам - список
    похожих авторов теперь ищется детерминированно прямо на сайте
    (SearchEngine.find_similar_artists) и добавляется к этому тексту уже в
    src/app/ai.py, а не спрашивается у LLM: ни одна модель (в т.ч. крупная
    облачная) не имеет живого доступа в интернет, чтобы реально знать стиль
    конкретных, часто уникальных 18+ псевдонимов буру-сайтов - она либо
    выдумывала факты, либо просто повторяла те же имена, что были на входе."""
    if not profile_tags:
        return tr_func("ai_no_profile_tags") if tr_func else "Not enough tag data to describe a style."

    tags_str = ", ".join(profile_tags)

    if provider == LOCAL_AI_PROVIDER:
        # Отдельная ветка, а не try-блок ниже: своя логика ошибок (скачивание
        # модели / отсутствие llama-cpp-python в сборке) - не сетевая ошибка
        # к внешнему провайдеру, поэтому не должна попадать в общий
        # "Ошибка сети" catch-all.
        return run_local_analysis(tags_str, lang, tr_func=tr_func, progress_callback=progress_callback)

    if lang == "en":
        prompt = (
            f"You are an expert in digital art and Rule34. "
            f"These are the most common content tags across a collection of favorite artwork: {tags_str}. "
            f"In a few sentences, describe the shared art style, genre or theme these tags suggest. "
            f"Do not invent or mention any specific artist names - you only know the tags, not who drew what. "
            f"Answer in English."
        )
    else:
        prompt = (
            f"Ты эксперт по цифровому искусству и платформе Rule34. "
            f"Вот самые частые теги содержимого в подборке любимых работ: {tags_str}. "
            f"В нескольких предложениях опиши, какой стиль, жанр или тематику объединяют эти теги. "
            f"Не придумывай и не называй конкретных имён авторов - тебе известны только теги, а не то, кто "
            f"именно это рисовал. "
            f"Отвечай на русском языке."
        )

    try:
        if provider == "Ollama (Локально)":
            url = "http://localhost:11434/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            resp = requests.post(url, json=payload, timeout=120)
            if resp.status_code == 200: return resp.json().get("response", "Empty")
            return tr_func("ai_err_api").format("Ollama",
                                                resp.status_code) if tr_func else f"Ollama Error: {resp.status_code}"

        elif provider == "LM Studio (Локально)":
            url = "http://localhost:1234/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
            return tr_func("ai_err_api").format("LM Studio",
                                                f"{resp.status_code}\n{resp.text}") if tr_func else f"LM Studio Error: {resp.status_code}"

        elif provider == "Gemini API":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200: return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return tr_func("ai_err_api").format("Gemini",
                                                f"{resp.status_code}\n{resp.text}") if tr_func else f"Gemini Error: {resp.status_code}"

        elif provider == "OpenAI API":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
            return tr_func("ai_err_api").format("OpenAI",
                                                f"{resp.status_code}\n{resp.text}") if tr_func else f"OpenAI Error: {resp.status_code}"

        elif provider == "Qwen API":
            url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"]
            return tr_func("ai_err_api").format("Qwen",
                                                f"{resp.status_code}\n{resp.text}") if tr_func else f"Qwen Error: {resp.status_code}"

    except Exception as e:
        return tr_func("ai_err_network").format(str(e)) if tr_func else f"Network Error: {str(e)}"
