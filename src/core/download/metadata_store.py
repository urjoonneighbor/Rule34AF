"""Чтение и запись per-файловых тегов автора (metadata.dat в папке автора),
с миграцией из устаревшего формата metadata.json."""
from __future__ import annotations

import hashlib
import json
import os

from src.core.storage import blob_codec

METADATA_DAT_FILENAME = "metadata.dat"
METADATA_JSON_FILENAME = "metadata.json"  # старый формат, только для миграции


def load_artist_metadata(artist_dir: str) -> dict:
    """Возвращает {имя_файла: строка_тегов} для папки автора.

    Сначала пробует новый формат (metadata.dat, base64+zlib+json), и только
    если его нет - старый (metadata.json, обычный json) для одноразовой
    миграции. Любая ошибка чтения/разбора молча даёт пустой словарь -
    так же, как вело себя изначальное поведение (try/except: pass)."""
    dat_path = os.path.join(artist_dir, METADATA_DAT_FILENAME)
    json_path = os.path.join(artist_dir, METADATA_JSON_FILENAME)

    if os.path.exists(dat_path):
        try:
            with open(dat_path, "rb") as f:
                data = blob_codec.decode_json(f.read())
        except OSError:
            return {}
        return data if isinstance(data, dict) else {}

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    return {}


def save_artist_metadata(artist_dir: str, meta: dict) -> None:
    """Сохраняет метаданные автора в новом формате и убирает устаревший
    metadata.json, если он остался с более старой версии программы.
    Исключения (OSError/ValueError/TypeError) намеренно не глушатся здесь -
    вызывающий код сам решает, как и куда залогировать ошибку записи."""
    dat_path = os.path.join(artist_dir, METADATA_DAT_FILENAME)
    json_path = os.path.join(artist_dir, METADATA_JSON_FILENAME)

    with open(dat_path, "wb") as f:
        f.write(blob_codec.encode_json(meta))

    if os.path.exists(json_path):
        try:
            os.remove(json_path)
        except OSError:
            pass


def get_file_md5(filepath: str) -> str:
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower()
    except OSError:
        return ""
