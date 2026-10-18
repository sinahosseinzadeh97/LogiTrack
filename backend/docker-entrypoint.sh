#!/bin/sh
# Bring a fresh database to a usable state, then start the server.
# Every step is idempotent, so restarts are cheap.
set -e
alembic upgrade head
python -m etl.run --if-empty      # full data in /data/raw if mounted, else the bundled sample
python -m ml.train --if-missing   # trains once; later starts reuse the saved model
if [ "${SEED_DEMO_USERS:-false}" = "true" ]; then
  python -m app.seed
fi
exec "$@"
