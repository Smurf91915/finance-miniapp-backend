from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Category, Subcategory, User
from app.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    SubcategoryCreate,
    SubcategoryRead,
    SubcategoryUpdate,
)
from app.services.query_helpers import ensure_choice

router = APIRouter()


@router.get("", response_model=list[CategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CategoryRead]:
    categories = db.scalars(
        select(Category)
        .where(Category.user_id == user.id)
        .options(selectinload(Category.subcategories))
        .order_by(Category.kind.asc(), Category.sort_order.asc(), Category.name.asc())
    ).all()
    return [CategoryRead.model_validate(category) for category in categories]


@router.post("", response_model=CategoryRead)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategoryRead:
    ensure_choice(payload.kind, {"expense", "investment"}, "kind")
    category = Category(
        user_id=user.id,
        kind=payload.kind,
        name=payload.name,
        sort_order=payload.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CategoryRead:
    category = db.scalar(
        select(Category)
        .where(Category.id == category_id, Category.user_id == user.id)
        .options(selectinload(Category.subcategories))
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.name is not None:
        category.name = payload.name
    if payload.is_archived is not None:
        category.is_archived = payload.is_archived
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order

    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)


@router.post("/subcategories", response_model=SubcategoryRead)
def create_subcategory(
    payload: SubcategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubcategoryRead:
    category = db.scalar(
        select(Category).where(Category.id == payload.category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    subcategory = Subcategory(
        category_id=category.id,
        name=payload.name,
        sort_order=payload.sort_order,
    )
    db.add(subcategory)
    db.commit()
    db.refresh(subcategory)
    return SubcategoryRead.model_validate(subcategory)


@router.patch("/subcategories/{subcategory_id}", response_model=SubcategoryRead)
def update_subcategory(
    subcategory_id: UUID,
    payload: SubcategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubcategoryRead:
    subcategory = db.scalar(
        select(Subcategory)
        .join(Category, Category.id == Subcategory.category_id)
        .where(Subcategory.id == subcategory_id, Category.user_id == user.id)
    )
    if subcategory is None:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    if payload.name is not None:
        subcategory.name = payload.name
    if payload.is_archived is not None:
        subcategory.is_archived = payload.is_archived
    if payload.sort_order is not None:
        subcategory.sort_order = payload.sort_order

    db.commit()
    db.refresh(subcategory)
    return SubcategoryRead.model_validate(subcategory)
