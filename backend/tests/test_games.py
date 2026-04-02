"""Test game routes, game rules, disconnect timeouts, and rematch creation.

Edit this file when lobby endpoints, move rules, disconnect behavior, or rematch logic changes.
Copy a test pattern here when you add another backend test for the game feature.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from backend.db.connection import parse_utc_text, utc_now_text
from backend.db.games import record_rematch_ready, refresh_disconnect_deadlines, resolve_due_forfeits
from backend.tests.conftest import login


async def _user_id(db, username: str) -> int:
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = await cursor.fetchone()
    assert row is not None
    return row["id"]


async def _insert_game(
    db,
    *,
    status: str,
    x_user_id: int,
    o_user_id: int | None,
    starter_symbol: str = "X",
    turn_symbol: str | None = "X",
    winner_symbol: str | None = None,
    finish_reason: str | None = None,
    disconnect_deadline_at: str | None = None,
) -> int:
    now = utc_now_text()
    cursor = await db.execute(
        """
        INSERT INTO games (
            status,
            x_user_id,
            o_user_id,
            starter_symbol,
            turn_symbol,
            winner_symbol,
            finish_reason,
            forfeit_user_id,
            disconnect_deadline_at,
            rematch_x_ready,
            rematch_o_ready,
            rematch_of_game_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        (
            status,
            x_user_id,
            o_user_id,
            starter_symbol,
            turn_symbol,
            winner_symbol,
            finish_reason,
            None,
            disconnect_deadline_at,
            0,
            0,
            None,
            now,
            now,
        ),
    )
    row = await cursor.fetchone()
    await db.commit()
    assert row is not None
    return row["id"]


