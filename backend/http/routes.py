"""Handle health, notes, and admin JSON endpoints outside the game feature.

Edit this file when shared non-game endpoints change.
Copy the route pattern here when you add another endpoint group backed by backend/db code.
"""

from __future__ import annotations

from aiohttp import web

from backend.auth.access import require_admin, require_user
from backend.db.notes import delete_note, list_notes, save_note
from backend.db.users import list_users
from backend.http.game_routes import setup_game_routes
from backend.http.json_api import AppError, ok, read_json
from backend.http.middleware import require_allowed_origin


async def health(request: web.Request) -> web.Response:
    return ok({"status": "ok"})


async def notes_list(request: web.Request) -> web.Response:
    user = require_user(request)
    notes = await list_notes(request.app["db"], user["id"])
    return ok({"notes": notes})


async def notes_save(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    note_id = payload.get("id")
    text = str(payload.get("text", "")).strip()
    if not text:
        raise AppError(400, "bad_request", "Note text is required.")
    if note_id is not None and not isinstance(note_id, int):
        raise AppError(400, "bad_request", "Note id must be an integer.")
    note = await save_note(request.app["db"], user["id"], text, note_id)
    await request.app["ws_hub"].send_to_user(user["id"], {"type": "notes.changed", "note": note})
    return ok({"note": note})


async def notes_delete(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    user = require_user(request)
    payload = await read_json(request)
    note_id = payload.get("id")
    if not isinstance(note_id, int):
        raise AppError(400, "bad_request", "Note id must be an integer.")
    deleted = await delete_note(request.app["db"], user["id"], note_id)
    if not deleted:
        raise AppError(404, "not_found", "Note does not exist.")
    await request.app["ws_hub"].send_to_user(user["id"], {"type": "notes.changed", "note_id": note_id})
    return ok({"deleted": True, "id": note_id})


async def admin_users_list(request: web.Request) -> web.Response:
    require_admin(request)
    users = await list_users(request.app["db"])
    return ok({"users": users})


def setup_api_routes(app: web.Application) -> None:
    app.router.add_get("/health", health)
    app.router.add_post("/notes/list", notes_list)
    app.router.add_post("/notes/save", notes_save)
    app.router.add_post("/notes/delete", notes_delete)
    app.router.add_post("/admin/users/list", admin_users_list)
    setup_game_routes(app)
