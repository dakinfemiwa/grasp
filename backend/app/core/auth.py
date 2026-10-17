"""Clerk session-token verification and the current-user dependency.

Identity always comes from a verified token's `sub` claim; endpoints never accept a user id
from the client.
"""

from collections.abc import Callable
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User

KeyResolver = Callable[[str], Any]


class TokenVerifier:
    def __init__(self, issuer: str, authorized_parties: list[str], resolve_key: KeyResolver) -> None:
        self.issuer = issuer.rstrip("/")
        self.authorized_parties = authorized_parties
        self.resolve_key = resolve_key

    def verify(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self.resolve_key(token),
                algorithms=["RS256"],
                issuer=self.issuer,
                leeway=30,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise _unauthenticated("Invalid or expired session token.") from exc
        # Clerk sets `azp` to the origin that requested the token; reject tokens minted for other sites.
        azp = claims.get("azp")
        if azp is not None and azp not in self.authorized_parties:
            raise _unauthenticated("Token was issued for an unrecognised origin.")
        return claims


def _unauthenticated(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    if not settings.clerk_issuer:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured.")
    jwks = jwt.PyJWKClient(f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json", cache_keys=True)
    return TokenVerifier(
        issuer=settings.clerk_issuer,
        authorized_parties=settings.cors_origins,
        resolve_key=lambda token: jwks.get_signing_key_from_jwt(token).key,
    )


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthenticated("Missing bearer token.")
    claims = verifier.verify(credentials.credentials)
    external_id: str = claims["sub"]

    user = db.scalar(select(User).where(User.external_auth_id == external_id))
    if user is not None:
        return user

    # First request from this identity: create the profile. Concurrent first requests can race,
    # so fall back to re-reading on a unique-constraint violation.
    user = User(external_auth_id=external_id)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.scalar(select(User).where(User.external_auth_id == external_id))
        if user is None:
            raise
    db.refresh(user)
    return user
