"""Schema for the scenario library (backend/content/scenarios/*.yaml).

A scenario is a reviewed context or representation (a garden, a Ferris wheel, an abstract
rectangle). It names exactly which template versions it is compatible with and supplies typed
wording "slots" for each, plus optional parameter bounds that may only narrow the template's
ranges. This module checks the file's own shape; app.engine.scenarios checks it against the
template registry.
"""

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from app.core.config import BACKEND_DIR
from app.models.enums import ReviewStatus

SCENARIO_DIR = BACKEND_DIR / "content" / "scenarios"

ScenarioId = Annotated[str, StringConstraints(pattern=r"^SCN-[A-Z0-9]+(-[A-Z0-9]+)*$")]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ScenarioError(ValueError):
    """Raised with every problem found, like CatalogueError, so a bad library is never used."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid scenario library:\n" + "\n".join(f"  - {p}" for p in problems))


class Bounds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min: int
    max: int

    @model_validator(mode="after")
    def ordered(self) -> "Bounds":
        if self.min > self.max:
            raise ValueError(f"min {self.min} is greater than max {self.max}")
        return self


class Compatibility(BaseModel):
    """One template version this scenario may be used with, and how."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template: NonEmptyText
    version: int = Field(ge=1)
    slots: dict[str, Any]  # validated against the template's slots_model
    bounds: dict[str, Bounds] = Field(default_factory=dict)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ScenarioId
    version: int = Field(ge=1)
    title: NonEmptyText
    description: NonEmptyText
    entities: list[NonEmptyText] = Field(min_length=1)
    relationships: list[NonEmptyText] = Field(min_length=1)
    assumptions: list[NonEmptyText] = Field(default_factory=list)
    presentation: Literal["narrative", "abstract"]
    review_status: ReviewStatus
    compatible_templates: list[Compatibility] = Field(min_length=1)

    @property
    def key(self) -> tuple[str, int]:
        return (self.id, self.version)

    def compatibility(self, template_id: str, version: int) -> Compatibility | None:
        return next(
            (c for c in self.compatible_templates if c.template == template_id and c.version == version), None
        )


class ScenarioFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenarios: list[Scenario] = Field(min_length=1)


def parse_scenario_file(data: Any, source: str = "<data>") -> list[Scenario]:
    try:
        return list(ScenarioFile.model_validate(data).scenarios)
    except ValidationError as exc:
        raise ScenarioError(
            [f"{source}: {'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()]
        ) from exc


def read_scenario_files(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    scenarios: list[Scenario] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            try:
                scenarios.extend(parse_scenario_file(yaml.safe_load(f), path.name))
            except ScenarioError as exc:
                problems.extend(exc.problems)
    if problems:
        raise ScenarioError(problems)
    return scenarios
