"""In-session memory store (ephemeral; cleared when the process exits)."""


class SessionMemory:
    def __init__(self):
        self._items = []

    def add(self, item: str) -> None:
        self._items.append(item)

    def list(self):
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self):
        return iter(self._items)
