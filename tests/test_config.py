"""Тесты для src.core.storage.config.ConfigManager - сохранения/загрузки
настроек и учётных данных, без создания настоящего Tk-окна (используется
FakeApp/FakeVar из conftest.py)."""
import json
import os

from src.core.storage import paths, secure_store
from src.core.storage.config import ConfigManager


def _make_manager(tmp_path, fake_app, monkeypatch):
    monkeypatch.setattr(paths, "get_app_data_dir", lambda: str(tmp_path))
    # Отключаем настоящее шифрование - в тестовой среде нет системного
    # хранилища ключей, используем предсказуемый RAW1-фоллбэк.
    monkeypatch.setattr(secure_store, "_get_or_create_key", lambda: None)
    return ConfigManager(fake_app)


def test_save_then_load_settings_roundtrip(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.min_posts_var.set("500")
    fake_app.any_amount_var.set(True)
    fake_app.included_tags = {"cat", "dog"}
    fake_app.grouped_history_data = {"Group": [{"artist": "a1", "count": "3", "tags": []}]}

    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.min_posts_var.get() == "500"
    assert fresh_app.any_amount_var.get() is True
    assert fresh_app.included_tags == {"cat", "dog"}
    assert fresh_app.grouped_history_data == {"Group": [{"artist": "a1", "count": "3", "tags": []}]}


def test_credentials_saved_encrypted_separately_from_settings(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.api_key_var.set("my-secret-api-key")
    fake_app.user_id_var.set("12345")
    mgr.save_settings()

    # В файле настроек (не зашифрованном) секретного ключа быть не должно.
    with open(mgr.settings_file, "rb") as f:
        raw_settings_bytes = f.read()
    assert b"my-secret-api-key" not in raw_settings_bytes

    # А из отдельного зашифрованного файла креды должны корректно вычитываться обратно.
    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()
    assert fresh_app.api_key_var.get() == "my-secret-api-key"
    assert fresh_app.user_id_var.get() == "12345"


def test_load_settings_with_no_files_uses_defaults(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)
    mgr.load_settings()  # не должно бросать исключений при отсутствии файлов

    assert fake_app.api_key_var.get() == ""
    assert fake_app.user_id_var.get() == ""


def test_load_settings_migrates_legacy_plaintext_credentials(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    # Симулируем старый формат: api_key/user_id лежали прямо в основном файле настроек.
    from src.core.storage import blob_codec
    legacy_data = {
        "site": "rule34.xxx",
        "api_key": "legacy-key",
        "user_id": "legacy-user",
    }
    with open(mgr.settings_file, "wb") as f:
        f.write(blob_codec.encode_json(legacy_data))

    mgr.load_settings()

    assert fake_app.api_key_var.get() == "legacy-key"
    assert fake_app.user_id_var.get() == "legacy-user"
    # После миграции креды должны были быть записаны в зашифрованный файл.
    assert os.path.exists(mgr.credentials_file)


def test_load_settings_corrupt_file_falls_back_to_defaults(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)
    with open(mgr.settings_file, "wb") as f:
        f.write(b"not a valid encoded payload")

    mgr.load_settings()  # не должно бросать исключение

    assert fake_app.api_key_var.get() == ""
