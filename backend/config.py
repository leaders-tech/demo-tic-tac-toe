"""Load backend settings from .env and keep them in one Settings object.

Edit this file when env variables, ports, cookie names, or dev/prod defaults change.
Do not copy this file. Change it when the app configuration model changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_COOKIE_SECRET = "change-this-secret"


@dataclass(slots=True)
class Settings:
    mode: str
    host: str
    port: int
    db_path: Path
    cookie_secret: str
    frontend_origin: str
    public_base_url: str
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    dev_oidc_test_mode: bool = False
    access_cookie_name: str = "template_access"
    refresh_cookie_name: str = "template_refresh"
    access_ttl_seconds: int = 2 * 60 * 60
    refresh_ttl_seconds: int = 60 * 24 * 60 * 60

    @property
    def secure_cookies(self) -> bool:
        return self.mode == "prod"

    @property
    def allowed_origins(self) -> set[str]:
        origins = {self.frontend_origin.rstrip("/")}
        if self.mode != "prod":
            origins.add(self.public_base_url.rstrip("/"))
            parsed = urlsplit(self.frontend_origin)
            if parsed.hostname == "127.0.0.1":
                origins.add(urlunsplit((parsed.scheme, f"localhost:{parsed.port}", parsed.path, parsed.query, parsed.fragment)).rstrip("/"))
            if parsed.hostname == "localhost":
                origins.add(urlunsplit((parsed.scheme, f"127.0.0.1:{parsed.port}", parsed.path, parsed.query, parsed.fragment)).rstrip("/"))
        return origins

    @property
    def migrations_path(self) -> Path:
        return ROOT_DIR / "backend" / "migrations"

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer_url and self.oidc_client_id and self.oidc_client_secret)

    @property
    def oidc_callback_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/auth/oidc/callback"


def load_settings() -> Settings:
    load_dotenv()
    mode = os.getenv("APP_MODE", "dev").strip().lower()
    host = os.getenv("APP_HOST", "localhost").strip()
    port = int(os.getenv("APP_PORT", "8000"))
    db_path = Path(os.getenv("DB_PATH", "./dev.sqlite3")).expanduser()
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    cookie_secret = os.getenv("COOKIE_SECRET", DEFAULT_COOKIE_SECRET)
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")
    public_base_url = os.getenv("PUBLIC_BASE_URL", f"http://{host}:{port}").rstrip("/")
    oidc_issuer_url = os.getenv("OIDC_ISSUER_URL", "").strip() or None
    oidc_client_id = os.getenv("OIDC_CLIENT_ID", "").strip() or None
    oidc_client_secret = os.getenv("OIDC_CLIENT_SECRET", "").strip() or None
    dev_oidc_test_mode = os.getenv("DEV_OIDC_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    settings = Settings(
        mode=mode,
        host=host,
        port=port,
        db_path=db_path,
        cookie_secret=cookie_secret,
        frontend_origin=frontend_origin,
        public_base_url=public_base_url,
        oidc_issuer_url=oidc_issuer_url,
        oidc_client_id=oidc_client_id,
        oidc_client_secret=oidc_client_secret,
        dev_oidc_test_mode=dev_oidc_test_mode,
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if settings.mode == "prod" and settings.cookie_secret == DEFAULT_COOKIE_SECRET:
        raise ValueError("Refusing to start in prod with the default COOKIE_SECRET. Set a real secret in .env or your deploy env.")
    if settings.mode == "prod" and not settings.public_base_url.startswith("https://"):
        raise ValueError("Refusing to start in prod without an https PUBLIC_BASE_URL.")
    if settings.oidc_enabled:
        if settings.oidc_issuer_url is None or settings.oidc_client_id is None or settings.oidc_client_secret is None:
            raise ValueError("OIDC settings are incomplete.")
        if settings.mode == "prod" and not settings.oidc_issuer_url.startswith("https://"):
            raise ValueError("Refusing to start in prod without an https OIDC_ISSUER_URL.")
