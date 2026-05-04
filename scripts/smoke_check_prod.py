#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import parse


DEFAULT_TIMEOUT_SECONDS = 20.0


class SmokeCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str | None
    bot_token: str
    webhook_path: str
    timeout_seconds: float
    backend_base_url: str | None

    @property
    def expected_webhook_url(self) -> str:
        if not self.base_url:
            raise SmokeCheckError("Base URL is not resolved")
        return f"{self.base_url}{self.webhook_path}"

    @property
    def healthcheck_url(self) -> str:
        if not self.base_url:
            raise SmokeCheckError("Base URL is not resolved")
        return f"{self.base_url}/health"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production smoke checks for backend health and Telegram webhook binding."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the backend .env file used to resolve BOT_TOKEN and PUBLIC_BASE_URL.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override PUBLIC_BASE_URL from .env.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds for each request.",
    )
    return parser.parse_args()


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SmokeCheckError(f".env file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def resolve_config(args: argparse.Namespace) -> Config:
    env_file = Path(args.env_file)
    dotenv_values = load_dotenv(env_file)

    base_url = args.base_url or os.environ.get("PUBLIC_BASE_URL") or dotenv_values.get("PUBLIC_BASE_URL")
    if base_url:
        base_url = base_url.rstrip("/")

    bot_token = os.environ.get("BOT_TOKEN") or dotenv_values.get("BOT_TOKEN")
    if not bot_token:
        raise SmokeCheckError("BOT_TOKEN is not configured in environment or .env")

    backend_base_url = os.environ.get("BACKEND_BASE_URL") or dotenv_values.get("BACKEND_BASE_URL")
    if backend_base_url:
        backend_base_url = backend_base_url.rstrip("/")

    webhook_path = (
        os.environ.get("TELEGRAM_WEBHOOK_PATH")
        or dotenv_values.get("TELEGRAM_WEBHOOK_PATH")
        or "/telegram/webhook"
    ).strip()
    if not webhook_path.startswith("/"):
        webhook_path = f"/{webhook_path}"

    return Config(
        base_url=base_url,
        bot_token=bot_token,
        webhook_path=webhook_path,
        timeout_seconds=args.timeout,
        backend_base_url=backend_base_url,
    )


def fetch_json(url: str, timeout_seconds: float, label: str) -> tuple[int, object]:
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout_seconds),
        "--write-out",
        "\n%{http_code}",
        "--url",
        url,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise SmokeCheckError(f"curl failed for {label}: {stderr}")

    payload, separator, status_code_text = completed.stdout.rpartition("\n")
    if not separator:
        raise SmokeCheckError(f"Malformed curl response for {label}")

    try:
        status_code = int(status_code_text.strip())
    except ValueError as exc:
        raise SmokeCheckError(f"Malformed HTTP status for {label}: {status_code_text!r}") from exc

    try:
        return status_code, json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SmokeCheckError(f"Non-JSON response from {label}: {payload}") from exc


def check_health(config: Config) -> None:
    status_code, payload = fetch_json(config.healthcheck_url, config.timeout_seconds, "backend healthcheck")
    if status_code != 200:
        raise SmokeCheckError(f"Healthcheck returned HTTP {status_code}")
    if payload != {"status": "ok"}:
        raise SmokeCheckError(f"Unexpected healthcheck body: {payload!r}")

    print(f"health ok: {config.healthcheck_url}")


def check_telegram_webhook(config: Config) -> None:
    telegram_url = f"https://api.telegram.org/bot{parse.quote(config.bot_token, safe='')}/getWebhookInfo"
    _, payload = fetch_json(telegram_url, config.timeout_seconds, "Telegram getWebhookInfo")

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SmokeCheckError("Telegram getWebhookInfo did not return ok=true")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise SmokeCheckError("Telegram getWebhookInfo payload is missing result")

    actual_url = result.get("url") or ""
    expected_url = config.expected_webhook_url
    if actual_url != expected_url:
        raise SmokeCheckError(
            "Telegram webhook URL mismatch: "
            f"expected {expected_url!r}, got {actual_url!r}"
        )

    pending_update_count = result.get("pending_update_count")
    print(
        "telegram webhook ok: "
        f"{expected_url} (pending_update_count={pending_update_count})"
    )


def derive_base_url(config: Config) -> str:
    if config.base_url:
        return config.base_url

    if config.backend_base_url:
        candidate = derive_base_url_from_backend_api(config.backend_base_url)
        if candidate:
            return candidate

    webhook_url = fetch_current_webhook_url(config)
    if webhook_url:
        return derive_base_url_from_webhook_url(webhook_url)

    raise SmokeCheckError(
        "Base URL could not be resolved from PUBLIC_BASE_URL, BACKEND_BASE_URL, or current Telegram webhook"
    )


def fetch_current_webhook_url(config: Config) -> str:
    telegram_url = f"https://api.telegram.org/bot{parse.quote(config.bot_token, safe='')}/getWebhookInfo"
    _, payload = fetch_json(telegram_url, config.timeout_seconds, "Telegram getWebhookInfo")

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SmokeCheckError("Telegram getWebhookInfo did not return ok=true")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise SmokeCheckError("Telegram getWebhookInfo payload is missing result")

    return str(result.get("url") or "")


def derive_base_url_from_backend_api(backend_base_url: str) -> str | None:
    parsed_url = parse.urlsplit(backend_base_url)
    if parsed_url.scheme not in {"http", "https"}:
        return None
    if parsed_url.hostname in {"127.0.0.1", "localhost"}:
        return None

    path = parsed_url.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[: -len("/api/v1")]
    if path and path != "/":
        return None

    return parse.urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", ""))


def derive_base_url_from_webhook_url(webhook_url: str) -> str:
    parsed_url = parse.urlsplit(webhook_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise SmokeCheckError(f"Current Telegram webhook URL is invalid: {webhook_url!r}")
    return parse.urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", ""))


def main() -> int:
    try:
        config = resolve_config(parse_args())
        config = Config(
            base_url=derive_base_url(config),
            bot_token=config.bot_token,
            webhook_path=config.webhook_path,
            timeout_seconds=config.timeout_seconds,
            backend_base_url=config.backend_base_url,
        )
        check_health(config)
        check_telegram_webhook(config)
    except SmokeCheckError as exc:
        print(f"smoke check failed: {exc}", file=sys.stderr)
        return 1

    print("production smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
