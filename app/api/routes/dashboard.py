from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Transaction, User
from app.schemas.dashboard import DashboardPeriod, DashboardRead
from app.schemas.transactions import TransactionRead
from app.services.query_helpers import date_range_to_datetimes

router = APIRouter()


def serialize_transaction(transaction: Transaction) -> TransactionRead:
    return TransactionRead(
        id=transaction.id,
        type=transaction.type,
        amount_minor=transaction.amount_minor,
        currency=transaction.currency,
        occurred_at=transaction.occurred_at,
        note=transaction.note,
        source=transaction.source,
        category_id=transaction.category_id,
        subcategory_id=transaction.subcategory_id,
        goal_id=transaction.goal_id,
        linked_transaction_id=transaction.linked_transaction_id,
        category_name=transaction.category.name if transaction.category else None,
        subcategory_name=transaction.subcategory.name if transaction.subcategory else None,
        goal_name=transaction.goal.name if transaction.goal else None,
    )


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> DashboardRead:
    start_dt, end_dt, start_date, end_date = date_range_to_datetimes(from_date, to_date)

    def total_for(tx_type: str) -> int:
        return (
            db.scalar(
                select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == tx_type,
                    Transaction.deleted_at.is_(None),
                    Transaction.occurred_at >= start_dt,
                    Transaction.occurred_at < end_dt,
                )
            )
            or 0
        )

    recent_transactions = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.occurred_at >= start_dt,
            Transaction.occurred_at < end_dt,
        )
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.subcategory),
            selectinload(Transaction.goal),
        )
        .order_by(Transaction.occurred_at.desc())
        .limit(5)
    ).all()

    income_total = total_for("income")
    expense_total = total_for("expense")
    investment_total = total_for("investment")
    goal_total = total_for("goal_allocation")
    refund_total = total_for("refund")

    return DashboardRead(
        period=DashboardPeriod(start=start_date, end=end_date),
        income_total_minor=income_total,
        expense_total_minor=expense_total,
        investment_total_minor=investment_total,
        goal_total_minor=goal_total,
        refund_total_minor=refund_total,
        available_minor=income_total + refund_total - expense_total - investment_total - goal_total,
        recent_transactions=[serialize_transaction(tx) for tx in recent_transactions],
    )
