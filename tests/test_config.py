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


def test_ai_provider_and_model_persist_across_restart(tmp_path, fake_app, monkeypatch):
    """Раньше вкладка AI-анализа при каждом перезапуске откатывалась на
    дефолтный "Ollama (Локально)", т.к. провайдер/модель вообще не
    сохранялись (см. CHANGELOG) - пользователь выбирал другого провайдера,
    закрывал программу, и при следующем запуске снова видел Ollama."""
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.ai_provider_var.set("Gemini API")
    fake_app.ai_model_var.set("gemini-2.0-flash")
    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.ai_provider_var.get() == "Gemini API"
    assert fresh_app.ai_model_var.get() == "gemini-2.0-flash"


def test_ai_api_key_saved_encrypted_separately_from_settings(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.ai_provider_var.set("Gemini API")
    fake_app.ai_api_key_var.set("my-secret-ai-key")
    mgr.save_settings()

    # В обычном (не зашифрованном) файле настроек ключа быть не должно - как
    # и для ключей буру-сайтов (см. test_credentials_saved_encrypted_separately_from_settings).
    with open(mgr.settings_file, "rb") as f:
        raw_settings_bytes = f.read()
    assert b"my-secret-ai-key" not in raw_settings_bytes

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()
    assert fresh_app.ai_api_key_var.get() == "my-secret-ai-key"


def test_gal_current_artist_persists_across_restart(tmp_path, fake_app, monkeypatch):
    """Раньше сохранялась только страница КАЖДОГО автора в галерее
    (gal_artist_positions), но не то, какой автор был открыт - после
    перезапуска список авторов оставался невыбранным, и сохранённая позиция
    была не к чему применить. Внешне это выглядело как "страница не
    сохраняется" (см. CHANGELOG)."""
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.gal_current_artist = "some_artist"
    fake_app.gal_artist_positions = {"some_artist": 3}
    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.gal_current_artist == "some_artist"
    assert fresh_app.gal_artist_positions == {"some_artist": 3}


def test_gal_last_viewed_files_persist_across_restart(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.gal_artist_last_files = {"some_artist": "some_artist_0037.jpg"}
    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.gal_artist_last_files == {"some_artist": "some_artist_0037.jpg"}


def test_gal_current_artist_defaults_to_empty_when_never_set(tmp_path, fake_app, monkeypatch):
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)
    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.gal_current_artist == ""


def test_ai_api_key_does_not_leak_into_site_credentials(tmp_path, fake_app, monkeypatch):
    """Ключ AI-провайдера хранится в том же зашифрованном файле, что и ключи
    буру-сайтов, под отдельным зарезервированным именем - но не должен
    попасть в site_credentials под видом настоящего сайта и не должен
    задеть реальные, ранее сохранённые ключи сайтов."""
    mgr = _make_manager(tmp_path, fake_app, monkeypatch)

    fake_app.site_var.set("rule34.xxx")
    fake_app.api_key_var.set("site-key")
    fake_app.user_id_var.set("site-user")
    fake_app.ai_api_key_var.set("ai-key")
    mgr.save_settings()

    fresh_app = type(fake_app)()
    mgr2 = ConfigManager(fresh_app)
    mgr2.load_settings()

    assert fresh_app.api_key_var.get() == "site-key"
    assert fresh_app.user_id_var.get() == "site-user"
    assert fresh_app.ai_api_key_var.get() == "ai-key"
    # Зарезервированный ключ AI не должен всплыть как обычный "сайт".
    assert "rule34.xxx" in fresh_app.site_credentials
    assert fresh_app.site_credentials["rule34.xxx"]["api_key"] == "site-key"
