from collections.abc import Sequence
from uuid import UUID

import httpx

from app.core.config import resolved_backend_base_url


class BackendClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=resolved_backend_base_url(), timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, telegram_id: int, json: dict | None = None) -> dict | list:
        response = await self._client.request(
            method,
            path,
            json=json,
            headers={"X-Telegram-Id": str(telegram_id)},
        )
        response.raise_for_status()
        return response.json()

    async def parse_text(self, telegram_id: int, text: str) -> dict:
        data = await self._request("POST", "/transactions/parse", telegram_id, json={"text": text})
        return dict(data)

    async def create_expense(self, telegram_id: int, payload: dict) -> dict:
        data = await self._request("POST", "/transactions/expense", telegram_id, json=payload)
        return dict(data)

    async def create_income(self, telegram_id: int, payload: dict) -> Sequence[dict]:
        data = await self._request("POST", "/transactions/income", telegram_id, json=payload)
        return list(data)

    async def create_investment(self, telegram_id: int, payload: dict) -> dict:
        data = await self._request("POST", "/transactions/investment", telegram_id, json=payload)
        return dict(data)

    async def list_goals(self, telegram_id: int) -> list[dict]:
        data = await self._request("GET", "/goals", telegram_id)
        return list(data)

    async def allocate_to_goal(self, telegram_id: int, goal_id: str | UUID, payload: dict) -> dict:
        data = await self._request("POST", f"/transactions/goals/{goal_id}/allocate", telegram_id, json=payload)
        return dict(data)

    async def get_dashboard(self, telegram_id: int) -> dict:
        data = await self._request("GET", "/dashboard", telegram_id)
        return dict(data)
