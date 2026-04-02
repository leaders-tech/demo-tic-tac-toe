"""Test websocket auth rules, subscriptions, and websocket error handling.

Edit this file when websocket auth, subscriptions, message parsing, or websocket replies change.
Copy a test pattern here when you add tests for another realtime feature.
"""

from __future__ import annotations

import pytest
from aiohttp import WSServerHandshakeError
from aiohttp import WSMsgType

from backend.tests.conftest import login


@pytest.mark.asyncio
async def test_websocket_requires_login(client) -> None:
    with pytest.raises(WSServerHandshakeError) as error:
        await client.ws_connect("/ws")
    assert error.value.status == 401


@pytest.mark.asyncio
async def test_websocket_rejects_wrong_origin(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)

    with pytest.raises(WSServerHandshakeError) as error:
        await client.ws_connect("/ws", headers={"Origin": "http://evil.example"})
    assert error.value.status == 403


@pytest.mark.asyncio
async def test_websocket_bad_message_returns_json_error(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)

    ws = await client.ws_connect("/ws")
    ready_message = await ws.receive_json()
    assert ready_message["type"] == "ws.ready"

    await ws.send_str("[]")
    error_message = await ws.receive_json()
    assert error_message == {"type": "error", "code": "bad_request", "message": "WebSocket message must be an object."}

    await ws.send_str('{"type":"ping"}')
    pong_message = await ws.receive_json()
    assert pong_message == {"type": "pong"}

    await ws.close()
    closed_message = await ws.receive()
    assert closed_message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING}


@pytest.mark.asyncio
async def test_websocket_lobby_and_game_subscriptions_send_snapshots(client, create_user, auth_headers) -> None:
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")
    await login(client, "alpha", "alpha", auth_headers)

    ws = await client.ws_connect("/ws")
    ready_message = await ws.receive_json()
    assert ready_message["type"] == "ws.ready"

    await ws.send_json({"type": "lobby.subscribe"})
    lobby_message = await ws.receive_json()
    assert lobby_message["type"] == "lobby.snapshot"
    assert lobby_message["lobby"]["waiting_games"] == []

    create_response = await client.post("/api/games/create", json={}, headers=auth_headers)
    game_id = (await create_response.json())["data"]["game_id"]
    lobby_update = await ws.receive_json()
    assert lobby_update["type"] == "lobby.snapshot"
    assert lobby_update["lobby"]["waiting_games"][0]["id"] == game_id

    await ws.send_json({"type": "game.subscribe", "game_id": game_id})
    game_message = await ws.receive_json()
    assert game_message["type"] == "game.snapshot"
    assert game_message["game"]["id"] == game_id
    assert game_message["game"]["status"] == "waiting"

    await ws.close()
