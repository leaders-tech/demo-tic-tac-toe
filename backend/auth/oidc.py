"""Handle small OIDC client helpers for browser login through an external auth service.

Edit this file when OIDC discovery, token validation, or callback helpers change.
Copy the helper style here when you add another small external-auth client.
"""

from __future__ import annotations

import json
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

import aiohttp
import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jwt import InvalidTokenError

from backend.config import Settings
from backend.http.json_api import AppError


OIDC_FLOW_COOKIE_NAME = "template_oidc_flow"
OIDC_FLOW_TTL_SECONDS = 10 * 60


def _flow_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.cookie_secret, salt="template-oidc-flow")


def ensure_oidc_enabled(settings: Settings) -> None:
    if not settings.oidc_enabled:
        raise AppError(404, "not_found", "OIDC login is not enabled.")


def create_oidc_flow_cookie(settings: Settings) -> tuple[str, str, str]:
    state = token_urlsafe(24)
    nonce = token_urlsafe(24)
    value = _flow_serializer(settings).dumps({"state": state, "nonce": nonce})
    return value, state, nonce


def read_oidc_flow_cookie(settings: Settings, raw_value: str | None) -> dict[str, str] | None:
    if not raw_value:
        return None
    try:
        payload = _flow_serializer(settings).loads(raw_value, max_age=OIDC_FLOW_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    state = str(payload.get("state", "")).strip()
    nonce = str(payload.get("nonce", "")).strip()
    if not state or not nonce:
        return None
    return {"state": state, "nonce": nonce}


async def get_discovery_document(app) -> dict[str, Any]:
    settings: Settings = app["settings"]
    ensure_oidc_enabled(settings)
    cache = app["oidc_cache"]
    cached = cache.get("discovery")
    if cached is not None:
        return cached

    async with app["http_session"].get(f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration") as response:
        if response.status != 200:
            raise AppError(502, "oidc_unavailable", "Could not load OIDC discovery.")
        document = await response.json()

    if str(document.get("issuer", "")).rstrip("/") != settings.oidc_issuer_url.rstrip("/"):
        raise AppError(502, "oidc_invalid_discovery", "OIDC discovery returned the wrong issuer.")

    cache["discovery"] = document
    return document


async def get_jwks_document(app) -> dict[str, Any]:
    cache = app["oidc_cache"]
    cached = cache.get("jwks")
    if cached is not None:
        return cached

    discovery = await get_discovery_document(app)
    jwks_url = str(discovery.get("jwks_uri", "")).strip()
    if not jwks_url:
        raise AppError(502, "oidc_invalid_discovery", "OIDC discovery is missing jwks_uri.")

    async with app["http_session"].get(jwks_url) as response:
        if response.status != 200:
            raise AppError(502, "oidc_unavailable", "Could not load OIDC keys.")
        document = await response.json()

    cache["jwks"] = document
    return document


async def build_authorize_url(app, state: str, nonce: str) -> str:
    settings: Settings = app["settings"]
    discovery = await get_discovery_document(app)
    authorize_url = str(discovery.get("authorization_endpoint", "")).strip()
    if not authorize_url:
        raise AppError(502, "oidc_invalid_discovery", "OIDC discovery is missing authorization_endpoint.")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": settings.oidc_callback_url,
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
        }
    )
    return f"{authorize_url}?{query}"


async def exchange_code_for_tokens(app, code: str) -> dict[str, Any]:
    settings: Settings = app["settings"]
    discovery = await get_discovery_document(app)
    token_url = str(discovery.get("token_endpoint", "")).strip()
    if not token_url:
        raise AppError(502, "oidc_invalid_discovery", "OIDC discovery is missing token_endpoint.")

    async with app["http_session"].post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oidc_callback_url,
        },
        auth=aiohttp.BasicAuth(settings.oidc_client_id or "", settings.oidc_client_secret or ""),
    ) as response:
        if response.status != 200:
            raise AppError(401, "oidc_login_failed", "OIDC token exchange failed.")
        payload = await response.json()

    if not str(payload.get("id_token", "")).strip():
        raise AppError(401, "oidc_login_failed", "OIDC token response is missing id_token.")
    return payload


def _find_signing_key(jwks_document: dict[str, Any], id_token: str):
    header = jwt.get_unverified_header(id_token)
    if header.get("alg") != "RS256":
        raise AppError(401, "oidc_login_failed", "OIDC returned an unsupported signing algorithm.")

    keys = jwks_document.get("keys")
    if not isinstance(keys, list) or not keys:
        raise AppError(502, "oidc_unavailable", "OIDC keys are missing.")

    key_id = header.get("kid")
    matching_keys = [item for item in keys if isinstance(item, dict) and item.get("kid") == key_id]
    if not matching_keys and key_id is None:
        matching_keys = [item for item in keys if isinstance(item, dict)]
    if not matching_keys:
        raise AppError(401, "oidc_login_failed", "OIDC returned an unknown signing key.")

    last_error: Exception | None = None
    for item in matching_keys:
        try:
            return jwt.PyJWK.from_dict(item).key
        except Exception as error:  # pragma: no cover - defensive branch for bad remote keys
            last_error = error
    raise AppError(502, "oidc_unavailable", f"OIDC signing key could not be read: {last_error}")


async def maybe_fetch_userinfo(app, access_token: str, expected_subject: str) -> dict[str, Any]:
    discovery = await get_discovery_document(app)
    userinfo_url = str(discovery.get("userinfo_endpoint", "")).strip()
    if not userinfo_url:
        return {}

    async with app["http_session"].get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}) as response:
        if response.status != 200:
            return {}
        payload = await response.json()

    if payload.get("sub") and str(payload["sub"]) != expected_subject:
        raise AppError(401, "oidc_login_failed", "OIDC userinfo returned the wrong subject.")
    return payload


async def validate_id_token_and_read_claims(app, id_token: str, nonce: str, access_token: str | None = None) -> dict[str, Any]:
    settings: Settings = app["settings"]
    jwks_document = await get_jwks_document(app)
    key = _find_signing_key(jwks_document, id_token)

    try:
        claims = jwt.decode(
            id_token,
            key=key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer_url,
            options={"require": ["iss", "sub", "aud", "iat", "exp"]},
        )
    except InvalidTokenError as error:
        raise AppError(401, "oidc_login_failed", "OIDC id_token validation failed.") from error

    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise AppError(401, "oidc_login_failed", "OIDC id_token is missing sub.")
    if claims.get("nonce") != nonce:
        raise AppError(401, "oidc_login_failed", "OIDC id_token nonce is invalid.")

    if access_token and ("email" not in claims or "email_verified" not in claims):
        userinfo = await maybe_fetch_userinfo(app, access_token, subject)
        for field_name in ("email", "email_verified"):
            if field_name not in claims and field_name in userinfo:
                claims[field_name] = userinfo[field_name]
    return claims


def build_login_redirect_url(settings: Settings, *, success: bool, error_code: str | None = None) -> str:
    path = "/lobby" if success else "/login"
    url = f"{settings.frontend_origin.rstrip('/')}{path}"
    if not success and error_code:
        query = urlencode({"error": error_code})
        return f"{url}?{query}"
    return url


def dump_jwk(public_key: Any, key_id: str) -> dict[str, Any]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = key_id
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return jwk
