"""Application settings.

Loaded once at startup via ``get_settings()`` (cached). All env vars are
documented in ``.env.example``. Settings объект — единственный источник
конфигурации; никаких ``os.getenv`` в остальном коде.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT: Path = Path(__file__).resolve().parents[1]
REPO_ROOT: Path = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Конфигурация приложения, читается из ``.env`` и переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "tco-backend"
    app_version: str = "0.1.0"
    app_env: str = Field(default="dev", description="dev | staging | prod")
    app_log_level: str = "INFO"
    app_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = "postgresql+asyncpg://tco:tco@localhost:5432/tco"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 days

    jwt_algorithm: str = "HS256"
    jwt_secret: str = "change-me-in-prod-at-least-32-bytes-secret"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 14
    jwt_refresh_cookie_name: str = "refresh_token"
    jwt_refresh_cookie_path: str = "/api/auth"
    jwt_refresh_cookie_domain: str | None = None
    jwt_refresh_cookie_samesite: str = "strict"
    jwt_refresh_cookie_secure: bool = False

    auth_login_rate_limit_count: int = 5
    auth_login_rate_limit_window_sec: int = 5 * 60
    auth_register_rate_limit_count: int = 10
    auth_register_rate_limit_window_sec: int = 60 * 60
    auth_password_reset_rate_limit_count: int = 5
    auth_password_reset_rate_limit_window_sec: int = 60 * 60

    app_public_base_url: str = "http://localhost:8000"
    password_reset_delivery_mode: str = "log"  # log | smtp
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@example.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшированный геттер; во всех зависимостях используем именно его."""
    return Settings()
