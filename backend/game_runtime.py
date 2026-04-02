"""Run the background timeout loop that turns disconnect deadlines into forfeits.

Edit this file when the realtime game timeout worker or its polling rules change.
Copy the task pattern here when you add another small background loop.
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from backend.db.games import resolve_due_forfeits
from backend.ws.broadcasts import publish_game_snapshot, publish_lobby_snapshot


async def game_timeout_loop(app: web.Application) -> None:
    try:
        while True:
            await asyncio.sleep(1)
            async with app["games_lock"]:
                changed_game_ids = await resolve_due_forfeits(app["db"], app["ws_hub"].connected_user_ids())
            if not changed_game_ids:
                continue
            await publish_lobby_snapshot(app)
            for game_id in changed_game_ids:
                await publish_game_snapshot(app, game_id)
    except asyncio.CancelledError:
        return
