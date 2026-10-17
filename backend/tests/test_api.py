"""End-to-end API tests against PostgreSQL (see conftest.py)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from httpx import AsyncClient

from tests.conftest import CUTOFF, auth_headers, login

# --------------------------------------------------------------------------- auth


async def test_health_reports_database_and_model(client: AsyncClient) -> None:
    body = (await client.get("/health")).json()
    assert body == {"status": "ok", "database": True, "model_loaded": True}


async def test_login_then_me_returns_the_profile_without_secrets(client: AsyncClient) -> None:
    headers = await auth_headers(client, "analyst")
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["email"] == "analyst@logitrack.dev" and me["role"] == "analyst"
    assert "hashed_password" not in me


@pytest.mark.parametrize("email", ["admin@logitrack.dev", "nobody@logitrack.dev"])
async def test_bad_credentials_get_the_same_401(client: AsyncClient, email: str) -> None:
    response = await client.post("/auth/login", json={"email": email, "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect e-mail or password."


async def test_endpoints_require_a_token(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/kpi/summary")).status_code == 401


async def test_refresh_tokens_are_single_use(client: AsyncClient) -> None:
    tokens = await login(client, "viewer")
    first = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    replay = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


async def test_logout_revokes_the_refresh_token(client: AsyncClient) -> None:
    tokens = await login(client, "viewer")
    out = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    again = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


async def test_an_access_token_is_not_accepted_as_a_refresh_token(client: AsyncClient) -> None:
    tokens = await login(client, "viewer")
    response = await client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401


async def test_login_is_rate_limited(client: AsyncClient) -> None:
    body = {"email": "viewer@logitrack.dev", "password": "wrong-pass"}
    codes = [(await client.post("/auth/login", json=body)).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


async def test_roles_gate_export_and_predict(client: AsyncClient) -> None:
    viewer = await auth_headers(client, "viewer")
    analyst = await auth_headers(client, "analyst")
    assert (await client.get("/api/v1/shipments/export", headers=viewer)).status_code == 403
    assert (await client.post("/api/v1/ml/predict", json={}, headers=viewer)).status_code == 403
    export = await client.get("/api/v1/shipments/export?customer_state=BA", headers=analyst)
    assert export.status_code == 200
    assert export.text.splitlines()[0].startswith("order_id,order_status")


async def test_only_admins_create_users(client: AsyncClient) -> None:
    new_user = {"email": "new@logitrack.dev", "password": "long-enough-pw", "full_name": "New"}
    analyst = await auth_headers(client, "analyst")
    admin = await auth_headers(client, "admin")
    assert (await client.post("/auth/users", json=new_user, headers=analyst)).status_code == 403
    assert (await client.post("/auth/users", json=new_user, headers=admin)).status_code == 201
    assert (await client.post("/auth/users", json=new_user, headers=admin)).status_code == 409


# --------------------------------------------------------------------------- KPIs


async def test_kpi_summary_matches_a_pandas_recount(
    client: AsyncClient, database: pd.DataFrame
) -> None:
    kpi = (
        await client.get("/api/v1/kpi/summary", headers=await auth_headers(client, "viewer"))
    ).json()
    delivered = database[database["is_late"].notna()]
    assert kpi["total_orders"] == len(database)
    assert kpi["delivered"] == len(delivered)
    assert kpi["late"] == int(delivered["is_late"].sum())
    assert kpi["on_time_rate"] == pytest.approx(100 * (1 - delivered["is_late"].mean()), abs=0.01)
    assert kpi["fulfillment_rate"] == pytest.approx(100 * len(delivered) / len(database), abs=0.01)


async def test_summary_respects_the_date_range(client: AsyncClient, database: pd.DataFrame) -> None:
    headers = await auth_headers(client, "viewer")
    kpi = (
        await client.get("/api/v1/kpi/summary?start=2017-03-01&end=2017-03-31", headers=headers)
    ).json()
    in_march = database["purchase_ts"].between("2017-03-01", "2017-03-31 23:59:59")
    assert kpi["total_orders"] == int(in_march.sum())


async def test_trend_and_regions(client: AsyncClient, database: pd.DataFrame) -> None:
    headers = await auth_headers(client, "viewer")
    trend = (await client.get("/api/v1/kpi/trend?granularity=month", headers=headers)).json()
    assert all(point["orders"] >= 30 for point in trend)
    assert [p["period"] for p in trend] == sorted(p["period"] for p in trend)

    regions = {
        r["state"]: r for r in (await client.get("/api/v1/kpi/regions", headers=headers)).json()
    }
    assert set(regions) == set(database["customer_state"])
    # The factory makes deliveries to BA slower, so BA must be the worst state.
    assert min(regions.values(), key=lambda r: r["on_time_rate"])["state"] == "BA"


# --------------------------------------------------------------------------- shipments & sellers


async def test_shipment_filters_and_pagination(client: AsyncClient, database: pd.DataFrame) -> None:
    headers = await auth_headers(client, "viewer")
    page = (
        await client.get(
            "/api/v1/shipments?customer_state=BA&is_late=true&page_size=7", headers=headers
        )
    ).json()
    expected = database[(database["customer_state"] == "BA") & (database["is_late"] == True)]  # noqa: E712
    assert page["total"] == len(expected)
    assert len(page["items"]) == 7
    assert all(item["customer_state"] == "BA" and item["is_late"] for item in page["items"])


async def test_shipment_detail(client: AsyncClient) -> None:
    headers = await auth_headers(client, "viewer")
    detail = (await client.get("/api/v1/shipments/o00001", headers=headers)).json()
    assert detail["order_id"] == "o00001" and "seller_prior_late_rate" in detail
    assert (await client.get("/api/v1/shipments/missing", headers=headers)).status_code == 404


async def test_seller_scorecard_and_detail(client: AsyncClient) -> None:
    headers = await auth_headers(client, "viewer")
    sellers = (await client.get("/api/v1/sellers?sort=orders&page_size=3", headers=headers)).json()
    orders = [s["orders"] for s in sellers["items"]]
    assert orders == sorted(orders, reverse=True) and sellers["total"] == 8
    seller_id = sellers["items"][0]["seller_id"]
    detail = (await client.get(f"/api/v1/sellers/{seller_id}", headers=headers)).json()
    assert detail["orders"] == orders[0] and detail["trend"]
    assert (await client.get("/api/v1/sellers/missing", headers=headers)).status_code == 404


# --------------------------------------------------------------------------- alerts & model


def _expected_queue(orders: pd.DataFrame, as_of: date, threshold: float) -> pd.DataFrame:
    """Independent pandas version of the backtest rules in app/routers/alerts.py."""
    t = pd.Timestamp(as_of)
    promised = pd.to_datetime(orders["estimated_delivery"])
    in_training = (orders["purchase_ts"] < CUTOFF) & (promised < CUTOFF)
    queue = orders[
        (orders["purchase_ts"] < t)
        & (orders["purchase_ts"] >= t - timedelta(days=60))
        & ~orders["order_status"].isin(["canceled", "unavailable"])
        & (orders["delivered_ts"].isna() | (orders["delivered_ts"] >= t))
        & ~in_training
        & (promised >= t)
    ]
    return queue.assign(
        flagged=queue["delay_probability"] >= threshold,
        missed=queue["is_late"].fillna(True).astype(bool),
    )


async def test_backtest_matches_an_independent_recount(
    client: AsyncClient, scored: tuple[pd.DataFrame, object]
) -> None:
    orders, model = scored
    headers = await auth_headers(client, "viewer")
    window = (await client.get("/api/v1/alerts/window", headers=headers)).json()
    assert window["cutoff"] == "2018-01-01"

    as_of = date(2018, 2, 15)
    body = (await client.get(f"/api/v1/alerts?as_of={as_of}&limit=500", headers=headers)).json()
    queue = _expected_queue(orders, as_of, model.threshold)
    stats = body["stats"]
    assert stats["in_transit"] == len(queue)
    assert stats["flagged"] == int(queue["flagged"].sum())
    assert stats["flagged_late"] == int((queue["flagged"] & queue["missed"]).sum())
    assert {i["order_id"] for i in body["items"]} == set(queue.loc[queue["flagged"], "order_id"])


async def test_backtest_refuses_dates_inside_the_training_window(client: AsyncClient) -> None:
    headers = await auth_headers(client, "viewer")
    assert (await client.get("/api/v1/alerts?as_of=2017-06-01", headers=headers)).status_code == 422


async def test_what_if_prediction_and_model_card(client: AsyncClient) -> None:
    analyst = await auth_headers(client, "analyst")
    slow = await client.post("/api/v1/ml/predict", json={"customer_state": "BA"}, headers=analyst)
    fast = await client.post("/api/v1/ml/predict", json={"customer_state": "SP"}, headers=analyst)
    assert slow.status_code == fast.status_code == 200
    assert slow.json()["delay_probability"] > fast.json()["delay_probability"]
    bad = await client.post("/api/v1/ml/predict", json={"price": -5}, headers=analyst)
    assert bad.status_code == 422

    card = (
        await client.get("/api/v1/ml/model", headers=await auth_headers(client, "viewer"))
    ).json()
    assert card["cutoff"] == "2018-01-01" and "roc_auc" in card["metrics"]
