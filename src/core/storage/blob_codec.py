"""Кодек для несекретных данных на диске: base64(zlib(...)). Это НЕ
шифрование - см. src.core.storage.secure_store для шифрования учётных
данных."""
from __future__ import annotations

import base64
import binascii
import json
import zlib


def encode_bytes(raw: bytes) -> bytes:
    """raw -> base64(zlib(raw))."""
    return base64.b64encode(zlib.compress(raw))


def decode_bytes(payload: bytes) -> bytes | None:
    """base64(zlib(raw)) -> raw, либо None при повреждённых/чужих данных."""
    try:
        return zlib.decompress(base64.b64decode(payload))
    except (ValueError, TypeError, zlib.error, binascii.Error):
        return None


def encode_json(data) -> bytes:
    """Любой JSON-сериализуемый объект -> base64(zlib(json))."""
    return encode_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def decode_json(payload: bytes):
    """base64(zlib(json)) -> объект, либо None при ошибке."""
    raw = decode_bytes(payload)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def encode_text(text: str) -> bytes:
    """Обычный текст -> base64(zlib(text))."""
    return encode_bytes(text.encode("utf-8"))


def decode_text(payload: bytes) -> str | None:
    """base64(zlib(text)) -> текст, либо None при ошибке."""
    raw = decode_bytes(payload)
    if raw is None:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
