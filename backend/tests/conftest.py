import os

# Unit tests run against an in-memory SQLite database so they need no running server.
# Must be set before any app module reads settings.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("DATABASE_URL_UNPOOLED", None)
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
