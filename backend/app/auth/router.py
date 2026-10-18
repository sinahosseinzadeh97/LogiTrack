from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserCreate, UserResponse
from app.auth.service import (
    AdminUser,
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.database import get_session

# ponytail: in-memory buckets are per process; use a Redis storage_uri if you run >1 worker.
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        expires_in=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().LOGIN_RATE_LIMIT)
async def login(request: Request, body: LoginRequest, db: Session) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    password_ok = verify_password(body.password, user.hashed_password if user else None)
    if not password_ok or user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect e-mail or password.")
    return _tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: Session) -> TokenResponse:
    payload = decode_token(body.refresh_token, "refresh")
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or not await revoke_refresh_token(payload, db):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is invalid or revoked.")
    return _tokens(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: Session) -> Response:
    await revoke_refresh_token(decode_token(body.refresh_token, "refresh"), db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> User:
    return user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: Session, _: AdminUser) -> User:
    if (await db.execute(select(User.id).where(User.email == body.email))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail is already registered.")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()
    return user
