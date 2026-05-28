"""Tests for the projector event model and payload parsing."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from projector.events import Event, EventType, parse_picked_up_payload


def test_event_validates_minimal_fields() -> None:
    """A well-formed event payload round-trips through the model."""
    event = Event(
        event_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        source_system="CENSITRAC_BOCA",
        source_event_id="abc-123",
        tray_id="TRAY-001",
        facility_id="BOCA",
        event_type=EventType.CHECKED_IN,
        timestamp_event=datetime(2026, 5, 27, 14, tzinfo=timezone.utc),
        timestamp_ingest=datetime(2026, 5, 27, 14, 1, tzinfo=timezone.utc),
    )
    assert event.payload == {}
    assert event.schema_version == 1


def test_event_extra_fields_are_ignored() -> None:
    """Forward-compatible: unknown fields on the wire do not break decoding."""
    event = Event.model_validate(
        {
            "event_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "source_system": "CENSITRAC_BOCA",
            "source_event_id": "abc-123",
            "tray_id": "TRAY-001",
            "facility_id": "BOCA",
            "event_type": "CHECKED_IN",
            "timestamp_event": "2026-05-27T14:00:00+00:00",
            "timestamp_ingest": "2026-05-27T14:01:00+00:00",
            "unrecognized_field": "should be ignored",
        }
    )
    assert event.tray_id == "TRAY-001"


def test_parse_picked_up_payload_happy() -> None:
    """A valid PICKED_UP payload parses into the typed model."""
    parsed = parse_picked_up_payload(
        {
            "client_id": "HOSPITAL_A",
            "tray_type_id": "TRAY-KNEE",
            "required_by_ts": "2026-05-27T13:00:00+00:00",
        }
    )
    assert parsed is not None
    assert parsed.client_id == "HOSPITAL_A"
    assert parsed.tray_type_id == "TRAY-KNEE"


def test_parse_picked_up_payload_missing_field_returns_none() -> None:
    """A payload missing required fields parses to ``None``, not a raise."""
    assert parse_picked_up_payload({"client_id": "HOSPITAL_A"}) is None


def test_parse_picked_up_payload_bad_type_returns_none() -> None:
    """A payload with a wrong-type field parses to ``None``."""
    assert (
        parse_picked_up_payload(
            {
                "client_id": "HOSPITAL_A",
                "tray_type_id": "TRAY-KNEE",
                "required_by_ts": "not-a-datetime",
            }
        )
        is None
    )
