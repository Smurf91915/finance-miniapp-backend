import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.bot.runtime import runtime
from app.core.config import (
    normalized_telegram_webhook_path,
    parsed_cors_origins,
    settings,
    validate_runtime_security,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO)
    validate_runtime_security()
    if settings.bot_mode == "webhook":
        await runtime.start_webhook_mode()
    yield
    await runtime.shutdown()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parsed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(normalized_telegram_webhook_path())
async def telegram_webhook(
    payload: dict,
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> Response:
    if settings.bot_mode != "webhook":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook mode is disabled")

    expected_secret = settings.telegram_webhook_secret
    if expected_secret and secret_token != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    try:
        await runtime.handle_webhook_update(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_200_OK)
