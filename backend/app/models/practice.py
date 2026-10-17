"""Generated question instances and the student evidence recorded against them.

Templates themselves are application code (app.engine), so they have no table: an instance
records the (template_id, template_version) it came from plus its seed and parameters, which
is enough to regenerate it exactly.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TZDateTime, str_enum, utcnow
from app.models.content import LearningObjective
from app.models.enums import EvidenceOutcome, StepOutcome


class QuestionInstance(Base):
    __tablename__ = "question_instances"
    __table_args__ = (
        # Generation is deterministic, so one row per (template, version, seed).
        UniqueConstraint("template_id", "template_version", "seed", name="uq_question_instances_template_seed"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[str] = mapped_column(String(60))
    template_version: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    scenario_id: Mapped[str | None] = mapped_column(String(60))  # Stage 5: scenario library
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType)
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[dict[str, Any]] = mapped_column(JSONType)
    worked_solution: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)
    validation: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # every check run, all passed
    difficulty: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    objectives: Mapped[list["InstanceObjective"]] = relationship(
        back_populates="instance", cascade="all, delete-orphan", order_by="InstanceObjective.objective_id"
    )


class InstanceObjective(Base):
    """Which objectives an instance assesses (objective tags)."""

    __tablename__ = "question_instance_objectives"

    instance_id: Mapped[int] = mapped_column(
        ForeignKey("question_instances.id", ondelete="CASCADE"), primary_key=True
    )
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    is_primary: Mapped[bool] = mapped_column(default=False)

    instance: Mapped[QuestionInstance] = relationship(back_populates="objectives")
    objective: Mapped[LearningObjective] = relationship()


class Evidence(Base):
    """One student attempt at one instance. Distinct from mastery (student_progress)."""

    __tablename__ = "student_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "instance_id", "attempt_number", name="uq_student_evidence_attempt"),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        Index("ix_student_evidence_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    instance_id: Mapped[int] = mapped_column(ForeignKey("question_instances.id", ondelete="RESTRICT"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)  # 1-based, per (user, instance)
    response: Mapped[dict[str, Any]] = mapped_column(JSONType)  # validated structured response
    outcome: Mapped[EvidenceOutcome] = mapped_column(str_enum(EvidenceOutcome, "evidence_outcome"))
    marking: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # per-step outcome + feedback
    hints_used: Mapped[list[str]] = mapped_column(JSONType, default=list)
    time_taken_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    instance: Mapped[QuestionInstance] = relationship()
    objectives: Mapped[list["EvidenceObjective"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan", order_by="EvidenceObjective.objective_id"
    )


class EvidenceObjective(Base):
    """Objective-level evidence from one attempt, e.g. MOD-05 correct but MOD-07 incorrect."""

    __tablename__ = "evidence_objectives"

    evidence_id: Mapped[int] = mapped_column(ForeignKey("student_evidence.id", ondelete="CASCADE"), primary_key=True)
    objective_id: Mapped[int] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    outcome: Mapped[StepOutcome] = mapped_column(str_enum(StepOutcome, "step_outcome"))

    evidence: Mapped[Evidence] = relationship(back_populates="objectives")
    objective: Mapped[LearningObjective] = relationship()
