import re
from typing import Any

import pytest

from app.engine import all_templates, build, generate, get_template
from app.engine.base import InvalidParameters
from app.engine.scenarios import (
    compatible_scenarios,
    effective_bounds,
    get_scenario,
    pick_scenario,
    scenario_library,
    validate_library,
)
from app.scenarios import ScenarioError, parse_scenario_file

QUAD = get_template("QUAD-RECT-AREA")


def scenario(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "SCN-T",
        "version": 1,
        "title": "t",
        "description": "d",
        "entities": ["e"],
        "relationships": ["r"],
        "presentation": "narrative",
        "review_status": "draft",
        "compatible_templates": [
            {"template": "QUAD-RECT-AREA", "version": 1, "slots": {"subject": "A pond", "unit": "m"}}
        ],
    }
    data.update(overrides)
    return data


def check(*scenarios: dict[str, Any]) -> None:
    validate_library(parse_scenario_file({"scenarios": list(scenarios)}))


def test_real_library_loads_and_is_compatible() -> None:
    library = scenario_library()
    ids = {s.id for s in library}
    assert {"SCN-RECT-ABSTRACT", "SCN-RECT-GARDEN", "SCN-RECT-TRAINING"} <= ids
    assert QUAD.default_scenario in ids
    assert len(compatible_scenarios(QUAD)) >= 5


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"compatible_templates": [{"template": "NOPE", "version": 1, "slots": {}}]}, "unknown template"),
        ({"compatible_templates": [{"template": "QUAD-RECT-AREA", "version": 9, "slots": {}}]}, "unknown template"),
        (
            {"compatible_templates": [{"template": "QUAD-RECT-AREA", "version": 1, "slots": {"subject": "A pond"}}]},
            "slots.unit",
        ),
        (
            {"compatible_templates": [{"template": "QUAD-RECT-AREA", "version": 1, "slots": {"subject": "x", "unit": "km"}}]},
            "slots.unit",
        ),
        (
            {
                "compatible_templates": [
                    {
                        "template": "QUAD-RECT-AREA",
                        "version": 1,
                        "slots": {"subject": "A pond", "unit": "m"},
                        "bounds": {"width": {"min": 1, "max": 30}},
                    }
                ]
            },
            "widens",
        ),
        (
            {
                "compatible_templates": [
                    {
                        "template": "QUAD-RECT-AREA",
                        "version": 1,
                        "slots": {"subject": "A pond", "unit": "m"},
                        "bounds": {"area": {"min": 1, "max": 30}},
                    }
                ]
            },
            "not a sampled parameter",
        ),
    ],
)
def test_rejects_incompatible_scenarios(overrides: dict[str, Any], expected: str) -> None:
    with pytest.raises(ScenarioError, match=expected):
        check(scenario(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [{"surprise": 1}, {"id": "garden"}, {"entities": []}, {"compatible_templates": []}, {"presentation": "video"}],
)
def test_rejects_malformed_scenarios(overrides: dict[str, Any]) -> None:
    with pytest.raises(ScenarioError):
        check(scenario(**overrides))


def test_rejects_duplicate_and_inverted_bounds() -> None:
    with pytest.raises(ScenarioError, match="duplicate"):
        check(scenario(), scenario())
    bad = scenario()
    bad["compatible_templates"][0]["bounds"] = {"width": {"min": 9, "max": 3}}
    with pytest.raises(ScenarioError, match="greater than max"):
        check(bad)


def test_bounds_narrow_sampling() -> None:
    training = get_scenario("SCN-RECT-TRAINING")
    assert effective_bounds(QUAD, training) == {"width": (10, 20), "difference": (2, 10)}
    widths = {generate(QUAD, seed, training).parameters["width"] for seed in range(1, 40)}
    assert min(widths) >= 10


def test_explicit_params_outside_scenario_bounds_are_rejected() -> None:
    with pytest.raises(InvalidParameters, match="scenario's range"):
        build(QUAD, {"width": 3, "difference": 4, "area": 21}, scenario=get_scenario("SCN-RECT-TRAINING"))


@pytest.mark.parametrize("scenario_id", [s.id for s in compatible_scenarios(QUAD)])
def test_every_rectangle_scenario_yields_20_valid_reproducible_instances(scenario_id: str) -> None:
    sc = get_scenario(scenario_id)
    slots = QUAD.slots_model.model_validate(sc.compatibility(QUAD.id, QUAD.version).slots)  # type: ignore[union-attr]
    instances = [generate(QUAD, seed, sc) for seed in range(1, 21)]
    assert all(all(c.passed for c in q.validation) for q in instances)
    assert all(q.scenario_id == scenario_id and slots.subject in q.prompt for q in instances)
    assert all(f"{slots.unit}²" in q.prompt for q in instances)
    assert generate(QUAD, 7, sc) == generate(QUAD, 7, sc)


def test_scenario_pick_is_deterministic_and_covers_the_library() -> None:
    candidates = compatible_scenarios(QUAD)
    assert pick_scenario(QUAD, 11, candidates) == pick_scenario(QUAD, 11, candidates)
    assert {generate(QUAD, seed).scenario_id for seed in range(1, 60)} == {s.id for s in candidates}


def test_abstract_scenario_reproduces_pre_library_instances() -> None:
    # Instances saved in Stage 4 (before scenarios) were backfilled to SCN-RECT-ABSTRACT v1.
    q = generate(QUAD, 1, get_scenario("SCN-RECT-ABSTRACT"))
    assert q.parameters == {"width": 8, "difference": 2, "area": 80}
    assert q.prompt.startswith("A rectangle has a length that is 2 cm greater than its width. Its area is 80 cm².")


@pytest.mark.parametrize(
    "template", [t for t in all_templates() if not t.id.startswith("TEST-")], ids=lambda t: t.id
)
def test_every_template_is_wired_to_the_library(template: Any) -> None:
    """Default scenario exists and is compatible; each scenario gives valid instances; spec refs are well-formed."""
    default = get_scenario(template.default_scenario)
    assert default.compatibility(template.id, template.version) is not None
    assert compatible_scenarios(template)
    assert template.spec_refs and all(re.fullmatch(r"OT\d\.\d|\d{1,2}\.\d{1,2}", r) for r in template.spec_refs)
    assert {c.step for c in template.marking_criteria} == {
        s.step for s in template.mark(*_expected(template, default))
    }


def _expected(template: Any, scenario: Any) -> tuple[Any, Any, Any]:
    q = generate(template, 1, scenario)
    params = template.params_model.model_validate(q.parameters)
    slots = template.slots_model.model_validate(scenario.compatibility(template.id, template.version).slots)
    return params, slots, template.expected_answer(params, slots)
