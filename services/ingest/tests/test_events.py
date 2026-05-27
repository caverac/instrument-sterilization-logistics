"""Tests for the Event schema and helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from ingest.events import Event, EventIn, EventType, assign_server_fields, deterministic_event_id


def test_event_in_minimal_defaults() -> None:
    ev = EventIn(
        source_system="X",
        source_event_id="y",
        tray_id="T",
        facility_id="F",
        event_type=EventType.CHECKED_IN,
        timestamp_event=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert ev.payload == {}
    assert ev.schema_version == 1
    assert ev.operator_id is None


def test_event_in_rejects_extra_fields() -> None:
    payload = {
        "source_system": "X",
        "source_event_id": "y",
        "tray_id": "T",
        "facility_id": "F",
        "event_type": "CHECKED_IN",
        "timestamp_event": "2026-01-01T00:00:00+00:00",
        "unknown_field": "bad",
    }
    with pytest.raises(ValidationError):
        EventIn.model_validate(payload)


def test_event_in_rejects_empty_strings() -> None:
    with pytest.raises(ValidationError):
        EventIn(
            source_system="",
            source_event_id="y",
            tray_id="T",
            facility_id="F",
            event_type=EventType.CHECKED_IN,
            timestamp_event=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_deterministic_event_id_is_stable() -> None:
    a = deterministic_event_id("SYS_A", "evt-1")
    b = deterministic_event_id("SYS_A", "evt-1")
    assert a == b
    assert isinstance(a, UUID)


def test_deterministic_event_id_differs_on_source_system() -> None:
    a = deterministic_event_id("SYS_A", "evt-1")
    b = deterministic_event_id("SYS_B", "evt-1")
    assert a != b


def test_deterministic_event_id_differs_on_source_event_id() -> None:
    a = deterministic_event_id("SYS_A", "evt-1")
    b = deterministic_event_id("SYS_A", "evt-2")
    assert a != b


def test_assign_server_fields_uses_deterministic_id() -> None:
    ev_in = EventIn(
        source_system="X",
        source_event_id="y",
        tray_id="T",
        facility_id="F",
        event_type=EventType.CHECKED_IN,
        timestamp_event=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    out = assign_server_fields(ev_in)
    assert isinstance(out, Event)
    assert out.event_id == deterministic_event_id("X", "y")
    assert out.timestamp_ingest.tzinfo is not None
