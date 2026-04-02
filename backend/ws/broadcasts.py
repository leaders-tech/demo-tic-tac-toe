"""Build and send websocket lobby and game snapshots to subscribed clients.

Edit this file when websocket snapshot payloads or subscriber fan-out changes.
Copy the helper style here when you add another websocket snapshot broadcaster.
"""

from __future__ import annotations

from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

from backend.db.games import get_game_snapshot, list_lobby_games


async def publish_lobby_snapshot(app: web.Application) -> None:
    hub = app["ws_hub"]
    connected_user_ids = hub.connected_user_ids()
    for ws in hub.lobby_subscribers():
        if ws.closed:
            continue
        user_id = hub.user_id_for_socket(ws)
        if user_id is None:
            continue
        async with app["games_lock"]:
            snapshot = await list_lobby_games(app["db"], user_id, connected_user_ids)
        try:
            await ws.send_json({"type": "lobby.snapshot", "lobby": snapshot})
        except ClientConnectionResetError:
            continue


async def publish_game_snapshot(app: web.Application, game_id: int) -> None:
    hub = app["ws_hub"]
    connected_user_ids = hub.connected_user_ids()
    for ws in hub.game_subscribers(game_id):
        if ws.closed:
            continue
        user_id = hub.user_id_for_socket(ws)
        if user_id is None:
            continue
        try:
            async with app["games_lock"]:
                snapshot = await get_game_snapshot(app["db"], game_id, user_id, connected_user_ids)
        except Exception:
            try:
                await ws.send_json({"type": "error", "code": "not_found", "message": "Game does not exist."})
            except ClientConnectionResetError:
                pass
            continue
        try:
            await ws.send_json({"type": "game.snapshot", "game": snapshot})
        except ClientConnectionResetError:
            continue
