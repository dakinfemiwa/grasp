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
from app.models.enums import ReviewStatus, StepOutcome


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


# Effective inclusive integer ranges per sampled parameter (template range ∩ scenario bounds).
Bounds = dict[str, tuple[int, int]]


@dataclass(frozen=True)
class GeneratedQuestion:
    """A concrete, validated instance. Pure data: persisting it is the caller's job."""

    template_id: str
    template_version: int
    scenario_id: str
    scenario_version: int
    seed: int | None
    parameters: dict[str, Any]
    prompt: str
    expected_answer: dict[str, Any]
    worked_solution: list[WorkedStep]
    primary_objective: str
    secondary_objectives: tuple[str, ...]
    difficulty: int
    validation: list[ValidationCheck] = field(default_factory=list)


class QuestionTemplate[P: BaseModel, S: BaseModel, R: BaseModel](ABC):
    """Extension point for every template family (quadratic, linear, trigonometric, ...).

    P: typed parameters. S: the wording "slots" a compatible scenario must supply.
    R: the structured student response.

    To add a template: subclass, fill in the class attributes and abstract methods, decorate
    with @register (app.engine.registry), and list it in at least one scenario's
    compatible_templates. A published (id, version) is immutable: change behaviour by bumping
    `version`, so stored instances stay reproducible.
    """

    id: ClassVar[str]
    version: ClassVar[int]
    title: ClassVar[str]
    domain: ClassVar[Domain]
    primary_objective: ClassVar[str]
    secondary_objectives: ClassVar[tuple[str, ...]] = ()
    # Pearson Edexcel 9MA0 (Issue 4) content/theme numbers this template draws on.
    spec_refs: ClassVar[tuple[str, ...]] = ()
    review_status: ClassVar[ReviewStatus] = ReviewStatus.DRAFT
    params_model: type[P]
    slots_model: type[S]
    response_model: type[R]
    default_scenario: ClassVar[str]  # used by build() when no scenario is given
    constraints: ClassVar[tuple[Constraint, ...]] = ()
    marking_criteria: ClassVar[tuple[MarkingCriterion, ...]]
    response_fields: ClassVar[tuple[ResponseField, ...]]
    hints: ClassVar[tuple[Hint, ...]] = ()
    difficulty_notes: ClassVar[str] = ""
    max_sampling_attempts: ClassVar[int] = 200

    @property
    def objectives(self) -> tuple[str, ...]:
        return (self.primary_objective, *self.secondary_objectives)

    def parameter_bounds(self) -> Bounds:
        """Inclusive ranges of the sampled (non-derived) integer parameters, from the params model."""
        bounds: Bounds = {}
        for name, info in self.params_model.model_fields.items():
            extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
            if extra.get("derived"):
                continue
            lo = next((m.ge for m in info.metadata if hasattr(m, "ge")), None)
            hi = next((m.le for m in info.metadata if hasattr(m, "le")), None)
            if lo is not None and hi is not None:
                bounds[name] = (int(lo), int(hi))
        return bounds

    @abstractmethod
    def sample(self, rng: random.Random, bounds: Bounds) -> P:
        """Choose independent values within bounds and derive dependent ones (never hope for luck)."""

    @abstractmethod
    def render_prompt(self, params: P, slots: S) -> str: ...

    @abstractmethod
    def expected_answer(self, params: P) -> R:
        """A model response; marking it must give every step CORRECT (checked by validation)."""

    @abstractmethod
    def worked_solution(self, params: P, slots: S) -> list[WorkedStep]: ...

    @abstractmethod
    def mark(self, params: P, slots: S, response: R) -> list[MarkedStep]: ...

    @abstractmethod
    def difficulty(self, params: P) -> int:
        """1 (easiest) .. 5."""

    def fields(self, slots: S) -> tuple[ResponseField, ...]:
        """Response fields as shown for one scenario (e.g. with its units). Override if needed."""
        return self.response_fields

    def checks(self, params: P, slots: S, prompt: str) -> list[ValidationCheck]:
        """Template-specific mathematical, pedagogical and presentation checks."""
        return []


AnyTemplate = QuestionTemplate[Any, Any, Any]
