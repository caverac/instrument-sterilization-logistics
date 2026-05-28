"""Tests for pure projection logic and the apply_event orchestrator.

Also exercises :class:`projector.store.InMemoryStore` end-to-end -- no need
for a separate test_store.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from projector.events import Event, EventType, parse_picked_up_payload
from projector.projections import (
    OpenJourney,
    apply_event,
    finalize_journey,
    open_journey_init,
    stage_apply,
    tray_from_event,
)
from projector.store import InMemoryStore

EventFactory = Callable[..., Event]
PayloadFactory = Callable[..., dict[str, Any]]

UTC = timezone.utc


def test_tray_from_event_pulls_fields_off_event(make_event: EventFactory) -> None:
    """``tray_from_event`` copies tray-relevant fields onto the projection."""
    event = make_event(EventType.CHECKED_IN, facility_id="LGB")
    tray = tray_from_event(event)
    assert tray.tray_id == event.tray_id
    assert tray.current_facility_id == "LGB"
    assert tray.current_stage == "CHECKED_IN"
    assert tray.last_event_id == event.event_id
    assert tray.last_event_ts == event.timestamp_event


def test_open_journey_init_uses_payload_metadata(make_event: EventFactory, picked_up_payload: PayloadFactory) -> None:
    """``open_journey_init`` pins client/tray-type/deadline from the payload."""
    event = make_event(
        EventType.PICKED_UP,
        facility_id="HOSPITAL_A",
        payload=picked_up_payload(
            client_id="ASC_X",
            tray_type_id="TRAY-SPINE",
            required_by=datetime(2026, 5, 27, 14, tzinfo=UTC),
        ),
    )
    parsed = parse_picked_up_payload(event.payload)
    assert parsed is not None
    journey = open_journey_init(event, parsed)
    assert journey.client_id == "ASC_X"
    assert journey.tray_type_id == "TRAY-SPINE"
    assert journey.pickup_ts == event.timestamp_event
    assert journey.required_by_ts == datetime(2026, 5, 27, 14, tzinfo=UTC)
    assert journey.facility_id is None  # pinned later, on first stage event


def test_stage_apply_writes_field_and_pins_facility(make_event: EventFactory) -> None:
    """First stage event populates the timestamp field and pins facility_id."""
    open_j = OpenJourney(
        tray_id="TRAY-1",
        pickup_event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        client_id="HOSPITAL_A",
        tray_type_id="TRAY-KNEE",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=UTC),
        required_by_ts=datetime(2026, 5, 27, 13, tzinfo=UTC),
    )
    decon = make_event(
        EventType.DECON_START,
        facility_id="BOCA",
        timestamp_event=datetime(2026, 5, 27, 8, 45, tzinfo=UTC),
    )
    updated = stage_apply(open_j, decon)
    assert updated.decon_start_ts == datetime(2026, 5, 27, 8, 45, tzinfo=UTC)
    assert updated.facility_id == "BOCA"


def test_stage_apply_does_not_overwrite_facility(make_event: EventFactory) -> None:
    """Once facility_id is pinned, subsequent stages do not move it."""
    open_j = OpenJourney(
        tray_id="TRAY-1",
        pickup_event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        client_id="HOSPITAL_A",
        tray_type_id="TRAY-KNEE",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=UTC),
        required_by_ts=datetime(2026, 5, 27, 13, tzinfo=UTC),
        facility_id="BOCA",
    )
    inspected = make_event(
        EventType.INSPECTED,
        facility_id="LGB",
        timestamp_event=datetime(2026, 5, 27, 9, 25, tzinfo=UTC),
    )
    updated = stage_apply(open_j, inspected)
    assert updated.facility_id == "BOCA"
    assert updated.inspected_ts == datetime(2026, 5, 27, 9, 25, tzinfo=UTC)


def test_finalize_journey_computes_dwells_and_on_time(make_event: EventFactory) -> None:
    """A complete open journey + DELIVERED yields a finalized row with dwells."""
    open_j = OpenJourney(
        tray_id="TRAY-1",
        pickup_event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        client_id="HOSPITAL_A",
        tray_type_id="TRAY-KNEE",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=UTC),
        required_by_ts=datetime(2026, 5, 27, 13, tzinfo=UTC),
        facility_id="BOCA",
        decon_start_ts=datetime(2026, 5, 27, 8, 45, tzinfo=UTC),
        decon_end_ts=datetime(2026, 5, 27, 9, 5, tzinfo=UTC),
        inspected_ts=datetime(2026, 5, 27, 9, 25, tzinfo=UTC),
        assembled_ts=datetime(2026, 5, 27, 9, 50, tzinfo=UTC),
        sterilized_ts=datetime(2026, 5, 27, 10, 30, tzinfo=UTC),
        packed_ts=datetime(2026, 5, 27, 10, 45, tzinfo=UTC),
        loaded_ts=datetime(2026, 5, 27, 11, tzinfo=UTC),
    )
    delivered = make_event(
        EventType.DELIVERED,
        facility_id="HOSPITAL_A",
        timestamp_event=datetime(2026, 5, 27, 11, 30, tzinfo=UTC),
    )
    row = finalize_journey(open_j, delivered)
    assert row is not None
    assert row.decon_dwell_min == 20.0
    assert row.inspection_dwell_min == 20.0
    assert row.assembly_dwell_min == 25.0
    assert row.sterilization_dwell_min == 40.0
    assert row.packout_dwell_min == 15.0
    assert row.transport_min == 30.0
    assert row.on_time is True
    assert row.delay_min == -90.0  # delivered 90 minutes early
    assert row.hour_of_pickup == 8
    assert row.day_of_week == 2  # 2026-05-27 is a Wednesday


def test_finalize_journey_marks_late_delivery(make_event: EventFactory) -> None:
    """When delivered past the deadline, on_time is False and delay is positive."""
    open_j = OpenJourney(
        tray_id="TRAY-1",
        pickup_event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        client_id="HOSPITAL_A",
        tray_type_id="TRAY-KNEE",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=UTC),
        required_by_ts=datetime(2026, 5, 27, 10, tzinfo=UTC),
        facility_id="BOCA",
        decon_start_ts=datetime(2026, 5, 27, 8, 45, tzinfo=UTC),
        decon_end_ts=datetime(2026, 5, 27, 9, 5, tzinfo=UTC),
        inspected_ts=datetime(2026, 5, 27, 9, 25, tzinfo=UTC),
        assembled_ts=datetime(2026, 5, 27, 9, 50, tzinfo=UTC),
        sterilized_ts=datetime(2026, 5, 27, 10, 30, tzinfo=UTC),
        packed_ts=datetime(2026, 5, 27, 10, 45, tzinfo=UTC),
        loaded_ts=datetime(2026, 5, 27, 11, tzinfo=UTC),
    )
    delivered = make_event(
        EventType.DELIVERED,
        timestamp_event=datetime(2026, 5, 27, 11, 30, tzinfo=UTC),
    )
    row = finalize_journey(open_j, delivered)
    assert row is not None
    assert row.on_time is False
    assert row.delay_min == 90.0


def test_finalize_journey_returns_none_when_incomplete(make_event: EventFactory) -> None:
    """A missing intermediate timestamp prevents finalization."""
    open_j = OpenJourney(
        tray_id="TRAY-1",
        pickup_event_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        client_id="HOSPITAL_A",
        tray_type_id="TRAY-KNEE",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=UTC),
        required_by_ts=datetime(2026, 5, 27, 13, tzinfo=UTC),
        facility_id="BOCA",
        decon_start_ts=datetime(2026, 5, 27, 8, 45, tzinfo=UTC),
        decon_end_ts=datetime(2026, 5, 27, 9, 5, tzinfo=UTC),
        inspected_ts=datetime(2026, 5, 27, 9, 25, tzinfo=UTC),
        # assembled / sterilized / packed / loaded missing
    )
    delivered = make_event(EventType.DELIVERED)
    assert finalize_journey(open_j, delivered) is None


def test_apply_full_journey_writes_one_row(in_memory_store: InMemoryStore, full_journey_events: list[Event]) -> None:
    """A full 10-event sequence yields one journey row and no open state."""
    for event in full_journey_events:
        apply_event(in_memory_store, event)
    assert len(in_memory_store.journeys) == 1
    assert in_memory_store.open_journeys == {}
    journey = in_memory_store.journeys[0]
    assert journey.tray_id == "TRAY-1"
    assert journey.facility_id == "BOCA"
    assert journey.client_id == "HOSPITAL_A"
    assert journey.tray_type_id == "TRAY-KNEE"
    assert in_memory_store.trays["TRAY-1"].current_stage == "DELIVERED"


def test_apply_event_picked_up_with_bad_payload_does_not_open_journey(
    in_memory_store: InMemoryStore, make_event: EventFactory
) -> None:
    """Malformed PICKED_UP payload still updates tray but opens no journey."""
    event = make_event(EventType.PICKED_UP, payload={"client_id": "HOSPITAL_A"})
    apply_event(in_memory_store, event)
    assert in_memory_store.open_journeys == {}
    assert "TRAY-1" in in_memory_store.trays


def test_apply_event_stage_without_pickup_is_skipped(in_memory_store: InMemoryStore, make_event: EventFactory) -> None:
    """Stage event for a tray with no open journey only updates tray."""
    event = make_event(EventType.DECON_START)
    apply_event(in_memory_store, event)
    assert in_memory_store.open_journeys == {}
    assert in_memory_store.trays["TRAY-1"].current_stage == "DECON_START"


def test_apply_event_delivered_without_pickup_is_skipped(
    in_memory_store: InMemoryStore, make_event: EventFactory
) -> None:
    """DELIVERED for a tray with no open journey writes no row."""
    event = make_event(EventType.DELIVERED)
    apply_event(in_memory_store, event)
    assert in_memory_store.journeys == []


def test_apply_event_delivered_incomplete_leaves_open_journey(
    in_memory_store: InMemoryStore,
    make_event: EventFactory,
    picked_up_payload: PayloadFactory,
) -> None:
    """DELIVERED on an incomplete journey leaves the open_journey row in place."""
    pickup = make_event(
        EventType.PICKED_UP,
        payload=picked_up_payload(),
        facility_id="HOSPITAL_A",
    )
    apply_event(in_memory_store, pickup)
    # Skip every stage; jump straight to DELIVERED.
    apply_event(in_memory_store, make_event(EventType.DELIVERED))
    assert in_memory_store.journeys == []
    assert "TRAY-1" in in_memory_store.open_journeys


def test_apply_event_checked_in_only_updates_tray(in_memory_store: InMemoryStore, make_event: EventFactory) -> None:
    """CHECKED_IN and DEFECT_REPORTED have no journey effect."""
    apply_event(in_memory_store, make_event(EventType.CHECKED_IN))
    apply_event(in_memory_store, make_event(EventType.DEFECT_REPORTED))
    assert in_memory_store.open_journeys == {}
    assert in_memory_store.journeys == []
    assert in_memory_store.trays["TRAY-1"].current_stage == "DEFECT_REPORTED"
