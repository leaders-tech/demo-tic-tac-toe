"""Store and update refresh-session rows for browser login state.

Edit this file when refresh-session fields or refresh-session queries change.
Copy this file as a starting point when you add queries for another auth-style table.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from backend.db.connection import utc_now_text


async def create_session(
    db: aiosqlite.Connection,
    session_id: str,
    user_id: int,
    token_hash: str,
    expires_at: str,
) -> None:
    now = utc_now_text()
    await db.execute(
        """
        INSERT INTO refresh_sessions (id, user_id, token_hash, created_at, updated_at, expires_at, last_used_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, user_id, token_hash, now, now, expires_at, now),
    )
    await db.commit()


async def get_session(db: aiosqlite.Connection, session_id: str) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """
        SELECT id, user_id, token_hash, created_at, updated_at, expires_at, last_used_at
        FROM refresh_sessions
        WHERE id = ?
        """,
        (session_id,),
    )
    return await cursor.fetchone()


async def rotate_session(db: aiosqlite.Connection, session_id: str, token_hash: str, expires_at: str) -> None:
    now = utc_now_text()
    await db.execute(
        """
        UPDATE refresh_sessions
        SET token_hash = ?, updated_at = ?, expires_at = ?, last_used_at = ?
        WHERE id = ?
        """,
        (token_hash, now, expires_at, now, session_id),
    )
    await db.commit()


async def delete_session(db: aiosqlite.Connection, session_id: str) -> None:
    await db.execute("DELETE FROM refresh_sessions WHERE id = ?", (session_id,))
    await db.commit()


async def count_sessions(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT COUNT(*) AS count FROM refresh_sessions")
    row = await cursor.fetchone()
    return int(row["count"]) if row is not None else 0


def row_to_session(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "expires_at": row["expires_at"],
        "last_used_at": row["last_used_at"],
    }
