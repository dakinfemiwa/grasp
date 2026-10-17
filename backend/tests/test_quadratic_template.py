from typing import Any

import pytest

from app.engine import build, generate, get_template
from app.engine.base import InvalidParameters
from app.engine.templates.quadratic_rectangle import RectangleParams, RectangleResponse, RectangleSlots
from app.models.enums import StepOutcome

TEMPLATE = get_template("QUAD-RECT-AREA")
GARDEN = RectangleParams(width=8, difference=4, area=96)
CM = RectangleSlots(subject="A rectangle", unit="cm")


def mark(**response: Any) -> dict[str, StepOutcome]:
    steps = TEMPLATE.mark(GARDEN, CM, RectangleResponse(**response))
    return {s.step: s.outcome for s in steps}


FULL = dict(variable="width", other_side="x + 4", equation="x(x + 4) = 96", roots=[8, -12], width=8, length=12)
ALL_CORRECT = {
    "define_variables": StepOutcome.CORRECT,
    "form_equation": StepOutcome.CORRECT,
    "solve": StepOutcome.CORRECT,
    "reject_invalid_root": StepOutcome.CORRECT,
    "interpret_dimensions": StepOutcome.CORRECT,
}


def test_brief_example_garden() -> None:
    q = build(TEMPLATE, GARDEN.model_dump(), seed=None)
    assert q.prompt.startswith("A rectangle has a length that is 4 cm greater than its width. Its area is 96 cm².")
    assert q.expected_answer["roots"] == [8, -12]
    assert (q.expected_answer["width"], q.expected_answer["length"]) == (8, 12)
    texts = " ".join(s.text for s in q.worked_solution)
    assert "x(x + 4) = 96" in texts and "reject x = -12" in texts and "8 × 12 = 96" in texts
    assert q.primary_objective == "MOD-05"


def test_generation_is_deterministic_per_seed_and_version() -> None:
    assert generate(TEMPLATE, 42) == generate(TEMPLATE, 42)
    assert len({str(generate(TEMPLATE, s).parameters) for s in range(1, 11)}) > 1


def test_at_least_20_generated_instances_pass_all_validation() -> None:
    instances = [generate(TEMPLATE, seed) for seed in range(1, 31)]
    distinct = {(q.parameters["width"], q.parameters["difference"]) for q in instances}
    assert len(distinct) >= 20
    assert {q.difficulty for q in instances} >= {1, 2, 3}
    for q in instances:
        assert q.validation and all(c.passed for c in q.validation), q.validation
        p = q.parameters
        a = q.expected_answer
        # The expected answer satisfies the original conditions...
        assert a["width"] * a["length"] == p["area"] and a["length"] - a["width"] == p["difference"]
        # ...and both roots satisfy the model, one of them negative.
        assert all(r * (r + p["difference"]) == p["area"] for r in a["roots"])
        assert min(a["roots"]) < 0 < a["width"]
        assert {s.objective for s in q.worked_solution} >= set(TEMPLATE.objectives)


@pytest.mark.parametrize(
    "params",
    [
        {"width": 0, "difference": 4, "area": 0},
        {"width": 8, "difference": 0, "area": 64},
        {"width": 8, "difference": 4, "area": 95},  # inconsistent derived value
        {"width": 20, "difference": 12, "area": 640},  # over the area limit
        {"width": 8, "difference": 4},
        {"width": "8", "difference": 4, "area": 96},
        {"width": 8.5, "difference": 4, "area": 102},
        {"width": 8, "difference": 4, "area": 96, "unit": "m"},
    ],
)
def test_invalid_parameters_are_rejected(params: dict[str, Any]) -> None:
    with pytest.raises(InvalidParameters) as exc:
        build(TEMPLATE, params)
    assert exc.value.problems


def test_full_correct_response() -> None:
    assert mark(**FULL) == ALL_CORRECT


@pytest.mark.parametrize(
    "equation", ["x^2 + 4x - 96 = 0", "96 = x(x+4)", "x**2 + 4*x = 96", "2x^2 + 8x = 192", "(x-8)(x+12)=0"]
)
def test_equivalent_equations_are_accepted(equation: str) -> None:
    assert mark(**{**FULL, "equation": equation})["form_equation"] is StepOutcome.CORRECT


def test_length_as_variable_is_an_equally_valid_model() -> None:
    response = dict(variable="length", other_side="x - 4", equation="x(x - 4) = 96", roots=[12, -8], width=8, length=12)
    assert mark(**response) == ALL_CORRECT


def test_negative_root_is_not_accepted_as_a_width() -> None:
    outcome = mark(**{**FULL, "width": -12, "length": -8})
    assert outcome["solve"] is StepOutcome.CORRECT
    assert outcome["reject_invalid_root"] is StepOutcome.INCORRECT
    assert outcome["interpret_dimensions"] is StepOutcome.INCORRECT


def test_marking_separates_construction_solving_and_interpretation() -> None:
    # Right equation, wrong solving.
    outcome = mark(**{**FULL, "roots": [6, -16]})
    assert (outcome["form_equation"], outcome["solve"]) == (StepOutcome.CORRECT, StepOutcome.INCORRECT)
    # Wrong equation (perimeter, not area) but solved correctly: follow-through credit for solving.
    outcome = mark(**{**FULL, "equation": "x^2 + 4x = 60", "roots": [6, -10]})
    assert (outcome["form_equation"], outcome["solve"]) == (StepOutcome.INCORRECT, StepOutcome.CORRECT)
    # Everything right except the final interpretation (swapped).
    outcome = mark(**{**FULL, "width": 12, "length": 8})
    assert outcome["solve"] is StepOutcome.CORRECT and outcome["interpret_dimensions"] is StepOutcome.INCORRECT


def test_wrong_variable_relationship_and_partial_answers() -> None:
    outcome = mark(**{**FULL, "other_side": "x - 4"})
    assert outcome["define_variables"] is StepOutcome.INCORRECT
    only_positive = TEMPLATE.mark(GARDEN, CM, RectangleResponse(**{**FULL, "roots": [8]}))
    solve = next(s for s in only_positive if s.step == "solve")
    assert solve.outcome is StepOutcome.INCORRECT and "two solutions" in solve.feedback
    assert set(mark().values()) == {StepOutcome.MISSING}


def test_unparseable_equation_gets_feedback_not_an_error() -> None:
    steps = TEMPLATE.mark(GARDEN, CM, RectangleResponse(**{**FULL, "equation": "x(x+4) 96"}))
    form = next(s for s in steps if s.step == "form_equation")
    assert form.outcome is StepOutcome.INCORRECT and "=" in form.feedback
