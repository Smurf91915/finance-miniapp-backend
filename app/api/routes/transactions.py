import re
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Category, Goal, KeywordRule, Subcategory, Transaction, User
from app.schemas.transactions import (
    ExpenseCreate,
    GoalAllocationCreate,
    IncomeCreate,
    InvestmentCreate,
    ParseRequest,
    ParsedTransaction,
    RefundCreate,
    TransactionRead,
    TransactionUpdate,
)
from app.services.query_helpers import date_range_to_datetimes, ensure_positive

router = APIRouter()


def base_transaction_query(user_id: UUID):
    return select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.deleted_at.is_(None),
    )


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


def get_transaction_or_404(db: Session, user_id: UUID, transaction_id: UUID) -> Transaction:
    transaction = db.scalar(
        base_transaction_query(user_id)
        .where(Transaction.id == transaction_id)
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.subcategory),
            selectinload(Transaction.goal),
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def get_category_or_404(db: Session, user_id: UUID, category_id: UUID, kind: str | None = None) -> Category:
    query = select(Category).where(
        Category.id == category_id,
        Category.user_id == user_id,
        Category.is_archived.is_(False),
    )
    if kind is not None:
        query = query.where(Category.kind == kind)
    category = db.scalar(query)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def validate_subcategory(
    db: Session,
    category_id: UUID,
    subcategory_id: UUID | None,
) -> Subcategory | None:
    if subcategory_id is None:
        return None
    subcategory = db.scalar(
        select(Subcategory).where(
            Subcategory.id == subcategory_id,
            Subcategory.category_id == category_id,
            Subcategory.is_archived.is_(False),
        )
    )
    if subcategory is None:
        raise HTTPException(status_code=400, detail="Subcategory does not belong to category")
    return subcategory


def get_goal_or_404(db: Session, user_id: UUID, goal_id: UUID) -> Goal:
    goal = db.scalar(
        select(Goal).where(
            Goal.id == goal_id,
            Goal.user_id == user_id,
            Goal.is_archived.is_(False),
        )
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def reserve_goal_or_404(db: Session, user_id: UUID) -> Goal:
    goal = db.scalar(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.kind == "reserve",
            Goal.is_archived.is_(False),
        )
    )
    if goal is None:
        raise HTTPException(status_code=400, detail="Reserve goal is not configured")
    return goal


def build_transaction(
    *,
    user_id: UUID,
    tx_type: str,
    amount_minor: int,
    currency: str,
    occurred_at: datetime,
    note: str | None,
    source: str,
    category_id: UUID | None = None,
    subcategory_id: UUID | None = None,
    goal_id: UUID | None = None,
    linked_transaction_id: UUID | None = None,
) -> Transaction:
    return Transaction(
        user_id=user_id,
        type=tx_type,
        amount_minor=amount_minor,
        currency=currency,
        occurred_at=occurred_at,
        note=note,
        source=source,
        category_id=category_id,
        subcategory_id=subcategory_id,
        goal_id=goal_id,
        linked_transaction_id=linked_transaction_id,
    )


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    tx_type: str | None = Query(default=None, alias="type"),
    category_id: UUID | None = None,
    goal_id: UUID | None = None,
    limit: int = Query(default=100, le=500),
) -> list[TransactionRead]:
    start_dt, end_dt, _, _ = date_range_to_datetimes(from_date, to_date)
    query = (
        base_transaction_query(user.id)
        .where(Transaction.occurred_at >= start_dt, Transaction.occurred_at < end_dt)
        .options(
            selectinload(Transaction.category),
            selectinload(Transaction.subcategory),
            selectinload(Transaction.goal),
        )
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
    )
    if tx_type:
        query = query.where(Transaction.type == tx_type)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if goal_id:
        query = query.where(Transaction.goal_id == goal_id)
    transactions = db.scalars(query).all()
    return [serialize_transaction(tx) for tx in transactions]


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    return serialize_transaction(get_transaction_or_404(db, user.id, transaction_id))


