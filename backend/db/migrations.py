"""Run yoyo migrations before the backend starts using the database.

Edit this file when migration startup flow or migration helper wiring changes.
Do not copy this file. Change it when the project-wide migration process changes.
"""

from __future__ import annotations

from pathlib import Path

from yoyo import get_backend, read_migrations

from backend.db.sqlite_time import sqlite_datetime_codecs


def run_migrations(db_path: Path, migrations_path: Path) -> None:
    migrations = read_migrations(str(migrations_path))
    with sqlite_datetime_codecs():
        backend = get_backend(f"sqlite:///{db_path}")
        try:
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))
        finally:
            backend.connection.close()
