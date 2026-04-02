"""Handle authenticated JSON endpoints for lobby, game state, moves, and rematches.

Edit this file when tic-tac-toe browser actions or game API behavior changes.
Copy this file as a starting point when you add another feature-specific route group.
"""

from __future__ import annotations

from aiohttp import web

from backend.auth.access import require_user
from backend.db.games import (
    apply_move,
    cancel_waiting_game,
    create_waiting_game,
    get_game_snapshot,
    join_waiting_game,
    list_lobby_games,
    record_rematch_ready,
    refresh_all_disconnect_deadlines,
    resolve_due_forfeits,
)
from backend.http.json_api import AppError, ok, read_json
from backend.http.middleware import require_allowed_origin
from backend.ws.broadcasts import publish_game_snapshot, publish_lobby_snapshot


def _require_game_id(payload: dict[str, object]) -> int:
    game_id = payload.get("game_id")
    if not isinstance(game_id, int):
        raise AppError(400, "bad_request", "Game id must be an integer.")
    return game_id


async def lobby(request: web.Request) -> web.Response:
    user = require_user(request)
    async with request.app["games_lock"]:
        await resolve_due_forfeits(request.app["db"], request.app["ws_hub"].connected_user_ids())
        await refresh_all_disconnect_deadlines(request.app["db"], request.app["ws_hub"].connected_user_ids())
        snapshot = await list_lobby_games(request.app["db"], user["id"], request.app["ws_hub"].connected_user_ids())
    return ok(snapshot)


async def create_game(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    await read_json(request)
    async with request.app["games_lock"]:
        game_id = await create_waiting_game(request.app["db"], user["id"])
    await publish_lobby_snapshot(request.app)
    await publish_game_snapshot(request.app, game_id)
    return ok({"game_id": game_id}, status=201)


async def join_game(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    async with request.app["games_lock"]:
        game_id = await join_waiting_game(request.app["db"], _require_game_id(payload), user["id"])
    await publish_lobby_snapshot(request.app)
    await publish_game_snapshot(request.app, game_id)
    return ok({"game_id": game_id})


async def cancel_game(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    game_id = _require_game_id(payload)
    async with request.app["games_lock"]:
        await cancel_waiting_game(request.app["db"], game_id, user["id"])
    await publish_lobby_snapshot(request.app)
    return ok({"cancelled": True, "game_id": game_id})


async def game_state(request: web.Request) -> web.Response:
    user = require_user(request)
    payload = await read_json(request)
    async with request.app["games_lock"]:
        await resolve_due_forfeits(request.app["db"], request.app["ws_hub"].connected_user_ids())
        await refresh_all_disconnect_deadlines(request.app["db"], request.app["ws_hub"].connected_user_ids())
        snapshot = await get_game_snapshot(request.app["db"], _require_game_id(payload), user["id"], request.app["ws_hub"].connected_user_ids())
    return ok(snapshot)


async def move(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    game_id = _require_game_id(payload)
    row_index = payload.get("row_index")
    col_index = payload.get("col_index")
    size = payload.get("size")
    if not isinstance(row_index, int) or not isinstance(col_index, int):
        raise AppError(400, "bad_request", "Board position must use integer row and column values.")
    if not isinstance(size, str):
        raise AppError(400, "bad_request", "Piece size is required.")

    async with request.app["games_lock"]:
        await resolve_due_forfeits(request.app["db"], request.app["ws_hub"].connected_user_ids())
        await apply_move(request.app["db"], game_id, user["id"], row_index, col_index, size)
    await publish_lobby_snapshot(request.app)
    await publish_game_snapshot(request.app, game_id)
    return ok({"accepted": True, "game_id": game_id})


async def rematch(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    game_id = _require_game_id(payload)
    async with request.app["games_lock"]:
        next_game_id = await record_rematch_ready(request.app["db"], game_id, user["id"])
    await publish_lobby_snapshot(request.app)
    await publish_game_snapshot(request.app, game_id)
    if next_game_id is not None:
        await publish_game_snapshot(request.app, next_game_id)
    return ok({"game_id": game_id, "next_game_id": next_game_id})


def setup_game_routes(app: web.Application) -> None:
    app.router.add_post("/api/games/lobby", lobby)
    app.router.add_post("/api/games/create", create_game)
    app.router.add_post("/api/games/join", join_game)
    app.router.add_post("/api/games/cancel", cancel_game)
    app.router.add_post("/api/games/state", game_state)
    app.router.add_post("/api/games/move", move)
    app.router.add_post("/api/games/rematch", rematch)
