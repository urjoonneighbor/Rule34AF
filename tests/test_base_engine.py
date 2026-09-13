"""Тесты для src.core.network.base_engine.BaseEngine - общей логики
фильтрации запросов/постов, одинаковой для всех Booru-движков."""
from src.core.network.base_engine import BaseEngine


def test_parse_query_splits_positive_and_negative_tags():
    pos, neg = BaseEngine._parse_query("cat_ears -rating:explicit dog -blood")
    assert pos == "cat_ears dog"
    assert neg == {"rating:explicit", "blood"}


def test_parse_query_no_negative_tags():
    pos, neg = BaseEngine._parse_query("cat_ears dog")
    assert pos == "cat_ears dog"
    assert neg == set()


def test_parse_query_lone_dash_treated_as_positive():
    # len(w) > 1 требуется, чтобы считать тег отрицательным - одиночный "-"
    # (edge case) остаётся как обычный позитивный токен.
    pos, neg = BaseEngine._parse_query("cat -")
    assert pos == "cat -"
    assert neg == set()


def test_parse_query_lowercases_negative_tags():
    pos, neg = BaseEngine._parse_query("-BLOOD")
    assert neg == {"blood"}


def test_is_bad_no_negative_tags_never_bad():
    assert BaseEngine._is_bad({"tags": "anything"}, set()) is False


def test_is_bad_matches_negative_tag():
    post = {"tags": "cat dog blood"}
    assert BaseEngine._is_bad(post, {"blood"}) is True


def test_is_bad_no_match_is_fine():
    post = {"tags": "cat dog"}
    assert BaseEngine._is_bad(post, {"blood"}) is False


def test_is_bad_rating_questionable():
    post = {"rating": "questionable", "tags": ""}
    assert BaseEngine._is_bad(post, {"rating:questionable"}) is True


def test_is_bad_rating_explicit_short_form():
    post = {"rating": "e", "tags": ""}
    assert BaseEngine._is_bad(post, {"rating:explicit"}) is True


def test_is_bad_rating_safe_not_excluded():
    post = {"rating": "safe", "tags": ""}
    assert BaseEngine._is_bad(post, {"rating:explicit"}) is False


def test_is_bad_uses_tag_string_fallback():
    post = {"tag_string": "cat blood"}
    assert BaseEngine._is_bad(post, {"blood"}) is True


def test_is_bad_uses_tag_fallback_for_paheal_style():
    post = {"tag": "cat blood"}
    assert BaseEngine._is_bad(post, {"blood"}) is True
