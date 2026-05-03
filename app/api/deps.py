import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.telegram_auth import extract_telegram_user_id
from app.db.session import SessionLocal
from app.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_telegram_id: int | None = Header(default=None, alias="X-Telegram-Id"),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
) -> User:
    if x_telegram_init_data:
        if not settings.bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="BOT_TOKEN is not configured for Telegram auth",
            )
        try:
            telegram_id = extract_telegram_user_id(
                x_telegram_init_data,
                settings.bot_token,
                settings.telegram_init_data_ttl_seconds,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
    elif x_internal_api_key:
        if not settings.internal_api_key or not hmac.compare_digest(
            x_internal_api_key,
            settings.internal_api_key,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid internal API key",
            )
        if x_telegram_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Telegram user id for internal request",
            )
        telegram_id = x_telegram_id
    elif settings.allow_insecure_dev_auth:
        telegram_id = x_telegram_id or settings.default_telegram_id
        if telegram_id is None:
            raise HTTPException(status_code=401, detail="Missing Telegram auth header")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signed Telegram auth header",
        )

    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
) -> None:
    if not x_internal_api_key or not settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal API key",
        )
    if not hmac.compare_digest(x_internal_api_key, settings.internal_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
