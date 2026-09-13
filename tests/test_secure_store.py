"""Тесты для src.core.storage.secure_store - шифрования учётных данных
(с keyring/cryptography и без них - fallback-режим)."""
import pytest

from src.core.storage import secure_store


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Модуль кэширует доступность шифрования в глобальных переменных -
    сбрасываем их до и после каждого теста для изоляции."""
    secure_store._fernet = None
    secure_store._encryption_available = None
    secure_store._warned_fallback = False
    yield
    secure_store._fernet = None
    secure_store._encryption_available = None
    secure_store._warned_fallback = False


def test_fallback_roundtrip_without_keyring(monkeypatch):
    """Если keyring/cryptography недоступны - используется RAW1: base64-фоллбэк,
    но данные всё равно должны корректно "туда-обратно" проходить."""
    monkeypatch.setattr(secure_store, "_get_or_create_key", lambda: None)

    payload = secure_store.encrypt(b"secret api key data")
    assert payload.startswith(b"RAW1:")

    decrypted = secure_store.decrypt(payload)
    assert decrypted == b"secret api key data"


def test_real_encryption_roundtrip_with_fake_key(monkeypatch):
    """Подсовываем фейковый ключ Fernet (без реального keyring), проверяем,
    что шифрование действительно шифрует (не просто base64) и расшифровывается обратно."""
    cryptography = pytest.importorskip("cryptography")
    from cryptography.fernet import Fernet

    fake_key = Fernet.generate_key()
    monkeypatch.setattr(secure_store, "_get_or_create_key", lambda: fake_key)

    payload = secure_store.encrypt(b"top secret")
    assert payload.startswith(b"ENC1:")
    # Не должно совпадать с обычным base64 представлением - т.е. действительно зашифровано.
    import base64
    assert base64.b64encode(b"top secret") not in payload

    assert secure_store.decrypt(payload) == b"top secret"


def test_decrypt_unknown_prefix_returns_none():
    assert secure_store.decrypt(b"GARBAGE:notarealpayload") is None


def test_decrypt_enc_prefix_without_key_returns_none(monkeypatch):
    monkeypatch.setattr(secure_store, "_get_or_create_key", lambda: None)
    # Помечено как зашифрованное, но ключа нет и никогда не было.
    assert secure_store.decrypt(b"ENC1:somepayload") is None


def test_is_encryption_available_cached(monkeypatch):
    calls = {"n": 0}

    def fake_get_key():
        calls["n"] += 1
        return None

    monkeypatch.setattr(secure_store, "_get_or_create_key", fake_get_key)

    secure_store.is_encryption_available()
    secure_store.is_encryption_available()

    assert calls["n"] == 1  # второй вызов должен использовать кэш
