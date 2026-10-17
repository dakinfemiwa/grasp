from typing import Any

from pydantic import BaseModel, Field

from app.engine.base import FieldKind, ReviewStatus
from app.models.enums import EvidenceOutcome, StepOutcome

MAX_SEED = 2**31 - 1


class TemplateOut(BaseModel):
    id: str
    version: int
    title: str
    domain: str
    primary_objective: str
    secondary_objectives: list[str]
    review_status: ReviewStatus


class CreateInstanceIn(BaseModel):
    template_id: str | None = Field(default=None, description="Defaults to a random servable template.")
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED, description="Defaults to a random seed.")


class ObjectiveTag(BaseModel):
    id: str
    is_primary: bool


class ResponseFieldOut(BaseModel):
    name: str
    label: str
    kind: FieldKind
    help: str
    options: list[str]
    unit: str | None


class HintOut(BaseModel):
    id: str
    objective: str
    text: str


class InstanceOut(BaseModel):
    """What a student sees before answering: no expected answer or worked solution."""

    id: int
    template_id: str
    template_version: int
    prompt: str
    difficulty: int
    objectives: list[ObjectiveTag]
    response_fields: list[ResponseFieldOut]
    hints: list[HintOut]


class AttemptIn(BaseModel):
    response: dict[str, Any] = Field(description="Validated against the template's response model.")
    hints_used: list[str] = Field(default_factory=list, max_length=20)
    time_taken_ms: int | None = Field(default=None, ge=0)


class MarkedStepOut(BaseModel):
    step: str
    objective: str
    outcome: StepOutcome
    feedback: str


class WorkedStepOut(BaseModel):
    objective: str
    title: str
    text: str


class AttemptOut(BaseModel):
    evidence_id: int
    attempt_number: int
    outcome: EvidenceOutcome
    steps: list[MarkedStepOut]
    objective_outcomes: dict[str, StepOutcome]
    expected_answer: dict[str, Any]
    worked_solution: list[WorkedStepOut]
