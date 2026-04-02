"""Handle the authenticated websocket endpoint, subscriptions, and JSON messages.

Edit this file when websocket auth, subscriptions, message types, or connection flow changes.
Copy the route pattern here when you add another websocket endpoint.
"""

from __future__ import annotations

import json

from aiohttp import WSMsgType, web
from aiohttp.client_exceptions import ClientConnectionResetError

from backend.auth.access import require_user
from backend.db.games import get_game_snapshot, list_lobby_games, list_related_game_ids_for_user, refresh_disconnect_deadlines, resolve_due_forfeits
from backend.http.middleware import require_allowed_origin
from backend.ws.broadcasts import publish_game_snapshot, publish_lobby_snapshot


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    require_allowed_origin(request)
    user = require_user(request)
    ws = web.WebSocketResponse(heartbeat=5.0)
    await ws.prepare(request)

    hub = request.app["ws_hub"]
    hub.add(user["id"], ws)
    async with request.app["games_lock"]:
        await resolve_due_forfeits(request.app["db"], hub.connected_user_ids())
        related_game_ids = await refresh_disconnect_deadlines(request.app["db"], hub.connected_user_ids(), user["id"])
    try:
        await ws.send_json({"type": "ws.ready", "user_id": user["id"], "connections": hub.count_for_user(user["id"])})
    except ClientConnectionResetError:
        hub.remove(user["id"], ws)
        return ws
    await publish_lobby_snapshot(request.app)
    for game_id in sorted(set(related_game_ids)):
        await publish_game_snapshot(request.app, game_id)

    try:
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(message.data)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "code": "bad_request", "message": "WebSocket message must be valid JSON."})
                continue
            if not isinstance(data, dict):
                await ws.send_json({"type": "error", "code": "bad_request", "message": "WebSocket message must be an object."})
                continue
            message_type = data.get("type")
            if message_type == "ping":
                try:
                    await ws.send_json({"type": "pong"})
                except ClientConnectionResetError:
                    break
            elif message_type == "lobby.subscribe":
                hub.subscribe_lobby(ws)
                async with request.app["games_lock"]:
                    snapshot = await list_lobby_games(request.app["db"], user["id"], hub.connected_user_ids())
                try:
                    await ws.send_json({"type": "lobby.snapshot", "lobby": snapshot})
                except ClientConnectionResetError:
                    break
            elif message_type == "game.subscribe":
                game_id = data.get("game_id")
                if not isinstance(game_id, int):
                    try:
                        await ws.send_json({"type": "error", "code": "bad_request", "message": "Game id must be an integer."})
                    except ClientConnectionResetError:
                        break
                    continue
                hub.subscribe_game(ws, game_id)
                try:
                    async with request.app["games_lock"]:
                        snapshot = await get_game_snapshot(request.app["db"], game_id, user["id"], hub.connected_user_ids())
                except Exception:
                    try:
                        await ws.send_json({"type": "error", "code": "not_found", "message": "Game does not exist."})
                    except ClientConnectionResetError:
                        break
                    continue
                try:
                    await ws.send_json({"type": "game.snapshot", "game": snapshot})
                except ClientConnectionResetError:
                    break
    finally:
        hub.remove(user["id"], ws)
        async with request.app["games_lock"]:
            await resolve_due_forfeits(request.app["db"], hub.connected_user_ids())
            related_game_ids = await list_related_game_ids_for_user(request.app["db"], user["id"])
            updated_game_ids = await refresh_disconnect_deadlines(request.app["db"], hub.connected_user_ids(), user["id"])
        await publish_lobby_snapshot(request.app)
        for game_id in sorted(set(related_game_ids + updated_game_ids)):
            await publish_game_snapshot(request.app, game_id)

    return ws


def setup_ws_routes(app: web.Application) -> None:
    app.router.add_get("/ws", websocket_handler)
