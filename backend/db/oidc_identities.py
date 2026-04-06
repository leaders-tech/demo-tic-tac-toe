"""Store links between local users and external OIDC identities.

Edit this file when OIDC identity fields or lookup rules change.
Copy this file as a starting point when you add queries for another auth-linked table.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from backend.db.connection import utc_now_text
from backend.db.users import row_to_user


async def get_identity_with_user(db: aiosqlite.Connection, issuer: str, subject: str) -> dict[str, Any] | None:
    cursor = await db.execute(
        """
        SELECT
            i.id AS identity_id,
            i.user_id,
            i.issuer,
            i.subject,
            i.email,
            i.email_verified,
            i.created_at AS identity_created_at,
            i.updated_at AS identity_updated_at,
            i.last_login_at,
            u.id,
            u.username,
            u.password_hash,
            u.is_admin,
            u.created_at,
            u.updated_at
        FROM user_oidc_identities AS i
        JOIN users AS u ON u.id = i.user_id
        WHERE i.issuer = ? AND i.subject = ?
        """,
        (issuer, subject),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {
        "identity_id": row["identity_id"],
        "issuer": row["issuer"],
        "subject": row["subject"],
        "email": row["email"],
        "email_verified": bool(row["email_verified"]),
        "last_login_at": row["last_login_at"],
        "user": row_to_user(row),
    }


async def create_identity(
    db: aiosqlite.Connection,
    user_id: int,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> None:
    now = utc_now_text()
    await db.execute(
        """
        INSERT INTO user_oidc_identities (
            user_id,
            issuer,
            subject,
            email,
            email_verified,
            created_at,
            updated_at,
            last_login_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, issuer, subject, email, int(email_verified), now, now, now),
    )
    await db.commit()


async def update_identity_login(
    db: aiosqlite.Connection,
    issuer: str,
    subject: str,
    email: str | None,
    email_verified: bool,
) -> None:
    now = utc_now_text()
    await db.execute(
        """
        UPDATE user_oidc_identities
        SET email = ?, email_verified = ?, updated_at = ?, last_login_at = ?
        WHERE issuer = ? AND subject = ?
        """,
        (email, int(email_verified), now, now, issuer, subject),
    )
    await db.commit()
