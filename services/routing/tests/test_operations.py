"""Tests for the /operations endpoints and their query helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

import numpy as np
import psycopg
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from routing.app import create_app, get_posterior, get_rng
from routing.config import Settings
from routing.model import Posterior
from routing.operations import (
    JourneyView,
    TrayStateView,
    fetch_recent_journeys,
    fetch_tray_states,
)

UTC = timezone.utc


class _FakeCursor:
    """Stand-in for ``psycopg.Cursor`` used for SELECT-only test paths."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        """Record the SQL + params; no real execution."""
        self.executed.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        """Return the prepared row list."""
        return self._rows

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_: Any) -> Literal[False]:
        return False


class _FakeConn:
    """Stand-in for ``psycopg.Connection`` -- duck-typed for SELECT paths."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cur = _FakeCursor(rows)
        self.closed = False

    def cursor(self, row_factory: Any = None) -> _FakeCursor:
        """Return the (single) fake cursor for any cursor() call."""
        del row_factory
        return self.cur

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_: Any) -> Literal[False]:
        self.closed = True
        return False


def _patch_connect_returns(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> _FakeConn:
    fake = _FakeConn(rows)
    monkeypatch.setattr("psycopg.connect", lambda dsn: fake)
    return fake


def _patch_connect_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_dsn: str) -> _FakeConn:
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr("psycopg.connect", boom)


def _sample_tray_row() -> dict[str, Any]:
    return {
        "tray_id": "TRAY-1",
        "current_facility_id": "BOCA",
        "current_stage": "DELIVERED",
        "last_event_ts": datetime(2026, 5, 27, 11, 30, tzinfo=UTC),
        "last_updated": datetime(2026, 5, 27, 11, 30, 5, tzinfo=UTC),
    }


def _sample_journey_row() -> dict[str, Any]:
    return {
        "journey_id": UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        "tray_id": "TRAY-1",
        "facility_id": "BOCA",
        "tray_type_id": "TRAY-KNEE",
        "client_id": "HOSPITAL_A",
        "pickup_ts": datetime(2026, 5, 27, 8, 0, tzinfo=UTC),
        "required_by_ts": datetime(2026, 5, 27, 13, 0, tzinfo=UTC),
        "delivered_ts": datetime(2026, 5, 27, 11, 30, tzinfo=UTC),
        "on_time": True,
        "delay_min": -90.0,
        "decon_dwell_min": 20.0,
        "inspection_dwell_min": 20.0,
        "assembly_dwell_min": 25.0,
        "sterilization_dwell_min": 40.0,
        "packout_dwell_min": 15.0,
        "transport_min": 30.0,
    }


def test_fetch_tray_states_parses_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows from Postgres are parsed into ``TrayStateView`` models."""
    fake = _patch_connect_returns(monkeypatch, [_sample_tray_row()])
    response = fetch_tray_states("postgresql://test", 50)
    assert response.trays == [TrayStateView(**_sample_tray_row())]
    sql, params = fake.cur.executed[0]
    assert "FROM tray" in sql
    assert params == (50,)
    assert fake.closed is True


def test_fetch_recent_journeys_parses_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rows from Postgres are parsed into ``JourneyView`` models."""
    fake = _patch_connect_returns(monkeypatch, [_sample_journey_row()])
    response = fetch_recent_journeys("postgresql://test", 25)
    assert response.journeys == [JourneyView(**_sample_journey_row())]
    sql, params = fake.cur.executed[0]
    assert "FROM journey" in sql
    assert params == (25,)


def test_fetch_tray_states_503_when_postgres_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """OperationalError from psycopg.connect surfaces as a 503 HTTPException."""
    _patch_connect_raises(monkeypatch)
    with pytest.raises(HTTPException) as excinfo:
        fetch_tray_states("postgresql://test", 50)
    assert excinfo.value.status_code == 503
    assert "Postgres unreachable" in str(excinfo.value.detail)


def test_fetch_recent_journeys_503_when_postgres_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """OperationalError surfaces as a 503 HTTPException on the journeys path too."""
    _patch_connect_raises(monkeypatch)
    with pytest.raises(HTTPException) as excinfo:
        fetch_recent_journeys("postgresql://test", 50)
    assert excinfo.value.status_code == 503


async def test_app_tray_states_endpoint_returns_rows(
    monkeypatch: pytest.MonkeyPatch, fake_posterior: Posterior
) -> None:
    """GET /operations/tray-states returns one row when the DB has one."""
    _patch_connect_returns(monkeypatch, [_sample_tray_row()])
    app = create_app(Settings())
    app.dependency_overrides[get_posterior] = lambda: fake_posterior
    app.dependency_overrides[get_rng] = lambda: np.random.default_rng(0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/operations/tray-states")
    assert response.status_code == 200
    body = response.json()
    assert len(body["trays"]) == 1
    assert body["trays"][0]["tray_id"] == "TRAY-1"


async def test_app_recent_journeys_endpoint_returns_rows(
    monkeypatch: pytest.MonkeyPatch, fake_posterior: Posterior
) -> None:
    """GET /operations/recent-journeys returns one row when the DB has one."""
    _patch_connect_returns(monkeypatch, [_sample_journey_row()])
    app = create_app(Settings())
    app.dependency_overrides[get_posterior] = lambda: fake_posterior
    app.dependency_overrides[get_rng] = lambda: np.random.default_rng(0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/operations/recent-journeys")
    assert response.status_code == 200
    body = response.json()
    assert len(body["journeys"]) == 1
    assert body["journeys"][0]["facility_id"] == "BOCA"
    assert body["journeys"][0]["on_time"] is True


async def test_app_operations_returns_503_when_postgres_down(
    monkeypatch: pytest.MonkeyPatch, fake_posterior: Posterior
) -> None:
    """Both operations endpoints propagate the 503 from a connect failure."""
    _patch_connect_raises(monkeypatch)
    app = create_app(Settings())
    app.dependency_overrides[get_posterior] = lambda: fake_posterior
    app.dependency_overrides[get_rng] = lambda: np.random.default_rng(0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        tray = await client.get("/operations/tray-states")
        journeys = await client.get("/operations/recent-journeys")
    assert tray.status_code == 503
    assert journeys.status_code == 503


async def test_create_app_sets_operations_limit_from_env(
    monkeypatch: pytest.MonkeyPatch, fake_posterior: Posterior
) -> None:
    """ROUTING_OPERATIONS_LIMIT and ROUTING_POSTGRES_DSN flow into the endpoints."""
    captured: dict[str, Any] = {}

    def fake_fetch(dsn: str, limit: int) -> Any:
        captured["dsn"] = dsn
        captured["limit"] = limit
        from routing.operations import TrayStatesResponse

        return TrayStatesResponse(trays=[])

    from routing import app as app_module

    monkeypatch.setattr(app_module, "fetch_tray_states", fake_fetch)
    cfg = Settings(operations_limit=7, postgres_dsn="postgresql://custom")
    app = create_app(cfg)
    app.dependency_overrides[get_posterior] = lambda: fake_posterior
    app.dependency_overrides[get_rng] = lambda: np.random.default_rng(0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/operations/tray-states")
    assert response.status_code == 200
    assert captured["dsn"] == "postgresql://custom"
    assert captured["limit"] == 7
