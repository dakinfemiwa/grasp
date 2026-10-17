from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TZDateTime, str_enum, utcnow
from app.models.content import Question
from app.models.enums import Correctness, ErrorType


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    submitted_answer: Mapped[str] = mapped_column(String(100))
    parsed_answer: Mapped[float | None] = mapped_column(Float)  # null when unparseable
    correctness: Mapped[Correctness] = mapped_column(str_enum(Correctness, "correctness"))
    error_type: Mapped[ErrorType] = mapped_column(str_enum(ErrorType, "error_type"))
    time_taken_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    question: Mapped[Question] = relationship()
