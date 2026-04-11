import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int | None) -> dict[str, str]:
    pairs = parse_qsl(init_data, strict_parsing=True)
    values = dict(pairs)

    received_hash = values.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing hash in initData")

    auth_date = values.get("auth_date")
    if not auth_date:
        raise ValueError("Missing auth_date in initData")

    try:
        auth_timestamp = int(auth_date)
    except ValueError as exc:
        raise ValueError("Invalid auth_date in initData") from exc

    if max_age_seconds is not None and time.time() - auth_timestamp > max_age_seconds:
        raise ValueError("initData is expired")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items(), key=lambda item: item[0])
    )
    expected_hash = hmac.new(
        _secret_key(bot_token),
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Invalid initData signature")

    return values


def extract_telegram_user_id(init_data: str, bot_token: str, max_age_seconds: int | None) -> int:
    values = verify_init_data(init_data, bot_token, max_age_seconds)
    raw_user = values.get("user")
    if not raw_user:
        raise ValueError("Missing user in initData")

    user = json.loads(raw_user)
    user_id = user.get("id")
    if not isinstance(user_id, int):
        raise ValueError("Invalid user id in initData")
    return user_id
