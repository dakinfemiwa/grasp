from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.core.config import BACKEND_DIR

MODELLING_CATALOGUE_PATH = BACKEND_DIR / "content" / "objectives" / "modelling.yaml"

ObjectiveId = Annotated[str, StringConstraints(pattern=r"^MOD-\d{2}$")]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# A Pearson Edexcel 9MA0 (Issue 4) reference: an overarching theme ("OT3.1") or a content number ("2.11").
SpecRef = Annotated[str, StringConstraints(pattern=r"^(OT\d\.\d|\d{1,2}\.\d{1,2})$")]


class Domain(StrEnum):
    LINEAR = "linear"
    QUADRATIC = "quadratic"
    TRIGONOMETRIC = "trigonometric"
    INTERPRETATION = "interpretation"


class EvidenceType(StrEnum):
    VARIABLE_DEFINITION = "variable_definition"
    EQUATION = "equation"
    NUMERIC_ANSWER = "numeric_answer"
    SELECTION = "selection"
    EXPLANATION = "explanation"


class Objective(BaseModel):
    """One Grasp-internal modelling objective (not an Edexcel identifier)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ObjectiveId
    title: NonEmptyText
    description: NonEmptyText
    success_criteria: list[NonEmptyText] = Field(min_length=1)
    prerequisites: list[ObjectiveId] = Field(default_factory=list)
    domains: list[Domain] = Field(min_length=1)
    evidence_types: list[EvidenceType] = Field(min_length=1)
    spec_refs: list[SpecRef] = Field(default_factory=list)


class Catalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalogue_version: int = Field(ge=1)
    domain_area: NonEmptyText
    objectives: list[Objective] = Field(min_length=1)


class CatalogueError(ValueError):
    """Raised with every problem found, so a malformed catalogue is never seeded silently."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid objective catalogue:\n" + "\n".join(f"  - {p}" for p in problems))


def _find_cycle(prerequisites: dict[str, list[str]]) -> list[str] | None:
    """Return one prerequisite cycle as a path (first == last), or None for a DAG."""
    visiting: set[str] = set()
    done: set[str] = set()
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        visiting.add(node)
        path.append(node)
        for nxt in prerequisites.get(node, []):
            if nxt in visiting:
                return path[path.index(nxt) :] + [nxt]
            if nxt not in done and (cycle := visit(nxt)):
                return cycle
        visiting.discard(node)
        done.add(node)
        path.pop()
        return None

    for node in prerequisites:
        if node not in done and (cycle := visit(node)):
            return cycle
    return None


def validate_catalogue(data: Any) -> Catalogue:
    try:
        catalogue = Catalogue.model_validate(data)
    except ValidationError as exc:
        raise CatalogueError(
            [f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}" for err in exc.errors()]
        ) from exc

    problems: list[str] = []
    ids = [o.id for o in catalogue.objectives]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"{dup}: duplicate objective id")
    known = set(ids)
    for o in catalogue.objectives:
        if o.id in o.prerequisites:
            problems.append(f"{o.id}: lists itself as a prerequisite")
        for p in o.prerequisites:
            if p not in known:
                problems.append(f"{o.id}: unknown prerequisite {p}")
        if len(set(o.prerequisites)) != len(o.prerequisites):
            problems.append(f"{o.id}: repeated prerequisite")
    if not problems:
        cycle = _find_cycle({o.id: [p for p in o.prerequisites if p != o.id] for o in catalogue.objectives})
        if cycle:
            problems.append("prerequisite cycle: " + " -> ".join(cycle))
    if problems:
        raise CatalogueError(problems)
    return catalogue


def load_catalogue(path: Path = MODELLING_CATALOGUE_PATH) -> Catalogue:
    with path.open(encoding="utf-8") as f:
        return validate_catalogue(yaml.safe_load(f))
