"""Event schema and helpers for the ingest service."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

# Stable namespace UUID for this project. Combined with (source_system,
# source_event_id) via UUIDv5 to produce a deterministic event_id, so that
# vendor retries always resolve to the same UUID and downstream consumers
# can dedup naturally on the primary key.
EVENT_ID_NAMESPACE = UUID("8b1a1f4c-0d4e-5e0a-9b1f-1c0e0a1b2c3d")


class EventType(str, enum.Enum):
    """Lifecycle states a tray can be in."""

    PICKED_UP = "PICKED_UP"
    CHECKED_IN = "CHECKED_IN"
    DECON_START = "DECON_START"
    DECON_END = "DECON_END"
    INSPECTED = "INSPECTED"
    ASSEMBLED = "ASSEMBLED"
    STERILIZED = "STERILIZED"
    PACKED = "PACKED"
    LOADED = "LOADED"
    DELIVERED = "DELIVERED"
    DEFECT_REPORTED = "DEFECT_REPORTED"


class EventIn(BaseModel):
    """Inbound event payload from a facility adapter.

    ``event_id`` is intentionally not accepted from the client; the server
    derives it deterministically from ``(source_system, source_event_id)``.
    """

    model_config = ConfigDict(extra="forbid")

    source_system: str = Field(min_length=1, max_length=64)
    source_event_id: str = Field(min_length=1, max_length=128)
    tray_id: str = Field(min_length=1, max_length=64)
    facility_id: str = Field(min_length=1, max_length=64)
    event_type: EventType
    operator_id: str | None = Field(default=None, max_length=64)
    timestamp_event: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = Field(default=1, ge=1)


class Event(EventIn):
    """A fully-formed event with server-assigned identifiers."""

    event_id: UUID
    timestamp_ingest: datetime


def deterministic_event_id(source_system: str, source_event_id: str) -> UUID:
    """Mint a stable UUIDv5 for an event from its source-side identifiers.

    Parameters
    ----------
    source_system : str
        Vendor system identifier (e.g. ``CENSITRAC_BOCA``).
    source_event_id : str
        Vendor's own ID for this event.

    Returns
    -------
    UUID
        UUIDv5 derived from the project namespace and the two inputs.
        Identical inputs always produce the same UUID.
    """
    return uuid5(EVENT_ID_NAMESPACE, f"{source_system}:{source_event_id}")


def assign_server_fields(event_in: EventIn) -> Event:
    """Derive ``event_id`` and stamp ``timestamp_ingest``.

    Parameters
    ----------
    event_in : EventIn
        Inbound event.

    Returns
    -------
    Event
        Fully-formed event with server-assigned fields.
    """
    return Event(
        **event_in.model_dump(),
        event_id=deterministic_event_id(event_in.source_system, event_in.source_event_id),
        timestamp_ingest=datetime.now(timezone.utc),
    )
