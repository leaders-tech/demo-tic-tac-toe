"""Store and load game rows, move rows, and derived game snapshots.

Edit this file when tic-tac-toe game rules, lobby queries, or game state behavior changes.
Copy this file as a starting point when you add queries for another feature with its own tables.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any, Literal, TypedDict

import aiosqlite

from backend.db.connection import parse_utc_text, utc_now_text
from backend.http.json_api import AppError


BOARD_SIZE = 3
DISCONNECT_TIMEOUT_SECONDS = 30
GAME_STATUSES = {"waiting", "active", "finished"}
GAME_SYMBOLS = ("X", "O")
GAME_SIZES = ("small", "medium", "large")
SIZE_RANK = {"small": 1, "medium": 2, "large": 3}
PIECES_PER_SIZE = 3

GameStatus = Literal["waiting", "active", "finished"]
GameSymbol = Literal["X", "O"]
GameSize = Literal["small", "medium", "large"]


class GamePiece(TypedDict):
    symbol: GameSymbol
    user_id: int
    size: GameSize
    row_index: int
    col_index: int
    turn_number: int


def _player_dict(user_id: int | None, username: str | None, connected_user_ids: set[int]) -> dict[str, Any] | None:
    if user_id is None or username is None:
        return None
    return {"id": user_id, "username": username, "connected": user_id in connected_user_ids}


def _other_symbol(symbol: GameSymbol) -> GameSymbol:
    return "O" if symbol == "X" else "X"


def _symbol_for_user(game_row: aiosqlite.Row, user_id: int) -> GameSymbol | None:
    if game_row["x_user_id"] == user_id:
        return "X"
    if game_row["o_user_id"] == user_id:
        return "O"
    return None


def _piece_from_row(row: aiosqlite.Row) -> GamePiece:
    return {
        "symbol": row["symbol"],
        "user_id": row["user_id"],
        "size": row["size"],
        "row_index": row["row_index"],
        "col_index": row["col_index"],
        "turn_number": row["turn_number"],
    }


def _build_board(move_rows: list[aiosqlite.Row]) -> tuple[list[list[dict[str, Any]]], dict[GameSymbol, dict[GameSize, int]]]:
    cells: list[list[list[GamePiece]]] = [[[] for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    used_counts: dict[GameSymbol, Counter[GameSize]] = {
        "X": Counter({"small": 0, "medium": 0, "large": 0}),
        "O": Counter({"small": 0, "medium": 0, "large": 0}),
    }
    for row in move_rows:
        piece = _piece_from_row(row)
        cells[piece["row_index"]][piece["col_index"]].append(piece)
        used_counts[piece["symbol"]][piece["size"]] += 1

    board: list[list[dict[str, Any]]] = []
    for row_index in range(BOARD_SIZE):
        row_cells: list[dict[str, Any]] = []
        for col_index in range(BOARD_SIZE):
            stack = cells[row_index][col_index]
            top_piece = stack[-1] if stack else None
            row_cells.append(
                {
                    "row_index": row_index,
                    "col_index": col_index,
                    "stack": stack,
                    "top_piece": top_piece,
                }
            )
        board.append(row_cells)

    remaining = {
        symbol: {size: PIECES_PER_SIZE - used_counts[symbol][size] for size in GAME_SIZES}
        for symbol in GAME_SYMBOLS
    }
    return board, remaining


def _winning_symbol(board: list[list[dict[str, Any]]]) -> GameSymbol | None:
    lines: list[list[dict[str, Any]]] = []
    lines.extend(board)
    lines.extend([[board[row_index][col_index] for row_index in range(BOARD_SIZE)] for col_index in range(BOARD_SIZE)])
    lines.append([board[index][index] for index in range(BOARD_SIZE)])
    lines.append([board[index][BOARD_SIZE - 1 - index] for index in range(BOARD_SIZE)])
    for line in lines:
        tops = [cell["top_piece"] for cell in line]
        if tops[0] is None:
            continue
        if all(piece is not None and piece["symbol"] == tops[0]["symbol"] for piece in tops):
            return tops[0]["symbol"]
    return None


def _available_sizes(top_piece: GamePiece | None, remaining: dict[GameSize, int]) -> list[GameSize]:
    if top_piece is None:
        return [size for size in GAME_SIZES if remaining[size] > 0]
    top_rank = SIZE_RANK[top_piece["size"]]
    return [size for size in GAME_SIZES if remaining[size] > 0 and SIZE_RANK[size] > top_rank]


def _has_any_legal_move(board: list[list[dict[str, Any]]], remaining: dict[GameSize, int]) -> bool:
    for row in board:
        for cell in row:
            if _available_sizes(cell["top_piece"], remaining):
                return True
    return False


def _viewer_role(game_row: aiosqlite.Row, viewer_id: int) -> str:
    if game_row["x_user_id"] == viewer_id:
        return "X"
    if game_row["o_user_id"] == viewer_id:
        return "O"
    return "spectator"


async def _fetch_game_row(db: aiosqlite.Connection, game_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """
        SELECT
            games.id,
            games.status,
            games.x_user_id,
            games.o_user_id,
            games.starter_symbol,
            games.turn_symbol,
            games.winner_symbol,
            games.finish_reason,
            games.forfeit_user_id,
            games.disconnect_deadline_at,
            games.rematch_x_ready,
            games.rematch_o_ready,
            games.rematch_of_game_id,
            games.created_at,
            games.updated_at,
            games_next.id AS next_game_id,
            users_x.username AS x_username,
            users_o.username AS o_username
        FROM games
        INNER JOIN users AS users_x ON users_x.id = games.x_user_id
        LEFT JOIN users AS users_o ON users_o.id = games.o_user_id
        LEFT JOIN games AS games_next ON games_next.rematch_of_game_id = games.id
        WHERE games.id = ?
        """,
        (game_id,),
    )
    return await cursor.fetchone()


async def _fetch_move_rows(db: aiosqlite.Connection, game_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """
        SELECT game_id, turn_number, symbol, user_id, size, row_index, col_index, created_at
        FROM game_moves
        WHERE game_id = ?
        ORDER BY turn_number
        """,
        (game_id,),
    )
    return await cursor.fetchall()


async def _list_game_rows(db: aiosqlite.Connection, status: GameStatus, limit: int | None = None) -> list[aiosqlite.Row]:
    query = """
        SELECT
            games.id,
            games.status,
            games.x_user_id,
            games.o_user_id,
            games.starter_symbol,
            games.turn_symbol,
            games.winner_symbol,
            games.finish_reason,
            games.forfeit_user_id,
            games.disconnect_deadline_at,
            games.rematch_x_ready,
            games.rematch_o_ready,
            games.rematch_of_game_id,
            games.created_at,
            games.updated_at,
            users_x.username AS x_username,
            users_o.username AS o_username
        FROM games
        INNER JOIN users AS users_x ON users_x.id = games.x_user_id
        LEFT JOIN users AS users_o ON users_o.id = games.o_user_id
        WHERE games.status = ?
        ORDER BY games.updated_at DESC, games.id DESC
    """
    params: list[object] = [status]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    cursor = await db.execute(query, params)
    return await cursor.fetchall()


async def _list_game_ids_for_user(db: aiosqlite.Connection, user_id: int) -> list[int]:
    cursor = await db.execute(
        """
        SELECT id
        FROM games
        WHERE x_user_id = ? OR o_user_id = ?
        ORDER BY id DESC
        """,
        (user_id, user_id),
    )
    rows = await cursor.fetchall()
    return [row["id"] for row in rows]


def _summary_from_row(row: aiosqlite.Row, viewer_id: int, connected_user_ids: set[int]) -> dict[str, Any]:
    viewer_role = _viewer_role(row, viewer_id)
    return {
        "id": row["id"],
        "status": row["status"],
        "starter_symbol": row["starter_symbol"],
        "turn_symbol": row["turn_symbol"],
        "winner_symbol": row["winner_symbol"],
        "finish_reason": row["finish_reason"],
        "disconnect_deadline_at": row["disconnect_deadline_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "viewer_role": viewer_role,
        "is_spectator": viewer_role == "spectator",
        "can_join": row["status"] == "waiting" and row["o_user_id"] is None and row["x_user_id"] != viewer_id,
        "can_cancel": row["status"] == "waiting" and row["x_user_id"] == viewer_id,
        "players": {
            "X": _player_dict(row["x_user_id"], row["x_username"], connected_user_ids),
            "O": _player_dict(row["o_user_id"], row["o_username"], connected_user_ids),
        },
    }


def _snapshot_from_state(game_row: aiosqlite.Row, move_rows: list[aiosqlite.Row], viewer_id: int, connected_user_ids: set[int]) -> dict[str, Any]:
    board, remaining = _build_board(move_rows)
    viewer_role = _viewer_role(game_row, viewer_id)
    turn_symbol = game_row["turn_symbol"]
    current_remaining = remaining[turn_symbol] if turn_symbol in GAME_SYMBOLS else {"small": 0, "medium": 0, "large": 0}

    for row in board:
        for cell in row:
            cell["available_sizes"] = _available_sizes(cell["top_piece"], current_remaining) if turn_symbol in GAME_SYMBOLS else []

    symbol_for_viewer = _symbol_for_user(game_row, viewer_id)
    can_move = game_row["status"] == "active" and symbol_for_viewer == game_row["turn_symbol"]

    return {
        "id": game_row["id"],
        "status": game_row["status"],
        "starter_symbol": game_row["starter_symbol"],
        "turn_symbol": game_row["turn_symbol"],
        "winner_symbol": game_row["winner_symbol"],
        "finish_reason": game_row["finish_reason"],
        "forfeit_user_id": game_row["forfeit_user_id"],
        "disconnect_deadline_at": game_row["disconnect_deadline_at"],
        "created_at": game_row["created_at"],
        "updated_at": game_row["updated_at"],
        "viewer_role": viewer_role,
        "is_spectator": viewer_role == "spectator",
        "can_move": can_move,
        "can_cancel": game_row["status"] == "waiting" and game_row["x_user_id"] == viewer_id,
        "can_rematch": game_row["status"] == "finished" and symbol_for_viewer in GAME_SYMBOLS,
        "next_game_id": game_row["next_game_id"],
        "players": {
            "X": _player_dict(game_row["x_user_id"], game_row["x_username"], connected_user_ids),
            "O": _player_dict(game_row["o_user_id"], game_row["o_username"], connected_user_ids),
        },
        "rematch": {
            "x_ready": bool(game_row["rematch_x_ready"]),
            "o_ready": bool(game_row["rematch_o_ready"]),
        },
        "remaining_pieces": remaining,
        "board": board,
        "move_count": len(move_rows),
        "legal_move_exists_for_turn": turn_symbol in GAME_SYMBOLS and _has_any_legal_move(board, remaining[turn_symbol]),
    }


async def list_lobby_games(db: aiosqlite.Connection, viewer_id: int, connected_user_ids: set[int]) -> dict[str, Any]:
    waiting_rows = await _list_game_rows(db, "waiting")
    active_rows = await _list_game_rows(db, "active")
    finished_rows = await _list_game_rows(db, "finished", limit=10)
    return {
        "waiting_games": [_summary_from_row(row, viewer_id, connected_user_ids) for row in waiting_rows],
        "active_games": [_summary_from_row(row, viewer_id, connected_user_ids) for row in active_rows],
        "finished_games": [_summary_from_row(row, viewer_id, connected_user_ids) for row in finished_rows],
    }


async def get_game_snapshot(db: aiosqlite.Connection, game_id: int, viewer_id: int, connected_user_ids: set[int]) -> dict[str, Any]:
    game_row = await _fetch_game_row(db, game_id)
    if game_row is None:
        raise AppError(404, "not_found", "Game does not exist.")
    move_rows = await _fetch_move_rows(db, game_id)
    return _snapshot_from_state(game_row, move_rows, viewer_id, connected_user_ids)


async def create_waiting_game(db: aiosqlite.Connection, user_id: int) -> int:
    now = utc_now_text()
    try:
        await db.execute("BEGIN IMMEDIATE")
        existing_cursor = await db.execute(
            """
            SELECT id
            FROM games
            WHERE status = 'waiting' AND x_user_id = ?
            """,
            (user_id,),
        )
        if await existing_cursor.fetchone() is not None:
            raise AppError(409, "conflict", "You already have a waiting game.")

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
            ("waiting", user_id, None, "X", "X", None, None, None, None, 0, 0, None, now, now),
        )
        row = await cursor.fetchone()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    if row is None:
        raise RuntimeError("Game was not created.")
    return row["id"]


async def join_waiting_game(db: aiosqlite.Connection, game_id: int, user_id: int) -> int:
    now = utc_now_text()
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await _fetch_game_row(db, game_id)
        if row is None:
            raise AppError(404, "not_found", "Game does not exist.")
        if row["status"] != "waiting" or row["o_user_id"] is not None:
            raise AppError(409, "conflict", "Game is no longer waiting for a player.")
        if row["x_user_id"] == user_id:
            raise AppError(400, "bad_request", "You cannot join your own waiting game.")

        await db.execute(
            """
            UPDATE games
            SET status = 'active', o_user_id = ?, turn_symbol = starter_symbol, updated_at = ?
            WHERE id = ?
            """,
            (user_id, now, game_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return game_id


async def cancel_waiting_game(db: aiosqlite.Connection, game_id: int, user_id: int) -> None:
    try:
        await db.execute("BEGIN IMMEDIATE")
        row = await _fetch_game_row(db, game_id)
        if row is None:
            raise AppError(404, "not_found", "Game does not exist.")
        if row["status"] != "waiting":
            raise AppError(409, "conflict", "Only waiting games can be cancelled.")
        if row["x_user_id"] != user_id:
            raise AppError(403, "forbidden", "Only the creator can cancel this game.")
        await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def apply_move(db: aiosqlite.Connection, game_id: int, user_id: int, row_index: int, col_index: int, size: str) -> None:
    if size not in GAME_SIZES:
        raise AppError(400, "bad_request", "Piece size must be small, medium, or large.")
    if row_index not in range(BOARD_SIZE) or col_index not in range(BOARD_SIZE):
        raise AppError(400, "bad_request", "Board position is outside the 3 by 3 grid.")

    now = utc_now_text()
    try:
        await db.execute("BEGIN IMMEDIATE")
        game_row = await _fetch_game_row(db, game_id)
        if game_row is None:
            raise AppError(404, "not_found", "Game does not exist.")
        if game_row["status"] != "active":
            raise AppError(409, "conflict", "This game is not active.")

        symbol = _symbol_for_user(game_row, user_id)
        if symbol is None:
            raise AppError(403, "forbidden", "Only players can make moves in this game.")
        if game_row["turn_symbol"] != symbol:
            raise AppError(409, "conflict", "It is not your turn.")

        move_rows = await _fetch_move_rows(db, game_id)
        board, remaining = _build_board(move_rows)
        if remaining[symbol][size] <= 0:
            raise AppError(409, "conflict", "You have no pieces left of that size.")

        top_piece = board[row_index][col_index]["top_piece"]
        if top_piece is not None and SIZE_RANK[size] <= SIZE_RANK[top_piece["size"]]:
            raise AppError(409, "conflict", "You can only cover a cell with a larger piece.")

        turn_number = len(move_rows) + 1
        await db.execute(
            """
            INSERT INTO game_moves (game_id, turn_number, symbol, user_id, size, row_index, col_index, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, turn_number, symbol, user_id, size, row_index, col_index, now),
        )

        cursor = await db.execute(
            """
            SELECT game_id, turn_number, symbol, user_id, size, row_index, col_index, created_at
            FROM game_moves
            WHERE game_id = ?
            ORDER BY turn_number
            """,
            (game_id,),
        )
        next_move_rows = await cursor.fetchall()
        next_board, next_remaining = _build_board(next_move_rows)
        winner_symbol = _winning_symbol(next_board)
        finish_reason: str | None = None
        next_turn_symbol: str | None = None

        if winner_symbol is not None:
            finish_reason = "line"
        else:
            next_turn_symbol = _other_symbol(symbol)
            if not _has_any_legal_move(next_board, next_remaining[next_turn_symbol]):
                winner_symbol = symbol
                finish_reason = "no_moves"
                next_turn_symbol = None

        if winner_symbol is not None:
            await db.execute(
                """
                UPDATE games
                SET
                    status = 'finished',
                    turn_symbol = NULL,
                    winner_symbol = ?,
                    finish_reason = ?,
                    disconnect_deadline_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (winner_symbol, finish_reason, now, game_id),
            )
        else:
            await db.execute(
                """
                UPDATE games
                SET turn_symbol = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_turn_symbol, now, game_id),
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def record_rematch_ready(db: aiosqlite.Connection, game_id: int, user_id: int) -> int | None:
    now = utc_now_text()
    try:
        await db.execute("BEGIN IMMEDIATE")
        game_row = await _fetch_game_row(db, game_id)
        if game_row is None:
            raise AppError(404, "not_found", "Game does not exist.")
        if game_row["status"] != "finished":
            raise AppError(409, "conflict", "Only finished games can start a rematch.")

        symbol = _symbol_for_user(game_row, user_id)
        if symbol is None:
            raise AppError(403, "forbidden", "Only players can request a rematch.")

        ready_column = "rematch_x_ready" if symbol == "X" else "rematch_o_ready"
        await db.execute(f"UPDATE games SET {ready_column} = 1, updated_at = ? WHERE id = ?", (now, game_id))

        refreshed_row = await _fetch_game_row(db, game_id)
        if refreshed_row is None:
            raise RuntimeError("Finished game disappeared during rematch.")
        if refreshed_row["next_game_id"] is not None:
            await db.commit()
            return refreshed_row["next_game_id"]

        if not refreshed_row["rematch_x_ready"] or not refreshed_row["rematch_o_ready"]:
            await db.commit()
            return None

        next_starter = _other_symbol(refreshed_row["starter_symbol"])
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
                "active",
                refreshed_row["x_user_id"],
                refreshed_row["o_user_id"],
                next_starter,
                next_starter,
                None,
                None,
                None,
                None,
                0,
                0,
                game_id,
                now,
                now,
            ),
        )
        next_game = await cursor.fetchone()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    if next_game is None:
        raise RuntimeError("Rematch game was not created.")
    return next_game["id"]


