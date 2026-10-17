"""Deterministic generation and validation of question instances.

generate(template, seed) is a pure function of (template id, template version, seed): the
same inputs always give the same instance. build(template, params) validates explicit
parameters instead of sampling them. Both raise rather than return an invalid instance.
"""

import random
from dataclasses import asdict
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError

from app.catalogue import load_catalogue
from app.engine.base import (
    AnyTemplate,
    GeneratedQuestion,
    GenerationError,
    InvalidInstance,
    InvalidParameters,
    ValidationCategory,
    ValidationCheck,
)
from app.engine.registry import UnknownTemplate, get_template
from app.models.enums import StepOutcome

S, M, P = ValidationCategory.STRUCTURAL, ValidationCategory.MATHEMATICAL, ValidationCategory.PEDAGOGICAL


@lru_cache
def catalogue_ids() -> frozenset[str]:
    return frozenset(o.id for o in load_catalogue().objectives)


def rng_for(template: AnyTemplate, seed: int) -> random.Random:
    # String seeds are hashed with SHA-512 by random.Random: stable across runs and platforms.
    return random.Random(f"{template.id}:v{template.version}:{seed}")


def parse_params(template: AnyTemplate, params: BaseModel | dict[str, Any]) -> BaseModel:
    raw = params.model_dump() if isinstance(params, BaseModel) else params
    try:
        parsed = template.params_model.model_validate(raw)
    except ValidationError as exc:
        raise InvalidParameters(
            f"Invalid parameters for {template.id} v{template.version}",
            [f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()],
        ) from exc
    failed = constraint_failures(template, parsed)
    if failed:
        raise InvalidParameters(f"Constraints failed for {template.id} v{template.version}", failed)
    return parsed


def constraint_failures(template: AnyTemplate, params: BaseModel) -> list[str]:
    return [f"{c.name}: {c.description}" for c in template.constraints if not c.holds(params)]


def generate(template: AnyTemplate, seed: int) -> GeneratedQuestion:
    rng = rng_for(template, seed)
    last: list[str] = []
    for _ in range(template.max_sampling_attempts):
        params = template.sample(rng)
        last = constraint_failures(template, params)
        if not last:
            return _assemble(template, params, seed)
    raise GenerationError(
        f"No valid parameters for {template.id} v{template.version} after "
        f"{template.max_sampling_attempts} attempts (seed {seed})",
        last,
    )


def build(template: AnyTemplate, params: BaseModel | dict[str, Any], seed: int | None = None) -> GeneratedQuestion:
    return _assemble(template, parse_params(template, params), seed)


def _assemble(template: AnyTemplate, params: BaseModel, seed: int | None) -> GeneratedQuestion:
    prompt = template.render_prompt(params)
    checks = validate(template, params, prompt)
    failed = [f"[{c.category}] {c.name}: {c.message}" for c in checks if not c.passed]
    if failed:
        raise InvalidInstance(f"Generated {template.id} v{template.version} instance is invalid", failed)
    return GeneratedQuestion(
        template_id=template.id,
        template_version=template.version,
        seed=seed,
        parameters=params.model_dump(mode="json"),
        prompt=prompt,
        expected_answer=template.expected_answer(params).model_dump(mode="json"),
        worked_solution=template.worked_solution(params),
        primary_objective=template.primary_objective,
        secondary_objectives=template.secondary_objectives,
        difficulty=template.difficulty(params),
        validation=checks,
    )


def _check(name: str, category: ValidationCategory, passed: bool, message: str = "") -> ValidationCheck:
    return ValidationCheck(name=name, category=category, passed=passed, message="" if passed else message)


def validate(template: AnyTemplate, params: BaseModel, prompt: str) -> list[ValidationCheck]:
    """Generic checks every template gets, followed by the template's own checks."""
    try:
        registered = get_template(template.id, template.version) is template
    except UnknownTemplate:
        registered = False
    unknown = [o for o in template.objectives if o not in catalogue_ids()]
    criteria_objectives = {c.objective for c in template.marking_criteria}
    worked_objectives = {s.objective for s in template.worked_solution(params)}
    marked = template.mark(params, template.expected_answer(params))
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
        _check("constraints_hold", M, not constraint_failures(template, params), "parameter constraints fail"),
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
    return checks + template.checks(params, prompt)


def check_dicts(checks: list[ValidationCheck]) -> list[dict[str, Any]]:
    return [asdict(c) for c in checks]
