from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Category, RecurringExpense, Subcategory, Transaction, User
from app.schemas.recurring_expenses import (
    RecurringExpenseCreate,
    RecurringExpenseRead,
    RecurringExpenseUpdate,
)
from app.services.query_helpers import ensure_choice

router = APIRouter()


def get_recurring_or_404(db: Session, user_id: UUID, recurring_id: UUID) -> RecurringExpense:
    recurring = db.scalar(
        select(RecurringExpense).where(
            RecurringExpense.id == recurring_id,
            RecurringExpense.user_id == user_id,
        )
    )
    if recurring is None:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    return recurring


@router.get("", response_model=list[RecurringExpenseRead])
def list_recurring_expenses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RecurringExpenseRead]:
    items = db.scalars(
        select(RecurringExpense)
        .where(RecurringExpense.user_id == user.id)
        .order_by(RecurringExpense.is_active.desc(), RecurringExpense.name.asc())
    ).all()
    return [RecurringExpenseRead.model_validate(item) for item in items]


@router.post("", response_model=RecurringExpenseRead)
def create_recurring_expense(
    payload: RecurringExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecurringExpenseRead:
    ensure_choice(payload.kind, {"fixed", "variable"}, "kind")
    ensure_choice(payload.cadence, {"monthly", "yearly", "custom"}, "cadence")

    category = db.scalar(
        select(Category).where(Category.id == payload.category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.subcategory_id is not None:
        subcategory = db.scalar(
            select(Subcategory).where(
                Subcategory.id == payload.subcategory_id,
                Subcategory.category_id == category.id,
            )
        )
        if subcategory is None:
            raise HTTPException(status_code=400, detail="Subcategory does not belong to category")

    item = RecurringExpense(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return RecurringExpenseRead.model_validate(item)


@router.post("/from-transaction/{transaction_id}", response_model=RecurringExpenseRead)
def create_recurring_from_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecurringExpenseRead:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user.id,
            Transaction.type == "expense",
            Transaction.deleted_at.is_(None),
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Expense transaction not found")
    if transaction.category_id is None:
        raise HTTPException(status_code=400, detail="Transaction has no category")

    item = RecurringExpense(
        user_id=user.id,
        name=transaction.note or "Регулярная трата",
        category_id=transaction.category_id,
        subcategory_id=transaction.subcategory_id,
        kind="fixed",
        cadence="monthly",
        expected_amount_minor=transaction.amount_minor,
        day_of_month=transaction.occurred_at.day,
        note="Создано из существующей операции",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return RecurringExpenseRead.model_validate(item)


@router.patch("/{recurring_id}", response_model=RecurringExpenseRead)
def update_recurring_expense(
    recurring_id: UUID,
    payload: RecurringExpenseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecurringExpenseRead:
    item = get_recurring_or_404(db, user.id, recurring_id)

    updates = payload.model_dump(exclude_unset=True)
    if "kind" in updates:
        ensure_choice(updates["kind"], {"fixed", "variable"}, "kind")
    if "cadence" in updates:
        ensure_choice(updates["cadence"], {"monthly", "yearly", "custom"}, "cadence")

    if "category_id" in updates and updates["category_id"] is not None:
        category = db.scalar(
            select(Category).where(Category.id == updates["category_id"], Category.user_id == user.id)
        )
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")

    if "subcategory_id" in updates and updates["subcategory_id"] is not None:
        category_id = updates.get("category_id", item.category_id)
        subcategory = db.scalar(
            select(Subcategory).where(
                Subcategory.id == updates["subcategory_id"],
                Subcategory.category_id == category_id,
            )
        )
        if subcategory is None:
            raise HTTPException(status_code=400, detail="Subcategory does not belong to category")

    for field, value in updates.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return RecurringExpenseRead.model_validate(item)