async def refresh_disconnect_deadlines(db: aiosqlite.Connection, connected_user_ids: set[int], user_id: int) -> list[int]:
    now = utc_now_text()
    now_dt = parse_utc_text(now)
    changed_game_ids: list[int] = []
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT id, status, x_user_id, o_user_id, disconnect_deadline_at
            FROM games
            WHERE status IN ('waiting', 'active', 'finished')
              AND (x_user_id = ? OR o_user_id = ?)
            """,
            (user_id, user_id),
        )
        rows = await cursor.fetchall()
        for row in rows:
            changed_game_ids.append(row["id"])
            if row["status"] != "active" or row["o_user_id"] is None:
                continue
            row_id = row["id"]
            x_connected = row["x_user_id"] in connected_user_ids
            o_connected = row["o_user_id"] in connected_user_ids
            next_deadline = None
            if x_connected != o_connected:
                next_deadline = (now_dt + timedelta(seconds=DISCONNECT_TIMEOUT_SECONDS)).isoformat(timespec="seconds")
            current_deadline = row["disconnect_deadline_at"]
            if current_deadline != next_deadline:
                await db.execute(
                    "UPDATE games SET disconnect_deadline_at = ?, updated_at = ? WHERE id = ?",
                    (next_deadline, now, row_id),
                )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return changed_game_ids


async def refresh_all_disconnect_deadlines(db: aiosqlite.Connection, connected_user_ids: set[int]) -> list[int]:
    now = utc_now_text()
    now_dt = parse_utc_text(now)
    changed_game_ids: list[int] = []
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT id, x_user_id, o_user_id, disconnect_deadline_at
            FROM games
            WHERE status = 'active' AND o_user_id IS NOT NULL
            """
        )
        rows = await cursor.fetchall()
        for row in rows:
            x_connected = row["x_user_id"] in connected_user_ids
            o_connected = row["o_user_id"] in connected_user_ids
            next_deadline = None
            if x_connected != o_connected:
                next_deadline = (now_dt + timedelta(seconds=DISCONNECT_TIMEOUT_SECONDS)).isoformat(timespec="seconds")
            if row["disconnect_deadline_at"] != next_deadline:
                await db.execute(
                    "UPDATE games SET disconnect_deadline_at = ?, updated_at = ? WHERE id = ?",
                    (next_deadline, now, row["id"]),
                )
                changed_game_ids.append(row["id"])
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return changed_game_ids


