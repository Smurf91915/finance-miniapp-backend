from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecurringExpense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_expenses"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    subcategory_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    cadence: Mapped[str] = mapped_column(String, nullable=False)
    expected_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="recurring_expenses")
    category = relationship("Category", back_populates="recurring_expenses")
    subcategory = relationship("Subcategory", back_populates="recurring_expenses")
