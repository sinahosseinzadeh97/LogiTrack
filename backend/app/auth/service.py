"""
JWT authentication and RBAC service layer.

Public API
----------
- ``hash_password``       — bcrypt hashing
- ``verify_password``     — constant-time comparison
- ``create_access_token`` — 30-minute signed JWT
- ``create_refresh_token``— 7-day signed JWT with unique JTI
- ``decode_token``        — verify + decode any JWT
- ``get_current_user``    — FastAPI dependency; returns authenticated User
- ``require_role``        — factory for role-gated dependencies
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import TokenBlacklist, User, UserRole
from app.config import get_settings
from app.database import get_async_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return the bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` iff *plain* matches the stored *hashed* password."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_id: int, role: str) -> str:
    """Mint a 30-minute signed access JWT.

    Claims:
        - ``sub``  — user ID as string
        - ``role`` — RBAC role string
        - ``type`` — literal ``"access"``
        - ``exp``  — expiry timestamp
        - ``iat``  — issued-at timestamp
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Mint a 7-day signed refresh JWT.

    Includes a unique ``jti`` claim so individual tokens can be blacklisted
    without invalidating all tokens for the user.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify *token*; raise ``HTTPException(401)`` on any failure."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as exc:
        logger.debug("JWT decode error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """FastAPI dependency that resolves the Bearer token to a ``User`` ORM object.

    Raises ``HTTP 401`` when:
    - The token is missing or malformed.
    - The ``type`` claim is not ``"access"``.
    - The user does not exist or is inactive.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise credentials_exc

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exc

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exc

    return user


def require_role(*roles: str):  # noqa: ANN201
    """Return a FastAPI dependency that enforces one of the given *roles*.

    Usage::

        @router.get("/admin-only")
        async def admin_endpoint(
            _: Annotated[User, Depends(require_role("admin"))],
        ): ...

    Raises ``HTTP 403`` when the authenticated user's role is not in *roles*.
    """

    async def _checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' is not authorised "
                    f"for this resource. Required: {list(roles)}"
                ),
            )
        return current_user

    return _checker


# ---------------------------------------------------------------------------
# Refresh-token blacklist helpers
# ---------------------------------------------------------------------------


async def blacklist_token(jti: str, token_hint: str, db: AsyncSession) -> None:
    """Insert a JTI into the blacklist table."""
    entry = TokenBlacklist(jti=jti, token_hint=token_hint[:500])
    db.add(entry)
    await db.flush()


async def is_token_blacklisted(jti: str, db: AsyncSession) -> bool:
    """Return ``True`` when the given JTI has been revoked."""
    result = await db.execute(
        select(TokenBlacklist).where(TokenBlacklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Role hierarchy helper
# ---------------------------------------------------------------------------

_ROLE_ORDER = {UserRole.viewer: 0, UserRole.analyst: 1, UserRole.admin: 2}

# All roles that include viewer-level access
VIEWER_AND_ABOVE = (UserRole.viewer.value, UserRole.analyst.value, UserRole.admin.value)
ANALYST_AND_ABOVE = (UserRole.analyst.value, UserRole.admin.value)
ADMIN_ONLY = (UserRole.admin.value,)
