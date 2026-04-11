from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    amount_minor: int
    currency: str
    occurred_at: datetime
    note: str | None
    source: str
    category_id: UUID | None
    subcategory_id: UUID | None
    goal_id: UUID | None
    linked_transaction_id: UUID | None
    category_name: str | None = None
    subcategory_name: str | None = None
    goal_name: str | None = None


class ExpenseCreate(BaseModel):
    amount_minor: int
    currency: str = "RUB"
    occurred_at: datetime
    category_id: UUID
    subcategory_id: UUID | None = None
    note: str | None = None
    source: str = "mini_app"


class IncomeCreate(BaseModel):
    amount_minor: int
    currency: str = "RUB"
    occurred_at: datetime
    note: str | None = None
    reserve_amount_minor: int | None = None
    source: str = "mini_app"


class InvestmentCreate(BaseModel):
    amount_minor: int
    currency: str = "RUB"
    occurred_at: datetime
    category_id: UUID
    subcategory_id: UUID | None = None
    note: str | None = None
    source: str = "mini_app"


class GoalAllocationCreate(BaseModel):
    amount_minor: int
    currency: str = "RUB"
    occurred_at: datetime
    note: str | None = None
    linked_transaction_id: UUID | None = None
    source: str = "mini_app"


class RefundCreate(BaseModel):
    amount_minor: int
    currency: str = "RUB"
    occurred_at: datetime
    note: str | None = None
    source: str = "mini_app"


class TransactionUpdate(BaseModel):
    amount_minor: int | None = None
    occurred_at: datetime | None = None
    note: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    goal_id: UUID | None = None


class ParsedTransaction(BaseModel):
    type: str
    amount_minor: int
    currency: str = "RUB"
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    goal_id: UUID | None = None
    note: str | None = None
    confidence: float


class ParseRequest(BaseModel):
    text: str
