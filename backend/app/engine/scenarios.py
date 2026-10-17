"""The scenario library checked against the template registry.

Compatibility is explicit in both directions: a scenario lists the template versions it
supports, and its slots for each must validate against that template's slots_model. Bounds
may only narrow a template's parameter ranges.
"""

import random
from collections.abc import Sequence
from functools import lru_cache

from pydantic import BaseModel, ValidationError

from app.engine.base import AnyTemplate, Bounds
from app.engine.registry import UnknownTemplate, get_template
from app.scenarios import Scenario, ScenarioError, read_scenario_files


class UnknownScenario(LookupError):
    pass


def cross_check(scenarios: Sequence[Scenario]) -> list[str]:
    """Every problem with these scenarios relative to the registered templates."""
    problems: list[str] = []
    keys = [s.key for s in scenarios]
    for dup in sorted({k for k in keys if keys.count(k) > 1}):
        problems.append(f"{dup[0]} v{dup[1]}: duplicate scenario")
    for s in scenarios:
        seen: set[tuple[str, int]] = set()
        for c in s.compatible_templates:
            where = f"{s.id} v{s.version} -> {c.template} v{c.version}"
            if (c.template, c.version) in seen:
                problems.append(f"{where}: listed twice")
            seen.add((c.template, c.version))
            try:
                template = get_template(c.template, c.version)
            except UnknownTemplate:
                problems.append(f"{where}: unknown template")
                continue
            try:
                template.slots_model.model_validate(c.slots)
            except ValidationError as exc:
                problems.extend(f"{where}: slots.{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            ranges = template.parameter_bounds()
            for name, b in c.bounds.items():
                if name not in ranges:
                    problems.append(f"{where}: bounds.{name} is not a sampled parameter")
                elif b.min < ranges[name][0] or b.max > ranges[name][1]:
                    problems.append(f"{where}: bounds.{name} [{b.min}, {b.max}] widens {list(ranges[name])}")
    return problems


def validate_library(scenarios: Sequence[Scenario]) -> list[Scenario]:
    problems = cross_check(scenarios)
    if problems:
        raise ScenarioError(problems)
    return sorted(scenarios, key=lambda s: s.key)


@lru_cache
def scenario_library() -> tuple[Scenario, ...]:
    return tuple(validate_library(read_scenario_files()))


def get_scenario(scenario_id: str, version: int | None = None) -> Scenario:
    """The given version, or the latest when version is None."""
    matches = [s for s in scenario_library() if s.id == scenario_id and (version is None or s.version == version)]
    if not matches:
        raise UnknownScenario(f"Unknown scenario {scenario_id}" + (f" v{version}" if version else ""))
    return max(matches, key=lambda s: s.version)


def compatible_scenarios(template: AnyTemplate) -> list[Scenario]:
    """Latest version of each scenario that supports this template version."""
    latest: dict[str, Scenario] = {}
    for s in scenario_library():
        if s.compatibility(template.id, template.version) and s.version >= latest.get(s.id, s).version:
            latest[s.id] = s
    return [latest[k] for k in sorted(latest)]


def pick_scenario(template: AnyTemplate, seed: int, candidates: Sequence[Scenario]) -> Scenario:
    """Deterministic choice from candidates, independent of the parameter RNG."""
    if not candidates:
        raise UnknownScenario(f"No scenario is available for {template.id} v{template.version}")
    ordered = sorted(candidates, key=lambda s: s.key)
    return random.Random(f"{template.id}:v{template.version}:{seed}:scenario").choice(ordered)


def slots_for(template: AnyTemplate, scenario: Scenario) -> BaseModel:
    compat = scenario.compatibility(template.id, template.version)
    if compat is None:
        raise UnknownScenario(f"{scenario.id} v{scenario.version} is not compatible with {template.id} v{template.version}")
    return template.slots_model.model_validate(compat.slots)


def effective_bounds(template: AnyTemplate, scenario: Scenario) -> Bounds:
    bounds = template.parameter_bounds()
    compat = scenario.compatibility(template.id, template.version)
    for name, b in (compat.bounds if compat else {}).items():
        lo, hi = bounds[name]
        bounds[name] = (max(lo, b.min), min(hi, b.max))
    return bounds
