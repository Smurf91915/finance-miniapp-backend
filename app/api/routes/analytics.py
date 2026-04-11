from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Category, Goal, Transaction, User
from app.schemas.analytics import CategorySpendItem, GoalAnalyticsItem, GoalAnalyticsRead, SpendingAnalyticsRead
from app.services.query_helpers import date_range_to_datetimes

router = APIRouter()


@router.get("/spending", response_model=SpendingAnalyticsRead)
def spending_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> SpendingAnalyticsRead:
    start_dt, end_dt, start_date, end_date = date_range_to_datetimes(from_date, to_date)

    expense_rows = db.execute(
        select(Category.id, Category.name, func.coalesce(func.sum(Transaction.amount_minor), 0))
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user.id,
            Transaction.type == "expense",
            Transaction.deleted_at.is_(None),
            Transaction.occurred_at >= start_dt,
            Transaction.occurred_at < end_dt,
        )
        .group_by(Category.id, Category.name)
    ).all()

    original = Transaction.__table__.alias("original")
    refund_map = {
        category_id: amount
        for category_id, amount in db.execute(
            select(original.c.category_id, func.coalesce(func.sum(Transaction.amount_minor), 0))
            .select_from(Transaction)
            .join(original, Transaction.linked_transaction_id == original.c.id)
            .where(
                Transaction.user_id == user.id,
                Transaction.type == "refund",
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
            .group_by(original.c.category_id)
        ).all()
    }

    categories: list[CategorySpendItem] = []
    expense_total = 0
    for category_id, category_name, raw_amount in expense_rows:
        net_amount = int(raw_amount or 0) - int(refund_map.get(category_id, 0) or 0)
        if net_amount <= 0:
            continue
        expense_total += net_amount
        categories.append(
            CategorySpendItem(
                category_id=str(category_id),
                category_name=category_name,
                amount_minor=net_amount,
                percent=0,
            )
        )

    for item in categories:
        item.percent = round((item.amount_minor / expense_total) * 100, 2) if expense_total else 0.0

    investment_total = (
        db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
                Transaction.user_id == user.id,
                Transaction.type == "investment",
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
        )
        or 0
    )
    goal_total = (
        db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
                Transaction.user_id == user.id,
                Transaction.type == "goal_allocation",
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
        )
        or 0
    )
    transaction_count = (
        db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.user_id == user.id,
                Transaction.type == "expense",
                Transaction.deleted_at.is_(None),
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
        )
        or 0
    )
    days_count = (end_date - start_date).days + 1

    return SpendingAnalyticsRead(
        expense_total_minor=int(expense_total),
        investment_total_minor=int(investment_total),
        goal_total_minor=int(goal_total),
        average_daily_expense_minor=int(expense_total / days_count) if days_count else 0,
        transaction_count=int(transaction_count),
        categories=sorted(categories, key=lambda item: item.amount_minor, reverse=True),
    )


@router.get("/goals", response_model=GoalAnalyticsRead)
def goals_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalAnalyticsRead:
    rows = db.execute(
        select(
            Goal.id,
            Goal.name,
            func.coalesce(func.sum(Transaction.amount_minor), 0),
        )
        .join(Transaction, Transaction.goal_id == Goal.id, isouter=True)
        .where(
            Goal.user_id == user.id,
            Goal.is_archived.is_(False),
            ((Transaction.deleted_at.is_(None)) & (Transaction.type == "goal_allocation")) | (Transaction.id.is_(None)),
        )
        .group_by(Goal.id, Goal.name)
        .order_by(Goal.name.asc())
    ).all()

    return GoalAnalyticsRead(
        goals=[
            GoalAnalyticsItem(
                goal_id=str(goal_id),
                goal_name=goal_name,
                amount_minor=int(amount_minor or 0),
            )
            for goal_id, goal_name, amount_minor in rows
        ]
    )
