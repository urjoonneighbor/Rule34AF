"""Тесты для src.core.local_ai - встроенной локальной AI-модели.

llama-cpp-python - опциональная зависимость (extra "local-ai"), которой
нет в быстром окружении tests.yml, поэтому все тесты работают через
моки sys.modules["llama_cpp"] и requests.get, не требуя реального пакета
и не скачивая настоящий файл модели."""
import os
import sys

import pytest
import requests

from src.core import local_ai


@pytest.fixture(autouse=True)
def _isolate_model_dir(tmp_path, monkeypatch):
    """model_path() читает каталог данных приложения - подменяем его на
    временную папку, чтобы тесты не трогали реальные файлы пользователя
    и не зависели друг от друга."""
    monkeypatch.setattr(local_ai, "get_app_data_dir", lambda: str(tmp_path))
    # Кэш загруженной модели - модульный синглтон, сбрасываем между тестами.
    local_ai._llm_instance = None
    yield
    local_ai._llm_instance = None


@pytest.fixture
def fake_llama_cpp_available(monkeypatch):
    """Подделывает наличие пакета llama-cpp-python в sys.modules, не
    требуя его реальной установки. Фейковая модель возвращает разный ответ
    на каждый вызов по порядку (полезно там, где тест сам вызывает
    run_local_analysis несколько раз), с нумерацией с 1."""
    fake_module = type(sys)("llama_cpp")

    class _FakeLlama:
        call_log = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            _FakeLlama.call_log.append(kwargs)
            n = len(_FakeLlama.call_log)
            return {"choices": [{"message": {"content": f"  fake answer {n}  "}}]}

    _FakeLlama.call_log = []
    fake_module.Llama = _FakeLlama
    fake_module._FakeLlama = _FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)
    return fake_module


@pytest.fixture
def fake_llama_cpp_missing(monkeypatch):
    """Присвоение None в sys.modules заставляет `import llama_cpp` кидать
    ImportError, независимо от того, установлен ли пакет на самом деле в
    окружении, где запускаются тесты."""
    monkeypatch.setitem(sys.modules, "llama_cpp", None)


def test_model_path_creates_models_dir(tmp_path):
    path = local_ai.model_path()
    assert path == os.path.join(str(tmp_path), "models", local_ai.MODEL_FILENAME)
    assert os.path.isdir(os.path.join(str(tmp_path), "models"))


def test_is_model_downloaded_false_when_missing():
    assert local_ai.is_model_downloaded() is False


def test_is_model_downloaded_false_for_empty_file():
    path = local_ai.model_path()
    open(path, "wb").close()
    assert local_ai.is_model_downloaded() is False


def test_is_model_downloaded_true_when_present():
    path = local_ai.model_path()
    with open(path, "wb") as f:
        f.write(b"fake gguf content")
    assert local_ai.is_model_downloaded() is True


def test_is_available_false_without_package(fake_llama_cpp_missing):
    assert local_ai.is_available() is False


def test_is_available_true_with_package(fake_llama_cpp_available):
    assert local_ai.is_available() is True


class _FakeResponse:
    def __init__(self, status_code=200, chunks=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    def iter_content(self, chunk_size):
        for chunk in self._chunks:
            yield chunk


def test_download_model_success_renames_part_file(monkeypatch):
    chunks = [b"hello ", b"world"]
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(200, chunks, {"Content-Length": "11"}))

    progress_calls = []
    ok = local_ai.download_model(progress_callback=lambda done, total: progress_calls.append((done, total)))

    assert ok is True
    path = local_ai.model_path()
    assert os.path.exists(path)
    assert not os.path.exists(path + ".part")
    with open(path, "rb") as f:
        assert f.read() == b"hello world"
    # Прогресс должен отражать нарастающий объём и известный total.
    assert progress_calls[-1] == (11, 11)


def test_download_model_http_error_leaves_no_file(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse(404))

    ok = local_ai.download_model()

    assert ok is False
    assert not os.path.exists(local_ai.model_path())
    assert not os.path.exists(local_ai.model_path() + ".part")


def test_download_model_network_exception_cleans_up_part_file(monkeypatch):
    def _raise(*a, **kw):
        raise requests.RequestException("connection reset")

    monkeypatch.setattr(requests, "get", _raise)

    ok = local_ai.download_model()

    assert ok is False
    assert not os.path.exists(local_ai.model_path() + ".part")


