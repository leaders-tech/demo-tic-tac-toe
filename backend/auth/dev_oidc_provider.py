"""Expose a tiny fake OIDC provider for local browser tests only.

Edit this file when the dev-only OIDC test flow changes.
Do not copy this file into product features. It exists only for local and e2e verification.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

import jwt
from aiohttp import web
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.auth.oidc import dump_jwk
from backend.config import Settings
from backend.http.json_api import AppError


def create_dev_oidc_provider_state(settings: Settings) -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_id = "dev-oidc-key"
    return {
        "issuer": settings.oidc_issuer_url or settings.public_base_url,
        "client_id": settings.oidc_client_id or "dev-client",
        "client_secret": settings.oidc_client_secret or "dev-secret",
        "private_key": private_key,
        "public_jwk": dump_jwk(private_key.public_key(), key_id),
        "key_id": key_id,
        "codes": {},
        "access_tokens": {},
        "user": {
            "sub": "dev-oidc-user",
            "email": "oidc-player@example.com",
            "email_verified": True,
        },
    }


def _provider_base_url(provider: dict[str, Any]) -> str:
    return str(provider["issuer"]).rstrip("/")


async def openid_configuration(request: web.Request) -> web.Response:
    provider = request.app["dev_oidc_provider"]
    base_url = _provider_base_url(provider)
    return web.json_response(
        {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oidc/authorize",
            "token_endpoint": f"{base_url}/oidc/token",
            "userinfo_endpoint": f"{base_url}/oidc/userinfo",
            "jwks_uri": f"{base_url}/oidc/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile", "userinfo:read:by-email"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "claims_supported": ["sub", "email", "email_verified"],
        }
    )


async def oidc_authorize(request: web.Request) -> web.Response:
    provider = request.app["dev_oidc_provider"]
    client_id = str(request.query.get("client_id", "")).strip()
    redirect_uri = str(request.query.get("redirect_uri", "")).strip()
    state = str(request.query.get("state", "")).strip()
    nonce = str(request.query.get("nonce", "")).strip()
    response_type = str(request.query.get("response_type", "")).strip()
    if response_type != "code" or client_id != provider["client_id"] or not redirect_uri or not state or not nonce:
        raise AppError(400, "bad_request", "Invalid dev OIDC authorize request.")

    code = token_urlsafe(24)
    provider["codes"][code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "nonce": nonce,
    }
    return web.HTTPFound(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}")


def _read_client_credentials(request: web.Request, form: dict[str, Any]) -> tuple[str, str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        import base64

        encoded = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        client_id, password = decoded.split(":", 1)
        return client_id, password
    client_id = str(form.get("client_id", "")).strip()
    client_secret = str(form.get("client_secret", "")).strip()
    return client_id, client_secret


async def oidc_token(request: web.Request) -> web.Response:
    provider = request.app["dev_oidc_provider"]
    form = await request.post()
    client_id, client_secret = _read_client_credentials(request, form)
    grant_type = str(form.get("grant_type", "")).strip()
    code = str(form.get("code", "")).strip()
    redirect_uri = str(form.get("redirect_uri", "")).strip()
    if client_id != provider["client_id"] or client_secret != provider["client_secret"]:
        raise AppError(401, "not_authenticated", "Wrong dev OIDC client credentials.")
    if grant_type != "authorization_code" or not code:
        raise AppError(400, "bad_request", "Invalid dev OIDC token request.")
    code_data = provider["codes"].pop(code, None)
    if code_data is None or code_data["redirect_uri"] != redirect_uri:
        raise AppError(400, "bad_request", "Invalid dev OIDC code.")

    now = datetime.now(tz=UTC)
    access_token = token_urlsafe(32)
    provider["access_tokens"][access_token] = provider["user"]
    id_token = jwt.encode(
        {
            "iss": provider["issuer"],
            "sub": provider["user"]["sub"],
            "aud": client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "email": provider["user"]["email"],
            "email_verified": provider["user"]["email_verified"],
            "nonce": code_data["nonce"],
        },
        provider["private_key"],
        algorithm="RS256",
        headers={"kid": provider["key_id"]},
    )
    return web.json_response(
        {
            "access_token": access_token,
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": 600,
            "scope": "openid email profile",
        }
    )


async def oidc_userinfo(request: web.Request) -> web.Response:
    provider = request.app["dev_oidc_provider"]
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AppError(401, "not_authenticated", "Missing dev OIDC bearer token.")
    access_token = auth_header.split(" ", 1)[1]
    user = provider["access_tokens"].get(access_token)
    if user is None:
        raise AppError(401, "not_authenticated", "Wrong dev OIDC bearer token.")
    return web.json_response(user)


async def oidc_jwks(request: web.Request) -> web.Response:
    provider = request.app["dev_oidc_provider"]
    return web.json_response({"keys": [provider["public_jwk"]]})


def setup_dev_oidc_provider_routes(app: web.Application) -> None:
    app.router.add_get("/.well-known/openid-configuration", openid_configuration)
    app.router.add_get("/oidc/authorize", oidc_authorize)
    app.router.add_post("/oidc/token", oidc_token)
    app.router.add_get("/oidc/userinfo", oidc_userinfo)
    app.router.add_get("/oidc/jwks.json", oidc_jwks)
