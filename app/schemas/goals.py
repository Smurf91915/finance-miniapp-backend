from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoalRead(BaseModel):
    id: UUID
    kind: str
    name: str
    target_amount_minor: int | None
    is_archived: bool
    sort_order: int
    balance_minor: int


class GoalCreate(BaseModel):
    kind: str
    name: str
    target_amount_minor: int | None = None
    sort_order: int = 0


class GoalHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    amount_minor: int
    currency: str
    occurred_at: datetime
    note: str | None
