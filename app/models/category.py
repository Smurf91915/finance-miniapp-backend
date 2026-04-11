from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "categories"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    user = relationship("User", back_populates="categories")
    subcategories = relationship("Subcategory", back_populates="category")
    transactions = relationship("Transaction", back_populates="category")
    recurring_expenses = relationship("RecurringExpense", back_populates="category")
    keyword_rules = relationship("KeywordRule", back_populates="category")
