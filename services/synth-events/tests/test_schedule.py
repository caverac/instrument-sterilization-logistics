"""Tests for the pickup-arrival schedule generator."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from synth_events.parameters import CLIENTS, FACILITIES, TRAY_TYPES
from synth_events.schedule import generate_pickups

_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_END = datetime(2026, 1, 8, tzinfo=timezone.utc)


def test_generate_pickups_returns_requested_count() -> None:
    rng = np.random.default_rng(0)
    pickups = generate_pickups(rng, 50, _START, _END)
    assert len(pickups) == 50


def test_pickup_ts_within_range() -> None:
    rng = np.random.default_rng(1)
    pickups = generate_pickups(rng, 200, _START, _END)
    for p in pickups:
        assert _START <= p.pickup_ts < _END


def test_required_by_ts_always_after_pickup() -> None:
    rng = np.random.default_rng(2)
    pickups = generate_pickups(rng, 200, _START, _END)
    for p in pickups:
        assert p.required_by_ts > p.pickup_ts


def test_facility_assignments_cover_all_facilities() -> None:
    rng = np.random.default_rng(3)
    pickups = generate_pickups(rng, 500, _START, _END)
    seen = {p.facility.facility_id for p in pickups}
    assert seen == {f.facility_id for f in FACILITIES}


def test_tray_type_assignments_cover_all_types() -> None:
    rng = np.random.default_rng(4)
    pickups = generate_pickups(rng, 500, _START, _END)
    seen = {p.tray_type.tray_type_id for p in pickups}
    assert seen == {t.tray_type_id for t in TRAY_TYPES}


def test_client_assignments_cover_all_clients() -> None:
    rng = np.random.default_rng(5)
    pickups = generate_pickups(rng, 500, _START, _END)
    seen = {p.client_id for p in pickups}
    assert seen == set(CLIENTS)


def test_seed_determines_output() -> None:
    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(7)
    a = generate_pickups(rng_a, 25, _START, _END)
    b = generate_pickups(rng_b, 25, _START, _END)
    for x, y in zip(a, b, strict=True):
        assert x == y
