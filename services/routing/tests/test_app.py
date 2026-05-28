"""Tests for the FastAPI app."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from routing.app import (
    FACILITY_METADATA,
    _is_peak,
    create_app,
    get_backtest,
    get_model_summary,
    get_posterior,
    get_rng,
)
from routing.config import Settings
from routing.model import Posterior, save
from routing.model_summary import compute_summary
from routing.simulate import Lift, PolicyResult, SimulationReport


def _app_with_fakes(posterior: Posterior, rng: np.random.Generator) -> FastAPI:
    app = create_app(Settings())
    app.dependency_overrides[get_posterior] = lambda: posterior
    app.dependency_overrides[get_rng] = lambda: rng
    return app


def _sample_payload() -> dict[str, Any]:
    return {
        "tray_type_id": "TRAY-KNEE",
        "hour_of_pickup": 10,
        "deadline_min": 220.0,
        "client_id": "HOSPITAL_A",
    }


def test_is_peak_window() -> None:
    """Peak window is 08:00-11:59 and 14:00-17:59."""
    assert _is_peak(9) == 1
    assert _is_peak(15) == 1
    assert _is_peak(7) == 0
    assert _is_peak(13) == 0
    assert _is_peak(20) == 0


async def test_healthz(fake_posterior: Posterior) -> None:
    rng = np.random.default_rng(0)
    app = _app_with_fakes(fake_posterior, rng)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_decide_returns_facilities_and_policies(fake_posterior: Posterior) -> None:
    rng = np.random.default_rng(0)
    app = _app_with_fakes(fake_posterior, rng)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/decide", json=_sample_payload())

    assert response.status_code == 200
    body = response.json()

    assert {f["facility_id"] for f in body["facilities"]} == set(fake_posterior.facility_ids)
    for facility in body["facilities"]:
        assert facility["expected_completion_min"] > 0.0
        assert 0.0 <= facility["p_on_time"] <= 1.0
        # Static metadata is wired in.
        assert facility["name"] == FACILITY_METADATA[facility["facility_id"]]["name"]
        assert facility["profile"] == FACILITY_METADATA[facility["facility_id"]]["profile"]

    policy_ids = {p["policy_id"] for p in body["policies"]}
    assert policy_ids == {"variance-aware", "mean-only", "proximity"}

    by_id = {p["policy_id"]: p for p in body["policies"]}
    assert by_id["variance-aware"]["score_metric"] == "p_on_time"
    assert by_id["mean-only"]["score_metric"] == "expected_completion_min"
    assert by_id["proximity"]["score_metric"] is None


async def test_decide_validation_error(fake_posterior: Posterior) -> None:
    rng = np.random.default_rng(0)
    app = _app_with_fakes(fake_posterior, rng)
    bad = {**_sample_payload(), "hour_of_pickup": 999}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/decide", json=bad)
    assert response.status_code == 422


def _fake_simulation_report() -> SimulationReport:
    return SimulationReport(
        n=42,
        per_policy=(
            PolicyResult("variance-aware", n=42, on_time_rate=0.61, mean_delay_min=-3.4, p95_delay_min=80.0),
            PolicyResult("mean-only", n=42, on_time_rate=0.58, mean_delay_min=1.2, p95_delay_min=84.0),
            PolicyResult("proximity", n=42, on_time_rate=0.49, mean_delay_min=6.8, p95_delay_min=92.0),
        ),
        lifts=(
            Lift("variance-aware", vs="mean-only", point_pp=3.0, ci_95_lo_pp=-0.5, ci_95_hi_pp=6.0),
            Lift("variance-aware", vs="proximity", point_pp=12.0, ci_95_lo_pp=8.5, ci_95_hi_pp=15.5),
        ),
        on_time_by_policy={
            "variance-aware": np.zeros(42, dtype=np.int32),
            "mean-only": np.zeros(42, dtype=np.int32),
            "proximity": np.zeros(42, dtype=np.int32),
        },
    )


async def test_backtest_summary_endpoint_returns_cached_report(fake_posterior: Posterior) -> None:
    """GET /backtest/summary returns the SimulationReport that lifespan cached."""
    rng = np.random.default_rng(0)
    report = _fake_simulation_report()
    app = _app_with_fakes(fake_posterior, rng)
    app.dependency_overrides[get_backtest] = lambda: report
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/backtest/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 42
    policy_ids = {p["policy_id"] for p in body["per_policy"]}
    assert policy_ids == {"variance-aware", "mean-only", "proximity"}
    # The variance-aware vs proximity lift should land between its CI bounds.
    va_vs_prox = next(lift for lift in body["lifts"] if lift["vs"] == "proximity")
    assert va_vs_prox["ci_95_lo_pp"] <= va_vs_prox["point_pp"] <= va_vs_prox["ci_95_hi_pp"]


async def test_model_summary_endpoint_returns_cached_summary(fake_posterior: Posterior) -> None:
    """GET /model/summary returns the ModelSummaryResponse that lifespan cached."""
    rng = np.random.default_rng(0)
    summary = compute_summary(fake_posterior)
    app = _app_with_fakes(fake_posterior, rng)
    app.dependency_overrides[get_model_summary] = lambda: summary
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/model/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["n_samples"] == fake_posterior.n_samples()
    assert body["facility_ids"] == ["BOCA", "LGB", "ELM"]
    names = {p["name"] for p in body["parameters"]}
    assert "mu_global" in names
    assert "alpha[BOCA]" in names
    assert "beta[TRAY-KNEE]" in names


async def test_decide_unknown_facility_falls_back_to_id_as_name(
    fake_posterior: Posterior,
) -> None:
    """A facility not in FACILITY_METADATA gets its id back as the display name."""
    fake_with_unknown = Posterior(
        facility_ids=("MARS",),
        tray_type_ids=fake_posterior.tray_type_ids,
        mu_global=fake_posterior.mu_global,
        alpha=fake_posterior.alpha[:, :1],
        sigma_facility=fake_posterior.sigma_facility[:, :1],
        beta=fake_posterior.beta,
        gamma_peak=fake_posterior.gamma_peak,
        mu_transport=fake_posterior.mu_transport,
        sigma_transport=fake_posterior.sigma_transport,
    )
    rng = np.random.default_rng(0)
    app = _app_with_fakes(fake_with_unknown, rng)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/decide", json=_sample_payload())
    assert response.status_code == 200
    facility = response.json()["facilities"][0]
    assert facility["facility_id"] == "MARS"
    assert facility["name"] == "MARS"
    assert facility["profile"] == ""


def test_lifespan_loads_posterior_and_seeds_rng(tmp_path: Path, fake_posterior: Posterior) -> None:
    """Lifespan loads the posterior, primes a seeded RNG, and pre-warms the cached surfaces."""
    model_path = tmp_path / "model.npz"
    save(fake_posterior, str(model_path))
    cfg = Settings(model_path=model_path, seed=7, backtest_n=10, backtest_seed=42)
    app = create_app(cfg)
    with TestClient(app) as client:
        assert app.state.posterior.facility_ids == fake_posterior.facility_ids
        assert isinstance(app.state.rng, np.random.Generator)
        assert app.state.backtest.n == 10
        assert app.state.model_summary.n_samples == fake_posterior.n_samples()
        assert client.get("/healthz").status_code == 200


def test_create_app_uses_environment_when_no_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_posterior: Posterior
) -> None:
    model_path = tmp_path / "env.npz"
    save(fake_posterior, str(model_path))
    monkeypatch.setenv("ROUTING_MODEL_PATH", str(model_path))
    monkeypatch.setenv("ROUTING_SEED", "13")
    monkeypatch.setenv("ROUTING_BACKTEST_N", "10")
    app = create_app()
    with TestClient(app):
        assert app.state.posterior.facility_ids == fake_posterior.facility_ids
        assert app.state.backtest.n == 10


async def test_dependency_resolvers_read_from_app_state(
    fake_posterior: Posterior,
) -> None:
    from unittest.mock import MagicMock

    rng = np.random.default_rng(0)
    report = MagicMock(spec=SimulationReport)
    summary = MagicMock()
    request = MagicMock()
    request.app.state.posterior = fake_posterior
    request.app.state.rng = rng
    request.app.state.backtest = report
    request.app.state.model_summary = summary
    assert (await get_posterior(request)) is fake_posterior
    assert (await get_rng(request)) is rng
    assert (await get_backtest(request)) is report
    assert (await get_model_summary(request)) is summary
