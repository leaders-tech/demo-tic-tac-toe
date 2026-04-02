"""Provide shared backend test fixtures for the aiohttp test app and test database.

Edit this file when many backend tests need the same fixture or helper.
Copy fixture patterns here when you add another shared backend test helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from yarl import URL

from backend.auth.passwords import hash_password
from backend.config import Settings
from backend.db.users import create_user_if_missing
from backend.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        mode="test",
        host="127.0.0.1",
        port=8081,
        db_path=tmp_path / "test.sqlite3",
        cookie_secret="test-secret",
        frontend_origin="http://127.0.0.1:5173",
    )


@pytest.fixture
async def app(test_settings: Settings):
    return create_app(test_settings)


@pytest.fixture
async def client(aiohttp_client, app) -> TestClient:
    return await aiohttp_client(app)


@pytest.fixture
async def db(app):
    return app["db"]


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture
def create_user(db) -> Callable[[str, str, bool], Awaitable[None]]:
    async def _create_user(username: str, password: str, is_admin: bool = False) -> None:
        await create_user_if_missing(db, username, hash_password(password), is_admin)

    return _create_user


@pytest.fixture
def extract_cookie() -> Callable[[TestClient, str, str], str]:
    def _extract_cookie(client: TestClient, name: str, path: str = "/auth/refresh") -> str:
        cookie = client.session.cookie_jar.filter_cookies(URL(f"http://127.0.0.1:8081{path}")).get(name)
        assert cookie is not None
        return cookie.value

    return _extract_cookie


async def login(client: TestClient, username: str, password: str, headers: dict[str, str]) -> None:
    response = await client.post("/auth/login", json={"username": username, "password": password}, headers=headers)
    assert response.status == 200
