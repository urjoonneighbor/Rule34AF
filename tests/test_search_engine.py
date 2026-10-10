"""Тесты для src.core.search.engine.SearchEngine.build_taste_profile и
find_similar_artists - детерминированного, основанного на реальных данных
сайта поиска "похожих авторов" (см. CHANGELOG). В отличие от search_worker,
здесь не поднимается настоящий Tk и не делается ни одного настоящего
сетевого запроса - app.api полностью подделан."""
from src.core.search.engine import SearchEngine


class _FakeApi:
    """app.api для тестов find_similar_artists: get_all_posts и
    check_tag_global_stats отвечают по заранее заданным словарям, без
    единого настоящего HTTP-запроса."""

    def __init__(self, posts_by_query=None, artist_stats=None):
        self.posts_by_query = posts_by_query or {}
        self.artist_stats = artist_stats or {}
        self.queries_made = []

    def get_all_posts(self, query_string, api_key, user_id, stop_event, log_callback=None):
        self.queries_made.append(query_string)
        return self.posts_by_query.get(query_string, [])

    def check_tag_global_stats(self, tag_name, api_key, user_id, stop_event):
        is_artist, count = self.artist_stats.get(tag_name, (False, 0))
        return tag_name, is_artist, count


class _FakeApp:
    def __init__(self, api=None):
        self.api = api or _FakeApi()
        self.MAX_WORKERS = 2


def _engine(api=None):
    return SearchEngine(_FakeApp(api))


# --- build_taste_profile ---------------------------------------------------

def test_build_taste_profile_ranks_by_frequency():
    engine = _engine()
    data = [
        {"artist": "a1", "tags": ["fantasy", "dragon", "rating:explicit"]},
        {"artist": "a2", "tags": ["fantasy", "elf"]},
        {"artist": "a3", "tags": ["fantasy", "dragon"]},
    ]
    profile = engine.build_taste_profile(data, known_names=set(), top_n=6)
    assert profile[0] == "fantasy"
    assert "dragon" in profile
    assert "elf" in profile


def test_build_taste_profile_excludes_rating_and_source_tags():
    engine = _engine()
    data = [{"artist": "a1", "tags": ["rating:explicit", "source:twitter", "fantasy"]}]
    profile = engine.build_taste_profile(data, known_names=set())
    assert profile == ["fantasy"]


def test_build_taste_profile_excludes_generic_composition_tags():
    engine = _engine()
    data = [{"artist": "a1", "tags": ["1girl", "solo", "highres", "fantasy"]}]
    profile = engine.build_taste_profile(data, known_names=set())
    assert profile == ["fantasy"]


def test_build_taste_profile_excludes_known_artist_names_used_as_tags():
    # Коллаборации: тег с именем другого известного автора не должен войти
    # в профиль вкуса как будто это тема/жанр.
    engine = _engine()
    data = [{"artist": "a1", "tags": ["fantasy", "other_known_artist"]}]
    profile = engine.build_taste_profile(data, known_names={"other_known_artist"})
    assert profile == ["fantasy"]


def test_build_taste_profile_respects_top_n():
    engine = _engine()
    data = [{"artist": "a1", "tags": ["t1", "t2", "t3", "t4"]}]
    profile = engine.build_taste_profile(data, known_names=set(), top_n=2)
    assert len(profile) == 2


def test_build_taste_profile_handles_missing_tags_field():
    engine = _engine()
    data = [{"artist": "a1"}, {"artist": "a2", "tags": []}]
    assert engine.build_taste_profile(data, known_names=set()) == []


# --- find_similar_artists ---------------------------------------------------

def test_find_similar_artists_returns_empty_without_profile_tags():
    engine = _engine()
    assert engine.find_similar_artists([], "key", "uid", known_names=set()) == []


def test_find_similar_artists_discovers_new_artist_from_posts():
    api = _FakeApi(
        posts_by_query={"fantasy dragon": [{"tags": "fantasy dragon new_artist_x rating:explicit"}]},
        artist_stats={"new_artist_x": (True, 500), "fantasy": (False, 0), "dragon": (False, 0)},
    )
    engine = _engine(api)
    result = engine.find_similar_artists(["fantasy", "dragon"], "key", "uid", known_names=set())
    assert result == [("new_artist_x", 500)]


def test_find_similar_artists_excludes_already_known_artists():
    api = _FakeApi(
        posts_by_query={"fantasy": [{"tags": "fantasy already_known_artist new_artist_x"}]},
        artist_stats={"already_known_artist": (True, 9999), "new_artist_x": (True, 100)},
    )
    engine = _engine(api)
    result = engine.find_similar_artists(["fantasy"], "key", "uid", known_names={"already_known_artist"})
    assert result == [("new_artist_x", 100)]


def test_find_similar_artists_ranks_by_post_count_descending():
    api = _FakeApi(
        posts_by_query={"fantasy": [{"tags": "fantasy low_count_artist high_count_artist"}]},
        artist_stats={"low_count_artist": (True, 50), "high_count_artist": (True, 900)},
    )
    engine = _engine(api)
    result = engine.find_similar_artists(["fantasy"], "key", "uid", known_names=set())
    assert result == [("high_count_artist", 900), ("low_count_artist", 50)]


def test_find_similar_artists_tries_broader_query_when_narrow_finds_nothing():
    # Запрос по всем трём тегам сразу не дал постов - должен произойти
    # переход к более широкому запросу (по двум, потом по одному тегу).
    api = _FakeApi(
        posts_by_query={
            "t1 t2 t3": [],
            "t1 t2": [],
            "t1": [{"tags": "t1 new_artist_x"}],
        },
        artist_stats={"new_artist_x": (True, 42)},
    )
    engine = _engine(api)
    result = engine.find_similar_artists(["t1", "t2", "t3"], "key", "uid", known_names=set())
    assert result == [("new_artist_x", 42)]
    assert "t1 t2 t3" in api.queries_made
    assert "t1" in api.queries_made


def test_find_similar_artists_stops_once_max_results_reached():
    api = _FakeApi(
        posts_by_query={
            "t1 t2": [{"tags": "t1 t2 artist_a artist_b"}],
            "t1": [{"tags": "t1 artist_c"}],
        },
        artist_stats={
            "artist_a": (True, 10), "artist_b": (True, 20), "artist_c": (True, 30),
        },
    )
    engine = _engine(api)
    result = engine.find_similar_artists(["t1", "t2"], "key", "uid", known_names=set(), max_results=2)
    assert len(result) == 2
    # Второй (более широкий) запрос по одному тегу не должен был потребоваться.
    assert "t1" not in api.queries_made


def test_find_similar_artists_ignores_non_artist_tags():
    api = _FakeApi(
        posts_by_query={"fantasy": [{"tags": "fantasy not_an_artist_tag"}]},
        artist_stats={"not_an_artist_tag": (False, 0)},
    )
    engine = _engine(api)
    assert engine.find_similar_artists(["fantasy"], "key", "uid", known_names=set()) == []


def test_find_similar_artists_handles_get_all_posts_exception_gracefully():
    class _ExplodingApi(_FakeApi):
        def get_all_posts(self, *a, **kw):
            raise RuntimeError("network boom")

    engine = _engine(_ExplodingApi())
    assert engine.find_similar_artists(["fantasy"], "key", "uid", known_names=set()) == []
