import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import cloudscraper

from src.core import applog
from src.core.network.engines.danbooru import DanbooruEngine
from src.core.network.engines.gelbooru import GelbooruEngine
from src.core.network.engines.paheal import PahealEngine

# Реестр движков по имени сайта. Чтобы добавить новый Booru-сайт, достаточно
# написать для него класс-движок (см. src.core.network.base_engine.BaseEngine)
# и добавить сюда одну строку - остальной код (Rule34API, UI) трогать не нужно.
SITE_ENGINES = {
    "rule34.xxx": GelbooruEngine,
    "allthefallen.moe": DanbooruEngine,
    "rule34.paheal.net": PahealEngine,
}

# Для check_servers_bulk: какой URL считать "пингом" для каждого сайта
# (бьём по API, а не по главной странице, чтобы обойти Cloudflare Anti-Bot).
_PING_URLS = {
    "rule34.xxx": "https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&limit=1",
    "allthefallen.moe": "https://allthefallen.moe/posts.json?limit=1",
}


class Rule34API:
    """Единая точка входа для работы с Booru-сайтами: не знает деталей
    конкретного сайта, а делегирует вызовы текущему движку (см.
    src.core.network.engines и реестр SITE_ENGINES ниже)."""

    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.engine = None

    def set_proxy(self, proxy_url: str) -> None:
        """Настраивает HTTP(S)-прокси для всех запросов к Booru-сайтам
        (например, для работы в корпоративной сети). Пустая строка отключает прокси."""
        proxy_url = (proxy_url or "").strip()
        if proxy_url:
            self.scraper.proxies = {"http": proxy_url, "https": proxy_url}
        else:
            self.scraper.proxies = {}

    def set_site(self, site_name):
        engine_cls = SITE_ENGINES.get(site_name, GelbooruEngine)
        self.engine = engine_cls(self.scraper)

    def fetch_autocomplete(self, query, api_key="", user_id=""):
        if not self.engine: return []
        return self.engine.fetch_autocomplete(query, api_key, user_id)

    def get_all_posts(self, query_string, api_key, user_id, stop_event, log_callback=None):
        if not self.engine: return []
        return self.engine.get_all_posts(query_string, api_key, user_id, stop_event, log_callback)

    def get_image_data(self, query_string, api_key, user_id, max_limit=0, exclude_tags=None):
        if not self.engine: return []
        return self.engine.get_image_data(query_string, api_key, user_id, max_limit, exclude_tags)

    def get_file_size(self, url):
        if not url: return 0
        if url.startswith("//"): url = "https:" + url
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = self.scraper.head(url, timeout=5, headers=headers)
            if resp.status_code == 200:
                return int(resp.headers.get("Content-Length", 0))
        except Exception as e:
            applog.debug(f"Не удалось получить размер файла {url}: {e}")
        return 0

    def check_tag_global_stats(self, tag_name, api_key, user_id, stop_event):
        if not self.engine: return tag_name, False, 0
        return self.engine.check_tag_global_stats(tag_name, api_key, user_id, stop_event)

    def download_file(self, url, filepath):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        for attempt in range(4):
            try:
                resp = self.scraper.get(url, stream=True, timeout=20, headers=headers)
                if resp.status_code == 200:
                    expected_size = int(resp.headers.get("Content-Length", 0))
                    downloaded_size = 0

                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(1024 * 8):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                    if expected_size > 0 and downloaded_size != expected_size:
                        time.sleep(1)
                        continue

                    return True
                elif resp.status_code in (429, 403):
                    time.sleep(1.5)
            except Exception as e:
                applog.debug(f"Попытка скачивания {url} не удалась: {e}")
                time.sleep(1)
        return False

    @staticmethod
    def check_servers_bulk(sites: list[str]) -> dict[str, bool]:
        results = {}

        def ping_site(site: str) -> tuple[str, bool]:
            url = _PING_URLS.get(site, f"https://{site}/")

            try:
                # Маскируемся под современный Chrome
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    return site, (response.getcode() == 200)
            except Exception:
                # Если сервер вернул HTTP-ошибку (например 403), но всё же ответил,
                # иногда это значит, что он доступен, но требует токен.
                # Для надежности считаем доступным только 200 OK.
                return site, False

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(ping_site, site) for site in sites]
            for future in as_completed(futures):
                site, is_ok = future.result()
                results[site] = is_ok

        return results
