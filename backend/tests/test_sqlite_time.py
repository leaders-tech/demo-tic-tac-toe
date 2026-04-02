"""Test the custom SQLite UTC datetime adapters and converters.

Edit this file when SQLite time encoding or decoding changes.
Copy a test pattern here when you add another small DB codec helper.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backend.db.sqlite_time import adapt_datetime_utc, convert_datetime_utc


def test_adapt_datetime_utc() -> None:
    value = datetime(2026, 3, 6, 10, 20, 30, tzinfo=UTC)
    assert adapt_datetime_utc(value) == "2026-03-06T10:20:30+00:00"


def test_convert_datetime_utc() -> None:
    value = convert_datetime_utc(b"2026-03-06T10:20:30+00:00")
    assert value == datetime(2026, 3, 6, 10, 20, 30, tzinfo=UTC)
