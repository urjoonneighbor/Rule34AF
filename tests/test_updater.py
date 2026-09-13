"""Тесты для src.core.network.updater - сравнения версий и логики
проверки обновлений через GitHub Releases."""
import threading
import time

from src.core.network import updater


def test_is_newer_true_for_higher_version():
    assert updater.is_newer("1.2.0", "1.1.0") is True


def test_is_newer_false_for_equal_version():
    assert updater.is_newer("1.1.0", "1.1.0") is False


def test_is_newer_false_for_lower_version():
    assert updater.is_newer("1.0.0", "1.1.0") is False


def test_is_newer_handles_v_prefix():
    assert updater.is_newer("v1.2.0", "1.1.0") is True


def test_is_newer_handles_missing_patch_component():
    assert updater.is_newer("1.2", "1.1.9") is True
    assert updater.is_newer("1.1", "1.1.0") is False


def test_is_newer_handles_extra_suffix_text():
    # "1.2.0-beta" -> цифры вычленяются, суффикс игнорируется
    assert updater.is_newer("1.2.0-beta", "1.1.0") is True


def test_is_newer_returns_false_on_garbage_input():
    assert updater.is_newer("not-a-version", "1.0.0") is False


def _fake_release_response(tag: str, html_url: str = "https://example.com/release"):
    class FakeResponse:
        status_code = 200

        def json(self_inner):
            return {"tag_name": tag, "html_url": html_url}

    return FakeResponse()


def test_check_for_updates_async_calls_callback_on_newer_version(monkeypatch):
    monkeypatch.setattr(updater, "REPO_OWNER", "someowner")
    monkeypatch.setattr(updater, "REPO_NAME", "somerepo")
    monkeypatch.setattr(
        updater.requests, "get",
        lambda url, timeout=None, headers=None: _fake_release_response("v999.0.0", "https://example.com/release"))

    called = threading.Event()
    result = {}

    def on_new_version(tag, html_url):
        result["tag"] = tag
        result["html_url"] = html_url
        called.set()

    updater.check_for_updates_async(on_new_version, timeout=1.0)
    assert called.wait(timeout=3.0), "callback не был вызван вовремя"
    assert result["tag"] == "v999.0.0"
    assert result["html_url"] == "https://example.com/release"


def test_check_for_updates_async_no_callback_when_up_to_date(monkeypatch):
    monkeypatch.setattr(updater, "REPO_OWNER", "someowner")
    monkeypatch.setattr(updater, "REPO_NAME", "somerepo")
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: _fake_release_response("v0.0.1"))

    called = threading.Event()
    updater.check_for_updates_async(lambda tag, url: called.set(), timeout=1.0)

    time.sleep(0.5)
    assert not called.is_set()


def test_check_for_updates_async_no_callback_when_repo_not_configured(monkeypatch):
    monkeypatch.setattr(updater, "REPO_OWNER", "")
    monkeypatch.setattr(updater, "REPO_NAME", "somerepo")

    def fake_get(*a, **k):
        raise AssertionError("не должен ходить в сеть, если репозиторий не настроен")

    monkeypatch.setattr(updater.requests, "get", fake_get)

    called = threading.Event()
    updater.check_for_updates_async(lambda tag, url: called.set(), timeout=1.0)
    time.sleep(0.3)
    assert not called.is_set()


def test_check_for_updates_async_swallows_network_errors(monkeypatch):
    monkeypatch.setattr(updater, "REPO_OWNER", "someowner")
    monkeypatch.setattr(updater, "REPO_NAME", "somerepo")

    def fake_get(*a, **k):
        raise ConnectionError("no network")

    monkeypatch.setattr(updater.requests, "get", fake_get)

    called = threading.Event()
    # Не должно бросить исключение наружу, даже если запрос падает.
    updater.check_for_updates_async(lambda tag, url: called.set(), timeout=1.0)
    time.sleep(0.5)
    assert not called.is_set()
