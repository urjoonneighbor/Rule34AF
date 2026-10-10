"""
Шифрование чувствительных данных (API-ключи, User ID / логины).

  - ключ шифрования создаётся один раз на машине и хранится в системном
    защищённом хранилище через пакет `keyring` (Windows Credential
    Manager / macOS Keychain / Secret Service на Linux);
  - сами данные на диске шифруются этим ключом через
    `cryptography.fernet.Fernet` (AES128 + HMAC);
  - если пакеты `keyring`/`cryptography` не установлены или системное
    хранилище недоступно (например, headless Linux без Secret Service),
    используется кодирование base64+zlib как запасной вариант, с
    предупреждением в лог о том, что это не защищает данные.
"""
from __future__ import annotations

import base64

from src.core import applog

_SERVICE_NAME = "Rule34ArtistFinder"
_KEY_USERNAME = "settings_encryption_key"

_fernet = None
_encryption_available: bool | None = None
_warned_fallback = False


def _get_or_create_key() -> bytes | None:
    try:
        import keyring
        from cryptography.fernet import Fernet
    except ImportError:
        return None

    try:
        existing = keyring.get_password(_SERVICE_NAME, _KEY_USERNAME)
        if existing:
            return existing.encode("utf-8")

        new_key = Fernet.generate_key()
        keyring.set_password(_SERVICE_NAME, _KEY_USERNAME, new_key.decode("utf-8"))
        return new_key
    except Exception as e:
        applog.warning(f"Не удалось получить/создать ключ шифрования в системном хранилище: {e}")
        return None


def is_encryption_available() -> bool:
    """Проверяет (один раз за сессию) доступность настоящего шифрования."""
    global _encryption_available, _fernet, _warned_fallback

    if _encryption_available is not None:
        return _encryption_available

    key = _get_or_create_key()
    if not key:
        _encryption_available = False
        if not _warned_fallback:
            applog.warning(
                "Пакеты 'keyring'/'cryptography' недоступны - учётные данные будут только "
                "закодированы (base64+zlib), а не зашифрованы. Установите их для реальной защиты: "
                "pip install keyring cryptography"
            )
            _warned_fallback = True
        return False

    try:
        from cryptography.fernet import Fernet

        _fernet = Fernet(key)
        _encryption_available = True
    except Exception as e:
        applog.warning(f"Шифрование недоступно: {e}")
        _encryption_available = False

    return _encryption_available


def encrypt(data: bytes) -> bytes:
    """Шифрует данные, если возможно; иначе кодирует base64 (с явным префиксом формата)."""
    if is_encryption_available():
        try:
            return b"ENC1:" + _fernet.encrypt(data)
        except Exception as e:
            applog.warning(f"Ошибка шифрования, сохраняем в кодированном (не зашифрованном) виде: {e}")
    return b"RAW1:" + base64.b64encode(data)


def decrypt(payload: bytes) -> bytes | None:
    """Расшифровывает/декодирует данные, полученные из encrypt(). Возвращает None при ошибке."""
    if payload.startswith(b"ENC1:"):
        if not is_encryption_available():
            applog.warning("Данные были зашифрованы, но ключ шифрования сейчас недоступен.")
            return None
        try:
            return _fernet.decrypt(payload[5:])
        except Exception as e:
            applog.warning(f"Не удалось расшифровать сохранённые данные: {e}")
            return None

    if payload.startswith(b"RAW1:"):
        try:
            return base64.b64decode(payload[5:])
        except Exception as e:
            applog.warning(f"Не удалось декодировать сохранённые данные: {e}")
            return None

    return None
