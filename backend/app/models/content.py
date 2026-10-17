from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Integer, String, Table, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TZDateTime, str_enum, utcnow
from app.models.enums import Representation

# Edge "objective requires prerequisite". Many-to-many, so prerequisites form a DAG, not a chain.
objective_prerequisites = Table(
    "objective_prerequisites",
    Base.metadata,
    Column("objective_id", ForeignKey("learning_objectives.id", ondelete="CASCADE"), primary_key=True),
    Column("prerequisite_id", ForeignKey("learning_objectives.id", ondelete="CASCADE"), primary_key=True),
    CheckConstraint("objective_id <> prerequisite_id", name="not_self"),
)


class LearningObjective(Base):
    """Database mirror of the objective catalogue (backend/content/objectives/*.yaml).

    The YAML file is the source of truth; `python -m app.seed` syncs it into this table.
    """

    __tablename__ = "learning_objectives"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Grasp-internal catalogue id, e.g. "MOD-05". Not an Edexcel identifier.
    code: Mapped[str] = mapped_column(String(100), unique=True)
    domain_area: Mapped[str] = mapped_column(String(100))  # e.g. "Pure: Mathematical modelling"
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    # Ordered display lists; never filtered on, so JSON rather than child tables.
    success_criteria: Mapped[list[str]] = mapped_column(JSONType, default=list)
    domains: Mapped[list[str]] = mapped_column(JSONType, default=list)
    evidence_types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    catalogue_version: Mapped[int] = mapped_column(Integer)

    prerequisites: Mapped[list["LearningObjective"]] = relationship(
        secondary=objective_prerequisites,
        primaryjoin=lambda: LearningObjective.id == objective_prerequisites.c.objective_id,
        secondaryjoin=lambda: LearningObjective.id == objective_prerequisites.c.prerequisite_id,
    )
    questions: Mapped[list["Question"]] = relationship(back_populates="learning_objective")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        CheckConstraint("tolerance >= 0", name="tolerance_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable slug from the content file. Lets re-seeding update in place.
    code: Mapped[str] = mapped_column(String(100), unique=True)
    learning_objective_id: Mapped[int] = mapped_column(
        ForeignKey("learning_objectives.id", ondelete="RESTRICT"), index=True
    )
    difficulty: Mapped[int] = mapped_column(Integer)  # 1 (easiest) .. 5
    representation: Mapped[Representation] = mapped_column(str_enum(Representation, "representation"))
    # Real-world setting, e.g. "abstract", "car braking", "lift". Free text, kept short.
    context: Mapped[str] = mapped_column(String(100))
    prompt: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[float] = mapped_column(Float)
    tolerance: Mapped[float] = mapped_column(Float)  # absolute tolerance
    unit: Mapped[str | None] = mapped_column(String(30))
    explanation: Mapped[str] = mapped_column(Text)
    # Flexible, content-specific extras (common error answers, graph data, tags).
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)

    learning_objective: Mapped[LearningObjective] = relationship(back_populates="questions")
