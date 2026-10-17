"""Deterministic generation and validation of question instances.

generate(template, seed, scenario) is a pure function of (template id, template version,
seed, scenario id, scenario version): the same inputs always give the same instance. With no
scenario, one is picked deterministically from the seed. build(template, params) validates
explicit parameters instead of sampling them. Both raise rather than return an invalid instance.
"""

import random
from dataclasses import asdict
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError

from app.catalogue import load_catalogue
from app.engine.base import (
    AnyTemplate,
    Bounds,
    GeneratedQuestion,
    GenerationError,
    InvalidInstance,
    InvalidParameters,
    ValidationCategory,
    ValidationCheck,
)
from app.engine.registry import UnknownTemplate, get_template
from app.engine.scenarios import (
    UnknownScenario,
    compatible_scenarios,
    effective_bounds,
    get_scenario,
    pick_scenario,
    slots_for,
)
from app.models.enums import StepOutcome
from app.scenarios import Scenario

S, M, P = ValidationCategory.STRUCTURAL, ValidationCategory.MATHEMATICAL, ValidationCategory.PEDAGOGICAL


@lru_cache
def catalogue_ids() -> frozenset[str]:
    return frozenset(o.id for o in load_catalogue().objectives)


def rng_for(template: AnyTemplate, seed: int) -> random.Random:
    # String seeds are hashed with SHA-512 by random.Random: stable across runs and platforms.
    return random.Random(f"{template.id}:v{template.version}:{seed}")


def parse_params(template: AnyTemplate, params: BaseModel | dict[str, Any], bounds: Bounds | None = None) -> BaseModel:
    raw = params.model_dump() if isinstance(params, BaseModel) else params
    try:
        parsed = template.params_model.model_validate(raw)
    except ValidationError as exc:
        raise InvalidParameters(
            f"Invalid parameters for {template.id} v{template.version}",
            [f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()],
        ) from exc
    failed = constraint_failures(template, parsed) + bounds_failures(parsed, bounds or {})
    if failed:
        raise InvalidParameters(f"Constraints failed for {template.id} v{template.version}", failed)
    return parsed


def constraint_failures(template: AnyTemplate, params: BaseModel) -> list[str]:
    return [f"{c.name}: {c.description}" for c in template.constraints if not c.holds(params)]


def bounds_failures(params: BaseModel, bounds: Bounds) -> list[str]:
    return [
        f"{name}={getattr(params, name)} is outside the scenario's range [{lo}, {hi}]"
        for name, (lo, hi) in bounds.items()
        if not lo <= getattr(params, name) <= hi
    ]


def _resolve(template: AnyTemplate, scenario: Scenario) -> tuple[BaseModel, Bounds]:
    try:
        return slots_for(template, scenario), effective_bounds(template, scenario)
    except (UnknownScenario, ValidationError) as exc:
        raise GenerationError(f"Scenario {scenario.id} v{scenario.version} cannot be used", [str(exc)]) from exc


def generate(template: AnyTemplate, seed: int, scenario: Scenario | None = None) -> GeneratedQuestion:
    if scenario is None:
        try:
            scenario = pick_scenario(template, seed, compatible_scenarios(template))
        except UnknownScenario as exc:
            raise GenerationError(f"Cannot generate {template.id} v{template.version}", [str(exc)]) from exc
    slots, bounds = _resolve(template, scenario)
    # The parameter RNG ignores the scenario: scenarios change sampling only through bounds.
    rng = rng_for(template, seed)
    last: list[str] = []
    for _ in range(template.max_sampling_attempts):
        params = template.sample(rng, bounds)
        last = constraint_failures(template, params) + bounds_failures(params, bounds)
        if not last:
            return _assemble(template, params, seed, scenario, slots)
    raise GenerationError(
        f"No valid parameters for {template.id} v{template.version} with {scenario.id} after "
        f"{template.max_sampling_attempts} attempts (seed {seed})",
        last,
    )


def build(
    template: AnyTemplate,
    params: BaseModel | dict[str, Any],
    seed: int | None = None,
    scenario: Scenario | None = None,
) -> GeneratedQuestion:
    scenario = scenario or get_scenario(template.default_scenario)
    slots, bounds = _resolve(template, scenario)
    return _assemble(template, parse_params(template, params, bounds), seed, scenario, slots)


