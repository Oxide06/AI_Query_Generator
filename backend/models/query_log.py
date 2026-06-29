from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    user_role: Mapped[str] = mapped_column(String(32), nullable=False)

    # What the user asked
    natural_language: Mapped[str] = mapped_column(Text, nullable=False)

    # What the LLM generated
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Security outcome
    passed_security: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Execution outcome
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", backref="query_logs")

    def __repr__(self) -> str:
        return f"<QueryLog id={self.id} user_id={self.user_id} passed={self.passed_security}>"
