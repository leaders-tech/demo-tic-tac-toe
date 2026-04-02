"""Create and read signed access tokens and hashed refresh-token helpers.

Edit this file when token payloads, signatures, or refresh-token hashing changes.
Copy the helper style here when you add another small token utility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hmac
from secrets import token_urlsafe
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer

from backend.config import Settings


def _serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.cookie_secret, salt="template-access-cookie")


def build_access_token(settings: Settings, user: dict[str, Any]) -> str:
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.access_ttl_seconds)
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "is_admin": bool(user["is_admin"]),
        "exp": expires_at.isoformat(timespec="seconds"),
    }
    return _serializer(settings).dumps(payload)


def read_access_token(settings: Settings, token: str) -> dict[str, Any] | None:
    try:
        payload = _serializer(settings).loads(token)
    except BadSignature:
        return None
    expires_at = datetime.fromisoformat(payload["exp"])
    if expires_at <= datetime.now(tz=UTC):
        return None
    return {
        "id": int(payload["user_id"]),
        "username": str(payload["username"]),
        "is_admin": bool(payload["is_admin"]),
    }


def create_refresh_token_pair() -> tuple[str, str]:
    session_id = token_urlsafe(16)
    raw_token = token_urlsafe(32)
    return session_id, raw_token


def hash_refresh_token(settings: Settings, raw_token: str) -> str:
    return hmac.digest(settings.cookie_secret.encode("utf-8"), raw_token.encode("utf-8"), "sha256").hex()
