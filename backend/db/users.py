"""Store and load user rows for login and admin features.

Edit this file when the users table or user query behavior changes.
Copy this file as a starting point when you add queries for another table.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from backend.db.connection import utc_now_text


def row_to_user(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def get_user_by_username(db: aiosqlite.Connection, username: str) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """
        SELECT id, username, password_hash, is_admin, created_at, updated_at
        FROM users
        WHERE username = ?
        """,
        (username,),
    )
    return await cursor.fetchone()


async def user_exists(db: aiosqlite.Connection, username: str) -> bool:
    cursor = await db.execute(
        """
        SELECT 1
        FROM users
        WHERE username = ?
        """,
        (username,),
    )
    return await cursor.fetchone() is not None


async def get_user_by_id(db: aiosqlite.Connection, user_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """
        SELECT id, username, password_hash, is_admin, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return await cursor.fetchone()


async def list_users(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT id, username, is_admin, created_at, updated_at
        FROM users
        ORDER BY id
        """
    )
    rows = await cursor.fetchall()
    return [row_to_user(row) for row in rows if row is not None]


async def create_user_if_missing(db: aiosqlite.Connection, username: str, password_hash: str, is_admin: bool) -> None:
    now = utc_now_text()
    await db.execute(
        """
        INSERT INTO users (username, password_hash, is_admin, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(username) DO NOTHING
        """,
        (username, password_hash, int(is_admin), now, now),
    )
    await db.commit()
