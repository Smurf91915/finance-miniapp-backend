from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SubcategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_archived: bool
    sort_order: int


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    name: str
    is_archived: bool
    sort_order: int
    subcategories: list[SubcategoryRead] = []


class CategoryCreate(BaseModel):
    kind: str
    name: str
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None
    sort_order: int | None = None


class SubcategoryCreate(BaseModel):
    category_id: UUID
    name: str
    sort_order: int = 0


class SubcategoryUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None
    sort_order: int | None = None
