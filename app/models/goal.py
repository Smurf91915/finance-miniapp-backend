from sqlalchemy import Boolean, ForeignKey, Integer, BigInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Goal(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    user = relationship("User", back_populates="goals")
    transactions = relationship("Transaction", back_populates="goal")
