"""Тесты для src.core.media_types - списка поддерживаемых расширений."""
from src.core import media_types


def test_image_and_video_extensions_disjoint():
    assert media_types.IMAGE_EXTENSIONS.isdisjoint(media_types.VIDEO_EXTENSIONS)


def test_allowed_is_union_of_image_and_video():
    assert media_types.ALLOWED_EXTENSIONS == (
        media_types.IMAGE_EXTENSIONS | media_types.VIDEO_EXTENSIONS
    )


def test_common_extensions_present():
    for ext in ("jpg", "png", "gif", "webp"):
        assert ext in media_types.IMAGE_EXTENSIONS
    for ext in ("mp4", "webm"):
        assert ext in media_types.VIDEO_EXTENSIONS


def test_unrelated_extension_not_allowed():
    assert "exe" not in media_types.ALLOWED_EXTENSIONS
    assert "txt" not in media_types.ALLOWED_EXTENSIONS
