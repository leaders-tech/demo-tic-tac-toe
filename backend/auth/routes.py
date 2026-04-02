"""Handle login, refresh, logout, and current-user auth endpoints.

Edit this file when auth endpoint behavior, cookies, or refresh-session rules change.
Copy the route and helper pattern here when you add another small auth endpoint group.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import web

from backend.auth.access import require_user
from backend.auth.passwords import verify_password
from backend.auth.tokens import build_access_token, create_refresh_token_pair, hash_refresh_token
from backend.config import Settings
from backend.db.games import list_related_game_ids_for_user, refresh_disconnect_deadlines, resolve_due_forfeits
from backend.db.refresh_sessions import create_session, delete_session, get_session, rotate_session
from backend.db.users import get_user_by_id, get_user_by_username, row_to_user
from backend.http.json_api import AppError, ok, read_json
from backend.http.middleware import require_allowed_origin
from backend.ws.broadcasts import publish_game_snapshot, publish_lobby_snapshot


def _set_auth_cookies(response: web.StreamResponse, settings: Settings, user: dict[str, Any], refresh_cookie_value: str) -> None:
    access_token = build_access_token(settings, user)
    response.set_cookie(
        settings.access_cookie_name,
        access_token,
        max_age=settings.access_ttl_seconds,
        httponly=True,
        samesite="Lax",
        secure=settings.secure_cookies,
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_cookie_value,
        max_age=settings.refresh_ttl_seconds,
        httponly=True,
        samesite="Lax",
        secure=settings.secure_cookies,
        path="/auth",
    )


def clear_auth_cookies(response: web.StreamResponse, settings: Settings) -> None:
    response.del_cookie(settings.access_cookie_name, path="/")
    response.del_cookie(settings.refresh_cookie_name, path="/auth")


def _parse_refresh_cookie(raw_value: str | None) -> tuple[str, str] | None:
    if not raw_value or "." not in raw_value:
        return None
    session_id, raw_token = raw_value.split(".", 1)
    if not session_id or not raw_token:
        return None
    return session_id, raw_token


async def login(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    payload = await read_json(request)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        raise AppError(400, "bad_request", "Username and password are required.")

    db = request.app["db"]
    settings: Settings = request.app["settings"]
    user_row = await get_user_by_username(db, username)
    if user_row is None or not verify_password(user_row["password_hash"], password):
        raise AppError(401, "invalid_credentials", "Wrong username or password.")

    old_cookie = _parse_refresh_cookie(request.cookies.get(settings.refresh_cookie_name))
    if old_cookie is not None:
        await delete_session(db, old_cookie[0])

    session_id, raw_token = create_refresh_token_pair()
    expires_at = (datetime.now(tz=UTC) + timedelta(seconds=settings.refresh_ttl_seconds)).isoformat(timespec="seconds")
    await create_session(db, session_id, user_row["id"], hash_refresh_token(settings, raw_token), expires_at)

    user = row_to_user(user_row)
    response = ok({"user": user})
    _set_auth_cookies(response, settings, user, f"{session_id}.{raw_token}")
    return response


async def refresh(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    settings: Settings = request.app["settings"]
    parsed_cookie = _parse_refresh_cookie(request.cookies.get(settings.refresh_cookie_name))
    if parsed_cookie is None:
        raise AppError(401, "not_authenticated", "Refresh session is missing.")

    session_id, raw_token = parsed_cookie
    db = request.app["db"]
    session = await get_session(db, session_id)
    if session is None:
        raise AppError(401, "not_authenticated", "Refresh session is invalid.")
    if session["token_hash"] != hash_refresh_token(settings, raw_token):
        await delete_session(db, session_id)
        raise AppError(401, "not_authenticated", "Refresh session is invalid.")

    if datetime.fromisoformat(session["expires_at"]) <= datetime.now(tz=UTC):
        await delete_session(db, session_id)
        raise AppError(401, "not_authenticated", "Refresh session expired.")

    user_row = await get_user_by_id(db, session["user_id"])
    if user_row is None:
        await delete_session(db, session_id)
        raise AppError(401, "not_authenticated", "User does not exist.")

    _, new_raw_token = create_refresh_token_pair()
    expires_at = (datetime.now(tz=UTC) + timedelta(seconds=settings.refresh_ttl_seconds)).isoformat(timespec="seconds")
    await rotate_session(db, session_id, hash_refresh_token(settings, new_raw_token), expires_at)

    user = row_to_user(user_row)
    response = ok({"user": user})
    _set_auth_cookies(response, settings, user, f"{session_id}.{new_raw_token}")
    return response


async def logout(request: web.Request) -> web.Response:
    require_allowed_origin(request)
    settings: Settings = request.app["settings"]
    user = None
    try:
        user = require_user(request)
    except AppError:
        user = None
    parsed_cookie = _parse_refresh_cookie(request.cookies.get(settings.refresh_cookie_name))
    if parsed_cookie is not None:
        await delete_session(request.app["db"], parsed_cookie[0])

    if user is not None:
        connected_user_ids = request.app["ws_hub"].connected_user_ids() - {user["id"]}
        async with request.app["games_lock"]:
            await resolve_due_forfeits(request.app["db"], connected_user_ids)
            related_game_ids = await list_related_game_ids_for_user(request.app["db"], user["id"])
            updated_game_ids = await refresh_disconnect_deadlines(request.app["db"], connected_user_ids, user["id"])
        await publish_lobby_snapshot(request.app)
        for game_id in sorted(set(related_game_ids + updated_game_ids)):
            await publish_game_snapshot(request.app, game_id)

    response = ok({"logged_out": True})
    clear_auth_cookies(response, settings)
    return response


async def me(request: web.Request) -> web.Response:
    user = require_user(request)
    db = request.app["db"]
    user_row = await get_user_by_id(db, user["id"])
    if user_row is None:
        raise AppError(401, "not_authenticated", "User does not exist.")
    return ok({"user": row_to_user(user_row)})


def setup_auth_routes(app: web.Application) -> None:
    app.router.add_post("/auth/login", login)
    app.router.add_post("/auth/refresh", refresh)
    app.router.add_post("/auth/logout", logout)
    app.router.add_post("/auth/me", me)
