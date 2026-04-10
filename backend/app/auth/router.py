"""
Authentication router — /auth prefix.

Endpoints:
    POST /auth/register  — create user (admin only)
    POST /auth/login     — exchange credentials for JWT pair
    POST /auth/refresh   — rotate access token via refresh token
    GET  /auth/me        — return current user profile
    POST /auth/logout    — blacklist refresh token
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.schemas import (
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.auth.service import (
    ADMIN_ONLY,
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    is_token_blacklisted,
    require_role,
    verify_password,
)
from app.config import get_settings
from app.database import get_async_session
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (admin only)",
)
async def register(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _admin: Annotated[User, Depends(require_role(*ADMIN_ONLY))],
) -> UserResponse:
    """Create a new user account.  Requires ``admin`` role."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"E-mail '{payload.email}' is already registered.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("New user registered: id=%d email=%s role=%s", user.id, user.email, user.role)
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain access + refresh tokens",
)
@limiter.limit("5/minute", key_func=get_remote_address)
async def login(
    request: Request,
    payload: UserLogin,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """Exchange e-mail + password for a JWT access/refresh token pair.

    Rate-limited to **5 requests per minute per IP address**.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect e-mail or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    settings = get_settings()
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)
    logger.info("User logged in: id=%d email=%s", user.id, user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> TokenResponse:
    """Rotate an access token using a valid refresh token."""
    token_data = decode_token(payload.refresh_token)

    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not a refresh token.",
        )

    jti: str = token_data.get("jti", "")
    if await is_token_blacklisted(jti, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked.",
        )

    user_id = int(token_data["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    # Blacklist old refresh token (rotation)
    await blacklist_token(jti, payload.refresh_token, db)

    settings = get_settings()
    new_access = create_access_token(user.id, user.role.value)
    new_refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return current authenticated user",
)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    payload: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Blacklist the provided refresh token so it can no longer be used."""
    token_data = decode_token(payload.refresh_token)

    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided token is not a refresh token.",
        )

    jti: str = token_data.get("jti", "")
    if not await is_token_blacklisted(jti, db):
        await blacklist_token(jti, payload.refresh_token, db)
        logger.info("Refresh token blacklisted: jti=%s", jti)
