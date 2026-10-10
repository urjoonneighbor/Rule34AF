import hashlib
import re
import time

from src.core import applog
from src.core.network.base_engine import BaseEngine


class DanbooruEngine(BaseEngine):
    """allthefallen.moe - Danbooru-style API, protected by a PoW challenge."""

    def __init__(self, scraper):
        self.scraper = scraper
        self.base_url = "https://booru.allthefallen.moe"

    def _solve_pow_challenge(self, html):
        try:
            cid = re.search(r'const challenge_id = "([^"]+)";', html).group(1)
            cgen = re.search(r'const challenge_generated = "([^"]+)";', html).group(1)
            cexp = re.search(r'const challenge_cookie_expires = "([^"]+)";', html).group(1)
            seed = re.search(r'const powSeed = "([^"]+)";', html).group(1)
            prefix_len = int(re.search(r'const powPrefix = "0".repeat\((\d+)\);', html).group(1))
            prefix = "0" * prefix_len

            nonce = 0
            while True:
                candidate = f"{seed}:{nonce}"
                h = hashlib.sha1(candidate.encode('utf-8')).hexdigest()
                if h.startswith(prefix):
                    break
                nonce += 1

            payload = {
                "challenge_id": cid,
                "challenge_generated": cgen,
                "challenge_cookie_expires": cexp,
                "pow_nonce": str(nonce),
                "pow_hash": h
            }
            headers = {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest",
                       "X-Verification-Challenge": "1"}

            post_to_m = re.search(r'const post_to = "([^"]+)";', html)
            post_to = post_to_m.group(1) if post_to_m else self.base_url
            if not post_to.startswith("http"): post_to = "https://" + post_to

            time.sleep(5.1)
            resp = self.scraper.post(post_to, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            applog.debug(f"Не удалось решить PoW-challenge Danbooru: {e}")
            return False

    def _safe_get(self, url, params=None, headers=None, timeout=10):
        resp = self.scraper.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200 and "challenge-checkbox" in resp.text:
            if self._solve_pow_challenge(resp.text):
                resp = self.scraper.get(url, params=params, headers=headers, timeout=timeout)
        return resp

    def fetch_autocomplete(self, query, api_key="", user_id=""):
        url = f"{self.base_url}/autocomplete"
        params = {"search[query]": query, "search[type]": "tag_query", "version": "1", "limit": 20}
        if api_key and user_id: params.update({"login": user_id, "api_key": api_key})
        headers = {"X-Requested-With": "XMLHttpRequest"}
        try:
            resp = self._safe_get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                html_content = resp.text
                results = []
                blocks = re.finditer(r'<li[^>]*data-autocomplete-value="([^"]+)"[^>]*>(.*?)</li>', html_content,
                                     re.DOTALL | re.IGNORECASE)
                for m in blocks:
                    tag = m.group(1)
                    inner_html = m.group(2)
                    count_m = re.search(r'<span class="post-count">([^<]+)</span>', inner_html)
                    count = count_m.group(1).strip() if count_m else "?"
                    results.append({"label": f"{tag} ({count})", "value": tag})
                return results
        except Exception as e:
            applog.debug(f"Danbooru autocomplete не удался: {e}")
        return []

    def get_all_posts(self, query_string, api_key, user_id, stop_event, log_callback):
        pos_query, neg_tags = self._parse_query(query_string)
        if not pos_query: return []

        posts, page, limit = [], 1, 200
        headers = {"X-Requested-With": "XMLHttpRequest"}
        while True:
            if stop_event.is_set(): break
            params = {"tags": pos_query, "limit": limit, "page": page}
            if api_key and user_id: params.update({"login": user_id, "api_key": api_key})

            resp = None
            for _ in range(4):
                if stop_event.is_set(): break
                try:
                    resp = self._safe_get(f"{self.base_url}/posts.json", params=params, headers=headers, timeout=20)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            try:
                data = resp.json()
            except ValueError:
                break

            if not data or not isinstance(data, list) or len(data) == 0: break

            valid_posts = []
            for p in data:
                if self._is_bad(p, neg_tags): continue
                p["tags"] = p.get("tag_string", "")
                valid_posts.append(p)

            posts.extend(valid_posts)
            if log_callback: log_callback(f"⬇️ Собрано постов: {len(posts)}")

            page += 1
            time.sleep(0.5)
        return posts

    def check_tag_global_stats(self, tag_name, api_key, user_id, stop_event):
        if stop_event.is_set(): return tag_name, False, 0
        params = {"search[name]": tag_name}
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if api_key and user_id: params.update({"login": user_id, "api_key": api_key})
        for attempt in range(4):
            if stop_event.is_set(): break
            time.sleep(0.4)
            try:
                resp = self._safe_get(f"{self.base_url}/tags.json", params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        continue
                    if data and isinstance(data, list) and len(data) > 0:
                        t_type = int(data[0].get("category", 0))
                        g_count = int(data[0].get("post_count", 0))
                        return tag_name, (t_type == 1), g_count
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
        page = 1
        page_limit = 200 if max_limit == 0 or max_limit > 200 else max_limit
        headers = {"X-Requested-With": "XMLHttpRequest"}
        while True:
            params = {"tags": pos_query, "limit": page_limit, "page": page}
            if api_key and user_id: params.update({"login": user_id, "api_key": api_key})

            resp = None
            for _ in range(4):
                try:
                    resp = self._safe_get(f"{self.base_url}/posts.json", params=params, headers=headers, timeout=20)
                    if resp.status_code == 200: break
                    time.sleep(1.5)
                except:
                    time.sleep(1)

            if not resp or resp.status_code != 200: break

            try:
                data = resp.json()
            except ValueError:
                break

            if not data or not isinstance(data, list) or len(data) == 0: break

            for p in data:
                if self._is_bad(p, neg_tags): continue
                url = p.get("file_url") or p.get("large_file_url")
                size = p.get("file_size", 0)
                tags = p.get("tag_string", "")
                md5 = str(p.get("md5", "")).lower()

                if url: results.append({"url": url, "size": size, "tags": tags, "md5": md5})

            if max_limit > 0 and len(results) >= max_limit:
                return results[:max_limit]

            page += 1
            time.sleep(0.2)
        return results
