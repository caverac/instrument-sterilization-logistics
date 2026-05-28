"""Shared fixtures for routing tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from routing.data import JourneyDataset
from routing.model import Posterior


@pytest.fixture
def tiny_dataset() -> JourneyDataset:
    """A small but valid dataset for tests that need to exercise the model.

    Three facilities, two tray types, 120 observations across them. Small
    enough that a NUTS fit completes in < 5 seconds.
    """
    rng = np.random.default_rng(0)
    n = 120
    facility_idx = rng.integers(0, 3, size=n).astype(np.int32)
    tray_idx = rng.integers(0, 2, size=n).astype(np.int32)
    is_peak = rng.integers(0, 2, size=n).astype(np.int32)
    hours = rng.integers(0, 24, size=n).astype(np.int32)
    # log-normal with facility-dependent mean / sigma, mirroring synth-events
    base_mu = np.log(165.0)
    facility_offsets = np.array([-0.06, 0.0, 0.12])  # BOCA, LGB, ELM
    facility_sigmas = np.array([0.4, 0.25, 0.15])
    log_mu = base_mu + facility_offsets[facility_idx] + 0.05 * is_peak
    sigma = facility_sigmas[facility_idx]
    total = rng.lognormal(log_mu, sigma)
    transport = rng.lognormal(np.log(30.0), 0.3, size=n)
    deadline = np.full(n, 220.0)
    return JourneyDataset(
        facility_ids=("BOCA", "ELM", "LGB"),
        tray_type_ids=("TRAY-KNEE", "TRAY-LAPS"),
        facility_idx=facility_idx,
        tray_idx=tray_idx,
        is_peak=is_peak,
        total_processing_min=total,
        transport_min=transport,
        delay_min=total + transport - deadline,
        on_time=(total + transport <= deadline),
        pickup_hours=hours,
    )


@pytest.fixture
def fake_posterior() -> Posterior:
    """Hand-built posterior with 200 deterministic samples for unit tests.

    Facility 0 has the lowest log-mean and high sigma (BOCA-ish).
    Facility 1 has a medium log-mean and medium sigma (LGB-ish).
    Facility 2 has the highest log-mean and low sigma (ELM-ish).
    The tray effects are zero so they don't affect comparisons.
    """
    rng = np.random.default_rng(123)
    n_samples = 200
    return Posterior(
        facility_ids=("BOCA", "LGB", "ELM"),
        tray_type_ids=("TRAY-KNEE", "TRAY-LAPS"),
        mu_global=rng.normal(np.log(165.0), 0.02, size=n_samples),
        alpha=np.column_stack(
            [
                rng.normal(-0.06, 0.01, size=n_samples),  # BOCA
                rng.normal(0.00, 0.01, size=n_samples),  # LGB
                rng.normal(0.12, 0.01, size=n_samples),  # ELM
            ]
        ),
        sigma_facility=np.column_stack(
            [
                rng.normal(0.40, 0.01, size=n_samples).clip(min=0.05),  # BOCA
                rng.normal(0.25, 0.01, size=n_samples).clip(min=0.05),  # LGB
                rng.normal(0.15, 0.01, size=n_samples).clip(min=0.05),  # ELM
            ]
        ),
        beta=np.column_stack(
            [
                rng.normal(0.00, 0.01, size=n_samples),
                rng.normal(0.00, 0.01, size=n_samples),
            ]
        ),
        gamma_peak=rng.normal(0.05, 0.005, size=n_samples),
        mu_transport=rng.normal(np.log(30.0), 0.02, size=n_samples),
        sigma_transport=rng.normal(0.30, 0.01, size=n_samples).clip(min=0.05),
    )


@pytest.fixture
def sample_parquet_path(tmp_path: Path) -> Path:
    """Tiny journey parquet on disk, suitable for load_journeys() tests."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    records = [
        {
            "journey_id": f"j{i}",
            "facility_id": ["BOCA", "LGB", "ELM"][i % 3],
            "tray_id": f"t{i}",
            "tray_type_id": "TRAY-KNEE" if i % 2 == 0 else "TRAY-LAPS",
            "client_id": "HOSPITAL_A",
            "pickup_ts": np.datetime64("2026-01-01T09:00:00", "us"),
            "required_by_ts": np.datetime64("2026-01-01T13:00:00", "us"),
            "decon_dwell_min": 15.0,
            "inspection_dwell_min": 20.0,
            "assembly_dwell_min": 30.0,
            "sterilization_dwell_min": 90.0,
            "packout_dwell_min": 10.0,
            "transport_min": 30.0,
            "delivered_ts": np.datetime64("2026-01-01T12:15:00", "us"),
            "on_time": True,
            "delay_min": -45.0,
            "hour_of_pickup": 9 if i % 4 == 0 else 13,  # mix peak and off-peak
            "day_of_week": 0,
        }
        for i in range(12)
    ]
    table = pa.Table.from_pylist(records)
    out = tmp_path / "j.parquet"
    pq.write_table(table, out)
    return out
