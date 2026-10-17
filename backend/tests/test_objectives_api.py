from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.catalogue import load_catalogue
from app.seed import sync_catalogue


def test_objectives_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/objectives")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_objectives_return_catalogue_with_prerequisites(
    client: TestClient, db: Session, make_token: Callable[..., str]
) -> None:
    sync_catalogue(db, load_catalogue())
    response = client.get("/api/v1/objectives", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 200
    body = response.json()
    assert [o["id"] for o in body] == [f"MOD-{n:02d}" for n in range(1, 12)]
    by_id = {o["id"]: o for o in body}
    assert by_id["MOD-05"]["prerequisites"] == ["MOD-02", "MOD-03"]
    assert by_id["MOD-01"]["prerequisites"] == []
    assert by_id["MOD-01"]["domain_area"] == "Pure: Mathematical modelling"
    assert by_id["MOD-01"]["success_criteria"]
    assert "interpretation" in by_id["MOD-01"]["domains"]


def test_objectives_expose_edexcel_spec_refs(
    client: TestClient, db: Session, make_token: Callable[..., str]
) -> None:
    sync_catalogue(db, load_catalogue())
    body = client.get("/api/v1/objectives", headers={"Authorization": f"Bearer {make_token()}"}).json()
    assert {o["id"]: o["spec_refs"] for o in body}["MOD-10"] == ["OT3.4", "2.11"]
