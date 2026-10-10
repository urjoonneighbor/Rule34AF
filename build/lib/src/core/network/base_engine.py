"""Общая логика фильтрации постов, одинаковая для всех Booru-движков."""


class BaseEngine:
    @staticmethod
    def _parse_query(query: str) -> tuple[str, set[str]]:
        """Отделяем плюсовые теги от минусовых, чтобы не злить сервер лимитами"""
        pos = []
        neg = set()
        for w in query.split():
            if w.startswith('-') and len(w) > 1:
                neg.add(w[1:].lower())
            else:
                pos.append(w)
        return " ".join(pos), neg

    @staticmethod
    def _is_bad(post: dict, neg_tags: set) -> bool:
        """Локальная фильтрация зараженных постов"""
        if not neg_tags: return False

        rating = str(post.get("rating", "")).lower()
        if (rating == "questionable" or rating == "q") and "rating:questionable" in neg_tags: return True
        if (rating == "explicit" or rating == "e") and "rating:explicit" in neg_tags: return True
        if (rating == "safe" or rating == "s") and "rating:safe" in neg_tags: return True

        tags = str(post.get("tags", "") or post.get("tag_string", ""))
        if not tags and "tag" in post:
            tags = str(post.get("tag", ""))

        post_tags_set = set(tags.lower().split())
        if neg_tags & post_tags_set:
            return True
        return False
