"""API tests run against a real PostgreSQL database named by TEST_DATABASE_URL.

The database is wiped and rebuilt with the Alembic migrations, so never point
this at a database you care about. Without TEST_DATABASE_URL the API tests are
skipped and only the pure unit tests run.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["DEMO_PASSWORD"] = "test-password"

CUTOFF = pd.Timestamp("2018-01-01")


@pytest.fixture(scope="session")
def database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[pd.DataFrame]:
    """Migrated schema + synthetic orders (loaded via the ETL CLI) + demo users.

    Yields the same orders built in memory, as the expected values for assertions.
    """
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run the API tests")
    from alembic.config import Config

    from alembic import command
    from app import seed
    from app.config import BACKEND_ROOT, get_settings
    from etl import run
    from etl.features import add_point_in_time_features
    from etl.transform import build_orders
    from tests.factory import make_raw

    get_settings.cache_clear()
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    raw = make_raw()
    data_dir = tmp_path_factory.mktemp("olist")
    for stem, frame in raw.items():
        frame.to_csv(data_dir / f"{stem}.csv.gz", index=False)
    run.main(["--data-dir", str(data_dir)])
    seed.main()
    yield add_point_in_time_features(build_orders(raw))


@pytest.fixture(scope="session")
def scored(database: pd.DataFrame) -> tuple[pd.DataFrame, object]:
    """Train on the synthetic data, write scores to the DB. Returns (scored orders, model)."""
    from sqlalchemy import create_engine

    from app.config import get_settings
    from app.routers.ml import LoadedModel
    from ml.features import as_frame
    from ml.train import train, write_scores

    pipe, card = train(database, CUTOFF)
    write_scores(create_engine(get_settings().sync_database_url), database, pipe)
    orders = database.assign(delay_probability=pipe.predict_proba(as_frame(database))[:, 1])
    return orders, LoadedModel(pipe, card)


@pytest_asyncio.fixture(scope="session")
async def client(scored: tuple[pd.DataFrame, object]) -> AsyncIterator[AsyncClient]:
    from app.main import app

    app.state.model = scored[1]  # ASGITransport does not run the lifespan that loads it
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    from app.auth.router import limiter

    limiter.reset()


async def login(client: AsyncClient, role: str) -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": f"{role}@logitrack.dev", "password": "test-password"}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def auth_headers(client: AsyncClient, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {(await login(client, role))['access_token']}"}
