"""
Rate-limiting utilities for LogiTrack API.

Two rate-limit strategies:
  - login:      5 requests / minute per client IP  (applied via @limiter.limit decorator)
  - general API: 100 requests / minute per authenticated user (applied as application_limits)

Key-function logic:
  - Authenticated requests → keyed by JWT ``sub`` claim  ("user:<id>")
  - Unauthenticated requests → keyed by client IP address

Backend:
  - Development / no REDIS_URL set → in-memory store (single-process only)
  - Production / REDIS_URL set     → Redis store (multi-process safe)
"""

from __future__ import annotations

import base64
import json
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key functions
# ---------------------------------------------------------------------------


def _ip_key(request: Request) -> str:
    """Return the remote client IP address."""
    return get_remote_address(request)


def _user_or_ip_key(request: Request) -> str:
    """Return 'user:<id>' from the Bearer JWT sub claim, or the client IP.

    Decodes only the payload section (no signature verification) — the
    signature is already verified by ``get_current_user`` before any
    business logic runs.  This function is used *only* to derive a
    rate-limit bucket key, never to authorise requests.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            token = auth[7:]
            part = token.split(".")[1]
            rem = len(part) % 4
            if rem:
                part += "=" * (4 - rem)
            payload = json.loads(base64.urlsafe_b64decode(part))
            uid = payload.get("sub")
            if uid:
                return f"user:{uid}"
        except Exception:  # noqa: BLE001
            logger.debug("Could not extract user ID from token for rate-limit key; falling back to IP.")
    return get_remote_address(request)


# ---------------------------------------------------------------------------
# Limiter singleton — shared by all routers
# ---------------------------------------------------------------------------

def _build_limiter() -> Limiter:
    """Construct the Limiter with the correct storage backend."""
    try:
        from app.config import get_settings  # deferred to avoid circular import at import time
        redis_url = get_settings().REDIS_URL
    except Exception:  # noqa: BLE001
        redis_url = None

    storage_uri = redis_url or "memory://"
    logger.debug("Rate-limiter storage: %s", "redis" if redis_url else "in-memory")

    return Limiter(
        key_func=_user_or_ip_key,
        # Applied to ALL routes; individual routes can declare stricter limits.
        application_limits=["100/minute"],
        storage_uri=storage_uri,
    )


limiter: Limiter = _build_limiter()
