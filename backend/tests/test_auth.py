"""Test backend auth flows, roles, cookies, and auth-related CORS behavior.

Edit this file when login, refresh, logout, or admin-access behavior changes.
Copy a test pattern here when you add another auth rule or auth endpoint.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from aiohttp import web
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.auth.oidc import dump_jwk
from backend.auth.tokens import build_access_token
from backend.auth.passwords import hash_password, verify_password
from backend.config import DEFAULT_COOKIE_SECRET, Settings
from backend.db.refresh_sessions import count_sessions
from backend.db.seed import seed_dev_data
from backend.db.users import list_users
from backend.main import create_app, on_cleanup, on_startup
from backend.tests.conftest import login


def build_test_oidc_provider(
    *,
    issuer_url: str | None = None,
    claims_overrides: dict[str, object] | None = None,
    sign_with_wrong_key: bool = False,
) -> web.Application:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    provider: dict[str, object] = {
        "issuer_url": issuer_url or "",
        "server_base_url": "",
        "client_id": "oidc-client",
        "client_secret": "oidc-secret",
        "private_key": private_key,
        "wrong_private_key": wrong_private_key,
        "public_jwk": dump_jwk(private_key.public_key(), "test-key"),
        "codes": {},
        "access_tokens": {},
        "claims_overrides": claims_overrides or {},
        "sign_with_wrong_key": sign_with_wrong_key,
        "user": {
            "sub": "oidc-user-123",
            "email": "alex@example.com",
            "email_verified": True,
        },
    }

    async def discovery(request: web.Request) -> web.Response:
        issuer_url = str(provider["issuer_url"])
        return web.json_response(
            {
                "issuer": issuer_url,
                "authorization_endpoint": f"{issuer_url}/oidc/authorize",
                "token_endpoint": f"{issuer_url}/oidc/token",
                "userinfo_endpoint": f"{issuer_url}/oidc/userinfo",
                "jwks_uri": f"{issuer_url}/oidc/jwks.json",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "client_credentials"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "email", "profile"],
                "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
                "claims_supported": ["sub", "email", "email_verified"],
            }
        )

    async def authorize(request: web.Request) -> web.Response:
        redirect_uri = str(request.query["redirect_uri"])
        state = str(request.query["state"])
        code = f"code-{len(provider['codes']) + 1}"
        provider["codes"][code] = {
            "client_id": request.query["client_id"],
            "redirect_uri": redirect_uri,
            "nonce": request.query["nonce"],
        }
        return web.HTTPFound(f"{redirect_uri}?code={code}&state={state}")

    async def token(request: web.Request) -> web.Response:
        auth_header = request.headers.get("Authorization", "")
        assert auth_header.startswith("Basic ")
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
        client_id, client_secret = decoded.split(":", 1)
        form = await request.post()
        assert client_id == provider["client_id"]
        assert client_secret == provider["client_secret"]
        code = str(form["code"])
        code_data = provider["codes"].pop(code)
        now = datetime.now(tz=UTC)
        access_token = f"access-{code}"
        provider["access_tokens"][access_token] = provider["user"]
        claims = {
            "iss": provider["issuer_url"],
            "sub": provider["user"]["sub"],
            "aud": client_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "email": provider["user"]["email"],
            "email_verified": provider["user"]["email_verified"],
            "nonce": code_data["nonce"],
        }
        claims.update(provider["claims_overrides"])
        signing_key = provider["wrong_private_key"] if provider["sign_with_wrong_key"] else provider["private_key"]
        id_token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-key"})
        return web.json_response(
            {
                "access_token": access_token,
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 600,
                "scope": "openid email profile",
            }
        )

    async def userinfo(request: web.Request) -> web.Response:
        access_token = request.headers["Authorization"].split(" ", 1)[1]
        return web.json_response(provider["access_tokens"][access_token])

    async def jwks(request: web.Request) -> web.Response:
        return web.json_response({"keys": [provider["public_jwk"]]})

    app = web.Application()
    app.router.add_get("/.well-known/openid-configuration", discovery)
    app.router.add_get("/oidc/authorize", authorize)
    app.router.add_post("/oidc/token", token)
    app.router.add_get("/oidc/userinfo", userinfo)
    app.router.add_get("/oidc/jwks.json", jwks)
    app["provider_state"] = provider
    return app


def configure_oidc(client, issuer_url: str) -> None:
    configure_oidc_with_internal_base(client, issuer_url)


def configure_oidc_with_internal_base(client, issuer_url: str, internal_base_url: str | None = None) -> None:
    settings = client.app["settings"]
    settings.public_base_url = str(client.make_url("")).rstrip("/")
    settings.oidc_issuer_url = issuer_url.rstrip("/")
    settings.oidc_internal_base_url = internal_base_url.rstrip("/") if internal_base_url else None
    settings.oidc_client_id = "oidc-client"
    settings.oidc_client_secret = "oidc-secret"
    client.app["oidc_cache"].clear()


async def run_oidc_callback(client) -> tuple[object, str]:
    start_response = await client.get("/auth/oidc/start", allow_redirects=False)
    assert start_response.status == 302
    authorize_response = await client.session.get(start_response.headers["Location"], allow_redirects=False)
    assert authorize_response.status == 302
    callback_url = authorize_response.headers["Location"]
    callback_response = await client.session.get(callback_url, allow_redirects=False)
    return callback_response, callback_url


async def run_oidc_callback_with_manual_provider(client, provider_server) -> tuple[object, str]:
    from backend.auth.oidc import create_oidc_flow_cookie

    settings = client.app["settings"]
    flow_cookie_value, state, nonce = create_oidc_flow_cookie(settings)
    authorize_response = await client.session.get(
        f"{str(provider_server.make_url('')).rstrip('/')}/oidc/authorize",
        params={
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": settings.oidc_callback_url,
            "state": state,
            "nonce": nonce,
        },
        allow_redirects=False,
    )
    assert authorize_response.status == 302
    callback_url = authorize_response.headers["Location"]
    callback_response = await client.session.get(
        callback_url,
        allow_redirects=False,
        cookies={"template_oidc_flow": flow_cookie_value},
    )
    return callback_response, callback_url


def test_password_hashing() -> None:
    password_hash = hash_password("secret")
    assert password_hash != "secret"
    assert verify_password(password_hash, "secret") is True
    assert verify_password(password_hash, "wrong") is False


@pytest.mark.asyncio
async def test_login_success_and_me(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    response = await client.post("/auth/login", json={"username": "user", "password": "user"}, headers=auth_headers)
    assert response.status == 200
    payload = await response.json()
    assert payload["ok"] is True
    assert payload["data"]["user"]["username"] == "user"

    me_response = await client.post("/auth/me", json={})
    assert me_response.status == 200


@pytest.mark.asyncio
async def test_login_invalid_credentials(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    response = await client.post("/auth/login", json={"username": "user", "password": "wrong"}, headers=auth_headers)
    assert response.status == 401


@pytest.mark.asyncio
async def test_requires_auth(client) -> None:
    response = await client.post("/notes/list", json={})
    assert response.status == 401


@pytest.mark.asyncio
async def test_tampered_access_cookie_returns_401(client, create_user, auth_headers, extract_cookie) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    access_cookie = extract_cookie(client, "template_access", "/")

    response = await client.post("/auth/me", json={}, cookies={"template_access": f"{access_cookie}tampered"})
    assert response.status == 401


@pytest.mark.asyncio
async def test_expired_access_cookie_returns_401(client, create_user) -> None:
    await create_user("user", "user")
    expired_settings = Settings(
        mode="test",
        host="127.0.0.1",
        port=8081,
        db_path=client.app["settings"].db_path,
        cookie_secret=client.app["settings"].cookie_secret,
        frontend_origin=client.app["settings"].frontend_origin,
        public_base_url=client.app["settings"].public_base_url,
        access_ttl_seconds=-1,
    )
    expired_token = build_access_token(
        expired_settings,
        {
            "id": 1,
            "username": "user",
            "is_admin": False,
        },
    )

    response = await client.post("/auth/me", json={}, cookies={"template_access": expired_token})
    assert response.status == 401


@pytest.mark.asyncio
async def test_auth_error_keeps_cors_headers_for_localhost_origin(client) -> None:
    response = await client.post("/auth/me", json={}, headers={"Origin": "http://localhost:5173"})
    assert response.status == 401
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


@pytest.mark.asyncio
async def test_admin_forbidden_for_normal_user(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    response = await client.post("/admin/users/list", json={})
    assert response.status == 403


@pytest.mark.asyncio
async def test_non_json_write_request_returns_400(client, create_user, auth_headers) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)

    response = await client.post(
        "/notes/save",
        data="text=bad",
        headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status == 400


@pytest.mark.asyncio
async def test_refresh_rotates_token(client, create_user, auth_headers, extract_cookie) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    first_refresh = extract_cookie(client, "template_refresh")

    refresh_response = await client.post("/auth/refresh", json={}, headers=auth_headers)
    assert refresh_response.status == 200
    second_refresh = extract_cookie(client, "template_refresh")
    assert second_refresh != first_refresh

    invalid_response = await client.post(
        "/auth/refresh",
        json={},
        headers=auth_headers,
        cookies={"template_refresh": first_refresh},
    )
    assert invalid_response.status == 401


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_session(client, create_user, auth_headers, extract_cookie, db) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    first_refresh = extract_cookie(client, "template_refresh")

    refresh_response = await client.post("/auth/refresh", json={}, headers=auth_headers)
    assert refresh_response.status == 200
    assert await count_sessions(db) == 1

    invalid_response = await client.post(
        "/auth/refresh",
        json={},
        headers=auth_headers,
        cookies={"template_refresh": first_refresh},
    )
    assert invalid_response.status == 401
    assert await count_sessions(db) == 0


@pytest.mark.asyncio
async def test_expired_refresh_session_returns_401_and_deletes_session(client, create_user, auth_headers, db) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    assert await count_sessions(db) == 1

    expired_at = (datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat(timespec="seconds")
    await db.execute("UPDATE refresh_sessions SET expires_at = ? WHERE id IS NOT NULL", (expired_at,))
    await db.commit()

    response = await client.post("/auth/refresh", json={}, headers=auth_headers)
    assert response.status == 401
    assert await count_sessions(db) == 0


@pytest.mark.asyncio
async def test_logout_removes_refresh_session(client, create_user, auth_headers, db) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    assert await count_sessions(db) == 1

    response = await client.post("/auth/logout", json={}, headers=auth_headers)
    assert response.status == 200
    assert await count_sessions(db) == 0


@pytest.mark.asyncio
async def test_bootstrap_returns_null_when_anonymous(client) -> None:
    response = await client.post("/auth/bootstrap", json={})
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["user"] is None


@pytest.mark.asyncio
async def test_bootstrap_restores_user_from_refresh_cookie(client, create_user, auth_headers, extract_cookie) -> None:
    await create_user("user", "user")
    await login(client, "user", "user", auth_headers)
    refresh_cookie = extract_cookie(client, "template_refresh")
    client.session.cookie_jar.clear()

    response = await client.post("/auth/bootstrap", json={}, cookies={"template_refresh": refresh_cookie})
    assert response.status == 200
    payload = await response.json()
    assert payload["data"]["user"]["username"] == "user"


@pytest.mark.asyncio
async def test_auth_options_reports_oidc_disabled_by_default(client) -> None:
    response = await client.post("/auth/options", json={})
    assert response.status == 200
    payload = await response.json()
    assert payload["data"] == {"oidc_enabled": False, "oidc_login_url": None}


@pytest.mark.asyncio
async def test_oidc_start_redirects_to_provider_and_sets_flow_cookie(client, aiohttp_server, extract_cookie) -> None:
    provider_app = build_test_oidc_provider()
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    response = await client.get("/auth/oidc/start", allow_redirects=False)

    assert response.status == 302
    assert response.headers["Location"].startswith(f"{provider_app['provider_state']['issuer_url']}/oidc/authorize?")
    assert extract_cookie(client, "template_oidc_flow", "/auth/oidc")


@pytest.mark.asyncio
async def test_oidc_start_uses_public_authorize_url_when_backend_uses_internal_base(client, aiohttp_server, extract_cookie) -> None:
    provider_app = build_test_oidc_provider(issuer_url="https://auth.example.test")
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    configure_oidc_with_internal_base(
        client,
        str(provider_app["provider_state"]["issuer_url"]),
        provider_app["provider_state"]["server_base_url"],
    )

    response = await client.get("/auth/oidc/start", allow_redirects=False)

    assert response.status == 302
    assert response.headers["Location"].startswith("https://auth.example.test/oidc/authorize?")
    assert extract_cookie(client, "template_oidc_flow", "/auth/oidc")


@pytest.mark.asyncio
async def test_oidc_callback_rejects_missing_or_bad_state(client, aiohttp_server) -> None:
    provider_app = build_test_oidc_provider()
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    response = await client.get("/auth/oidc/callback?code=anything&state=wrong", allow_redirects=False)
    assert response.status == 302
    assert response.headers["Location"] == "http://127.0.0.1:5173/login?error=oidc_state_invalid"

    await client.get("/auth/oidc/start", allow_redirects=False)
    bad_state_response = await client.get("/auth/oidc/callback?code=anything&state=wrong", allow_redirects=False)
    assert bad_state_response.status == 302
    assert bad_state_response.headers["Location"] == "http://127.0.0.1:5173/login?error=oidc_state_invalid"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("claims_overrides", "sign_with_wrong_key"),
    [
        ({"iss": "http://wrong-issuer.example"}, False),
        ({"aud": "wrong-client"}, False),
        ({"nonce": "wrong-nonce"}, False),
        ({"exp": 1}, False),
        ({}, True),
    ],
)
async def test_oidc_callback_rejects_invalid_tokens(client, aiohttp_server, claims_overrides, sign_with_wrong_key) -> None:
    provider_app = build_test_oidc_provider(claims_overrides=claims_overrides, sign_with_wrong_key=sign_with_wrong_key)
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    callback_response, _ = await run_oidc_callback(client)

    assert callback_response.status == 302
    assert callback_response.headers["Location"] == "http://127.0.0.1:5173/login?error=oidc_login_failed"


@pytest.mark.asyncio
async def test_oidc_first_login_auto_creates_user_and_session(client, aiohttp_server, db) -> None:
    provider_app = build_test_oidc_provider()
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    callback_response, _ = await run_oidc_callback(client)

    assert callback_response.status == 302
    assert callback_response.headers["Location"] == "http://127.0.0.1:5173/lobby"
    assert await count_sessions(db) == 1
    users = await list_users(db)
    assert [user["username"] for user in users] == ["alex"]

    me_response = await client.post("/auth/me", json={})
    assert me_response.status == 200
    payload = await me_response.json()
    assert payload["data"]["user"]["username"] == "alex"
    assert payload["data"]["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_oidc_repeated_login_reuses_linked_user(client, aiohttp_server, db) -> None:
    provider_app = build_test_oidc_provider()
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    first_response, _ = await run_oidc_callback(client)
    assert first_response.status == 302

    await client.post("/auth/logout", json={}, headers={"Origin": "http://127.0.0.1:5173"})
    second_response, _ = await run_oidc_callback(client)
    assert second_response.status == 302

    users = await list_users(db)
    assert [user["username"] for user in users] == ["alex"]
    assert await count_sessions(db) == 1


@pytest.mark.asyncio
async def test_oidc_logged_in_user_is_not_admin_by_default(client, aiohttp_server) -> None:
    provider_app = build_test_oidc_provider()
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    provider_app["provider_state"]["issuer_url"] = provider_app["provider_state"]["server_base_url"]
    configure_oidc(client, provider_app["provider_state"]["issuer_url"])

    callback_response, _ = await run_oidc_callback(client)
    assert callback_response.status == 302

    response = await client.post("/admin/users/list", json={})
    assert response.status == 403


@pytest.mark.asyncio
async def test_oidc_callback_uses_internal_base_for_server_side_requests(client, aiohttp_server, db) -> None:
    provider_app = build_test_oidc_provider(issuer_url="https://auth.example.test")
    provider_server = await aiohttp_server(provider_app)
    provider_app["provider_state"]["server_base_url"] = str(provider_server.make_url("")).rstrip("/")
    configure_oidc_with_internal_base(
        client,
        str(provider_app["provider_state"]["issuer_url"]),
        provider_app["provider_state"]["server_base_url"],
    )

    callback_response, _ = await run_oidc_callback_with_manual_provider(client, provider_server)

    assert callback_response.status == 302
    assert callback_response.headers["Location"] == "http://127.0.0.1:5173/lobby"
    assert await count_sessions(db) == 1
    users = await list_users(db)
    assert [user["username"] for user in users] == ["alex"]


@pytest.mark.asyncio
async def test_dev_seed_only_creates_missing_users(tmp_path, monkeypatch) -> None:
    settings = Settings(
        mode="dev",
        host="127.0.0.1",
        port=8081,
        db_path=tmp_path / "seed.sqlite3",
        cookie_secret="test-secret",
        frontend_origin="http://127.0.0.1:5173",
        public_base_url="http://127.0.0.1:8081",
    )
    app = create_app(settings)
    calls: list[str] = []

    def fake_hash_password(password: str) -> str:
        calls.append(password)
        return f"hashed:{password}"

    monkeypatch.setattr("backend.db.seed.hash_password", fake_hash_password)

    try:
        await on_startup(app)
        assert calls == ["user", "admin", "viewer", "nikita", "elias", "alex"]
        await seed_dev_data(app["db"], settings)
        users = await list_users(app["db"])
        assert [user["username"] for user in users] == ["user", "admin", "viewer", "nikita", "elias", "alex"]
        assert calls == ["user", "admin", "viewer", "nikita", "elias", "alex"]
    finally:
        await on_cleanup(app)


def test_create_app_refuses_default_secret_in_prod(tmp_path) -> None:
    settings = Settings(
        mode="prod",
        host="127.0.0.1",
        port=8081,
        db_path=tmp_path / "prod.sqlite3",
        cookie_secret=DEFAULT_COOKIE_SECRET,
        frontend_origin="http://127.0.0.1:5173",
        public_base_url="https://example.test",
    )

    with pytest.raises(ValueError, match="default COOKIE_SECRET"):
        create_app(settings)