@router.post("/expense", response_model=TransactionRead)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    ensure_positive(payload.amount_minor)
    category = get_category_or_404(db, user.id, payload.category_id, "expense")
    subcategory = validate_subcategory(db, category.id, payload.subcategory_id)

    transaction = build_transaction(
        user_id=user.id,
        tx_type="expense",
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
        source=payload.source,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    transaction.category = category
    transaction.subcategory = subcategory
    return serialize_transaction(transaction)


@router.post("/income", response_model=list[TransactionRead])
def create_income(
    payload: IncomeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TransactionRead]:
    ensure_positive(payload.amount_minor)
    if payload.reserve_amount_minor is not None:
        ensure_positive(payload.reserve_amount_minor)
        if payload.reserve_amount_minor > payload.amount_minor:
            raise HTTPException(status_code=400, detail="reserve_amount_minor cannot exceed income amount")

    income = build_transaction(
        user_id=user.id,
        tx_type="income",
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
        source=payload.source,
    )
    db.add(income)
    db.flush()

    created = [income]
    if payload.reserve_amount_minor:
        reserve_goal = reserve_goal_or_404(db, user.id)
        reserve = build_transaction(
            user_id=user.id,
            tx_type="goal_allocation",
            amount_minor=payload.reserve_amount_minor,
            currency=payload.currency,
            occurred_at=payload.occurred_at,
            note="Пополнение неприкосновенного запаса",
            source=payload.source,
            goal_id=reserve_goal.id,
            linked_transaction_id=income.id,
        )
        db.add(reserve)
        created.append(reserve)

    db.commit()
    for transaction in created:
        db.refresh(transaction)
    return [serialize_transaction(tx) for tx in created]


@router.post("/investment", response_model=TransactionRead)
def create_investment(
    payload: InvestmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    ensure_positive(payload.amount_minor)
    category = get_category_or_404(db, user.id, payload.category_id, "investment")
    subcategory = validate_subcategory(db, category.id, payload.subcategory_id)

    transaction = build_transaction(
        user_id=user.id,
        tx_type="investment",
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
        source=payload.source,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    transaction.category = category
    transaction.subcategory = subcategory
    return serialize_transaction(transaction)


@router.post("/goals/{goal_id}/allocate", response_model=TransactionRead)
def allocate_to_goal(
    goal_id: UUID,
    payload: GoalAllocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    ensure_positive(payload.amount_minor)
    goal = get_goal_or_404(db, user.id, goal_id)

    transaction = build_transaction(
        user_id=user.id,
        tx_type="goal_allocation",
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
        source=payload.source,
        goal_id=goal.id,
        linked_transaction_id=payload.linked_transaction_id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    transaction.goal = goal
    return serialize_transaction(transaction)


@router.post("/{transaction_id}/refund", response_model=TransactionRead)
def create_refund(
    transaction_id: UUID,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    ensure_positive(payload.amount_minor)
    original = get_transaction_or_404(db, user.id, transaction_id)
    if original.type not in {"expense", "investment"}:
        raise HTTPException(status_code=400, detail="Refund can only be linked to expense or investment")

    refunded_total = (
        db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(
                Transaction.linked_transaction_id == original.id,
                Transaction.type == "refund",
                Transaction.deleted_at.is_(None),
            )
        )
        or 0
    )
    remaining = original.amount_minor - refunded_total
    if payload.amount_minor > remaining:
        raise HTTPException(status_code=400, detail="Refund exceeds remaining refundable amount")

    refund = build_transaction(
        user_id=user.id,
        tx_type="refund",
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        occurred_at=payload.occurred_at,
        note=payload.note,
        source=payload.source,
        linked_transaction_id=original.id,
        category_id=original.category_id,
        subcategory_id=original.subcategory_id,
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    refund.category = original.category
    refund.subcategory = original.subcategory
    return serialize_transaction(refund)


@router.patch("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: UUID,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    transaction = get_transaction_or_404(db, user.id, transaction_id)

    if payload.amount_minor is not None:
        ensure_positive(payload.amount_minor)
        transaction.amount_minor = payload.amount_minor
    if payload.occurred_at is not None:
        transaction.occurred_at = payload.occurred_at
    if payload.note is not None:
        transaction.note = payload.note

    if payload.category_id is not None:
        category_kind = "investment" if transaction.type == "investment" else "expense"
        category = get_category_or_404(db, user.id, payload.category_id, category_kind)
        transaction.category_id = category.id
        transaction.category = category
        transaction.subcategory_id = None
        transaction.subcategory = None

    if payload.subcategory_id is not None:
        if transaction.category_id is None:
            raise HTTPException(status_code=400, detail="Category must be set before subcategory")
        subcategory = validate_subcategory(db, transaction.category_id, payload.subcategory_id)
        transaction.subcategory_id = subcategory.id if subcategory else None
        transaction.subcategory = subcategory

    if payload.goal_id is not None:
        goal = get_goal_or_404(db, user.id, payload.goal_id)
        transaction.goal_id = goal.id
        transaction.goal = goal

    db.commit()
    db.refresh(transaction)
    return serialize_transaction(transaction)


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    transaction = get_transaction_or_404(db, user.id, transaction_id)
    transaction.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/parse", response_model=ParsedTransaction)
def parse_text(
    payload: ParseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ParsedTransaction:
    text = payload.text.strip()
    lowered = text.lower()
    match = re.search(r"(\d[\d\s]*)$", lowered)
    if match is None:
        raise HTTPException(status_code=400, detail="Could not parse amount from text")

    amount_minor = int(match.group(1).replace(" ", "")) * 100
    note = lowered[: match.start()].strip() or None

    if lowered.startswith("зарплата"):
        return ParsedTransaction(type="income", amount_minor=amount_minor, note=note, confidence=0.99)

    if lowered.startswith("облигации"):
        category = db.scalar(
            select(Category).where(
                Category.user_id == user.id,
                Category.kind == "investment",
                Category.name == "Облигации",
            )
        )
        return ParsedTransaction(
            type="investment",
            amount_minor=amount_minor,
            category_id=category.id if category else None,
            note=note,
            confidence=0.99,
        )

    if lowered.startswith("вклад"):
        goal = db.scalar(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.kind == "deposit",
                Goal.is_archived.is_(False),
            )
        )
        return ParsedTransaction(
            type="goal_allocation",
            amount_minor=amount_minor,
            goal_id=goal.id if goal else None,
            note=note,
            confidence=0.99,
        )

    if lowered.startswith("запас"):
        goal = db.scalar(
            select(Goal).where(
                Goal.user_id == user.id,
                Goal.kind == "reserve",
                Goal.is_archived.is_(False),
            )
        )
        return ParsedTransaction(
            type="goal_allocation",
            amount_minor=amount_minor,
            goal_id=goal.id if goal else None,
            note=note,
            confidence=0.99,
        )

    rules = db.scalars(
        select(KeywordRule)
        .where(KeywordRule.user_id == user.id, KeywordRule.is_active.is_(True))
        .order_by(KeywordRule.priority.asc())
    ).all()
    for rule in rules:
        if rule.phrase.lower() in lowered:
            category = db.get(Category, rule.category_id)
            tx_type = "investment" if category and category.kind == "investment" else "expense"
            return ParsedTransaction(
                type=tx_type,
                amount_minor=amount_minor,
                category_id=rule.category_id,
                subcategory_id=rule.subcategory_id,
                note=note,
                confidence=0.95,
            )

    return ParsedTransaction(type="expense", amount_minor=amount_minor, note=note, confidence=0.4)
