from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Goal, Transaction, User
from app.schemas.goals import GoalCreate, GoalHistoryItem, GoalRead
from app.services.query_helpers import ensure_choice

router = APIRouter()


@router.get("", response_model=list[GoalRead])
def list_goals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GoalRead]:
    goals = db.scalars(
        select(Goal)
        .where(Goal.user_id == user.id)
        .order_by(Goal.sort_order.asc(), Goal.name.asc())
    ).all()

    balances = {
        goal_id: amount
        for goal_id, amount in db.execute(
            select(
                Transaction.goal_id,
                func.coalesce(func.sum(Transaction.amount_minor), 0),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == "goal_allocation",
                Transaction.deleted_at.is_(None),
                Transaction.goal_id.is_not(None),
            )
            .group_by(Transaction.goal_id)
        ).all()
    }

    return [
        GoalRead(
            id=goal.id,
            kind=goal.kind,
            name=goal.name,
            target_amount_minor=goal.target_amount_minor,
            is_archived=goal.is_archived,
            sort_order=goal.sort_order,
            balance_minor=int(balances.get(goal.id, 0) or 0),
        )
        for goal in goals
    ]


@router.post("", response_model=GoalRead)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GoalRead:
    ensure_choice(payload.kind, {"reserve", "deposit", "custom"}, "kind")
    goal = Goal(
        user_id=user.id,
        kind=payload.kind,
        name=payload.name,
        target_amount_minor=payload.target_amount_minor,
        sort_order=payload.sort_order,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalRead(
        id=goal.id,
        kind=goal.kind,
        name=goal.name,
        target_amount_minor=goal.target_amount_minor,
        is_archived=goal.is_archived,
        sort_order=goal.sort_order,
        balance_minor=0,
    )


@router.get("/{goal_id}/history", response_model=list[GoalHistoryItem])
def goal_history(
    goal_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GoalHistoryItem]:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    items = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.goal_id == goal.id,
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.occurred_at.desc())
    ).all()
    return [GoalHistoryItem.model_validate(item) for item in items]
