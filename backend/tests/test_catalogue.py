from typing import Any

import pytest
import yaml

from app.catalogue import MODELLING_CATALOGUE_PATH, CatalogueError, load_catalogue
from app.catalogue.schema import _find_cycle, validate_catalogue


def raw_catalogue() -> dict[str, Any]:
    with MODELLING_CATALOGUE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def entry(id_: str, prerequisites: list[str] | None = None, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": id_,
        "title": "t",
        "description": "d",
        "success_criteria": ["c"],
        "prerequisites": prerequisites or [],
        "domains": ["linear"],
        "evidence_types": ["equation"],
    }
    item.update(overrides)
    return item


def catalogue(*objectives: dict[str, Any]) -> dict[str, Any]:
    return {"catalogue_version": 1, "domain_area": "Pure: Mathematical modelling", "objectives": list(objectives)}


def test_real_catalogue_has_mod_01_to_11_as_a_dag() -> None:
    cat = load_catalogue()
    assert [o.id for o in cat.objectives] == [f"MOD-{n:02d}" for n in range(1, 12)]
    assert cat.catalogue_version == 1
    assert _find_cycle({o.id: o.prerequisites for o in cat.objectives}) is None
    # Not an artificial chain: several roots and at least one multi-prerequisite objective.
    assert sum(1 for o in cat.objectives if not o.prerequisites) >= 2
    assert any(len(o.prerequisites) > 1 for o in cat.objectives)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (catalogue(entry("MOD-01"), entry("MOD-01")), "duplicate objective id"),
        (catalogue(entry("MOD-01", ["MOD-99"])), "unknown prerequisite MOD-99"),
        (catalogue(entry("MOD-01", ["MOD-01"])), "lists itself"),
        (
            catalogue(entry("MOD-01", ["MOD-03"]), entry("MOD-02", ["MOD-01"]), entry("MOD-03", ["MOD-02"])),
            "prerequisite cycle",
        ),
        (catalogue(entry("MOD-01", domains=["calculus"])), "domains"),
        (catalogue(entry("MOD-01", difficulty=3)), "Extra inputs are not permitted"),
        (catalogue(entry("MOD-01", success_criteria=[])), "success_criteria"),
        (catalogue(entry("MOD-01", success_criteria=["  "])), "success_criteria"),
        (catalogue(entry("SUVAT-1")), "id"),
    ],
)
def test_rejects_malformed_catalogue(data: dict[str, Any], expected: str) -> None:
    with pytest.raises(CatalogueError, match=expected):
        validate_catalogue(data)


def test_reports_every_problem_at_once() -> None:
    data = raw_catalogue()
    data["objectives"][0]["prerequisites"] = ["MOD-01", "MOD-42"]
    with pytest.raises(CatalogueError) as exc:
        validate_catalogue(data)
    assert len(exc.value.problems) == 2
