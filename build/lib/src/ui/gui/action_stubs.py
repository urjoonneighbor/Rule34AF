class ActionStubsMixin:
    """Контракт бизнес-методов, которые реализует Rule34ArtistFinderApp
    (см. src/app/): пустые методы-заглушки (Template Method), без которых
    AppGUI можно было бы создать напрямую и сразу словить AttributeError
    при первом клике на кнопку."""

    def save_settings(self):
        pass

    def start_search(self):
        pass

    def stop_search(self):
        pass

    def clear_all(self):
        pass

    def on_site_change(self, _event=None, force_update_labels=False):
        pass

    def schedule_autocomplete(self, event, tag_type):
        pass

    def add_tag(self, tag_type, from_enter=False):
        pass

    def on_ai_provider_change(self, _event=None):
        pass

    def run_ai_analysis(self):
        pass

    def show_ai_help(self):
        pass

    def show_api_help(self):
        pass

    def download_by_query(self):
        pass

    def apply_history_filter(self):
        pass

    def on_hist_search_key(self, event):
        pass

    def on_history_double_click(self, event):
        pass

    def show_history_context_menu(self, event):
        pass

    def run_history_item(self):
        pass

    def copy_history_item(self):
        pass

    def delete_history_item(self):
        pass

    def clear_history_list(self):
        pass

    def export_history(self):
        pass

    def download_from_history(self):
        pass

    def apply_network_settings(self):
        pass

