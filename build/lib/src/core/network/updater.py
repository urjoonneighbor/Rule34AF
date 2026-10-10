"""
Необязательная проверка обновлений через GitHub Releases.

  - выполняется в фоновом потоке и никогда не блокирует запуск приложения;
  - никогда не показывает пользователю ошибку - при любой сетевой
    проблеме, недоступном GitHub или отсутствии более новой версии просто
    ничего не происходит;
  - не скачивает и не заменяет исполняемый файл сама - только сообщает
    о новой версии и даёт ссылку на страницу релиза, которую пользователь
    открывает сам.

Репозиторий публичный, поэтому обычный анонимный запрос к
api.github.com/repos/{owner}/{repo}/releases/latest работает без токена
(REPO_OWNER/REPO_NAME - см. src/core/version.py).
"""
import threading
from typing import Callable

import requests

from src.core import applog
from src.core.version import REPO_NAME, REPO_OWNER, REPO_URL, __version__


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote_version: str, local_version: str) -> bool:
    try:
        return _parse_version(remote_version) > _parse_version(local_version)
    except (ValueError, TypeError):
        return False


def check_for_updates_async(on_new_version: Callable[[str, str], None], timeout: float = 4.0) -> None:
    """Запускает проверку в фоновом потоке.

    on_new_version(latest_tag, html_url) будет вызван (из фонового потока -
    вызывающая сторона должна сама передать выполнение в UI-поток, например
    через Tk .after()) ТОЛЬКО если найдена версия новее текущей.
    """

    def worker():
        if not REPO_OWNER or not REPO_NAME:
            applog.debug("Проверка обновлений: REPO_OWNER/REPO_NAME не заданы, проверка пропущена.")
            return

        try:
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
            resp = requests.get(url, timeout=timeout, headers={"Accept": "application/vnd.github+json"})

            if resp.status_code != 200:
                applog.debug(f"Проверка обновлений: не удалось получить последний релиз (статус {resp.status_code}).")
                return

            data = resp.json()
            tag = str(data.get("tag_name", "")).strip()
            html_url = str(data.get("html_url") or f"{REPO_URL}/releases")

            if tag and is_newer(tag, __version__):
                applog.info(f"Проверка обновлений: найдена новая версия {tag} (текущая {__version__}).")
                on_new_version(tag, html_url)
            else:
                applog.debug(f"Проверка обновлений: установлена актуальная версия ({__version__}, последний релиз: {tag or '?'}).")
        except Exception as e:
            # Отсутствие сети/GitHub, битый JSON и т.п. - ожидаемая, не критичная ситуация.
            applog.debug(f"Проверка обновлений не удалась (не критично): {e}")

    threading.Thread(target=worker, daemon=True).start()
