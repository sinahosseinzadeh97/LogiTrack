"""Password hashing, JWT issuing/verification, and the auth dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RevokedToken, Role, User
from app.config import get_settings
from app.database import get_session

ALGORITHM = "HS256"
ISSUER = "logitrack"
AUDIENCE = "logitrack-api"
BCRYPT_MAX_BYTES = 72

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED, "Could not validate credentials.", {"WWW-Authenticate": "Bearer"}
)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# Used when the e-mail is unknown so a failed login costs the same time either way.
_DUMMY_HASH = hash_password("not-a-real-password")


def verify_password(plain: str, hashed: str | None) -> bool:
    raw = plain.encode()
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    return bcrypt.checkpw(raw, (hashed or _DUMMY_HASH).encode()) and hashed is not None


def _encode(claims: dict[str, Any], lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {**claims, "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, get_settings().SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user: User) -> str:
    minutes = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES
    return _encode(
        {"sub": str(user.id), "role": user.role.value, "type": "access"}, timedelta(minutes=minutes)
    )


def create_refresh_token(user: User) -> str:
    days = get_settings().REFRESH_TOKEN_EXPIRE_DAYS
    return _encode(
        {"sub": str(user.id), "type": "refresh", "jti": str(uuid.uuid4())}, timedelta(days=days)
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            get_settings().SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise _UNAUTHORIZED from exc
    if payload["type"] != expected_type:
        raise _UNAUTHORIZED
    return payload


async def revoke_refresh_token(payload: dict[str, Any], db: AsyncSession) -> bool:
    """Revoke a refresh token. Returns False if it was already revoked.

    A single INSERT ... ON CONFLICT makes this atomic, so two concurrent
    refreshes with the same token cannot both succeed.
    """
    await db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(UTC)))
    stmt = (
        insert(RevokedToken)
        .values(jti=payload["jti"], expires_at=datetime.fromtimestamp(payload["exp"], UTC))
        .on_conflict_do_nothing()
        .returning(RevokedToken.jti)
    )
    return (await db.execute(stmt)).first() is not None


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    payload = decode_token(token, "access")
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: allow ``minimum`` and every role ranked above it."""

    async def _checker(user: CurrentUser) -> User:
        if user.role.rank < minimum.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{minimum}' or higher.")
        return user

    return _checker


ViewerUser = Annotated[User, Depends(require_role(Role.viewer))]
AnalystUser = Annotated[User, Depends(require_role(Role.analyst))]
AdminUser = Annotated[User, Depends(require_role(Role.admin))]
