from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogue import load_catalogue
from app.core.config import Settings, get_settings
from app.main import app
from app.models import EvidenceObjective, LearningObjective
from app.seed import sync_catalogue

FULL = {"variable": "width", "other_side": "x + 4", "equation": "x(x + 4) = 96", "roots": [8, -12]}


@pytest.fixture
def headers(db: Session, make_token: Callable[..., str]) -> dict[str, str]:
    sync_catalogue(db, load_catalogue())
    return {"Authorization": f"Bearer {make_token()}"}


def create(client: TestClient, headers: dict[str, str], seed: int = 5) -> dict:
    response = client.post("/api/v1/practice/instances", json={"template_id": "QUAD-RECT-AREA", "seed": seed}, headers=headers)
    assert response.status_code == 201, response.json()
    return response.json()


def correct_response(instance_params: dict) -> dict:
    w, d, a = instance_params["width"], instance_params["difference"], instance_params["area"]
    return {
        "variable": "width",
        "other_side": f"x + {d}",
        "equation": f"x(x + {d}) = {a}",
        "roots": [w, -(w + d)],
        "width": w,
        "length": w + d,
    }


def params_of(db: Session, instance_id: int) -> dict:
    from app.models import QuestionInstance

    instance = db.get(QuestionInstance, instance_id)
    assert instance is not None
    return instance.parameters


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/templates"),
        ("post", "/api/v1/practice/instances"),
        ("get", "/api/v1/practice/instances/1"),
        ("post", "/api/v1/practice/instances/1/attempts"),
        ("get", "/api/v1/practice/evidence/summary"),
    ],
)
def test_practice_requires_authentication(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path, json={}).status_code == 401


def test_create_instance_hides_the_answer_and_is_deterministic(client: TestClient, headers: dict[str, str]) -> None:
    body = create(client, headers)
    assert body["template_id"] == "QUAD-RECT-AREA"
    assert "expected_answer" not in body and "worked_solution" not in body
    assert {"id": "MOD-05", "is_primary": True} in body["objectives"]
    assert [f["name"] for f in body["response_fields"]][:3] == ["variable", "other_side", "equation"]
    assert create(client, headers)["id"] == body["id"]  # same seed → same instance
    assert client.get(f"/api/v1/practice/instances/{body['id']}", headers=headers).json() == body


