from typing import Any

import pytest

from app.engine import build, generate, get_template
from app.engine.base import InvalidParameters
from app.engine.scenarios import compatible_scenarios, get_scenario, slots_for
from app.engine.templates.linear_two_point import LinearParams, LinearResponse, LinearSlots
from app.models.enums import StepOutcome

TEMPLATE = get_template("LIN-TWO-POINT")
TAXI = get_scenario("SCN-LIN-TAXI")
SLOTS: LinearSlots = slots_for(TEMPLATE, TAXI)  # type: ignore[assignment]
# The docstring example: 4 miles £11, 10 miles £23, estimate at 7 miles. y = 2x + 3.
EXAMPLE = LinearParams(
    gradient_tenths=20, intercept=3, x1=4, gap=6, extrapolate=0, x2=10, x3=7, y1=11, y2=23, y3=17
)
FULL = dict(
    gradient=2,
    equation="y = 2x + 3",
    gradient_meaning="the cost per mile",
    prediction=17,
    reliability="within the data",
)


def mark(**response: Any) -> dict[str, StepOutcome]:
    return {s.step: s.outcome for s in TEMPLATE.mark(EXAMPLE, SLOTS, LinearResponse(**response))}


def test_example_question_and_solution() -> None:
    q = build(TEMPLATE, EXAMPLE.model_dump(), scenario=TAXI)
    assert q.prompt.startswith("A taxi journey of 4 miles costs £11 and a journey of 10 miles costs £23.")
    assert q.expected_answer["equation"] == "y = 2x + 3" and q.expected_answer["prediction"] == 17
    texts = " ".join(s.text for s in q.worked_solution)
    assert "12 ÷ 6 = 2" in texts and "c = 3" in texts and "interpolation" in texts


@pytest.mark.parametrize("scenario_id", [s.id for s in compatible_scenarios(TEMPLATE)])
def test_20_valid_instances_per_scenario(scenario_id: str) -> None:
    sc = get_scenario(scenario_id)
    instances = [generate(TEMPLATE, seed, sc) for seed in range(1, 21)]
    assert len({str(q.parameters) for q in instances}) >= 15
    for q in instances:
        assert all(c.passed for c in q.validation), [c for c in q.validation if not c.passed]
        p = q.parameters
        m = p["gradient_tenths"] / 10
        for i in (1, 2, 3):
            assert p[f"y{i}"] == pytest.approx(m * p[f"x{i}"] + p["intercept"])
        assert (p["x3"] > p["x2"]) == bool(p["extrapolate"])


def test_temperature_scenario_is_the_exact_conversion_and_never_extrapolates() -> None:
    sc = get_scenario("SCN-LIN-TEMPERATURE")
    for seed in range(1, 30):
        p = generate(TEMPLATE, seed, sc).parameters
        assert (p["gradient_tenths"], p["intercept"], p["extrapolate"]) == (18, 32, 0)


def test_both_reliability_cases_occur() -> None:
    flags = {generate(TEMPLATE, seed, TAXI).parameters["extrapolate"] for seed in range(1, 30)}
    assert flags == {0, 1}


@pytest.mark.parametrize(
    "overrides",
    [
        {"y2": 24},  # not on the line
        {"x2": 11},  # inconsistent with gap
        {"x3": 12},  # outside the data but extrapolate=0
        {"gradient_tenths": 0},
        {"gap": 0},
        {"y1": "11"},
        {"slope": 2},
    ],
)
def test_invalid_parameters_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidParameters):
        build(TEMPLATE, {**EXAMPLE.model_dump(), **overrides}, scenario=TAXI)


def test_full_response_is_correct() -> None:
    assert set(mark(**FULL).values()) == {StepOutcome.CORRECT}


@pytest.mark.parametrize("equation", ["y = 2x + 3", "y=3+2x", "2x - y + 3 = 0", "2y = 4x + 6", "y - 3 = 2(x)"])
def test_equivalent_line_equations_are_accepted(equation: str) -> None:
    assert mark(**{**FULL, "equation": equation})["form_equation"] is StepOutcome.CORRECT


@pytest.mark.parametrize("equation", ["y = 3x + 2", "y = 2x", "x = 2y + 3", "y = 2x^2 + 3"])
def test_wrong_line_equations_are_rejected(equation: str) -> None:
    assert mark(**{**FULL, "equation": equation})["form_equation"] is StepOutcome.INCORRECT


def test_marking_separates_gradient_model_interpretation_and_evaluation() -> None:
    outcome = mark(**{**FULL, "gradient": 0.5})  # inverted
    assert outcome["find_gradient"] is StepOutcome.INCORRECT and outcome["form_equation"] is StepOutcome.CORRECT
    outcome = mark(**{**FULL, "gradient_meaning": "the fixed charge"})
    assert outcome["interpret_gradient"] is StepOutcome.INCORRECT
    outcome = mark(**{**FULL, "reliability": "beyond the data"})
    assert outcome["judge_reliability"] is StepOutcome.INCORRECT and outcome["predict"] is StepOutcome.CORRECT


def test_prediction_follows_through_from_a_wrong_equation() -> None:
    outcome = mark(**{**FULL, "equation": "y = 3x + 2", "prediction": 23})
    assert outcome["form_equation"] is StepOutcome.INCORRECT and outcome["predict"] is StepOutcome.CORRECT
    assert mark(**{**FULL, "equation": "y = 3x + 2", "prediction": 30})["predict"] is StepOutcome.INCORRECT


def test_meaning_options_come_from_the_scenario_and_are_sorted() -> None:
    (field,) = [f for f in TEMPLATE.fields(SLOTS) if f.name == "gradient_meaning"]
    assert set(field.options) == {"the cost per mile", "the fixed charge", "the total cost of the journey"}
    assert list(field.options) == sorted(field.options)


def test_slots_reject_missing_placeholders() -> None:
    with pytest.raises(ValueError, match="x1"):
        LinearSlots(**{**SLOTS.model_dump(), "data": "A journey costs £{y1}."})
    with pytest.raises(ValueError, match="differ"):
        LinearSlots(**{**SLOTS.model_dump(), "distractor": "the cost per mile"})
