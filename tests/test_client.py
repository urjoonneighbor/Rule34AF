"""Тесты для src.core.network.client.Rule34API - фасада, диспетчеризующего
вызовы на текущий движок через реестр SITE_ENGINES (Open/Closed)."""
from src.core.network.client import Rule34API, SITE_ENGINES
from src.core.network.engines.danbooru import DanbooruEngine
from src.core.network.engines.gelbooru import GelbooruEngine
from src.core.network.engines.paheal import PahealEngine


def test_set_site_selects_correct_engine():
    api = Rule34API()

    api.set_site("rule34.xxx")
    assert isinstance(api.engine, GelbooruEngine)

    api.set_site("allthefallen.moe")
    assert isinstance(api.engine, DanbooruEngine)

    api.set_site("rule34.paheal.net")
    assert isinstance(api.engine, PahealEngine)


def test_set_site_unknown_site_falls_back_to_gelbooru():
    api = Rule34API()
    api.set_site("some.unknown.site")
    assert isinstance(api.engine, GelbooruEngine)


def test_site_engines_registry_covers_expected_sites():
    assert set(SITE_ENGINES.keys()) == {"rule34.xxx", "allthefallen.moe", "rule34.paheal.net"}


def test_methods_return_empty_before_site_selected():
    api = Rule34API()
    assert api.engine is None
    assert api.fetch_autocomplete("cat") == []
    assert api.get_all_posts("cat", "", "", None) == []
    assert api.get_image_data("cat", "", "") == []


def test_set_proxy_empty_string_clears_proxies():
    api = Rule34API()
    api.set_proxy("http://127.0.0.1:8080")
    assert api.scraper.proxies == {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"}

    api.set_proxy("")
    assert api.scraper.proxies == {}


def test_get_file_size_empty_url_returns_zero():
    api = Rule34API()
    assert api.get_file_size("") == 0
