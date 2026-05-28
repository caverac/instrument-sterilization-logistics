"""Event model decoded from Kafka.

Mirrors the wire-format schema published by ``services/ingest``. Duplicated
deliberately so projector evolves its internal representation without
coupling to ingest's Python class.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


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


class Event(BaseModel):
    """Event as decoded from Kafka.

    Schema mirrors the wire-format JSON published by the ingest service.
    Extra fields are ignored so forward-compatible schema evolution (new
    optional fields added upstream) does not break this consumer.
    """

    model_config = ConfigDict(extra="ignore")

    event_id: UUID
    source_system: str
    source_event_id: str
    tray_id: str
    facility_id: str
    event_type: EventType
    operator_id: str | None = None
    timestamp_event: datetime
    timestamp_ingest: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = Field(default=1, ge=1)


class PickedUpPayload(BaseModel):
    """Required fields carried in a ``PICKED_UP`` event's ``payload``.

    The hospital adapter is responsible for filling these in at pickup time.
    The projector reads them once when starting a journey; they are not
    expected on later stage events.
    """

    model_config = ConfigDict(extra="ignore")

    client_id: str = Field(min_length=1, max_length=64)
    tray_type_id: str = Field(min_length=1, max_length=64)
    required_by_ts: datetime


def parse_picked_up_payload(payload: dict[str, Any]) -> PickedUpPayload | None:
    """Validate and return the typed PICKED_UP payload.

    Returns
    -------
    PickedUpPayload | None
        ``None`` if the payload is missing required fields or fails
        validation. Callers should treat that as "skip this journey" rather
        than crashing the consumer loop.
    """
    try:
        return PickedUpPayload.model_validate(payload)
    except ValidationError:
        return None
