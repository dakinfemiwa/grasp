import random
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.catalogue import Domain
from app.engine import build, generate, get_template
from app.engine.base import (
    Constraint,
    FieldKind,
    GenerationError,
    InvalidInstance,
    MarkedStep,
    MarkingCriterion,
    QuestionTemplate,
    ResponseField,
    WorkedStep,
)
from app.engine import registry
from app.engine.registry import UnknownTemplate, register
from app.models.enums import StepOutcome


@pytest.fixture(autouse=True, scope="module")
def _unregister_test_templates() -> Iterator[None]:
    yield
    for key in [k for k in registry._TEMPLATES if k[0].startswith("TEST-")]:
        del registry._TEMPLATES[key]


class NParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    n: int = Field(ge=0, le=10)


class NResponse(BaseModel):
    n: float | None = None


class Doubling(QuestionTemplate[NParams, NResponse]):
    """Minimal template for exercising the generic pipeline."""

    id = "TEST-DOUBLE"
    version = 1
    title = "Double it"
    domain = Domain.LINEAR
    primary_objective = "MOD-07"
    params_model = NParams
    response_model = NResponse
    marking_criteria = (MarkingCriterion("answer", "MOD-07", "Doubles n."),)
    response_fields = (ResponseField("n", "Answer", FieldKind.NUMBER),)

    def sample(self, rng: random.Random) -> NParams:
        return NParams(n=rng.randint(0, 10))

    def render_prompt(self, p: NParams) -> str:
        return f"Double {p.n}."

    def expected_answer(self, p: NParams) -> NResponse:
        return NResponse(n=2 * p.n)

    def worked_solution(self, p: NParams) -> list[WorkedStep]:
        return [WorkedStep("MOD-07", "Double", f"2 × {p.n} = {2 * p.n}")]

    def mark(self, p: NParams, r: NResponse) -> list[MarkedStep]:
        ok = r.n == 2 * p.n
        return [MarkedStep("answer", "MOD-07", StepOutcome.CORRECT if ok else StepOutcome.INCORRECT, "")]

    def difficulty(self, p: NParams) -> int:
        return 1


@register
class RegisteredDoubling(Doubling):
    id = "TEST-DOUBLE-REG"


def test_registry_lookup_and_immutable_versions() -> None:
    assert get_template("TEST-DOUBLE-REG").version == 1
    assert get_template("QUAD-RECT-AREA", 1).id == "QUAD-RECT-AREA"
    with pytest.raises(UnknownTemplate):
        get_template("NOPE")
    with pytest.raises(UnknownTemplate):
        get_template("QUAD-RECT-AREA", 99)
    with pytest.raises(ValueError, match="already registered"):
        register(RegisteredDoubling)


def test_generic_pipeline_validates_a_well_formed_template() -> None:
    q = generate(get_template("TEST-DOUBLE-REG"), 3)
    assert all(c.passed for c in q.validation)
    assert q.expected_answer == {"n": 2 * q.parameters["n"]}


def test_unregistered_template_fails_structural_validation() -> None:
    with pytest.raises(InvalidInstance, match="template_registered"):
        generate(Doubling(), 1)


def test_misaligned_expected_answer_is_caught() -> None:
    @register
    class WrongAnswer(Doubling):
        id = "TEST-WRONG-ANSWER"

        def expected_answer(self, p: NParams) -> NResponse:
            return NResponse(n=2 * p.n + 1)

    with pytest.raises(InvalidInstance, match="answer_marking_aligned"):
        generate(get_template("TEST-WRONG-ANSWER"), 1)


def test_unknown_objective_is_caught() -> None:
    @register
    class BadObjective(Doubling):
        id = "TEST-BAD-OBJECTIVE"
        secondary_objectives = ("MOD-42",)

    with pytest.raises(InvalidInstance, match="objectives_exist"):
        generate(get_template("TEST-BAD-OBJECTIVE"), 1)


def test_unsatisfiable_constraints_raise_generation_error() -> None:
    @register
    class Impossible(Doubling):
        id = "TEST-IMPOSSIBLE"
        max_sampling_attempts = 5
        constraints = (Constraint("never", "n must exceed 10", lambda p: p.n > 10),)

    with pytest.raises(GenerationError, match="never"):
        generate(get_template("TEST-IMPOSSIBLE"), 1)


def test_build_with_explicit_params_reports_every_problem() -> None:
    template: Any = get_template("TEST-DOUBLE-REG")
    with pytest.raises(Exception) as exc:
        build(template, {"n": 11, "extra": 1})
    assert len(exc.value.problems) == 2  # type: ignore[attr-defined]
