"""Shared fixtures and fakes for ingest tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from ingest.events import Event, EventIn, EventType, assign_server_fields


class FakeProducer:
    """In-memory stand-in for a confluent-kafka Producer."""

    def __init__(self) -> None:
        self.produced: list[dict[str, Any]] = []
        self.poll_calls: int = 0
        self.flush_calls: int = 0

    def produce(self, *, topic: str, key: bytes, value: bytes, **_: Any) -> None:
        """Record the message in-memory."""
        self.produced.append({"topic": topic, "key": key, "value": value})

    def poll(self, _timeout: float) -> int:
        """Record the poll call (used by Producer to serve delivery callbacks)."""
        self.poll_calls += 1
        return 0

    def flush(self, timeout: float | None = None) -> int:  # pylint: disable=unused-argument
        """Record the flush call (used on shutdown)."""
        self.flush_calls += 1
        return 0


class FakeSerializer:
    """Stand-in for confluent-kafka's JSONSerializer.

    Skips the magic-byte + schema-id wire-format wrapping that the real
    serializer applies; tests don't need the wire format, only the payload.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, value: Any, ctx: Any) -> bytes:
        """Record the call and return the JSON-encoded value."""
        self.calls.append((value, ctx))
        return json.dumps(value, default=str).encode("utf-8")


@pytest.fixture
def fake_producer() -> FakeProducer:
    """Return a fresh in-memory FakeProducer."""
    return FakeProducer()


@pytest.fixture
def fake_serializer() -> FakeSerializer:
    """Return a fresh in-memory FakeSerializer."""
    return FakeSerializer()


@pytest.fixture
def sample_event_in() -> EventIn:
    """Return a minimal, valid EventIn for tests."""
    return EventIn(
        source_system="CENSITRAC_BOCA",
        source_event_id="abc-123",
        tray_id="TRAY-001",
        facility_id="BOCA",
        event_type=EventType.CHECKED_IN,
        timestamp_event=datetime(2026, 5, 25, 14, 30, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_event(sample_event_in: EventIn) -> Event:
    """Return a fully-formed Event with server-assigned fields."""
    return assign_server_fields(sample_event_in)
