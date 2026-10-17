"""Core types for deterministic question templates.

A template is executable application code (never a database string). It declares typed
parameters, explicit constraints, prompt rendering, solution logic, an expected answer and
step-level marking. The generator (app.engine.generator) drives it from a seed.
"""

import random
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel

from app.catalogue import Domain
from app.models.enums import StepOutcome


class ReviewStatus(StrEnum):
    DRAFT = "draft"  # authored, not yet reviewed by a person
    REVIEWED = "reviewed"  # reviewed, changes may be pending
    APPROVED = "approved"  # cleared for the normal student question bank


class ValidationCategory(StrEnum):
    STRUCTURAL = "structural"
    MATHEMATICAL = "mathematical"
    PEDAGOGICAL = "pedagogical"  # automated proxies only; real review is ReviewStatus
    PRESENTATION = "presentation"


class FieldKind(StrEnum):
    CHOICE = "choice"
    EXPRESSION = "expression"  # in terms of x
    EQUATION = "equation"  # in terms of x, exactly one "="
    NUMBER = "number"
    NUMBER_LIST = "number_list"


class EngineError(ValueError):
    """Base class: every engine failure carries a list of human-readable problems."""

    def __init__(self, message: str, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(message + ":\n" + "\n".join(f"  - {p}" for p in problems))


class InvalidParameters(EngineError):
    pass


class GenerationError(EngineError):
    pass


class InvalidInstance(EngineError):
    pass


@dataclass(frozen=True)
class Constraint:
    """A named, executable condition the parameters must satisfy."""

    name: str
    description: str
    holds: Callable[[Any], bool]


@dataclass(frozen=True)
class MarkingCriterion:
    step: str
    objective: str  # catalogue id, e.g. "MOD-05"
    description: str


@dataclass(frozen=True)
class ResponseField:
    """Describes one part of the structured response so a client can render an input for it."""

    name: str
    label: str
    kind: FieldKind
    help: str = ""
    options: tuple[str, ...] = ()
    unit: str | None = None


@dataclass(frozen=True)
class Hint:
    id: str
    objective: str
    text: str


@dataclass(frozen=True)
class WorkedStep:
    objective: str
    title: str
    text: str


@dataclass(frozen=True)
class MarkedStep:
    step: str
    objective: str
    outcome: StepOutcome
    feedback: str


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    category: ValidationCategory
    passed: bool
    message: str = ""


@dataclass(frozen=True)
class GeneratedQuestion:
    """A concrete, validated instance. Pure data: persisting it is the caller's job."""

    template_id: str
    template_version: int
    seed: int | None
    parameters: dict[str, Any]
    prompt: str
    expected_answer: dict[str, Any]
    worked_solution: list[WorkedStep]
    primary_objective: str
    secondary_objectives: tuple[str, ...]
    difficulty: int
    validation: list[ValidationCheck] = field(default_factory=list)
    scenario_id: str | None = None  # Stage 5: scenario library


class QuestionTemplate[P: BaseModel, R: BaseModel](ABC):
    """Extension point for every template family (quadratic now; linear and trig next).

    To add a template: subclass, fill in the class attributes and abstract methods, and
    decorate with @register (app.engine.registry). A published (id, version) is immutable:
    change behaviour by bumping `version`, so stored instances stay reproducible.
    """

    id: ClassVar[str]
    version: ClassVar[int]
    title: ClassVar[str]
    domain: ClassVar[Domain]
    primary_objective: ClassVar[str]
    secondary_objectives: ClassVar[tuple[str, ...]] = ()
    review_status: ClassVar[ReviewStatus] = ReviewStatus.DRAFT
    params_model: type[P]
    response_model: type[R]
    constraints: ClassVar[tuple[Constraint, ...]] = ()
    marking_criteria: ClassVar[tuple[MarkingCriterion, ...]]
    response_fields: ClassVar[tuple[ResponseField, ...]]
    hints: ClassVar[tuple[Hint, ...]] = ()
    difficulty_notes: ClassVar[str] = ""
    max_sampling_attempts: ClassVar[int] = 200

    @property
    def objectives(self) -> tuple[str, ...]:
        return (self.primary_objective, *self.secondary_objectives)

    @abstractmethod
    def sample(self, rng: random.Random) -> P:
        """Choose independent values from rng and derive dependent ones (never hope for luck)."""

    @abstractmethod
    def render_prompt(self, params: P) -> str: ...

    @abstractmethod
    def expected_answer(self, params: P) -> R:
        """A model response; marking it must give every step CORRECT (checked by validation)."""

    @abstractmethod
    def worked_solution(self, params: P) -> list[WorkedStep]: ...

    @abstractmethod
    def mark(self, params: P, response: R) -> list[MarkedStep]: ...

    @abstractmethod
    def difficulty(self, params: P) -> int:
        """1 (easiest) .. 5."""

    def checks(self, params: P, prompt: str) -> list[ValidationCheck]:
        """Template-specific mathematical, pedagogical and presentation checks."""
        return []


AnyTemplate = QuestionTemplate[Any, Any]
