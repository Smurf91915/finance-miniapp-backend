from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="Europe/Samara")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")

    categories = relationship("Category", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    recurring_expenses = relationship("RecurringExpense", back_populates="user")
    keyword_rules = relationship("KeywordRule", back_populates="user")
