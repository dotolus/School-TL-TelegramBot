class PendingProposals:
    def __init__(self):
        self._items: dict[int, dict] = {}

    def set(self, chat_id: int, item: dict) -> None:
        self._items[chat_id] = item

    def pop(self, chat_id: int) -> dict | None:
        return self._items.pop(chat_id, None)