async def _insert_move(db, *, game_id: int, turn_number: int, symbol: str, user_id: int, size: str, row_index: int, col_index: int) -> None:
    await db.execute(
        """
        INSERT INTO game_moves (game_id, turn_number, symbol, user_id, size, row_index, col_index, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (game_id, turn_number, symbol, user_id, size, row_index, col_index, utc_now_text()),
    )
    await db.commit()


@pytest.mark.asyncio
async def test_game_create_join_cancel_and_lobby(client, create_user, auth_headers) -> None:
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")

    await login(client, "alpha", "alpha", auth_headers)
    create_response = await client.post("/api/games/create", json={}, headers=auth_headers)
    assert create_response.status == 201
    created_game_id = (await create_response.json())["data"]["game_id"]

    lobby_response = await client.post("/api/games/lobby", json={})
    lobby_payload = (await lobby_response.json())["data"]
    assert lobby_payload["waiting_games"][0]["id"] == created_game_id
    assert lobby_payload["waiting_games"][0]["can_cancel"] is True

    second_create = await client.post("/api/games/create", json={}, headers=auth_headers)
    assert second_create.status == 409

    await login(client, "beta", "beta", auth_headers)
    join_response = await client.post("/api/games/join", json={"game_id": created_game_id}, headers=auth_headers)
    assert join_response.status == 200

    game_response = await client.post("/api/games/state", json={"game_id": created_game_id})
    game_payload = (await game_response.json())["data"]
    assert game_payload["status"] == "active"
    assert game_payload["viewer_role"] == "O"
    assert game_payload["players"]["O"]["username"] == "beta"

    await login(client, "alpha", "alpha", auth_headers)
    create_second = await client.post("/api/games/create", json={}, headers=auth_headers)
    second_game_id = (await create_second.json())["data"]["game_id"]
    cancel_response = await client.post("/api/games/cancel", json={"game_id": second_game_id}, headers=auth_headers)
    assert cancel_response.status == 200

    lobby_after_cancel = await client.post("/api/games/lobby", json={})
    lobby_after_cancel_payload = (await lobby_after_cancel.json())["data"]
    assert [game["id"] for game in lobby_after_cancel_payload["waiting_games"]] == []


@pytest.mark.asyncio
async def test_game_visible_top_pieces_and_move_rejections(client, create_user, auth_headers) -> None:
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")

    await login(client, "alpha", "alpha", auth_headers)
    create_response = await client.post("/api/games/create", json={}, headers=auth_headers)
    game_id = (await create_response.json())["data"]["game_id"]
    await login(client, "beta", "beta", auth_headers)
    await client.post("/api/games/join", json={"game_id": game_id}, headers=auth_headers)

    await login(client, "alpha", "alpha", auth_headers)
    assert (await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 0, "size": "small"}, headers=auth_headers)).status == 200
    await login(client, "beta", "beta", auth_headers)
    assert (await client.post("/api/games/move", json={"game_id": game_id, "row_index": 1, "col_index": 0, "size": "small"}, headers=auth_headers)).status == 200
    await login(client, "alpha", "alpha", auth_headers)
    assert (await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 1, "size": "small"}, headers=auth_headers)).status == 200
    await login(client, "beta", "beta", auth_headers)
    assert (await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 0, "size": "medium"}, headers=auth_headers)).status == 200

    await login(client, "alpha", "alpha", auth_headers)
    smaller_cover = await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 0, "size": "small"}, headers=auth_headers)
    assert smaller_cover.status == 409
    assert "larger piece" in (await smaller_cover.json())["error"]["message"]

    valid_move = await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 2, "size": "small"}, headers=auth_headers)
    assert valid_move.status == 200

    state_response = await client.post("/api/games/state", json={"game_id": game_id})
    state_payload = (await state_response.json())["data"]
    assert state_payload["status"] == "active"
    assert state_payload["winner_symbol"] is None
    assert state_payload["board"][0][0]["top_piece"]["symbol"] == "O"
    assert state_payload["board"][0][0]["top_piece"]["size"] == "medium"

    await login(client, "beta", "beta", auth_headers)
    same_size_cover = await client.post("/api/games/move", json={"game_id": game_id, "row_index": 0, "col_index": 2, "size": "small"}, headers=auth_headers)
    assert same_size_cover.status == 409
    assert "larger piece" in (await same_size_cover.json())["error"]["message"]


@pytest.mark.asyncio
async def test_game_inventory_exhaustion(client, create_user, auth_headers) -> None:
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")

    await login(client, "alpha", "alpha", auth_headers)
    create_response = await client.post("/api/games/create", json={}, headers=auth_headers)
    game_id = (await create_response.json())["data"]["game_id"]
    await login(client, "beta", "beta", auth_headers)
    await client.post("/api/games/join", json={"game_id": game_id}, headers=auth_headers)

    moves = [
        ("alpha", 0, 0, "small"),
        ("beta", 2, 2, "small"),
        ("alpha", 0, 1, "small"),
        ("beta", 1, 2, "small"),
        ("alpha", 1, 0, "small"),
        ("beta", 2, 1, "small"),
    ]
    for username, row_index, col_index, size in moves:
        await login(client, username, username, auth_headers)
        response = await client.post(
            "/api/games/move",
            json={"game_id": game_id, "row_index": row_index, "col_index": col_index, "size": size},
            headers=auth_headers,
        )
        assert response.status == 200

    await login(client, "alpha", "alpha", auth_headers)
    exhausted = await client.post("/api/games/move", json={"game_id": game_id, "row_index": 1, "col_index": 1, "size": "small"}, headers=auth_headers)
    assert exhausted.status == 409
    assert "no pieces left" in (await exhausted.json())["error"]["message"]


@pytest.mark.asyncio
async def test_game_finishes_when_next_player_has_no_legal_move(client, create_user) -> None:
    db = client.app["db"]
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")
    alpha_id = await _user_id(db, "alpha")
    beta_id = await _user_id(db, "beta")
    game_id = await _insert_game(db, status="active", x_user_id=alpha_id, o_user_id=beta_id, turn_symbol="X")

    preset_moves = [
        ("O", beta_id, "medium", 0, 0),
        ("O", beta_id, "large", 0, 1),
        ("X", alpha_id, "large", 0, 0),
        ("O", beta_id, "large", 1, 0),
        ("X", alpha_id, "small", 0, 2),
        ("O", beta_id, "large", 1, 2),
        ("X", alpha_id, "small", 1, 1),
        ("O", beta_id, "medium", 2, 0),
        ("O", beta_id, "medium", 2, 2),
    ]
    for turn_number, (symbol, user_id, size, row_index, col_index) in enumerate(preset_moves, start=1):
        await _insert_move(
            db,
            game_id=game_id,
            turn_number=turn_number,
            symbol=symbol,
            user_id=user_id,
            size=size,
            row_index=row_index,
            col_index=col_index,
        )

    from backend.db.games import apply_move, get_game_snapshot

    await apply_move(db, game_id, alpha_id, 2, 1, "small")
    snapshot = await get_game_snapshot(db, game_id, alpha_id, connected_user_ids={alpha_id, beta_id})
    assert snapshot["status"] == "finished"
    assert snapshot["winner_symbol"] == "X"
    assert snapshot["finish_reason"] == "no_moves"


@pytest.mark.asyncio
async def test_disconnect_timeout_forfeit_and_rematch(client, create_user) -> None:
    db = client.app["db"]
    await create_user("alpha", "alpha")
    await create_user("beta", "beta")
    alpha_id = await _user_id(db, "alpha")
    beta_id = await _user_id(db, "beta")

    active_game_id = await _insert_game(db, status="active", x_user_id=alpha_id, o_user_id=beta_id, turn_symbol="X")
    changed_ids = await refresh_disconnect_deadlines(db, {alpha_id}, beta_id)
    assert active_game_id in changed_ids

    cursor = await db.execute("SELECT disconnect_deadline_at FROM games WHERE id = ?", (active_game_id,))
    row = await cursor.fetchone()
    assert row is not None
    assert row["disconnect_deadline_at"] is not None

    await db.execute(
        "UPDATE games SET disconnect_deadline_at = ? WHERE id = ?",
        ((parse_utc_text(utc_now_text()) - timedelta(seconds=1)).isoformat(timespec="seconds"), active_game_id),
    )
    await db.commit()

    resolved_ids = await resolve_due_forfeits(db, {alpha_id})
    assert resolved_ids == [active_game_id]
    finished_cursor = await db.execute("SELECT status, winner_symbol, finish_reason, forfeit_user_id FROM games WHERE id = ?", (active_game_id,))
    finished_row = await finished_cursor.fetchone()
    assert finished_row is not None
    assert finished_row["status"] == "finished"
    assert finished_row["winner_symbol"] == "X"
    assert finished_row["finish_reason"] == "forfeit"
    assert finished_row["forfeit_user_id"] == beta_id

    finished_game_id = await _insert_game(
        db,
        status="finished",
        x_user_id=alpha_id,
        o_user_id=beta_id,
        turn_symbol=None,
        winner_symbol="X",
        finish_reason="line",
    )
    assert await record_rematch_ready(db, finished_game_id, alpha_id) is None
    next_game_id = await record_rematch_ready(db, finished_game_id, beta_id)
    assert isinstance(next_game_id, int)

    rematch_cursor = await db.execute(
        "SELECT status, starter_symbol, turn_symbol, rematch_of_game_id FROM games WHERE id = ?",
        (next_game_id,),
    )
    rematch_row = await rematch_cursor.fetchone()
    assert rematch_row is not None
    assert rematch_row["status"] == "active"
    assert rematch_row["starter_symbol"] == "O"
    assert rematch_row["turn_symbol"] == "O"
    assert rematch_row["rematch_of_game_id"] == finished_game_id
