"""
Pydantic v2 request / response schemas for the authentication layer.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.auth.models import UserRole


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Payload for ``POST /auth/register`` (admin only)."""

    email: EmailStr = Field(..., description="Unique user e-mail address.")
    password: str = Field(..., min_length=8, description="Plain-text password (min 8 chars).")
    full_name: str = Field(..., min_length=1, description="Display name.")
    role: UserRole = Field(default=UserRole.viewer, description="RBAC role assignment.")


class UserLogin(BaseModel):
    """Payload for ``POST /auth/login``."""

    email: EmailStr = Field(..., description="Registered e-mail address.")
    password: str = Field(..., description="Plain-text password.")


class RefreshRequest(BaseModel):
    """Payload for ``POST /auth/refresh``."""

    refresh_token: str = Field(..., description="A valid, non-blacklisted refresh token.")


class LogoutRequest(BaseModel):
    """Payload for ``POST /auth/logout``."""

    refresh_token: str = Field(..., description="The refresh token to blacklist.")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """Returned by ``POST /auth/login`` and ``POST /auth/refresh``."""

    access_token: str = Field(..., description="Short-lived JWT access token (30 min).")
    refresh_token: str = Field(..., description="Long-lived JWT refresh token (7 days).")
    token_type: str = Field(default="bearer", description="OAuth2 token type.")
    expires_in: int = Field(..., description="Access token TTL in seconds.", ge=1)


class UserResponse(BaseModel):
    """Safe public representation of a user — no password hash."""

    id: int = Field(..., description="Internal user ID.")
    email: str = Field(..., description="User e-mail address.")
    full_name: str = Field(..., description="Display name.")
    role: UserRole = Field(..., description="RBAC role.")
    is_active: bool = Field(..., description="Whether the account is active.")
    created_at: datetime = Field(..., description="UTC timestamp of account creation.")

    model_config = {"from_attributes": True}
