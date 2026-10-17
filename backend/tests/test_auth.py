import time
from collections.abc import Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import UserRole


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_first_request_creates_student_profile(
    client: TestClient, db: Session, make_token: Callable[..., str]
) -> None:
    response = client.get("/api/v1/me", headers=auth(make_token(sub="user_abc")))
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == UserRole.STUDENT.value
    assert "external_auth_id" not in body

    user = db.scalar(select(User).where(User.external_auth_id == "user_abc"))
    assert user is not None and user.id == body["id"]


def test_repeat_requests_reuse_profile(client: TestClient, db: Session, make_token: Callable[..., str]) -> None:
    first = client.get("/api/v1/me", headers=auth(make_token(sub="user_abc"))).json()
    second = client.get("/api/v1/me", headers=auth(make_token(sub="user_abc"))).json()
    other = client.get("/api/v1/me", headers=auth(make_token(sub="user_xyz"))).json()

    assert first["id"] == second["id"]
    assert other["id"] != first["id"]
    assert db.scalar(select(func.count()).select_from(User)) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 3600},  # expired
        {"iss": "https://someone-else.clerk.accounts.dev"},  # wrong issuer
        {"azp": "https://evil.example"},  # minted for another origin
        {"sub": None},  # no subject
    ],
    ids=["expired", "wrong-issuer", "wrong-azp", "missing-sub"],
)
def test_rejects_invalid_tokens(
    client: TestClient, make_token: Callable[..., str], overrides: dict[str, object]
) -> None:
    response = client.get("/api/v1/me", headers=auth(make_token(**overrides)))
    assert response.status_code == 401


def test_rejects_token_signed_by_unknown_key(client: TestClient, make_token: Callable[..., str]) -> None:
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = client.get("/api/v1/me", headers=auth(make_token(key=attacker_key)))
    assert response.status_code == 401


def test_rejects_garbage_token(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers=auth("not-a-jwt"))
    assert response.status_code == 401
