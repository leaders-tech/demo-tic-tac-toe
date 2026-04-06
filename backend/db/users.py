"""Store and load user rows for login and admin features.

Edit this file when the users table or user query behavior changes.
Copy this file as a starting point when you add queries for another table.
"""

from __future__ import annotations

import re
from typing import Any

import aiosqlite

from backend.db.connection import utc_now_text


_USERNAME_CHARS = re.compile(r"[^a-z0-9]+")


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


def username_base_from_email(email: str | None) -> str:
    if email:
        local_part = email.split("@", 1)[0].strip().lower()
        cleaned = _USERNAME_CHARS.sub("-", local_part).strip("-")
        if cleaned:
            return cleaned
    return "user"


async def create_user(db: aiosqlite.Connection, username: str, password_hash: str, is_admin: bool) -> dict[str, Any]:
    now = utc_now_text()
    cursor = await db.execute(
        """
        INSERT INTO users (username, password_hash, is_admin, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, password_hash, int(is_admin), now, now),
    )
    await db.commit()
    return {
        "id": int(cursor.lastrowid),
        "username": username,
        "is_admin": bool(is_admin),
        "created_at": now,
        "updated_at": now,
    }


async def create_user_with_available_username(db: aiosqlite.Connection, base_username: str, password_hash: str, is_admin: bool) -> dict[str, Any]:
    base = _USERNAME_CHARS.sub("-", base_username.strip().lower()).strip("-") or "user"
    suffix = 1
    while True:
        candidate = base if suffix == 1 else f"{base}-{suffix}"
        try:
            return await create_user(db, candidate, password_hash, is_admin)
        except aiosqlite.IntegrityError:
            suffix += 1


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
