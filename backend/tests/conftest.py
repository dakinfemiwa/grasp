import os

# Unit tests run against an in-memory SQLite database so they need no running server.
# Must be set before any app module reads settings.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("DATABASE_URL_UNPOOLED", None)
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

import time  # noqa: E402
from collections.abc import Callable, Generator  # noqa: E402
from typing import Any  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402, F401
from app.core.auth import TokenVerifier, get_token_verifier  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_ISSUER = "https://test-instance.clerk.accounts.dev"
TEST_ORIGIN = "http://localhost:3000"
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn: Any, _: Any) -> None:
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(
        issuer=TEST_ISSUER,
        authorized_parties=[TEST_ORIGIN],
        resolve_key=lambda _token: _private_key.public_key(),
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_token() -> Callable[..., str]:
    """Sign a Clerk-shaped session token with the test key."""

    def _make(sub: str = "user_test_1", key: Any = None, **overrides: Any) -> str:
        now = int(time.time())
        claims = {"sub": sub, "iss": TEST_ISSUER, "iat": now, "exp": now + 300, "azp": TEST_ORIGIN}
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key or _private_key, algorithm="RS256")

    return _make
