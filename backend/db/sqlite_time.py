"""Register UTC ISO datetime adapters and converters for SQLite code paths.

Edit this file when SQLite datetime encoding or decoding rules change.
Copy the helper style here when you add another small SQLite codec helper.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator


def adapt_datetime_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat(timespec="seconds")


def convert_datetime_utc(raw: bytes) -> datetime:
    value = datetime.fromisoformat(raw.decode("utf-8"))
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@contextmanager
def sqlite_datetime_codecs() -> Iterator[None]:
    saved_adapters = sqlite3.adapters.copy()
    saved_converters = sqlite3.converters.copy()
    sqlite3.register_adapter(datetime, adapt_datetime_utc)
    sqlite3.register_converter("timestamp", convert_datetime_utc)
    sqlite3.register_converter("TIMESTAMP", convert_datetime_utc)
    try:
        yield
    finally:
        sqlite3.adapters = saved_adapters
        sqlite3.converters = saved_converters
