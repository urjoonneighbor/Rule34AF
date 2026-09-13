"""Тесты для src.core.download.metadata_store - чтения/записи metadata.dat
в папке автора."""
import os

from src.core.download import metadata_store


def test_load_metadata_missing_dir_returns_empty_dict(tmp_path):
    artist_dir = str(tmp_path / "no_such_artist")
    assert metadata_store.load_artist_metadata(artist_dir) == {}


def test_save_and_load_roundtrip(tmp_path):
    artist_dir = str(tmp_path)
    meta = {"pic1.jpg": "tag1 tag2", "pic2.png": "tag3"}

    metadata_store.save_artist_metadata(artist_dir, meta)
    loaded = metadata_store.load_artist_metadata(artist_dir)

    assert loaded == meta
    assert os.path.exists(os.path.join(artist_dir, metadata_store.METADATA_DAT_FILENAME))


def test_legacy_json_fallback_used_when_dat_missing(tmp_path):
    artist_dir = str(tmp_path)
    legacy_path = os.path.join(artist_dir, metadata_store.METADATA_JSON_FILENAME)
    with open(legacy_path, "w", encoding="utf-8") as f:
        f.write('{"old_pic.jpg": "legacy tags"}')

    loaded = metadata_store.load_artist_metadata(artist_dir)
    assert loaded == {"old_pic.jpg": "legacy tags"}


def test_new_format_takes_priority_over_legacy(tmp_path):
    artist_dir = str(tmp_path)
    with open(os.path.join(artist_dir, metadata_store.METADATA_JSON_FILENAME), "w", encoding="utf-8") as f:
        f.write('{"old.jpg": "old"}')
    metadata_store.save_artist_metadata(artist_dir, {"new.jpg": "new"})

    loaded = metadata_store.load_artist_metadata(artist_dir)
    assert loaded == {"new.jpg": "new"}


def test_save_removes_stale_legacy_json(tmp_path):
    artist_dir = str(tmp_path)
    legacy_path = os.path.join(artist_dir, metadata_store.METADATA_JSON_FILENAME)
    with open(legacy_path, "w", encoding="utf-8") as f:
        f.write("{}")

    metadata_store.save_artist_metadata(artist_dir, {"a.jpg": "t"})

    assert not os.path.exists(legacy_path)


def test_load_corrupt_dat_returns_empty_dict(tmp_path):
    artist_dir = str(tmp_path)
    with open(os.path.join(artist_dir, metadata_store.METADATA_DAT_FILENAME), "wb") as f:
        f.write(b"not a valid payload")

    assert metadata_store.load_artist_metadata(artist_dir) == {}


def test_get_file_md5(tmp_path):
    filepath = tmp_path / "file.bin"
    filepath.write_bytes(b"hello world")

    import hashlib
    expected = hashlib.md5(b"hello world").hexdigest().lower()
    assert metadata_store.get_file_md5(str(filepath)) == expected


def test_get_file_md5_missing_file_returns_empty_string(tmp_path):
    assert metadata_store.get_file_md5(str(tmp_path / "nope.bin")) == ""
