from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin


class KeywordRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "keyword_rules"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    phrase: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    subcategory_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    user = relationship("User", back_populates="keyword_rules")
    category = relationship("Category", back_populates="keyword_rules")
    subcategory = relationship("Subcategory", back_populates="keyword_rules")
