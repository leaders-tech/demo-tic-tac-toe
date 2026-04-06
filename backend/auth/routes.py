"""Handle login, refresh, logout, and current-user auth endpoints.

Edit this file when auth endpoint behavior, cookies, or refresh-session rules change.
Copy the route and helper pattern here when you add another small auth endpoint group.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any

from aiohttp import web

from backend.auth.access import current_user, require_user
from backend.auth.oidc import (
    OIDC_FLOW_COOKIE_NAME,
    OIDC_FLOW_TTL_SECONDS,
    build_authorize_url,
    build_login_redirect_url,
    create_oidc_flow_cookie,
    ensure_oidc_enabled,
    exchange_code_for_tokens,
    read_oidc_flow_cookie,
    validate_id_token_and_read_claims,
)
from backend.auth.passwords import hash_password
from backend.auth.passwords import verify_password
from backend.auth.tokens import build_access_token, create_refresh_token_pair, hash_refresh_token
from backend.config import Settings
from backend.db.games import list_related_game_ids_for_user, refresh_disconnect_deadlines, resolve_due_forfeits
from backend.db.oidc_identities import create_identity, get_identity_with_user, update_identity_login
from backend.db.refresh_sessions import create_session, delete_session, get_session, rotate_session
from backend.db.users import create_user_with_available_username, get_user_by_id, get_user_by_username, row_to_user, username_base_from_email
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


def clear_oidc_flow_cookie(response: web.StreamResponse, settings: Settings) -> None:
    response.del_cookie(OIDC_FLOW_COOKIE_NAME, path="/auth/oidc")


def _parse_refresh_cookie(raw_value: str | None) -> tuple[str, str] | None:
    if not raw_value or "." not in raw_value:
        return None
    session_id, raw_token = raw_value.split(".", 1)
    if not session_id or not raw_token:
        return None
    return session_id, raw_token


async def _replace_refresh_session(request: web.Request, user: dict[str, Any]) -> str:
    db = request.app["db"]
    settings: Settings = request.app["settings"]
    old_cookie = _parse_refresh_cookie(request.cookies.get(settings.refresh_cookie_name))
    if old_cookie is not None:
        await delete_session(db, old_cookie[0])

    session_id, raw_token = create_refresh_token_pair()
    expires_at = (datetime.now(tz=UTC) + timedelta(seconds=settings.refresh_ttl_seconds)).isoformat(timespec="seconds")
    await create_session(db, session_id, user["id"], hash_refresh_token(settings, raw_token), expires_at)
    return f"{session_id}.{raw_token}"


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

    user = row_to_user(user_row)
    refresh_cookie_value = await _replace_refresh_session(request, user)
    response = ok({"user": user})
    _set_auth_cookies(response, settings, user, refresh_cookie_value)
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


async def bootstrap(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    db = request.app["db"]
    user = current_user(request)
    if user is not None:
        user_row = await get_user_by_id(db, user["id"])
        if user_row is None:
            response = ok({"user": None})
            clear_auth_cookies(response, settings)
            return response
        return ok({"user": row_to_user(user_row)})

    parsed_cookie = _parse_refresh_cookie(request.cookies.get(settings.refresh_cookie_name))
    if parsed_cookie is None:
        return ok({"user": None})

    session_id, raw_token = parsed_cookie
    response = ok({"user": None})
    session = await get_session(db, session_id)
    if session is None:
        clear_auth_cookies(response, settings)
        return response
    if session["token_hash"] != hash_refresh_token(settings, raw_token):
        await delete_session(db, session_id)
        clear_auth_cookies(response, settings)
        return response
    if datetime.fromisoformat(session["expires_at"]) <= datetime.now(tz=UTC):
        await delete_session(db, session_id)
        clear_auth_cookies(response, settings)
        return response

    user_row = await get_user_by_id(db, session["user_id"])
    if user_row is None:
        await delete_session(db, session_id)
        clear_auth_cookies(response, settings)
        return response

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
    clear_oidc_flow_cookie(response, settings)
    return response


async def me(request: web.Request) -> web.Response:
    user = require_user(request)
    db = request.app["db"]
    user_row = await get_user_by_id(db, user["id"])
    if user_row is None:
        raise AppError(401, "not_authenticated", "User does not exist.")
    return ok({"user": row_to_user(user_row)})


async def auth_options(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    return ok(
        {
            "oidc_enabled": settings.oidc_enabled,
            "oidc_login_url": "/auth/oidc/start" if settings.oidc_enabled else None,
        }
    )


async def oidc_start(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    ensure_oidc_enabled(settings)
    flow_cookie_value, state, nonce = create_oidc_flow_cookie(settings)
    authorize_url = await build_authorize_url(request.app, state, nonce)
    response = web.HTTPFound(authorize_url)
    response.set_cookie(
        OIDC_FLOW_COOKIE_NAME,
        flow_cookie_value,
        max_age=OIDC_FLOW_TTL_SECONDS,
        httponly=True,
        samesite="Lax",
        secure=settings.secure_cookies,
        path="/auth/oidc",
    )
    return response


async def _resolve_local_user_for_oidc(
    request: web.Request,
    *,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> dict[str, Any]:
    db = request.app["db"]
    existing_identity = await get_identity_with_user(db, issuer, subject)
    if existing_identity is not None:
        await update_identity_login(db, issuer, subject, email, email_verified)
        return existing_identity["user"]

    password_hash = hash_password(token_urlsafe(32))
    user = await create_user_with_available_username(db, username_base_from_email(email), password_hash, False)
    await create_identity(db, user["id"], issuer, subject, email, email_verified)
    return user


async def oidc_callback(request: web.Request) -> web.Response:
    settings: Settings = request.app["settings"]
    ensure_oidc_enabled(settings)
    response_error = request.query.get("error")
    if response_error:
        response = web.HTTPFound(build_login_redirect_url(settings, success=False, error_code="oidc_login_failed"))
        clear_oidc_flow_cookie(response, settings)
        return response

    code = str(request.query.get("code", "")).strip()
    state = str(request.query.get("state", "")).strip()
    flow = read_oidc_flow_cookie(settings, request.cookies.get(OIDC_FLOW_COOKIE_NAME))
    if flow is None or not code or flow["state"] != state:
        response = web.HTTPFound(build_login_redirect_url(settings, success=False, error_code="oidc_state_invalid"))
        clear_oidc_flow_cookie(response, settings)
        return response

    try:
        tokens = await exchange_code_for_tokens(request.app, code)
        claims = await validate_id_token_and_read_claims(
            request.app,
            str(tokens["id_token"]),
            flow["nonce"],
            str(tokens.get("access_token", "")).strip() or None,
        )
        user = await _resolve_local_user_for_oidc(
            request,
            issuer=settings.oidc_issuer_url or "",
            subject=str(claims["sub"]),
            email=str(claims["email"]).strip() if claims.get("email") else None,
            email_verified=bool(claims.get("email_verified")),
        )
        refresh_cookie_value = await _replace_refresh_session(request, user)
    except AppError as error:
        response = web.HTTPFound(build_login_redirect_url(settings, success=False, error_code=error.code))
        clear_oidc_flow_cookie(response, settings)
        return response

    response = web.HTTPFound(build_login_redirect_url(settings, success=True))
    _set_auth_cookies(response, settings, user, refresh_cookie_value)
    clear_oidc_flow_cookie(response, settings)
    return response


def setup_auth_routes(app: web.Application) -> None:
    app.router.add_post("/auth/bootstrap", bootstrap)
    app.router.add_post("/auth/login", login)
    app.router.add_post("/auth/options", auth_options)
    app.router.add_post("/auth/refresh", refresh)
    app.router.add_post("/auth/logout", logout)
    app.router.add_post("/auth/me", me)
    app.router.add_get("/auth/oidc/start", oidc_start)
    app.router.add_get("/auth/oidc/callback", oidc_callback)
