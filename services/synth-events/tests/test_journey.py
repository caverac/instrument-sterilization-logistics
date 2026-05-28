"""Tests for the Journey dataclass and simulator."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import numpy as np

from synth_events.journey import Journey, rng_uuid, simulate_journey
from synth_events.parameters import FACILITIES, TRAY_TYPES
from synth_events.schedule import Pickup

_PICKUP_TS = datetime(2026, 1, 5, 10, 30, tzinfo=timezone.utc)
_DEADLINE_TS = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def _make_pickup() -> Pickup:
    return Pickup(
        pickup_ts=_PICKUP_TS,
        required_by_ts=_DEADLINE_TS,
        client_id="HOSPITAL_A",
        facility=FACILITIES[1],  # LGB
        tray_type=TRAY_TYPES[1],  # TRAY-KNEE
    )


def test_rng_uuid_is_deterministic_given_seed() -> None:
    rng_a = np.random.default_rng(11)
    rng_b = np.random.default_rng(11)
    assert rng_uuid(rng_a) == rng_uuid(rng_b)


def test_rng_uuid_yields_distinct_uuids() -> None:
    rng = np.random.default_rng(11)
    uuids = {rng_uuid(rng) for _ in range(100)}
    assert len(uuids) == 100


def test_simulate_journey_populates_all_fields() -> None:
    rng = np.random.default_rng(13)
    journey = simulate_journey(rng, _make_pickup())
    assert isinstance(journey, Journey)
    assert isinstance(journey.journey_id, UUID)
    assert journey.facility_id == "LGB"
    assert journey.tray_id.startswith("TRAY-")
    assert journey.tray_type_id == "TRAY-KNEE"
    assert journey.client_id == "HOSPITAL_A"
    assert journey.pickup_ts == _PICKUP_TS
    assert journey.required_by_ts == _DEADLINE_TS
    for dwell in (
        journey.decon_dwell_min,
        journey.inspection_dwell_min,
        journey.assembly_dwell_min,
        journey.sterilization_dwell_min,
        journey.packout_dwell_min,
        journey.transport_min,
    ):
        assert dwell > 0
    assert journey.hour_of_pickup == 10
    assert journey.day_of_week == _PICKUP_TS.weekday()


def test_delivered_ts_consistent_with_dwells() -> None:
    rng = np.random.default_rng(15)
    journey = simulate_journey(rng, _make_pickup())
    total_min = (
        journey.decon_dwell_min
        + journey.inspection_dwell_min
        + journey.assembly_dwell_min
        + journey.sterilization_dwell_min
        + journey.packout_dwell_min
        + journey.transport_min
    )
    expected_delivered_sec = journey.pickup_ts.timestamp() + total_min * 60.0
    assert abs(journey.delivered_ts.timestamp() - expected_delivered_sec) < 1e-3


def test_on_time_flag_matches_delay_sign() -> None:
    rng = np.random.default_rng(17)
    for _ in range(50):
        journey = simulate_journey(rng, _make_pickup())
        assert journey.on_time == (journey.delay_min <= 0)


def test_to_record_produces_flat_dict() -> None:
    rng = np.random.default_rng(19)
    journey = simulate_journey(rng, _make_pickup())
    record = journey.to_record()
    assert record["journey_id"] == str(journey.journey_id)
    assert record["facility_id"] == "LGB"
    assert record["on_time"] is journey.on_time
    assert record["hour_of_pickup"] == journey.hour_of_pickup
    assert isinstance(record["delivered_ts"], datetime)
