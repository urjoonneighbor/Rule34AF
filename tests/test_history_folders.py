from src.app.history import is_search_folder, visible_folder_items


def test_search_folders_are_recognised():
    assert is_search_folder("🔍 Поиск: elf")
    assert not is_search_folder("Избранное")
    assert not is_search_folder("⭐ История")


def test_rated_artists_leave_search_folders():
    items = [{"artist": "a"}, {"artist": "b"}, {"artist": "c"}]
    marks = {"a": "good", "c": "bad"}
    assert visible_folder_items("🔍 Поиск: elf", items, marks) == [{"artist": "b"}]


def test_custom_folders_keep_rated_artists():
    items = [{"artist": "a"}, {"artist": "b"}]
    assert visible_folder_items("Избранное", items, {"a": "good"}) == items
