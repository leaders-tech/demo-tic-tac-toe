"""Seed simple default data for local development only.

Edit this file when dev-only starter users or other dev seed data changes.
Copy the small helper style here when you add another dev-only seed step.
"""

from __future__ import annotations

import aiosqlite

from backend.auth.passwords import hash_password
from backend.config import Settings
from backend.db.users import create_user_if_missing, user_exists


async def seed_dev_data(db: aiosqlite.Connection, settings: Settings) -> None:
    if settings.mode != "dev":
        return
    if not await user_exists(db, "user"):
        await create_user_if_missing(db, "user", hash_password("user"), False)
    if not await user_exists(db, "admin"):
        await create_user_if_missing(db, "admin", hash_password("admin"), True)
    if not await user_exists(db, "viewer"):
        await create_user_if_missing(db, "viewer", hash_password("viewer"), False)
    if not await user_exists(db, "nikita"):
        await create_user_if_missing(db, "nikita", hash_password("nikita"), False)
    if not await user_exists(db, "elias"):
        await create_user_if_missing(db, "elias", hash_password("elias"), False)
    if not await user_exists(db, "alex"):
        await create_user_if_missing(db, "alex", hash_password("alex"), False)
