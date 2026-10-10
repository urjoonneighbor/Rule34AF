"""Список поддерживаемых расширений изображений и видео - используется и для
распознавания локальных файлов, и как белый список при сохранении
скачанных файлов."""

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "bmp"}
VIDEO_EXTENSIONS = {"mp4", "webm", "avi", "mkv", "mov"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
