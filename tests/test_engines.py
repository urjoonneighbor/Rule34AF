"""Тесты для движков Booru-сайтов (src.core.network.engines.*) с
замоканным HTTP-клиентом (fake scraper) - без единого реального сетевого
запроса."""
import threading

from src.core.network.engines.danbooru import DanbooruEngine
from src.core.network.engines.gelbooru import GelbooruEngine
from src.core.network.engines.paheal import PahealEngine


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class FakeScraper:
    """Мок для cloudscraper.create_scraper() - возвращает заранее заданные
    ответы по очереди, не делая реальных сетевых запросов."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None, **kwargs):
        self.calls.append((url, params))
        if not self._responses:
            return FakeResponse(status_code=404)
        return self._responses.pop(0)

    def post(self, url, json=None, headers=None, timeout=None, **kwargs):
        self.calls.append((url, json))
        if not self._responses:
            return FakeResponse(status_code=404)
        return self._responses.pop(0)


def _stopped_event_false():
    ev = threading.Event()
    return ev


# ---------------------------------------------------------------------
# GelbooruEngine
# ---------------------------------------------------------------------

def test_gelbooru_get_image_data_parses_posts():
    posts_page = [
        {"file_url": "http://x/1.jpg", "tags": "cat dog", "hash": "ABC123"},
        {"file_url": "http://x/2.jpg", "tags": "cat blood", "hash": "DEF456"},
    ]
    scraper = FakeScraper([FakeResponse(json_data=posts_page), FakeResponse(json_data=[])])
    engine = GelbooruEngine(scraper)

    results = engine.get_image_data("cat -blood", "", "", max_limit=0)

    assert len(results) == 1
    assert results[0]["url"] == "http://x/1.jpg"
    assert results[0]["md5"] == "abc123"


def test_gelbooru_get_image_data_empty_query_returns_empty():
    engine = GelbooruEngine(FakeScraper([]))
    assert engine.get_image_data("-onlynegative", "", "", 0) == []


def test_gelbooru_fetch_autocomplete_success():
    scraper = FakeScraper([FakeResponse(json_data=[{"label": "cat_ears (100)", "value": "cat_ears"}])])
    engine = GelbooruEngine(scraper)
    result = engine.fetch_autocomplete("cat")
    assert result == [{"label": "cat_ears (100)", "value": "cat_ears"}]


def test_gelbooru_fetch_autocomplete_network_error_returns_empty_list():
    class RaisingScraper(FakeScraper):
        def get(self, *a, **k):
            raise ConnectionError("boom")

    engine = GelbooruEngine(RaisingScraper([]))
    assert engine.fetch_autocomplete("cat") == []


def test_gelbooru_get_all_posts_respects_stop_event():
    scraper = FakeScraper([FakeResponse(json_data=[{"tags": "cat"}])])
    engine = GelbooruEngine(scraper)
    stop_event = threading.Event()
    stop_event.set()

    result = engine.get_all_posts("cat", "", "", stop_event, None)
    assert result == []


# ---------------------------------------------------------------------
# DanbooruEngine
# ---------------------------------------------------------------------

def test_danbooru_get_image_data_parses_posts():
    posts_page = [
        {"file_url": "http://x/1.jpg", "tag_string": "cat dog", "md5": "ABC123", "file_size": 100},
    ]
    scraper = FakeScraper([FakeResponse(json_data=posts_page), FakeResponse(json_data=[])])
    engine = DanbooruEngine(scraper)

    results = engine.get_image_data("cat", "", "", max_limit=0)

    assert len(results) == 1
    assert results[0]["md5"] == "abc123"
    assert results[0]["size"] == 100


def test_danbooru_get_image_data_empty_query_returns_empty():
    engine = DanbooruEngine(FakeScraper([]))
    assert engine.get_image_data("-onlynegative", "", "", 0) == []


def test_danbooru_safe_get_solves_pow_challenge_when_present():
    challenge_html = (
        'const challenge_id = "cid123";'
        'const challenge_generated = "gen123";'
        'const challenge_cookie_expires = "exp123";'
        'const powSeed = "seed123";'
        'const powPrefix = "0".repeat(1);'
        'const post_to = "https://booru.allthefallen.moe/verify";'
        '<div class="challenge-checkbox"></div>'
    )
    scraper = FakeScraper([
        FakeResponse(status_code=200, text=challenge_html),
        FakeResponse(status_code=200),
        FakeResponse(status_code=200, json_data=[]),
    ])
    engine = DanbooruEngine(scraper)
    resp = engine._safe_get("https://booru.allthefallen.moe/posts.json")
    assert resp.status_code == 200
    # Должен был сходить: 1) первый get (challenge) 2) post (решение) 3) повторный get
    assert len(scraper.calls) >= 2


# ---------------------------------------------------------------------
# PahealEngine
# ---------------------------------------------------------------------

def test_paheal_get_image_data_parses_xml():
    xml_page = (
        '<posts>'
        '<post file_url="http://x/1.jpg" tags="cat dog" md5="ABC123" />'
        '</posts>'
    )
    xml_empty = '<posts></posts>'
    scraper = FakeScraper([
        FakeResponse(status_code=200, text=xml_page),
        FakeResponse(status_code=200, text=xml_empty),
    ])
    engine = PahealEngine(scraper)

    results = engine.get_image_data("cat", "", "", max_limit=0)

    assert len(results) == 1
    assert results[0]["url"] == "http://x/1.jpg"
    assert results[0]["md5"] == "abc123"


def test_paheal_get_image_data_empty_query_returns_empty():
    engine = PahealEngine(FakeScraper([]))
    assert engine.get_image_data("-onlynegative", "", "", 0) == []


def test_paheal_check_tag_global_stats_always_true():
    engine = PahealEngine(FakeScraper([]))
    tag, exists, count = engine.check_tag_global_stats("anything", "", "", threading.Event())
    assert exists is True
    assert count == 0


def test_paheal_fetch_autocomplete_parses_dict_response():
    scraper = FakeScraper([FakeResponse(json_data={"cat_ears": {"count": 42}})])
    engine = PahealEngine(scraper)
    result = engine.fetch_autocomplete("cat")
    assert result == [{"label": "cat_ears (42)", "value": "cat_ears"}]
