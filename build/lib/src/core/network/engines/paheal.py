import time
import xml.etree.ElementTree as ET

from src.core import applog
from src.core.network.base_engine import BaseEngine


class PahealEngine(BaseEngine):
    """rule34.paheal.net - XML-based API, no artist/tag distinction."""

    def __init__(self, scraper):
        self.scraper = scraper
        self.base_url = "https://rule34.paheal.net"

    def fetch_autocomplete(self, query, api_key="", user_id=""):
        url = f"{self.base_url}/api/internal/autocomplete"
        try:
            resp = self.scraper.get(url, params={"s": query}, timeout=5)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    return []
                results = []
                if isinstance(data, dict):
                    for tag, info in data.items():
                        count = "?"
                        if isinstance(info, dict): count = info.get("count", "?")
                        results.append({"label": f"{tag} ({count})", "value": tag})
                return results
        except Exception as e:
            applog.debug(f"Paheal autocomplete не удался: {e}")
        return []

    def get_all_posts(self, query_string, api_key, user_id, stop_event, log_callback):
        pos_query, neg_tags = self._parse_query(query_string)
        if not pos_query: return []

        posts, pid, limit = [], 1, 1000
        while True:
            if stop_event.is_set(): break
            params = {"tags": pos_query, "limit": limit, "pid": pid}

            resp = None
            for _ in range(4):
                if stop_event.is_set(): break
                try:
                    resp = self.scraper.get(f"{self.base_url}/api/danbooru/find_posts/index.xml", params=params,
                                            timeout=15)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            root = ET.fromstring(resp.text)
            if len(root) == 0: break

            for post_xml in root:
                p_dict = {"tags": post_xml.attrib.get("tags", "")}
                if not self._is_bad(p_dict, neg_tags):
                    posts.append(p_dict)

            if log_callback: log_callback(f"⬇️ Собрано постов: {len(posts)}")

            pid += 1
            time.sleep(0.5)
        return posts

    def check_tag_global_stats(self, tag_name, api_key, user_id, stop_event):
        if stop_event.is_set(): return tag_name, False, 0
        time.sleep(0.05)
        return tag_name, True, 0

    def get_image_data(self, query_string, api_key, user_id, max_limit, exclude_tags=None):
        exclude_tags = exclude_tags or set()
        pos_query, neg_tags = self._parse_query(query_string)
        neg_tags.update(exclude_tags)
        if not pos_query: return []

        results = []
        pid = 1
        page_limit = 1000 if max_limit == 0 or max_limit > 1000 else max_limit
        while True:
            params = {"tags": pos_query, "limit": page_limit, "pid": pid}

            resp = None
            for _ in range(4):
                try:
                    resp = self.scraper.get(f"{self.base_url}/api/danbooru/find_posts/index.xml", params=params,
                                            timeout=15)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            root = ET.fromstring(resp.text)
            if len(root) == 0: break

            for post_xml in root:
                p_dict = {"tags": post_xml.attrib.get("tags", "")}
                if self._is_bad(p_dict, neg_tags): continue

                url = post_xml.attrib.get("file_url")
                tags = post_xml.attrib.get("tags", "")
                md5 = str(post_xml.attrib.get("md5", "")).lower()

                if url: results.append({"url": url, "size": 0, "tags": tags, "md5": md5})

            if max_limit > 0 and len(results) >= max_limit:
                return results[:max_limit]

            pid += 1
            time.sleep(0.2)
        return results
