#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib import error, parse, request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TELEGRAM_ID = 448027140


class SmokeTestError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiClient:
    base_url: str
    telegram_id: int

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected_status: int = 200,
    ) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "X-Telegram-Id": str(self.telegram_id),
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                body = response.read().decode("utf-8")
                status_code = response.getcode()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SmokeTestError(f"{method} {path} failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise SmokeTestError(f"{method} {path} failed: {exc.reason}") from exc

        if status_code != expected_status:
            raise SmokeTestError(f"{method} {path} returned HTTP {status_code}, expected {expected_status}")

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SmokeTestError(f"{method} {path} returned non-JSON payload: {body}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local API smoke tests against a running backend instance.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL, without /api/v1 suffix.")
    parser.add_argument(
        "--telegram-id",
        type=int,
        default=DEFAULT_TELEGRAM_ID,
        help="Telegram user id to pass via insecure dev auth header.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise SmokeTestError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_truthy(value: Any, message: str) -> None:
    if not value:
        raise SmokeTestError(message)


def main() -> int:
    args = parse_args()
    client = ApiClient(base_url=args.base_url.rstrip("/"), telegram_id=args.telegram_id)
    api_prefix = "/api/v1"
    occurred_at = utc_now()

    try:
        category = client.request_json(
            "POST",
            f"{api_prefix}/categories",
            {
                "kind": "expense",
                "name": "CI Smoke Expenses",
                "sort_order": 999,
            },
        )
        category_id = category["id"]

        subcategory = client.request_json(
            "POST",
            f"{api_prefix}/categories/subcategories",
            {
                "category_id": category_id,
                "name": "CI Coffee",
                "sort_order": 999,
            },
        )
        subcategory_id = subcategory["id"]

        expense = client.request_json(
            "POST",
            f"{api_prefix}/transactions/expense",
            {
                "amount_minor": 32000,
                "currency": "RUB",
                "occurred_at": occurred_at,
                "category_id": category_id,
                "subcategory_id": subcategory_id,
                "note": "CI smoke coffee",
                "source": "ci_smoke",
            },
        )
        expense_id = expense["id"]
        assert_equal(expense["type"], "expense", "Created transaction type mismatch")
        assert_equal(expense["subcategory_id"], subcategory_id, "Expense subcategory mismatch")

        updated_expense = client.request_json(
            "PATCH",
            f"{api_prefix}/transactions/{expense_id}",
            {
                "amount_minor": 35000,
                "note": "CI smoke coffee updated",
                "occurred_at": occurred_at,
            },
        )
        assert_equal(updated_expense["amount_minor"], 35000, "Expense update amount mismatch")
        assert_equal(updated_expense["note"], "CI smoke coffee updated", "Expense update note mismatch")

        refund = client.request_json(
            "POST",
            f"{api_prefix}/transactions/{expense_id}/refund",
            {
                "amount_minor": 5000,
                "currency": "RUB",
                "occurred_at": occurred_at,
                "note": "CI smoke refund",
                "source": "ci_smoke",
            },
        )
        assert_equal(refund["type"], "refund", "Refund transaction type mismatch")
        assert_equal(refund["linked_transaction_id"], expense_id, "Refund linkage mismatch")

        recurring = client.request_json(
            "POST",
            f"{api_prefix}/recurring-expenses/from-transaction/{expense_id}",
        )
        recurring_id = recurring["id"]
        assert_equal(recurring["category_id"], category_id, "Recurring category mismatch")
        assert_equal(recurring["subcategory_id"], subcategory_id, "Recurring subcategory mismatch")
        assert_equal(recurring["expected_amount_minor"], 35000, "Recurring amount mismatch")

        updated_recurring = client.request_json(
            "PATCH",
            f"{api_prefix}/recurring-expenses/{recurring_id}",
            {
                "is_active": False,
                "expected_amount_minor": 36000,
                "note": "CI smoke recurring updated",
            },
        )
        assert_equal(updated_recurring["is_active"], False, "Recurring active flag mismatch")
        assert_equal(updated_recurring["expected_amount_minor"], 36000, "Recurring update amount mismatch")
        assert_equal(updated_recurring["note"], "CI smoke recurring updated", "Recurring update note mismatch")

        listed_transactions = client.request_json("GET", f"{api_prefix}/transactions?limit=20")
        assert_truthy(
            any(item["id"] == expense_id and item["amount_minor"] == 35000 for item in listed_transactions),
            "Updated expense not found in transaction list",
        )
        assert_truthy(
            any(item["id"] == refund["id"] and item["linked_transaction_id"] == expense_id for item in listed_transactions),
            "Refund not found in transaction list",
        )

        listed_recurring = client.request_json("GET", f"{api_prefix}/recurring-expenses")
        recurring_item = next((item for item in listed_recurring if item["id"] == recurring_id), None)
        assert_truthy(recurring_item, "Recurring expense not found in recurring list")
        assert_equal(recurring_item["is_active"], False, "Recurring list active flag mismatch")

    except SmokeTestError as exc:
        print(f"api smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("api smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
