"""Shared fixtures for projector tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid5

import pytest

from projector.events import Event, EventType
from projector.store import InMemoryStore

UTC = timezone.utc

# Stable namespace for deterministic event_ids in tests. XORed with the
# event_type and tray_id to yield distinct ids per event.
_EVENT_ID_NAMESPACE = UUID("11111111-2222-3333-4444-555555555555")


EventFactory = Callable[..., Event]
PayloadFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def make_event() -> EventFactory:
    """Return a factory that builds valid test events with sensible defaults."""

    def _make(
        event_type: EventType,
        *,
        tray_id: str = "TRAY-1",
        facility_id: str = "BOCA",
        timestamp_event: datetime | None = None,
        payload: dict[str, Any] | None = None,
        event_id: UUID | None = None,
    ) -> Event:
        ts = timestamp_event or datetime(2026, 5, 27, 8, 0, tzinfo=UTC)
        derived_id = event_id or uuid5(_EVENT_ID_NAMESPACE, f"{tray_id}:{event_type.value}")
        return Event(
            event_id=derived_id,
            source_system="TEST",
            source_event_id=f"src-{event_type.value}-{tray_id}",
            tray_id=tray_id,
            facility_id=facility_id,
            event_type=event_type,
            timestamp_event=ts,
            timestamp_ingest=ts,
            payload=payload or {},
        )

    return _make


@pytest.fixture
def picked_up_payload() -> PayloadFactory:
    """Return a factory for valid PICKED_UP event payloads."""

    def _make(
        client_id: str = "HOSPITAL_A",
        tray_type_id: str = "TRAY-KNEE",
        required_by: datetime | None = None,
    ) -> dict[str, Any]:
        deadline = required_by or datetime(2026, 5, 27, 13, 0, tzinfo=UTC)
        return {
            "client_id": client_id,
            "tray_type_id": tray_type_id,
            "required_by_ts": deadline.isoformat(),
        }

    return _make


@pytest.fixture
def in_memory_store() -> InMemoryStore:
    """Return a fresh in-memory store for each test."""
    return InMemoryStore()


@pytest.fixture
def full_journey_events(make_event: EventFactory, picked_up_payload: PayloadFactory) -> list[Event]:
    """Return a complete, well-formed sequence of 10 events for one journey."""
    ts_pickup = datetime(2026, 5, 27, 8, 0, tzinfo=UTC)
    ts_checkin = datetime(2026, 5, 27, 8, 30, tzinfo=UTC)
    ts_decon_start = datetime(2026, 5, 27, 8, 45, tzinfo=UTC)
    ts_decon_end = datetime(2026, 5, 27, 9, 5, tzinfo=UTC)
    ts_inspected = datetime(2026, 5, 27, 9, 25, tzinfo=UTC)
    ts_assembled = datetime(2026, 5, 27, 9, 50, tzinfo=UTC)
    ts_sterilized = datetime(2026, 5, 27, 10, 30, tzinfo=UTC)
    ts_packed = datetime(2026, 5, 27, 10, 45, tzinfo=UTC)
    ts_loaded = datetime(2026, 5, 27, 11, 0, tzinfo=UTC)
    ts_delivered = datetime(2026, 5, 27, 11, 30, tzinfo=UTC)

    return [
        make_event(
            EventType.PICKED_UP,
            facility_id="HOSPITAL_A",
            timestamp_event=ts_pickup,
            payload=picked_up_payload(required_by=datetime(2026, 5, 27, 13, 0, tzinfo=UTC)),
        ),
        make_event(EventType.CHECKED_IN, timestamp_event=ts_checkin),
        make_event(EventType.DECON_START, timestamp_event=ts_decon_start),
        make_event(EventType.DECON_END, timestamp_event=ts_decon_end),
        make_event(EventType.INSPECTED, timestamp_event=ts_inspected),
        make_event(EventType.ASSEMBLED, timestamp_event=ts_assembled),
        make_event(EventType.STERILIZED, timestamp_event=ts_sterilized),
        make_event(EventType.PACKED, timestamp_event=ts_packed),
        make_event(EventType.LOADED, timestamp_event=ts_loaded),
        make_event(
            EventType.DELIVERED,
            facility_id="HOSPITAL_A",
            timestamp_event=ts_delivered,
        ),
    ]
