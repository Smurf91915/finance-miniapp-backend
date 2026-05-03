from fastapi import APIRouter, Depends

from app.api.deps import require_internal_api_key
from app.bot.runtime import runtime
from app.core.config import settings, telegram_webhook_url


router = APIRouter(dependencies=[Depends(require_internal_api_key)])


@router.get("/webhook-status")
async def webhook_status() -> dict[str, object]:
    await runtime.initialize()
    assert runtime.bot is not None
    info = await runtime.bot.get_webhook_info()
    return {
        "bot_mode": settings.bot_mode,
        "webhook_url": telegram_webhook_url(),
        "telegram_webhook_url": info.url,
        "pending_update_count": info.pending_update_count,
        "has_custom_certificate": info.has_custom_certificate,
        "last_error_date": info.last_error_date.isoformat() if info.last_error_date else None,
        "last_error_message": info.last_error_message,
    }


@router.post("/setup-webhook")
async def setup_webhook() -> dict[str, object]:
    await runtime.configure_for_webhook()
    return await webhook_status()
