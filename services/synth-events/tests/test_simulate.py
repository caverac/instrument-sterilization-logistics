"""Tests for the per-stage sampling functions."""

from __future__ import annotations

import numpy as np

from synth_events.parameters import (
    BASE_STAGE_TOTAL_MIN,
    FACILITIES,
    PEAK_HOUR_OFFSET_MIN,
    STAGES,
    TRANSPORT_MEAN_MIN,
    TRAY_TYPES,
    Facility,
    TrayType,
)
from synth_events.simulate import (
    _lognormal_mu_for_mean,
    journey_target_mean_min,
    sample_stage_dwells,
    sample_transport_min,
)


def _by_id(facility_id: str) -> Facility:
    return next(f for f in FACILITIES if f.facility_id == facility_id)


def _tray(tray_type_id: str) -> TrayType:
    return next(t for t in TRAY_TYPES if t.tray_type_id == tray_type_id)


def test_journey_target_mean_reflects_facility_offset() -> None:
    knee = _tray("TRAY-KNEE")
    boca = journey_target_mean_min(_by_id("BOCA"), knee, hour=2)
    lgb = journey_target_mean_min(_by_id("LGB"), knee, hour=2)
    elm = journey_target_mean_min(_by_id("ELM"), knee, hour=2)
    assert boca < lgb < elm


def test_journey_target_mean_reflects_tray_complexity() -> None:
    lgb = _by_id("LGB")
    small = journey_target_mean_min(lgb, _tray("TRAY-SMALL"), hour=2)
    knee = journey_target_mean_min(lgb, _tray("TRAY-KNEE"), hour=2)
    spine = journey_target_mean_min(lgb, _tray("TRAY-SPINE"), hour=2)
    assert small < knee < spine


def test_journey_target_mean_reflects_peak_hour() -> None:
    lgb = _by_id("LGB")
    knee = _tray("TRAY-KNEE")
    off_peak = journey_target_mean_min(lgb, knee, hour=2)
    on_peak = journey_target_mean_min(lgb, knee, hour=10)
    assert on_peak == off_peak + PEAK_HOUR_OFFSET_MIN


def test_lognormal_mu_recovers_target_mean() -> None:
    rng = np.random.default_rng(0)
    sigma = 0.25
    target = 50.0
    mu = _lognormal_mu_for_mean(target, sigma)
    samples = rng.lognormal(mu, sigma, size=200_000)
    assert abs(samples.mean() - target) / target < 0.01


def test_sample_stage_dwells_returns_all_stages() -> None:
    rng = np.random.default_rng(1)
    dwells = sample_stage_dwells(rng, _by_id("LGB"), _tray("TRAY-KNEE"), hour=2)
    assert set(dwells.keys()) == {s.name for s in STAGES}
    assert all(v > 0 for v in dwells.values())


def test_sample_stage_dwells_means_match_target() -> None:
    rng = np.random.default_rng(2)
    facility = _by_id("LGB")
    tray = _tray("TRAY-KNEE")
    hour = 2
    target = journey_target_mean_min(facility, tray, hour)
    totals = [sum(sample_stage_dwells(rng, facility, tray, hour).values()) for _ in range(5_000)]
    sample_mean = float(np.mean(totals))
    assert abs(sample_mean - target) / target < 0.02


def test_facility_variance_ordering_holds_empirically() -> None:
    """BOCA should be more variable than LGB, and LGB more than ELM."""
    rng = np.random.default_rng(3)
    tray = _tray("TRAY-KNEE")
    hour = 2

    def total_std(facility_id: str) -> float:
        facility = _by_id(facility_id)
        totals = [sum(sample_stage_dwells(rng, facility, tray, hour).values()) for _ in range(3_000)]
        return float(np.std(totals))

    boca_std = total_std("BOCA")
    lgb_std = total_std("LGB")
    elm_std = total_std("ELM")
    assert boca_std > lgb_std > elm_std


def test_sample_transport_min_is_positive_and_mean_matches() -> None:
    rng = np.random.default_rng(4)
    samples = [sample_transport_min(rng) for _ in range(20_000)]
    assert all(s > 0 for s in samples)
    assert abs(float(np.mean(samples)) - TRANSPORT_MEAN_MIN) / TRANSPORT_MEAN_MIN < 0.02


def test_target_mean_baseline_is_base_stage_total() -> None:
    """When all shifts are zero, target equals BASE_STAGE_TOTAL_MIN."""
    lgb = _by_id("LGB")
    knee = _tray("TRAY-KNEE")
    target = journey_target_mean_min(lgb, knee, hour=2)
    assert target == BASE_STAGE_TOTAL_MIN
