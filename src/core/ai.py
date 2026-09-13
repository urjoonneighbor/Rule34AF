import requests


def run_ai_analysis_request(provider, api_key, model, search_history, lang="ru", tr_func=None):
    if not search_history:
        return tr_func("ai_empty_history") if tr_func else "Artists history is empty."

    tags_str = ", ".join(search_history)

    if lang == "en":
        prompt = (
            f"You are an expert in digital art and Rule34. "
            f"User likes these artists: {tags_str}. "
            f"1) Briefly describe the art style or genre that unites them. "
            f"2) Suggest 5-7 similar high-quality artists. "
            f"Answer in English, use bullet points."
        )
    else:
        prompt = (
            f"Ты эксперт по цифровому искусству и платформе Rule34. "
            f"Пользователю нравятся следующие авторы (художники): {tags_str}. "
            f"1) Коротко опиши, какой стиль или жанр объединяет этих авторов. "
            f"2) Предложи 5-7 похожих качественных авторов. "
            f"Отвечай на русском языке, структурировано."
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
