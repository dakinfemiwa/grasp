from collections.abc import Generator

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import get_db
from app.main import app


def test_liveness(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_api_and_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "flexa-api", "database": "ok"}


def test_health_returns_structured_503_when_database_down(client: TestClient) -> None:
    class BrokenSession:
        def execute(self, *_: object) -> None:
            raise ConnectionError("db down")

    def broken_db() -> Generator[BrokenSession, None, None]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "SERVICE_UNAVAILABLE", "message": "Database connection unavailable"}
    }


def test_unknown_route_returns_structured_404(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_postgres_url_is_normalised_to_psycopg() -> None:
    settings = Settings(database_url="postgres://u:p@host:5432/db", frontend_url="a, b")
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert settings.cors_origins == ["a", "b"]
