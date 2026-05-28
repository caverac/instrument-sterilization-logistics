"""Tests for the journey-to-events mapping."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from synth_events.event_stream import journey_to_events
from synth_events.journey import Journey


def _journey() -> Journey:
    """Return a fixed Journey covering every dwell field with distinct values."""
    pickup = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)
    return Journey(
        journey_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        facility_id="BOCA",
        tray_id="TRAY-ABCDEF",
        tray_type_id="TRAY-KNEE",
        client_id="HOSPITAL_A",
        pickup_ts=pickup,
        required_by_ts=datetime(2026, 5, 27, 13, 0, tzinfo=timezone.utc),
        decon_dwell_min=20.0,
        inspection_dwell_min=20.0,
        assembly_dwell_min=25.0,
        sterilization_dwell_min=40.0,
        packout_dwell_min=15.0,
        transport_min=30.0,
        delivered_ts=datetime(2026, 5, 27, 10, 30, tzinfo=timezone.utc),
        on_time=True,
        delay_min=-150.0,
        hour_of_pickup=8,
        day_of_week=2,
    )


def test_journey_emits_ten_events_in_order() -> None:
    """One journey produces exactly 10 events in PICKED_UP -> DELIVERED order."""
    events = journey_to_events(_journey())
    assert [e["event_type"] for e in events] == [
        "PICKED_UP",
        "CHECKED_IN",
        "DECON_START",
        "DECON_END",
        "INSPECTED",
        "ASSEMBLED",
        "STERILIZED",
        "PACKED",
        "LOADED",
        "DELIVERED",
    ]


def test_pickup_payload_carries_required_metadata() -> None:
    """PICKED_UP payload includes client_id, tray_type_id, required_by_ts."""
    events = journey_to_events(_journey())
    payload = events[0]["payload"]
    assert payload["client_id"] == "HOSPITAL_A"
    assert payload["tray_type_id"] == "TRAY-KNEE"
    assert payload["required_by_ts"] == "2026-05-27T13:00:00+00:00"


def test_facility_id_alternates_between_hospital_and_facility() -> None:
    """PICKED_UP and DELIVERED use client_id; mid-cycle events use facility_id."""
    events = journey_to_events(_journey())
    assert events[0]["facility_id"] == "HOSPITAL_A"  # PICKED_UP
    assert events[1]["facility_id"] == "BOCA"  # CHECKED_IN
    assert events[8]["facility_id"] == "BOCA"  # LOADED
    assert events[9]["facility_id"] == "HOSPITAL_A"  # DELIVERED


def test_timestamps_yield_exact_dwells_when_projected() -> None:
    """Differences between consecutive stage timestamps equal the dwell fields."""
    j = _journey()
    events = {e["event_type"]: datetime.fromisoformat(e["timestamp_event"]) for e in journey_to_events(j)}
    assert (events["DECON_END"] - events["DECON_START"]).total_seconds() / 60.0 == j.decon_dwell_min
    assert (events["INSPECTED"] - events["DECON_END"]).total_seconds() / 60.0 == j.inspection_dwell_min
    assert (events["ASSEMBLED"] - events["INSPECTED"]).total_seconds() / 60.0 == j.assembly_dwell_min
    assert (events["STERILIZED"] - events["ASSEMBLED"]).total_seconds() / 60.0 == j.sterilization_dwell_min
    assert (events["PACKED"] - events["STERILIZED"]).total_seconds() / 60.0 == j.packout_dwell_min
    assert (events["DELIVERED"] - events["LOADED"]).total_seconds() / 60.0 == j.transport_min


def test_delivered_ts_matches_journey_delivered_ts() -> None:
    """The DELIVERED event timestamp equals Journey.delivered_ts."""
    j = _journey()
    events = journey_to_events(j)
    delivered = datetime.fromisoformat(events[9]["timestamp_event"])
    assert delivered == j.delivered_ts


def test_source_event_ids_are_unique_per_journey() -> None:
    """All 10 events have distinct source_event_ids derived from tray_id."""
    events = journey_to_events(_journey())
    ids = [e["source_event_id"] for e in events]
    assert len(set(ids)) == 10
    assert all(eid.startswith("TRAY-ABCDEF-") for eid in ids)
