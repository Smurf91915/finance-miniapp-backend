#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select


DEFAULT_TELEGRAM_ID = 448027141
DEFAULT_BOT_TOKEN = "test-bot-token"
DEFAULT_WEBHOOK_SECRET = "ci-webhook-secret"


class SmokeTestError(RuntimeError):
    pass


def configure_env() -> None:
    os.environ["BOT_TOKEN"] = os.environ.get("BOT_TOKEN", DEFAULT_BOT_TOKEN)
    os.environ["BOT_MODE"] = "webhook"
    os.environ["PUBLIC_BASE_URL"] = "https://example.invalid"
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = DEFAULT_WEBHOOK_SECRET
    os.environ["DEBUG"] = "false"
    os.environ["ALLOW_INSECURE_DEV_AUTH"] = "false"
    os.environ["DEFAULT_TELEGRAM_ID"] = str(DEFAULT_TELEGRAM_ID)


def build_signed_init_data(bot_token: str, telegram_id: int) -> str:
    user = {
        "id": telegram_id,
        "is_bot": False,
        "first_name": "CI",
        "username": "ci_smoke",
        "language_code": "ru",
    }
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items(), key=lambda item: item[0]))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(values)


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise SmokeTestError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_truthy(value: Any, message: str) -> None:
    if not value:
        raise SmokeTestError(message)


def main() -> int:
    configure_env()

    from fastapi.testclient import TestClient

    from app.bot.runtime import runtime
    from app.core.config import normalized_telegram_webhook_path
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import User

    delivered_updates: list[dict[str, Any]] = []

    async def fake_start_webhook_mode() -> None:
        return None

    async def fake_handle_webhook_update(payload: dict[str, Any]) -> None:
        delivered_updates.append(payload)

    runtime.start_webhook_mode = fake_start_webhook_mode
    runtime.handle_webhook_update = fake_handle_webhook_update

    with SessionLocal() as db:
        existing_user = db.scalar(select(User).where(User.telegram_id == DEFAULT_TELEGRAM_ID))
        if existing_user is None:
            db.add(
                User(
                    telegram_id=DEFAULT_TELEGRAM_ID,
                    name="Telegram Smoke",
                    timezone="Europe/Samara",
                    currency="RUB",
                )
            )
            db.commit()

    signed_init_data = build_signed_init_data(os.environ["BOT_TOKEN"], DEFAULT_TELEGRAM_ID)
    invalid_init_data = f"{signed_init_data}0"
    webhook_path = normalized_telegram_webhook_path()
    webhook_payload = {
        "update_id": 100001,
        "message": {
            "message_id": 1,
            "date": int(time.time()),
            "chat": {"id": DEFAULT_TELEGRAM_ID, "type": "private"},
            "from": {"id": DEFAULT_TELEGRAM_ID, "is_bot": False, "first_name": "CI"},
            "text": "/start",
        },
    }

    try:
        with TestClient(app) as client:
            valid_auth_response = client.get(
                "/api/v1/dashboard",
                headers={"X-Telegram-Init-Data": signed_init_data},
            )
            assert_equal(valid_auth_response.status_code, 200, "Signed Telegram auth should succeed")
            assert_equal(
                valid_auth_response.json()["available_minor"],
                0,
                "Signed Telegram auth dashboard response mismatch",
            )

            invalid_auth_response = client.get(
                "/api/v1/dashboard",
                headers={"X-Telegram-Init-Data": invalid_init_data},
            )
            assert_equal(invalid_auth_response.status_code, 401, "Invalid initData should be rejected")
            assert_equal(
                invalid_auth_response.json()["detail"],
                "Invalid initData signature",
                "Invalid initData error message mismatch",
            )

            missing_secret_response = client.post(webhook_path, json=webhook_payload)
            assert_equal(missing_secret_response.status_code, 403, "Webhook without secret should be rejected")
            assert_equal(
                missing_secret_response.json()["detail"],
                "Invalid webhook secret",
                "Missing webhook secret error message mismatch",
            )

            valid_webhook_response = client.post(
                webhook_path,
                json=webhook_payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": DEFAULT_WEBHOOK_SECRET},
            )
            assert_equal(valid_webhook_response.status_code, 200, "Webhook with valid secret should succeed")
            assert_equal(valid_webhook_response.text, "", "Webhook success body mismatch")
            assert_equal(len(delivered_updates), 1, "Webhook payload should be delivered exactly once")
            assert_equal(delivered_updates[0], webhook_payload, "Delivered webhook payload mismatch")

    except SmokeTestError as exc:
        print(f"telegram runtime smoke test failed: {exc}")
        return 1

    print("telegram runtime smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