def _assemble(
    template: AnyTemplate, params: BaseModel, seed: int | None, scenario: Scenario, slots: BaseModel
) -> GeneratedQuestion:
    prompt = template.render_prompt(params, slots)
    checks = validate(template, params, slots, scenario, prompt)
    failed = [f"[{c.category}] {c.name}: {c.message}" for c in checks if not c.passed]
    if failed:
        raise InvalidInstance(f"Generated {template.id} v{template.version} instance is invalid", failed)
    return GeneratedQuestion(
        template_id=template.id,
        template_version=template.version,
        scenario_id=scenario.id,
        scenario_version=scenario.version,
        seed=seed,
        parameters=params.model_dump(mode="json"),
        prompt=prompt,
        expected_answer=template.expected_answer(params, slots).model_dump(mode="json"),
        worked_solution=template.worked_solution(params, slots),
        primary_objective=template.primary_objective,
        secondary_objectives=template.secondary_objectives,
        difficulty=template.difficulty(params),
        validation=checks,
    )


def _check(name: str, category: ValidationCategory, passed: bool, message: str = "") -> ValidationCheck:
    return ValidationCheck(name=name, category=category, passed=passed, message="" if passed else message)


def validate(
    template: AnyTemplate, params: BaseModel, slots: BaseModel, scenario: Scenario, prompt: str
) -> list[ValidationCheck]:
    """Generic checks every template gets, followed by the template's own checks."""
    try:
        registered = get_template(template.id, template.version) is template
    except UnknownTemplate:
        registered = False
    unknown = [o for o in template.objectives if o not in catalogue_ids()]
    criteria_objectives = {c.objective for c in template.marking_criteria}
    worked_objectives = {s.objective for s in template.worked_solution(params, slots)}
    marked = template.mark(params, slots, template.expected_answer(params, slots))
    bounds = effective_bounds(template, scenario)
    not_correct = [m.step for m in marked if m.outcome is not StepOutcome.CORRECT]
    criteria_steps = [c.step for c in template.marking_criteria]

    checks = [
        _check("template_registered", S, registered, f"{template.id} v{template.version} is not in the registry"),
        _check("objectives_exist", S, not unknown, f"unknown objectives {unknown}"),
        _check(
            "marking_objectives_declared",
            S,
            criteria_objectives <= set(template.objectives),
            f"marking criteria assess undeclared objectives {sorted(criteria_objectives - set(template.objectives))}",
        ),
        _check(
            "parameters_typed",
            S,
            isinstance(params, template.params_model),
            f"parameters are not a {template.params_model.__name__}",
        ),
        _check(
            "scenario_compatible",
            S,
            scenario.compatibility(template.id, template.version) is not None,
            f"{scenario.id} v{scenario.version} does not list {template.id} v{template.version}",
        ),
        _check(
            "slots_typed", S, isinstance(slots, template.slots_model), f"slots are not a {template.slots_model.__name__}"
        ),
        _check("constraints_hold", M, not constraint_failures(template, params), "parameter constraints fail"),
        _check("within_scenario_bounds", M, not bounds_failures(params, bounds), "parameters outside scenario bounds"),
        _check(
            "primary_objective_assessed",
            P,
            template.primary_objective in criteria_objectives,
            f"no marking criterion assesses the primary objective {template.primary_objective}",
        ),
        _check(
            "answer_marking_aligned",
            P,
            not not_correct and [m.step for m in marked] == criteria_steps,
            f"the expected answer is not marked fully correct (steps {not_correct})",
        ),
        _check(
            "worked_solution_covers_criteria",
            P,
            criteria_objectives <= worked_objectives,
            f"worked solution misses objectives {sorted(criteria_objectives - worked_objectives)}",
        ),
        _check("difficulty_range", M, 1 <= template.difficulty(params) <= 5, "difficulty must be 1..5"),
    ]
    return checks + template.checks(params, slots, prompt)


def check_dicts(checks: list[ValidationCheck]) -> list[dict[str, Any]]:
    return [asdict(c) for c in checks]