def test_correct_attempt_records_objective_level_evidence(
    client: TestClient, db: Session, headers: dict[str, str]
) -> None:
    instance = create(client, headers)
    response = client.post(
        f"/api/v1/practice/instances/{instance['id']}/attempts",
        json={"response": correct_response(params_of(db, instance["id"])), "hints_used": ["area"], "time_taken_ms": 9000},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["outcome"] == "correct" and body["attempt_number"] == 1
    assert set(body["objective_outcomes"]) == {"MOD-02", "MOD-05", "MOD-07", "MOD-08", "MOD-09"}
    assert body["worked_solution"] and body["expected_answer"]["width"] > 0

    rows = db.execute(
        select(LearningObjective.code, EvidenceObjective.outcome).join(EvidenceObjective.objective)
    ).all()
    assert {code for code, _ in rows} == set(body["objective_outcomes"])


def test_partial_attempt_and_attempt_numbers(client: TestClient, db: Session, headers: dict[str, str]) -> None:
    instance = create(client, headers)
    url = f"/api/v1/practice/instances/{instance['id']}/attempts"
    good = correct_response(params_of(db, instance["id"]))
    negative = {**good, "width": min(good["roots"])}

    first = client.post(url, json={"response": negative}, headers=headers).json()
    assert first["outcome"] == "partial"
    assert first["objective_outcomes"]["MOD-09"] == "incorrect"
    assert first["objective_outcomes"]["MOD-05"] == "correct"

    second = client.post(url, json={"response": good}, headers=headers).json()
    assert second["attempt_number"] == 2 and second["outcome"] == "correct"


@pytest.mark.parametrize(
    ("body", "loc"),
    [
        ({"response": {"variable": "area"}}, ["body", "response", "variable"]),
        ({"response": {"surprise": 1}}, ["body", "response", "surprise"]),
        ({"response": {}, "hints_used": ["nope"]}, ["body", "hints_used"]),
    ],
)
def test_invalid_attempts_are_structured_422s(
    client: TestClient, headers: dict[str, str], body: dict, loc: list[str]
) -> None:
    instance = create(client, headers)
    response = client.post(f"/api/v1/practice/instances/{instance['id']}/attempts", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == loc


def test_unknown_instance_is_404(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/api/v1/practice/instances/999/attempts", json={"response": FULL}, headers=headers)
    assert response.status_code == 404


def test_scenario_can_be_requested_and_is_reported(client: TestClient, headers: dict[str, str]) -> None:
    body = {"template_id": "QUAD-RECT-AREA", "scenario_id": "SCN-RECT-GARDEN", "seed": 5}
    response = client.post("/api/v1/practice/instances", json=body, headers=headers)
    assert response.status_code == 201
    instance = response.json()
    assert instance["scenario"]["id"] == "SCN-RECT-GARDEN"
    assert instance["prompt"].startswith("A rectangular garden")
    assert {f["name"]: f["unit"] for f in instance["response_fields"]}["width"] == "m"
    # Same seed, different scenario: a different instance.
    other = client.post(
        "/api/v1/practice/instances", json={**body, "scenario_id": "SCN-RECT-ABSTRACT"}, headers=headers
    ).json()
    assert other["id"] != instance["id"]

    missing = client.post("/api/v1/practice/instances", json={**body, "scenario_id": "SCN-NOPE"}, headers=headers)
    assert missing.status_code == 404


def test_linear_attempt_aggregates_steps_per_objective(
    client: TestClient, db: Session, headers: dict[str, str]
) -> None:
    body = {"template_id": "LIN-TWO-POINT", "scenario_id": "SCN-LIN-TAXI", "seed": 3}
    instance = client.post("/api/v1/practice/instances", json=body, headers=headers).json()
    p = params_of(db, instance["id"])
    m = p["gradient_tenths"] / 10
    meaning = next(f for f in instance["response_fields"] if f["name"] == "gradient_meaning")
    assert "the cost per mile" in meaning["options"]
    response = {
        "gradient": m,
        "equation": f"y = {m}x + {p['intercept']}",
        "gradient_meaning": "the cost per mile",
        "prediction": p["y3"] + 1,  # wrong prediction, everything else right
        "reliability": "beyond the data" if p["extrapolate"] else "within the data",
    }
    result = client.post(
        f"/api/v1/practice/instances/{instance['id']}/attempts", json={"response": response}, headers=headers
    ).json()
    assert result["outcome"] == "partial"
    # MOD-07 covers both find_gradient (correct) and predict (incorrect), so it is incorrect overall.
    assert result["objective_outcomes"] == {
        "MOD-05": "correct",
        "MOD-07": "incorrect",
        "MOD-08": "correct",
        "MOD-10": "correct",
    }


def test_templates_list_spec_refs_and_scenarios(client: TestClient, headers: dict[str, str]) -> None:
    (quad,) = [t for t in client.get("/api/v1/templates", headers=headers).json() if t["id"] == "QUAD-RECT-AREA"]
    assert "2.3" in quad["spec_refs"]
    assert {"SCN-RECT-ABSTRACT", "SCN-RECT-GARDEN"} <= {s["id"] for s in quad["scenarios"]}


def test_draft_templates_are_not_served_outside_development(client: TestClient, headers: dict[str, str]) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(environment="production")
    assert client.get("/api/v1/templates", headers=headers).json() == []
    assert client.post("/api/v1/practice/instances", json={}, headers=headers).status_code == 404


def test_evidence_summary_counts_per_objective_and_is_per_user(
    client: TestClient, db: Session, headers: dict[str, str], make_token: Callable[..., str]
) -> None:
    empty = client.get("/api/v1/practice/evidence/summary", headers=headers).json()
    assert empty["total_attempts"] == 0 and empty["recent"] == []
    assert len(empty["objectives"]) == 11 and all(o["last_outcome"] is None for o in empty["objectives"])
    assert "not an estimate of mastery" in empty["note"]

    instance = create(client, headers)
    url = f"/api/v1/practice/instances/{instance['id']}/attempts"
    good = correct_response(params_of(db, instance["id"]))
    client.post(url, json={"response": {**good, "width": min(good["roots"])}}, headers=headers)  # MOD-09 wrong
    client.post(url, json={"response": good}, headers=headers)

    summary = client.get("/api/v1/practice/evidence/summary", headers=headers).json()
    by_id = {o["id"]: o for o in summary["objectives"]}
    assert summary["total_attempts"] == 2
    assert by_id["MOD-09"] == {**by_id["MOD-09"], "correct": 1, "incorrect": 1, "last_outcome": "correct"}
    assert by_id["MOD-05"]["correct"] == 2
    assert by_id["MOD-11"]["correct"] == by_id["MOD-11"]["incorrect"] == 0  # not assessed
    assert [r["attempt_number"] for r in summary["recent"]] == [2, 1]
    assert summary["recent"][0]["template_title"] == "Rectangle dimensions from area"

    other = {"Authorization": f"Bearer {make_token(sub='user_other')}"}
    assert client.get("/api/v1/practice/evidence/summary", headers=other).json()["total_attempts"] == 0
