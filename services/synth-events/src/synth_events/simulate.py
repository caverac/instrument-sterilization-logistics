"""Per-stage dwell-time sampling from log-normal distributions."""

from __future__ import annotations

import numpy as np

from synth_events.parameters import (
    BASE_STAGE_TOTAL_MIN,
    PEAK_HOUR_OFFSET_MIN,
    PEAK_HOURS,
    STAGES,
    TRANSPORT_MEAN_MIN,
    TRANSPORT_SIGMA,
    Facility,
    TrayType,
)


def journey_target_mean_min(facility: Facility, tray_type: TrayType, hour: int) -> float:
    """Return the expected total journey mean for this cell.

    Parameters
    ----------
    facility : Facility
        Routing target.
    tray_type : TrayType
        Determines a multiplicative shift on total mean.
    hour : int
        Hour of day (0-23). Triggers a peak-hour offset for busy hours.

    Returns
    -------
    float
        Target mean total reprocessing time, in minutes.
    """
    base = BASE_STAGE_TOTAL_MIN
    facility_shift = facility.mu_offset_min
    tray_shift = (tray_type.complexity_multiplier - 1.0) * base
    peak_shift = PEAK_HOUR_OFFSET_MIN if hour in PEAK_HOURS else 0.0
    return base + facility_shift + tray_shift + peak_shift


def _lognormal_mu_for_mean(target_mean: float, sigma: float) -> float:
    """Return mu such that E[LogNormal(mu, sigma)] = target_mean.

    Log-normal expectation is exp(mu + sigma^2 / 2), so we offset mu down
    by sigma^2 / 2 to land the mean exactly on the target.
    """
    return float(np.log(target_mean)) - 0.5 * sigma * sigma


def sample_stage_dwells(
    rng: np.random.Generator,
    facility: Facility,
    tray_type: TrayType,
    hour: int,
) -> dict[str, float]:
    """Sample per-stage dwell times in minutes.

    Each stage is log-normal. Stage means are uniformly scaled so the
    sum of expected dwells matches the target for the (facility, tray,
    hour) cell. Sigma scales with facility -- BOCA is variable, ELM is
    tight, LGB is in between.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded RNG for reproducibility.
    facility : Facility
        Routing target.
    tray_type : TrayType
        Tray complexity.
    hour : int
        Hour of pickup, 0-23.

    Returns
    -------
    dict[str, float]
        Stage name -> dwell time in minutes.
    """
    target_total = journey_target_mean_min(facility, tray_type, hour)
    scale = target_total / BASE_STAGE_TOTAL_MIN
    dwells: dict[str, float] = {}
    for stage in STAGES:
        stage_mean = stage.mean_min * scale
        sigma = stage.sigma * facility.sigma_multiplier
        mu = _lognormal_mu_for_mean(stage_mean, sigma)
        dwells[stage.name] = float(rng.lognormal(mu, sigma))
    return dwells


def sample_transport_min(rng: np.random.Generator) -> float:
    """Sample the one-way return-transport time in minutes (log-normal)."""
    mu = _lognormal_mu_for_mean(TRANSPORT_MEAN_MIN, TRANSPORT_SIGMA)
    return float(rng.lognormal(mu, TRANSPORT_SIGMA))
