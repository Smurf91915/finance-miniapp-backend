from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecurringExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category_id: UUID
    subcategory_id: UUID | None
    kind: str
    cadence: str
    expected_amount_minor: int | None
    day_of_month: int | None
    is_active: bool
    note: str | None


class RecurringExpenseCreate(BaseModel):
    name: str
    category_id: UUID
    subcategory_id: UUID | None = None
    kind: str
    cadence: str
    expected_amount_minor: int | None = None
    day_of_month: int | None = None
    note: str | None = None


class RecurringExpenseUpdate(BaseModel):
    name: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    kind: str | None = None
    cadence: str | None = None
    expected_amount_minor: int | None = None
    day_of_month: int | None = None
    is_active: bool | None = None
    note: str | None = None
