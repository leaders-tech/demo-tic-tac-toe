"""Build the shared JSON API response shape and read JSON request bodies.

Edit this file when the common success or error envelope changes.
Copy the helper style here when you add another small shared HTTP utility.
"""

from __future__ import annotations

from typing import Any

from aiohttp import web


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def ok(data: Any, status: int = 200) -> web.Response:
    return web.json_response({"ok": True, "data": data}, status=status)


def fail(status: int, code: str, message: str) -> web.Response:
    return web.json_response({"ok": False, "error": {"code": code, "message": message}}, status=status)


async def read_json(request: web.Request) -> dict[str, Any]:
    if request.content_type != "application/json":
        raise AppError(400, "bad_request", "Expected application/json.")
    data = await request.json()
    if not isinstance(data, dict):
        raise AppError(400, "bad_request", "Expected a JSON object.")
    return data
