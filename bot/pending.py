import secrets


class PendingProposals:
    def __init__(self):
        self._items: dict[int, tuple[str, dict]] = {}

    def set(self, chat_id: int, item: dict) -> str:
        token = secrets.token_urlsafe(8)
        self._items[chat_id] = (token, item)
        return token

    def peek_token(self, chat_id: int) -> str | None:
        entry = self._items.get(chat_id)
        return entry[0] if entry is not None else None

    def pop(self, chat_id: int, token: str | None = None) -> dict | None:
        entry = self._items.get(chat_id)
        if entry is None:
            return None
        stored_token, item = entry
        if token is not None and token != stored_token:
            return None
        del self._items[chat_id]
        return item
