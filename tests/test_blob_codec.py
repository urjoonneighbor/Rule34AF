"""Тесты для src.core.storage.blob_codec - кодека base64(zlib(...))."""
from src.core.storage import blob_codec


def test_bytes_roundtrip():
    raw = b"\x00\x01hello world\xff" * 10
    encoded = blob_codec.encode_bytes(raw)
    assert blob_codec.decode_bytes(encoded) == raw


def test_json_roundtrip():
    data = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}, "ru": "привет"}
    encoded = blob_codec.encode_json(data)
    assert blob_codec.decode_json(encoded) == data


def test_text_roundtrip():
    text = "тестовая строка с юникодом 日本語"
    encoded = blob_codec.encode_text(text)
    assert blob_codec.decode_text(encoded) == text


def test_decode_bytes_corrupt_payload_returns_none():
    assert blob_codec.decode_bytes(b"not a valid base64/zlib payload!!!") is None


def test_decode_json_corrupt_payload_returns_none():
    assert blob_codec.decode_json(b"garbage") is None


def test_decode_json_valid_zlib_but_not_json_returns_none():
    # Валидный base64+zlib, но внутри не JSON, а просто текст.
    encoded = blob_codec.encode_bytes(b"just some text, not json")
    assert blob_codec.decode_json(encoded) is None


def test_decode_text_corrupt_payload_returns_none():
    assert blob_codec.decode_text(b"!!!not valid!!!") is None


def test_empty_json_roundtrip():
    assert blob_codec.decode_json(blob_codec.encode_json({})) == {}
    assert blob_codec.decode_json(blob_codec.encode_json([])) == []