def test_download_model_interrupted_mid_stream_cleans_up_part_file(monkeypatch):
    """Если скачивание падает уже во время чтения чанков (не при самом
    запросе), временный .part-файл всё равно не должен остаться - иначе
    is_model_downloaded() никогда не подтвердит новую попытку по имени
    финального файла, но полурабочий .part будет висеть вечно."""

    class _BrokenResponse(_FakeResponse):
        def iter_content(self, chunk_size):
            yield b"partial"
            raise requests.RequestException("dropped")

    monkeypatch.setattr(requests, "get", lambda *a, **kw: _BrokenResponse(200))

    ok = local_ai.download_model()

    assert ok is False
    assert not os.path.exists(local_ai.model_path() + ".part")
    assert not os.path.exists(local_ai.model_path())


def test_run_local_analysis_unavailable_without_package(fake_llama_cpp_missing):
    result = local_ai.run_local_analysis("some_artist")
    assert "llama-cpp-python" in result or "not available" in result.lower()


def test_run_local_analysis_unavailable_uses_tr_func(fake_llama_cpp_missing):
    tr_func = lambda key: f"[{key}]"
    result = local_ai.run_local_analysis("some_artist", tr_func=tr_func)
    assert result == "[ai_err_local_unavailable]"


def test_run_local_analysis_downloads_model_then_runs(fake_llama_cpp_available, monkeypatch):
    assert not local_ai.is_model_downloaded()

    def _fake_download(progress_callback=None):
        if progress_callback:
            progress_callback(5, 10)
        with open(local_ai.model_path(), "wb") as f:
            f.write(b"fake model bytes")
        return True

    monkeypatch.setattr(local_ai, "download_model", _fake_download)

    progress_texts = []
    result = local_ai.run_local_analysis("tag_a, tag_b", progress_callback=progress_texts.append)

    # run_local_analysis теперь отвечает ТОЛЬКО за описание стиля (один
    # запрос к модели) - список похожих авторов больше не спрашивается у
    # LLM вообще, а ищется детерминированно на сайте (см.
    # SearchEngine.find_similar_artists) и добавляется уже в src/app/ai.py.
    assert result == "fake answer 1"
    assert any("Downloading" in t or "download" in t.lower() for t in progress_texts)
    assert any("Loading" in t or "load" in t.lower() for t in progress_texts)


def test_run_local_analysis_makes_single_style_only_request(fake_llama_cpp_available):
    path = local_ai.model_path()
    with open(path, "wb") as f:
        f.write(b"fake model bytes")

    local_ai.run_local_analysis("tag_a, tag_b", lang="ru")

    calls = sys.modules["llama_cpp"]._FakeLlama.call_log
    assert len(calls) == 1
    user_msg = next(m["content"] for m in calls[0]["messages"] if m["role"] == "user")
    # Промпт про стиль/теги, а не про "предложи похожих авторов" - и не
    # составной ("1) ... 2) ...") промпт из старой версии.
    assert "стиль" in user_msg.lower()
    assert not ("1)" in user_msg and "2)" in user_msg)
    assert "имён авторов" in user_msg or "artist names" in user_msg.lower()


def test_run_local_analysis_english_prompts_for_english_lang(fake_llama_cpp_available):
    path = local_ai.model_path()
    with open(path, "wb") as f:
        f.write(b"fake model bytes")

    result = local_ai.run_local_analysis("tag_a", lang="en")

    assert result == "fake answer 1"
    calls = sys.modules["llama_cpp"]._FakeLlama.call_log
    assert len(calls) == 1
    system_msg = next(m["content"] for m in calls[0]["messages"] if m["role"] == "system")
    assert "English" in system_msg


def test_run_local_analysis_download_failure_returns_error(fake_llama_cpp_available, monkeypatch):
    monkeypatch.setattr(local_ai, "download_model", lambda progress_callback=None: False)

    result = local_ai.run_local_analysis("some_artist")

    assert "Failed" in result or "failed" in result.lower()


def test_run_local_analysis_reuses_cached_llm_instance(fake_llama_cpp_available):
    path = local_ai.model_path()
    with open(path, "wb") as f:
        f.write(b"fake model bytes")

    local_ai.run_local_analysis("first_artist")
    first_instance = local_ai._llm_instance
    local_ai.run_local_analysis("second_artist")

    assert local_ai._llm_instance is first_instance


def test_run_local_analysis_handles_inference_exception(fake_llama_cpp_available, monkeypatch):
    path = local_ai.model_path()
    with open(path, "wb") as f:
        f.write(b"fake model bytes")

    class _ExplodingLlm:
        def create_chat_completion(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(local_ai, "_get_llm", lambda: _ExplodingLlm())

    result = local_ai.run_local_analysis("some_artist")

    assert "boom" in result
