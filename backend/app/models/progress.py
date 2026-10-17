from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TZDateTime, utcnow


class StudentProgress(Base):
    """Per-student, per-objective rollup. Derivable from attempts; stored for fast reads."""

    __tablename__ = "student_progress"
    __table_args__ = (
        CheckConstraint("correct_attempts <= attempts", name="correct_le_attempts"),
        CheckConstraint("current_difficulty BETWEEN 1 AND 5", name="difficulty_range"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    learning_objective_id: Mapped[int] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="CASCADE"), primary_key=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)
    recent_accuracy: Mapped[float] = mapped_column(Float, default=0.0)  # over a recent window, 0..1
    estimated_mastery: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    current_difficulty: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow, onupdate=utcnow)
