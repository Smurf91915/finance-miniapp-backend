from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Finance Mini App API"
    debug: bool = False
    database_url: str | None = None
    default_telegram_id: int | None = None
    backend_base_url: str = "http://127.0.0.1:8000/api/v1"
    bot_token: str | None = None
    telegram_proxy: str | None = None
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


def require_database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return settings.database_url
