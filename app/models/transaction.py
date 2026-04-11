from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=True)
    goal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True)
    linked_transaction_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'mini_app'"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    subcategory = relationship("Subcategory", back_populates="transactions")
    goal = relationship("Goal", back_populates="transactions")
    linked_transaction = relationship("Transaction", remote_side="Transaction.id")
