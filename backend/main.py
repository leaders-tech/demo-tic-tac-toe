"""Build and run the backend aiohttp application.

Edit this file when startup, cleanup, or top-level route setup changes.
Do not copy this file. Change it when the whole backend app boot flow changes.
"""

from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web

from backend.auth.dev_oidc_provider import create_dev_oidc_provider_state, setup_dev_oidc_provider_routes
from backend.auth.routes import setup_auth_routes
from backend.config import Settings, load_settings, validate_settings
from backend.db.connection import open_db
from backend.db.migrations import run_migrations
from backend.db.seed import seed_dev_data
from backend.game_runtime import game_timeout_loop
from backend.http.middleware import cors_middleware, error_middleware
from backend.http.routes import setup_api_routes
from backend.ws.hub import WebSocketHub
from backend.ws.routes import setup_ws_routes


async def on_startup(app: web.Application) -> None:
    settings: Settings = app["settings"]
    run_migrations(settings.db_path, settings.migrations_path)
    app["db"] = await open_db(settings.db_path)
    app["http_session"] = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
    await seed_dev_data(app["db"], settings)
    app["game_timeout_task"] = asyncio.create_task(game_timeout_loop(app))


async def on_cleanup(app: web.Application) -> None:
    timeout_task = app.get("game_timeout_task")
    if timeout_task is not None:
        timeout_task.cancel()
        try:
            await timeout_task
        except asyncio.CancelledError:
            pass
    db = app.get("db")
    if db is not None:
        await db.close()
    http_session = app.get("http_session")
    if http_session is not None:
        await http_session.close()


def create_app(settings: Settings | None = None) -> web.Application:
    app = web.Application(middlewares=[error_middleware, cors_middleware])
    resolved_settings = settings or load_settings()
    validate_settings(resolved_settings)
    app["settings"] = resolved_settings
    app["ws_hub"] = WebSocketHub()
    app["games_lock"] = asyncio.Lock()
    app["oidc_cache"] = {}
    if resolved_settings.dev_oidc_test_mode:
        app["dev_oidc_provider"] = create_dev_oidc_provider_state(resolved_settings)
        setup_dev_oidc_provider_routes(app)

    setup_auth_routes(app)
    setup_api_routes(app)
    setup_ws_routes(app)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def run() -> None:
    settings = load_settings()
    web.run_app(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
