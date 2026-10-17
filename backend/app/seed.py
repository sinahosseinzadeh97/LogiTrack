"""Create the demo accounts if they don't exist: ``python -m app.seed``."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.models import Role, User
from app.auth.service import hash_password
from app.config import get_settings

logger = logging.getLogger("seed")

DEMO_USERS = [
    ("admin@logitrack.dev", "Demo Admin", Role.admin),
    ("analyst@logitrack.dev", "Demo Analyst", Role.analyst),
    ("viewer@logitrack.dev", "Demo Viewer", Role.viewer),
]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    with Session(create_engine(settings.sync_database_url)) as db:
        existing = set(db.scalars(select(User.email)))
        for email, name, role in DEMO_USERS:
            if email not in existing:
                db.add(
                    User(
                        email=email,
                        full_name=name,
                        role=role,
                        hashed_password=hash_password(settings.DEMO_PASSWORD),
                    )
                )
                logger.info("created %s (%s)", email, role)
        db.commit()


if __name__ == "__main__":
    main()
