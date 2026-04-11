from datetime import date

from pydantic import BaseModel

from app.schemas.transactions import TransactionRead


class DashboardPeriod(BaseModel):
    start: date
    end: date


class DashboardRead(BaseModel):
    period: DashboardPeriod
    income_total_minor: int
    expense_total_minor: int
    investment_total_minor: int
    goal_total_minor: int
    refund_total_minor: int
    available_minor: int
    recent_transactions: list[TransactionRead]
