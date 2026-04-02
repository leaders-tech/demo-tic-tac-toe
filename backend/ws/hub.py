"""Track websocket connections, subscriptions, and user-to-socket lookups.

Edit this file when websocket connection storage, subscriptions, or fan-out behavior changes.
Copy the helper style here when you add another small websocket utility.
"""

from __future__ import annotations

from collections import defaultdict
from weakref import WeakKeyDictionary, WeakSet

from aiohttp import web


class WebSocketHub:
    def __init__(self) -> None:
        self._connections: dict[int, WeakSet[web.WebSocketResponse]] = defaultdict(WeakSet)
        self._socket_users: WeakKeyDictionary[web.WebSocketResponse, int] = WeakKeyDictionary()
        self._lobby_subscribers: WeakSet[web.WebSocketResponse] = WeakSet()
        self._game_subscribers: dict[int, WeakSet[web.WebSocketResponse]] = defaultdict(WeakSet)
        self._game_by_socket: WeakKeyDictionary[web.WebSocketResponse, int] = WeakKeyDictionary()

    def add(self, user_id: int, ws: web.WebSocketResponse) -> None:
        self._connections[user_id].add(ws)
        self._socket_users[ws] = user_id

    def remove(self, user_id: int, ws: web.WebSocketResponse) -> None:
        self.clear_subscriptions(ws)
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(ws)
        if len(sockets) == 0:
            self._connections.pop(user_id, None)
        self._socket_users.pop(ws, None)

    async def send_to_user(self, user_id: int, message: dict[str, object]) -> None:
        sockets = list(self._connections.get(user_id, ()))
        for ws in sockets:
            if ws.closed:
                self.remove(user_id, ws)
                continue
            await ws.send_json(message)

    def count_for_user(self, user_id: int) -> int:
        return len(self._connections.get(user_id, ()))

    def connected_user_ids(self) -> set[int]:
        return {user_id for user_id, sockets in self._connections.items() if len(sockets) > 0}

    def user_id_for_socket(self, ws: web.WebSocketResponse) -> int | None:
        return self._socket_users.get(ws)

    def subscribe_lobby(self, ws: web.WebSocketResponse) -> None:
        self._lobby_subscribers.add(ws)

    def lobby_subscribers(self) -> list[web.WebSocketResponse]:
        return list(self._lobby_subscribers)

    def subscribe_game(self, ws: web.WebSocketResponse, game_id: int) -> None:
        previous_game_id = self._game_by_socket.get(ws)
        if previous_game_id is not None:
            subscribers = self._game_subscribers.get(previous_game_id)
            if subscribers is not None:
                subscribers.discard(ws)
                if len(subscribers) == 0:
                    self._game_subscribers.pop(previous_game_id, None)
        self._game_subscribers[game_id].add(ws)
        self._game_by_socket[ws] = game_id

    def game_subscribers(self, game_id: int) -> list[web.WebSocketResponse]:
        return list(self._game_subscribers.get(game_id, ()))

    def clear_subscriptions(self, ws: web.WebSocketResponse) -> None:
        self._lobby_subscribers.discard(ws)
        previous_game_id = self._game_by_socket.pop(ws, None)
        if previous_game_id is None:
            return
        subscribers = self._game_subscribers.get(previous_game_id)
        if subscribers is None:
            return
        subscribers.discard(ws)
        if len(subscribers) == 0:
            self._game_subscribers.pop(previous_game_id, None)
