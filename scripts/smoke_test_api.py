#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib import error, request


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


def utc_at(offset_seconds: int = 0) -> str:
    value = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=offset_seconds)
    return value.isoformat().replace("+00:00", "Z")


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

    try:
        expense_category = client.request_json(
            "POST",
            f"{api_prefix}/categories",
            {
                "kind": "expense",
                "name": "CI Smoke Expenses",
                "sort_order": 999,
            },
        )
        expense_category_id = expense_category["id"]

        subcategory = client.request_json(
            "POST",
            f"{api_prefix}/categories/subcategories",
            {
                "category_id": expense_category_id,
                "name": "CI Coffee",
                "sort_order": 999,
            },
        )
        subcategory_id = subcategory["id"]

        investment_category = client.request_json(
            "POST",
            f"{api_prefix}/categories",
            {
                "kind": "investment",
                "name": "Облигации",
                "sort_order": 998,
            },
        )
        investment_category_id = investment_category["id"]

        reserve_goal = client.request_json(
            "POST",
            f"{api_prefix}/goals",
            {
                "kind": "reserve",
                "name": "CI Reserve",
                "target_amount_minor": 200000,
                "sort_order": 999,
            },
        )
        reserve_goal_id = reserve_goal["id"]

        deposit_goal = client.request_json(
            "POST",
            f"{api_prefix}/goals",
            {
                "kind": "deposit",
                "name": "CI Deposit",
                "target_amount_minor": 300000,
                "sort_order": 998,
            },
        )
        deposit_goal_id = deposit_goal["id"]

        expense = client.request_json(
            "POST",
            f"{api_prefix}/transactions/expense",
            {
                "amount_minor": 32000,
                "currency": "RUB",
                "occurred_at": utc_at(0),
                "category_id": expense_category_id,
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
                "occurred_at": utc_at(1),
            },
        )
        assert_equal(updated_expense["amount_minor"], 35000, "Expense update amount mismatch")
        assert_equal(updated_expense["note"], "CI smoke coffee updated", "Expense update note mismatch")

        income_transactions = client.request_json(
            "POST",
            f"{api_prefix}/transactions/income",
            {
                "amount_minor": 120000,
                "currency": "RUB",
                "occurred_at": utc_at(2),
                "note": "CI salary",
                "reserve_amount_minor": 20000,
                "source": "ci_smoke",
            },
        )
        assert_equal(len(income_transactions), 2, "Income with reserve should create two transactions")
        income_transaction = next((item for item in income_transactions if item["type"] == "income"), None)
        reserve_allocation = next(
            (item for item in income_transactions if item["type"] == "goal_allocation"),
            None,
        )
        assert_truthy(income_transaction, "Income transaction is missing from create income response")
        assert_truthy(reserve_allocation, "Reserve allocation is missing from create income response")
        assert_equal(reserve_allocation["goal_id"], reserve_goal_id, "Reserve allocation goal mismatch")
        assert_equal(
            reserve_allocation["linked_transaction_id"],
            income_transaction["id"],
            "Reserve allocation linkage mismatch",
        )

        direct_goal_allocation = client.request_json(
            "POST",
            f"{api_prefix}/transactions/goals/{deposit_goal_id}/allocate",
            {
                "amount_minor": 15000,
                "currency": "RUB",
                "occurred_at": utc_at(3),
                "note": "CI deposit top-up",
                "source": "ci_smoke",
            },
        )
        assert_equal(direct_goal_allocation["type"], "goal_allocation", "Goal allocation type mismatch")
        assert_equal(direct_goal_allocation["goal_id"], deposit_goal_id, "Goal allocation goal mismatch")

        refund = client.request_json(
            "POST",
            f"{api_prefix}/transactions/{expense_id}/refund",
            {
                "amount_minor": 5000,
                "currency": "RUB",
                "occurred_at": utc_at(4),
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
        assert_equal(recurring["category_id"], expense_category_id, "Recurring category mismatch")
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

        parsed_income = client.request_json(
            "POST",
            f"{api_prefix}/transactions/parse",
            {"text": "зарплата 1500"},
        )
        assert_equal(parsed_income["type"], "income", "Parsed income type mismatch")
        assert_equal(parsed_income["amount_minor"], 150000, "Parsed income amount mismatch")

        parsed_investment = client.request_json(
            "POST",
            f"{api_prefix}/transactions/parse",
            {"text": "облигации 2300"},
        )
        assert_equal(parsed_investment["type"], "investment", "Parsed investment type mismatch")
        assert_equal(parsed_investment["category_id"], investment_category_id, "Parsed investment category mismatch")

        parsed_deposit = client.request_json(
            "POST",
            f"{api_prefix}/transactions/parse",
            {"text": "вклад 1700"},
        )
        assert_equal(parsed_deposit["type"], "goal_allocation", "Parsed deposit type mismatch")
        assert_equal(parsed_deposit["goal_id"], deposit_goal_id, "Parsed deposit goal mismatch")

        parsed_reserve = client.request_json(
            "POST",
            f"{api_prefix}/transactions/parse",
            {"text": "запас 900"},
        )
        assert_equal(parsed_reserve["type"], "goal_allocation", "Parsed reserve type mismatch")
        assert_equal(parsed_reserve["goal_id"], reserve_goal_id, "Parsed reserve goal mismatch")

        parsed_default_expense = client.request_json(
            "POST",
            f"{api_prefix}/transactions/parse",
            {"text": "кофе 320"},
        )
        assert_equal(parsed_default_expense["type"], "expense", "Parsed default expense type mismatch")
        assert_equal(parsed_default_expense["amount_minor"], 32000, "Parsed default expense amount mismatch")

        listed_transactions = client.request_json("GET", f"{api_prefix}/transactions?limit=20")
        assert_truthy(
            any(item["id"] == expense_id and item["amount_minor"] == 35000 for item in listed_transactions),
            "Updated expense not found in transaction list",
        )
        assert_truthy(
            any(item["id"] == refund["id"] and item["linked_transaction_id"] == expense_id for item in listed_transactions),
            "Refund not found in transaction list",
        )
        assert_truthy(
            any(item["id"] == income_transaction["id"] and item["type"] == "income" for item in listed_transactions),
            "Income transaction not found in transaction list",
        )
        assert_truthy(
            any(
                item["id"] == direct_goal_allocation["id"] and item["goal_id"] == deposit_goal_id
                for item in listed_transactions
            ),
            "Direct goal allocation not found in transaction list",
        )

        listed_recurring = client.request_json("GET", f"{api_prefix}/recurring-expenses")
        recurring_item = next((item for item in listed_recurring if item["id"] == recurring_id), None)
        assert_truthy(recurring_item, "Recurring expense not found in recurring list")
        assert_equal(recurring_item["is_active"], False, "Recurring list active flag mismatch")

        listed_goals = client.request_json("GET", f"{api_prefix}/goals")
        reserve_goal_item = next((item for item in listed_goals if item["id"] == reserve_goal_id), None)
        deposit_goal_item = next((item for item in listed_goals if item["id"] == deposit_goal_id), None)
        assert_truthy(reserve_goal_item, "Reserve goal not found in goals list")
        assert_truthy(deposit_goal_item, "Deposit goal not found in goals list")
        assert_equal(reserve_goal_item["balance_minor"], 20000, "Reserve goal balance mismatch")
        assert_equal(deposit_goal_item["balance_minor"], 15000, "Deposit goal balance mismatch")

        deposit_goal_history = client.request_json("GET", f"{api_prefix}/goals/{deposit_goal_id}/history")
        assert_truthy(deposit_goal_history, "Deposit goal history is empty")
        assert_equal(
            deposit_goal_history[0]["id"],
            direct_goal_allocation["id"],
            "Deposit goal history does not contain the expected allocation",
        )

        dashboard = client.request_json("GET", f"{api_prefix}/dashboard")
        assert_equal(dashboard["income_total_minor"], 120000, "Dashboard income total mismatch")
        assert_equal(dashboard["expense_total_minor"], 35000, "Dashboard expense total mismatch")
        assert_equal(dashboard["goal_total_minor"], 35000, "Dashboard goal total mismatch")
        assert_equal(dashboard["refund_total_minor"], 5000, "Dashboard refund total mismatch")
        assert_equal(dashboard["investment_total_minor"], 0, "Dashboard investment total mismatch")
        assert_equal(dashboard["available_minor"], 55000, "Dashboard available amount mismatch")

    except SmokeTestError as exc:
        print(f"api smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("api smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
