import math
from typing import Any

import pytest

from app.engine import build, generate, get_template
from app.engine.base import InvalidParameters
from app.engine.scenarios import compatible_scenarios, get_scenario, slots_for
from app.engine.templates.trig_wheel_height import (
    CORRECT_ASSUMPTION,
    WheelParams,
    WheelResponse,
    WheelSlots,
)
from app.models.enums import StepOutcome

TEMPLATE = get_template("TRIG-WHEEL-HEIGHT")
FERRIS = get_scenario("SCN-WHEEL-FERRIS")
SLOTS: WheelSlots = slots_for(TEMPLATE, FERRIS)  # type: ignore[assignment]
# Docstring example: radius 20 m, lowest point 2 m, 12 minutes per revolution, target 32 m.
EXAMPLE = WheelParams(radius=20, clearance=2, period=12, angle=120, centre=22, target_height=32, t1=4, t2=8)
FULL: dict[str, Any] = dict(
    amplitude=20, centre_height=22, period=12, model="h = 22 - 20cos(30t)", times=[4, 8], assumption=CORRECT_ASSUMPTION
)


def mark(**response: Any) -> dict[str, StepOutcome]:
    return {s.step: s.outcome for s in TEMPLATE.mark(EXAMPLE, SLOTS, WheelResponse(**response))}


def test_example_question_and_solution() -> None:
    q = build(TEMPLATE, EXAMPLE.model_dump(), scenario=FERRIS)
    assert "radius of 20 m" in q.prompt and "every 12 minutes" in q.prompt and "32 m above the ground" in q.prompt
    assert q.expected_answer["times"] == [4, 8]
    texts = " ".join(s.text for s in q.worked_solution)
    assert "cos(30t) = (22 - 32) ÷ 20 = -0.5" in texts and "16 and 20" in texts


@pytest.mark.parametrize("scenario_id", [s.id for s in compatible_scenarios(TEMPLATE)])
def test_20_valid_instances_per_scenario(scenario_id: str) -> None:
    sc = get_scenario(scenario_id)
    instances = [generate(TEMPLATE, seed, sc) for seed in range(1, 21)]
    assert len({str(q.parameters) for q in instances}) >= 12
    for q in instances:
        assert all(c.passed for c in q.validation), [c for c in q.validation if not c.passed]
        p = WheelParams(**q.parameters)
        # Exact-value derivation: both times give the target height, within one revolution.
        for t in (p.t1, p.t2):
            assert p.height(t) == pytest.approx(p.target_height)
            assert 0 < t < p.period
        assert 360 % p.period == 0 and p.angle in (60, 90, 120)
        assert "cos" not in q.prompt and "constant" not in q.prompt


def test_all_three_exact_angles_occur() -> None:
    angles = {generate(TEMPLATE, seed, FERRIS).parameters["angle"] for seed in range(1, 60)}
    assert angles == {60, 90, 120}


@pytest.mark.parametrize(
    "overrides",
    [
        {"period": 7, "t2": 3},  # 7 does not divide 360
        {"angle": 45},  # inexact cosine
        {"target_height": 33},  # not derived from the angle
        {"t1": 5, "t2": 7},  # wrong times
        {"centre": 21},  # centre != radius + clearance
        {"radius": 21, "centre": 23, "target_height": 33},  # odd radius with cos = -0.5
        {"radius": "20"},
    ],
)
def test_invalid_parameters_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidParameters):
        build(TEMPLATE, {**EXAMPLE.model_dump(), **overrides}, scenario=FERRIS)


def test_full_response_is_correct() -> None:
    assert set(mark(**FULL).values()) == {StepOutcome.CORRECT}


@pytest.mark.parametrize(
    "model",
    ["22 - 20cos(30t)", "h=22-20cos(30t)", "22 + 20sin(30t - 90)", "-20cos(30t) + 22", "22 - 20 cos (30 t)"],
)
def test_equivalent_models_are_accepted(model: str) -> None:
    assert mark(**{**FULL, "model": model})["form_model"] is StepOutcome.CORRECT


def test_model_starting_at_the_top_gets_specific_feedback() -> None:
    steps = TEMPLATE.mark(EXAMPLE, SLOTS, WheelResponse(**{**FULL, "model": "22 + 20cos(30t)"}))
    form = next(s for s in steps if s.step == "form_model")
    assert form.outcome is StepOutcome.INCORRECT and "highest point" in form.feedback


@pytest.mark.parametrize("model", ["22 - 20cos(t)", "20 - 22cos(30t)", "22 - 20sin(30t)", "tan(30t)"])
def test_wrong_models_are_rejected(model: str) -> None:
    assert mark(**{**FULL, "model": model})["form_model"] is StepOutcome.INCORRECT


def test_times_outside_the_first_revolution_are_rejected() -> None:
    outcome = mark(**{**FULL, "times": [4, 8, 16]})
    assert outcome["solve"] is StepOutcome.CORRECT
    assert outcome["validate_times"] is StepOutcome.INCORRECT
    assert mark(**{**FULL, "times": [-4, 4, 8]})["validate_times"] is StepOutcome.INCORRECT


def test_only_one_time_is_incomplete() -> None:
    steps = TEMPLATE.mark(EXAMPLE, SLOTS, WheelResponse(**{**FULL, "times": [4]}))
    by_step = {s.step: s for s in steps}
    assert by_step["solve"].outcome is StepOutcome.CORRECT
    assert by_step["validate_times"].outcome is StepOutcome.INCORRECT and "twice" in by_step["validate_times"].feedback


def test_marking_separates_extraction_model_and_assumption() -> None:
    outcome = mark(**{**FULL, "centre_height": 20})
    assert outcome["extract_features"] is StepOutcome.INCORRECT and outcome["form_model"] is StepOutcome.CORRECT
    outcome = mark(**{**FULL, "assumption": "The wheel speeds up during each revolution."})
    assert outcome["state_assumption"] is StepOutcome.INCORRECT and outcome["solve"] is StepOutcome.CORRECT
    assert set(mark().values()) == {StepOutcome.MISSING}


def test_units_follow_the_scenario() -> None:
    water = slots_for(TEMPLATE, get_scenario("SCN-WHEEL-WATERMILL"))
    units = {f.name: f.unit for f in TEMPLATE.fields(water)}
    assert units["times"] == "seconds" and units["amplitude"] == "m"
    q = generate(TEMPLATE, 2, get_scenario("SCN-WHEEL-WATERMILL"))
    assert "above the floor of the pit" in q.prompt and "ground" not in q.prompt


def test_height_function_matches_the_lowest_and_highest_points() -> None:
    assert EXAMPLE.height(0) == pytest.approx(2)
    assert EXAMPLE.height(6) == pytest.approx(42)
    assert math.isclose(EXAMPLE.height(12), 2, abs_tol=1e-9)
