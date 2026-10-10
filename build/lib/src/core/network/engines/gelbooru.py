import time
import xml.etree.ElementTree as ET

from src.core import applog
from src.core.network.base_engine import BaseEngine


class GelbooruEngine(BaseEngine):
    """rule34.xxx - JSON-based Gelbooru API."""

    def __init__(self, scraper):
        self.scraper = scraper
        self.base_url = "https://api.rule34.xxx/index.php"

    def fetch_autocomplete(self, query, api_key="", user_id=""):
        url = f"https://api.rule34.xxx/autocomplete.php?q={query}"
        try:
            resp = self.scraper.get(url, timeout=5)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    pass
        except Exception as e:
            applog.debug(f"Gelbooru autocomplete не удался: {e}")
        return []

    def get_all_posts(self, query_string, api_key, user_id, stop_event, log_callback):
        pos_query, neg_tags = self._parse_query(query_string)
        if not pos_query: return []

        posts, pid, limit = [], 0, 1000
        while True:
            if stop_event.is_set(): break
            params = {"page": "dapi", "s": "post", "q": "index", "json": "1", "tags": pos_query, "limit": limit,
                      "pid": pid}
            if api_key and user_id: params.update({"api_key": api_key, "user_id": user_id})

            resp = None
            for _ in range(4):
                if stop_event.is_set(): break
                try:
                    resp = self.scraper.get(self.base_url, params=params, timeout=15)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            try:
                data = resp.json()
            except ValueError:
                break

            # Если сервер вернул пустой массив - это 100% конец
            if not data or len(data) == 0: break

            valid_posts = [p for p in data if not self._is_bad(p, neg_tags)]
            posts.extend(valid_posts)

            if log_callback: log_callback(f"⬇️ Собрано постов: {len(posts)}")

            pid += 1
            time.sleep(0.5)
        return posts

    def check_tag_global_stats(self, tag_name, api_key, user_id, stop_event):
        if stop_event.is_set(): return tag_name, False, 0
        params = {"page": "dapi", "s": "tag", "q": "index", "name": tag_name}
        if api_key and user_id: params.update({"api_key": api_key, "user_id": user_id})
        for attempt in range(4):
            if stop_event.is_set(): break
            time.sleep(0.4)
            try:
                resp = self.scraper.get(self.base_url, params=params, timeout=10)
                if resp.status_code == 200:
                    try:
                        root = ET.fromstring(resp.text)
                        if len(root) > 0:
                            t_type = int(root[0].attrib.get("type", 0))
                            g_count = int(root[0].attrib.get("count", 0))
                            return tag_name, (t_type == 1), g_count
                    except:
                        pass
                    return tag_name, False, 0
                elif resp.status_code in (429, 403):
                    time.sleep(1.5);
                    continue
            except:
                time.sleep(1);
                continue
        return tag_name, False, 0

    def get_image_data(self, query_string, api_key, user_id, max_limit, exclude_tags=None):
        exclude_tags = exclude_tags or set()
        pos_query, neg_tags = self._parse_query(query_string)
        neg_tags.update(exclude_tags)
        if not pos_query: return []

        results = []
        pid = 0
        # Запрашиваем сразу по 1000, чтобы не долбить сервер кучей запросов
        page_limit = 1000 if max_limit == 0 or max_limit > 1000 else max_limit

        while True:
            params = {"page": "dapi", "s": "post", "q": "index", "json": "1", "tags": pos_query, "limit": page_limit,
                      "pid": pid}
            if api_key and user_id: params.update({"api_key": api_key, "user_id": user_id})

            resp = None
            for _ in range(4):
                try:
                    resp = self.scraper.get(self.base_url, params=params, timeout=15)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            try:
                data = resp.json()
            except ValueError:
                break

            if not data or len(data) == 0: break

            for p in data:
                if self._is_bad(p, neg_tags): continue
                url = p.get("file_url")
                tags = p.get("tags", "")
                md5 = str(p.get("hash", "")).lower()

                if url: results.append({"url": url, "size": 0, "tags": tags, "md5": md5})

            if max_limit > 0 and len(results) >= max_limit:
                return results[:max_limit]

            pid += 1
            time.sleep(0.2)
        return results
