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
    get_posterior,
    get_rng,
)
from routing.config import Settings
from routing.model import Posterior, save


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
    """Lifespan reads the configured model_path and primes a seeded RNG."""
    model_path = tmp_path / "model.npz"
    save(fake_posterior, str(model_path))
    cfg = Settings(model_path=model_path, seed=7)
    app = create_app(cfg)
    with TestClient(app) as client:
        assert app.state.posterior.facility_ids == fake_posterior.facility_ids
        assert isinstance(app.state.rng, np.random.Generator)
        assert client.get("/healthz").status_code == 200


def test_create_app_uses_environment_when_no_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_posterior: Posterior
) -> None:
    model_path = tmp_path / "env.npz"
    save(fake_posterior, str(model_path))
    monkeypatch.setenv("ROUTING_MODEL_PATH", str(model_path))
    monkeypatch.setenv("ROUTING_SEED", "13")
    app = create_app()
    with TestClient(app):
        assert app.state.posterior.facility_ids == fake_posterior.facility_ids


async def test_dependency_resolvers_read_from_app_state(
    fake_posterior: Posterior,
) -> None:
    from unittest.mock import MagicMock

    rng = np.random.default_rng(0)
    request = MagicMock()
    request.app.state.posterior = fake_posterior
    request.app.state.rng = rng
    assert (await get_posterior(request)) is fake_posterior
    assert (await get_rng(request)) is rng
