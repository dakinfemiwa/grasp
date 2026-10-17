from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType

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
    spec_refs: Mapped[list[str]] = mapped_column(JSONType, default=list)  # Edexcel 9MA0 references
    catalogue_version: Mapped[int] = mapped_column(Integer)

    prerequisites: Mapped[list["LearningObjective"]] = relationship(
        secondary=objective_prerequisites,
        primaryjoin=lambda: LearningObjective.id == objective_prerequisites.c.objective_id,
        secondaryjoin=lambda: LearningObjective.id == objective_prerequisites.c.prerequisite_id,
    )
