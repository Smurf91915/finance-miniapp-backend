from pydantic import BaseModel


class CategorySpendItem(BaseModel):
    category_id: str
    category_name: str
    amount_minor: int
    percent: float


class SpendingAnalyticsRead(BaseModel):
    expense_total_minor: int
    investment_total_minor: int
    goal_total_minor: int
    average_daily_expense_minor: int
    transaction_count: int
    categories: list[CategorySpendItem]


class GoalAnalyticsItem(BaseModel):
    goal_id: str
    goal_name: str
    amount_minor: int


class GoalAnalyticsRead(BaseModel):
    goals: list[GoalAnalyticsItem]
