"""
SQLAlchemy ORM models for authentication.

Tables:
  - ``users``              — registered users with roles
  - ``token_blacklist``    — revoked refresh tokens (logout/refresh rotation)
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.shipment import Base


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    """RBAC roles available in LogiTrack."""

    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class User(Base):
    """Registered user with hashed password and role assignment.

    Passwords are stored as bcrypt hashes; plain-text is never persisted.
    The ``role`` column drives the RBAC dependency (``require_role``).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False, default=UserRole.viewer
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


# ---------------------------------------------------------------------------
# token_blacklist
# ---------------------------------------------------------------------------


class TokenBlacklist(Base):
    """Revoked refresh tokens stored until their natural expiry.

    On ``POST /auth/logout`` the refresh token's JTI (JWT ID) is inserted here.
    The ``get_current_user`` dependency checks this table before accepting a
    refresh-token exchange.

    Rows older than ``REFRESH_TOKEN_EXPIRE_DAYS`` days can be pruned by a
    periodic scheduled task without affecting security.
    """

    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    blacklisted_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Store the raw token so an admin can inspect it for audit purposes
    token_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TokenBlacklist jti={self.jti!r}>"
