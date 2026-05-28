"""Tests for the head-to-head simulation harness."""

from __future__ import annotations

from typing import Callable

import numpy as np

from routing.model import Posterior
from routing.simulate import (
    run_simulation,
    synth_events_data_generator,
)


def _constant_data_gen(
    processing: float, transport: float
) -> Callable[[str, str, int, np.random.Generator], tuple[float, float]]:
    """A data generator that returns fixed (processing, transport) regardless of input."""

    def gen(
        _facility_id: str,
        _tray_type_id: str,
        _is_peak: int,
        _rng: np.random.Generator,
    ) -> tuple[float, float]:
        return processing, transport

    return gen


def test_simulation_returns_expected_shapes(fake_posterior: Posterior) -> None:
    rng = np.random.default_rng(0)
    report = run_simulation(fake_posterior, _constant_data_gen(150.0, 30.0), 200, rng)
    assert report.n == 200
    assert len(report.per_policy) == 3
    assert {r.policy_id for r in report.per_policy} == {
        "variance-aware",
        "mean-only",
        "proximity",
    }
    assert {lift.vs for lift in report.lifts} == {"mean-only", "proximity"}
    assert set(report.on_time_by_policy.keys()) == {
        "variance-aware",
        "mean-only",
        "proximity",
    }


def test_constant_under_deadline_yields_all_on_time(fake_posterior: Posterior) -> None:
    """If processing+transport is always 180, all pickups beat a 250-min deadline."""
    rng = np.random.default_rng(1)
    report = run_simulation(
        fake_posterior,
        _constant_data_gen(150.0, 30.0),
        200,
        rng,
        deadline_mean_min=250.0,
        deadline_sigma=0.01,
    )
    for r in report.per_policy:
        assert r.on_time_rate > 0.95


def test_synth_events_data_generator_returns_positive_values() -> None:
    """The synth-events-backed generator returns sensible positive values."""
    gen = synth_events_data_generator()
    rng = np.random.default_rng(7)
    processing, transport = gen("BOCA", "TRAY-KNEE", 0, rng)
    assert processing > 0
    assert transport > 0


def test_variance_aware_beats_proximity_in_simulation(fake_posterior: Posterior) -> None:
    """Sanity-check the integration: variance-aware should lift over proximity."""
    rng = np.random.default_rng(42)
    report = run_simulation(fake_posterior, synth_events_data_generator(), 800, rng)
    on_time = {r.policy_id: r.on_time_rate for r in report.per_policy}
    assert on_time["variance-aware"] >= on_time["proximity"]
