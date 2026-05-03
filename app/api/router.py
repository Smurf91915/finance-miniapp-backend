from fastapi import APIRouter

from app.api.routes import analytics, categories, dashboard, goals, ops, recurring_expenses, transactions


api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(goals.router, prefix="/goals", tags=["goals"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(recurring_expenses.router, prefix="/recurring-expenses", tags=["recurring-expenses"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
