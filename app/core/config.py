from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Finance Mini App API"
    debug: bool = False
    database_url: str | None = None
    default_telegram_id: int | None = None
    port: int = 8000
    backend_base_url: str | None = None
    bot_token: str | None = None
    bot_mode: Literal["polling", "webhook"] = "polling"
    telegram_proxy: str | None = None
    public_base_url: str | None = None
    telegram_webhook_path: str = "/telegram/webhook"
    telegram_webhook_secret: str | None = None
    mini_app_url: str | None = None
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    telegram_init_data_ttl_seconds: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


def parsed_cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def resolved_backend_base_url() -> str:
    internal_base_url = f"http://127.0.0.1:{settings.port}/api/v1"
    configured_base_url = settings.backend_base_url.rstrip("/") if settings.backend_base_url else None
    public_base_url = normalized_public_base_url()

    if settings.bot_mode == "webhook":
        if configured_base_url and configured_base_url not in {
            "http://127.0.0.1:8000/api/v1",
            "http://localhost:8000/api/v1",
        }:
            return configured_base_url

        if public_base_url:
            return f"{public_base_url}/api/v1"

        return internal_base_url

    if configured_base_url:
        return configured_base_url

    return internal_base_url


def normalized_public_base_url() -> str | None:
    if not settings.public_base_url:
        return None
    return settings.public_base_url.rstrip("/")


def normalized_telegram_webhook_path() -> str:
    path = settings.telegram_webhook_path.strip() or "/telegram/webhook"
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def telegram_webhook_url() -> str | None:
    base_url = normalized_public_base_url()
    if not base_url:
        return None
    return f"{base_url}{normalized_telegram_webhook_path()}"


def require_database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return settings.database_url