async def resolve_due_forfeits(db: aiosqlite.Connection, connected_user_ids: set[int]) -> list[int]:
    now = utc_now_text()
    changed_ids: list[int] = []
    try:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT id, x_user_id, o_user_id, disconnect_deadline_at
            FROM games
            WHERE status = 'active'
              AND disconnect_deadline_at IS NOT NULL
              AND disconnect_deadline_at <= ?
            """,
            (now,),
        )
        rows = await cursor.fetchall()
        for row in rows:
            if row["o_user_id"] is None:
                continue
            x_connected = row["x_user_id"] in connected_user_ids
            o_connected = row["o_user_id"] in connected_user_ids
            if x_connected == o_connected:
                await db.execute(
                    "UPDATE games SET disconnect_deadline_at = NULL, updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                changed_ids.append(row["id"])
                continue
            forfeit_user_id = row["x_user_id"] if not x_connected else row["o_user_id"]
            winner_symbol: GameSymbol = "O" if forfeit_user_id == row["x_user_id"] else "X"
            await db.execute(
                """
                UPDATE games
                SET
                    status = 'finished',
                    turn_symbol = NULL,
                    winner_symbol = ?,
                    finish_reason = 'forfeit',
                    forfeit_user_id = ?,
                    disconnect_deadline_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (winner_symbol, forfeit_user_id, now, row["id"]),
            )
            changed_ids.append(row["id"])
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return changed_ids


async def list_related_game_ids_for_user(db: aiosqlite.Connection, user_id: int) -> list[int]:
    return await _list_game_ids_for_user(db, user_id)
