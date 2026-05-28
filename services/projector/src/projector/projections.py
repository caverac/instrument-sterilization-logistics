"""Pure projection logic: events to (tray, open-journey, journey) state changes.

These functions operate on plain data. They do not touch Postgres directly;
the orchestrator in :func:`apply_event` calls them and dispatches the
results through a :class:`projector.store.Store`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from projector.events import Event, EventType, PickedUpPayload, parse_picked_up_payload

if TYPE_CHECKING:
    from projector.store import Store

# UUIDv5 namespace for journey ids. Combined with the pickup event_id, a
# journey gets a stable, deterministic id derivable from its first event.
JOURNEY_ID_NAMESPACE = UUID("c0ffee00-c0ff-eeee-baaa-c0ffeec0ffee")


STAGE_EVENT_TYPES = frozenset(
    {
        EventType.DECON_START,
        EventType.DECON_END,
        EventType.INSPECTED,
        EventType.ASSEMBLED,
        EventType.STERILIZED,
        EventType.PACKED,
        EventType.LOADED,
    }
)


@dataclass(frozen=True)
class TrayState:
    """Current-state projection for one tray."""

    tray_id: str
    current_facility_id: str
    current_stage: str
    last_event_id: UUID
    last_event_ts: datetime


@dataclass(frozen=True)
class OpenJourney:
    """Intermediate state for a pickup-to-delivery cycle still in flight.

    ``facility_id`` is filled when the first stage event (DECON_START) lands,
    not at pickup -- the pickup happens at the hospital, the work happens at
    the facility.
    """

    tray_id: str
    pickup_event_id: UUID
    client_id: str
    tray_type_id: str
    pickup_ts: datetime
    required_by_ts: datetime
    facility_id: str | None = None
    decon_start_ts: datetime | None = None
    decon_end_ts: datetime | None = None
    inspected_ts: datetime | None = None
    assembled_ts: datetime | None = None
    sterilized_ts: datetime | None = None
    packed_ts: datetime | None = None
    loaded_ts: datetime | None = None


@dataclass(frozen=True)
class JourneyRow:
    """Finalized journey row. Schema mirrors ``synth-events`` parquet."""

    journey_id: UUID
    tray_id: str
    facility_id: str
    tray_type_id: str
    client_id: str
    pickup_ts: datetime
    required_by_ts: datetime
    decon_dwell_min: float
    inspection_dwell_min: float
    assembly_dwell_min: float
    sterilization_dwell_min: float
    packout_dwell_min: float
    transport_min: float
    delivered_ts: datetime
    on_time: bool
    delay_min: float
    hour_of_pickup: int
    day_of_week: int


def tray_from_event(event: Event) -> TrayState:
    """Derive the new tray projection state from any inbound event."""
    return TrayState(
        tray_id=event.tray_id,
        current_facility_id=event.facility_id,
        current_stage=event.event_type.value,
        last_event_id=event.event_id,
        last_event_ts=event.timestamp_event,
    )


def open_journey_init(event: Event, payload: PickedUpPayload) -> OpenJourney:
    """Start a new open journey from a validated PICKED_UP event."""
    return OpenJourney(
        tray_id=event.tray_id,
        pickup_event_id=event.event_id,
        client_id=payload.client_id,
        tray_type_id=payload.tray_type_id,
        pickup_ts=event.timestamp_event,
        required_by_ts=payload.required_by_ts,
    )


def stage_apply(open_journey: OpenJourney, event: Event) -> OpenJourney:
    """Record the timestamp of a stage event onto an open journey.

    The ``facility_id`` of the cycle is pinned the first time we see a stage
    event for this tray -- typically DECON_START. CHECKED_IN deliberately
    does not pin it because routing/transport between facilities can land
    a tray at a different site than where it gets processed.
    """
    facility_id = open_journey.facility_id if open_journey.facility_id is not None else event.facility_id
    ts = event.timestamp_event
    et = event.event_type
    if et == EventType.DECON_START:
        return dataclasses.replace(open_journey, facility_id=facility_id, decon_start_ts=ts)
    if et == EventType.DECON_END:
        return dataclasses.replace(open_journey, facility_id=facility_id, decon_end_ts=ts)
    if et == EventType.INSPECTED:
        return dataclasses.replace(open_journey, facility_id=facility_id, inspected_ts=ts)
    if et == EventType.ASSEMBLED:
        return dataclasses.replace(open_journey, facility_id=facility_id, assembled_ts=ts)
    if et == EventType.STERILIZED:
        return dataclasses.replace(open_journey, facility_id=facility_id, sterilized_ts=ts)
    if et == EventType.PACKED:
        return dataclasses.replace(open_journey, facility_id=facility_id, packed_ts=ts)
    return dataclasses.replace(open_journey, facility_id=facility_id, loaded_ts=ts)


def finalize_journey(open_journey: OpenJourney, delivered: Event) -> JourneyRow | None:
    """Close out a journey on DELIVERED. Returns ``None`` if state is incomplete.

    Per-stage dwells are computed from consecutive timestamps. Missing
    intermediate events (vendor data loss, out-of-order delivery) leave the
    journey unfinalized; the open_journey row stays in place for inspection.
    """
    fid = open_journey.facility_id
    ds = open_journey.decon_start_ts
    de = open_journey.decon_end_ts
    ins = open_journey.inspected_ts
    asm = open_journey.assembled_ts
    ster = open_journey.sterilized_ts
    pkd = open_journey.packed_ts
    ld = open_journey.loaded_ts
    if (
        fid is None
        or ds is None
        or de is None
        or ins is None
        or asm is None
        or ster is None
        or pkd is None
        or ld is None
    ):
        return None

    delivered_ts = delivered.timestamp_event
    delay_min = (delivered_ts - open_journey.required_by_ts).total_seconds() / 60.0
    return JourneyRow(
        journey_id=uuid5(JOURNEY_ID_NAMESPACE, str(open_journey.pickup_event_id)),
        tray_id=open_journey.tray_id,
        facility_id=fid,
        tray_type_id=open_journey.tray_type_id,
        client_id=open_journey.client_id,
        pickup_ts=open_journey.pickup_ts,
        required_by_ts=open_journey.required_by_ts,
        decon_dwell_min=(de - ds).total_seconds() / 60.0,
        inspection_dwell_min=(ins - de).total_seconds() / 60.0,
        assembly_dwell_min=(asm - ins).total_seconds() / 60.0,
        sterilization_dwell_min=(ster - asm).total_seconds() / 60.0,
        packout_dwell_min=(pkd - ster).total_seconds() / 60.0,
        transport_min=(delivered_ts - ld).total_seconds() / 60.0,
        delivered_ts=delivered_ts,
        on_time=delivered_ts <= open_journey.required_by_ts,
        delay_min=delay_min,
        hour_of_pickup=open_journey.pickup_ts.hour,
        day_of_week=open_journey.pickup_ts.weekday(),
    )


def apply_event(store: Store, event: Event) -> None:
    """Dispatch an event to the right projection updates.

    Every event refreshes the tray projection. PICKED_UP starts an open
    journey, stage events accumulate timestamps onto it, DELIVERED
    finalizes it. CHECKED_IN and DEFECT_REPORTED only touch the tray.

    Boundary checks (malformed payloads, stage events without a pickup,
    delivered events without a pickup) are skipped silently rather than
    raising -- the consumer must keep making progress on the partition.
    """
    store.upsert_tray(tray_from_event(event))

    if event.event_type == EventType.PICKED_UP:
        payload = parse_picked_up_payload(event.payload)
        if payload is None:
            return
        store.upsert_open_journey(open_journey_init(event, payload))
        return

    if event.event_type in STAGE_EVENT_TYPES:
        existing = store.get_open_journey(event.tray_id)
        if existing is None:
            return
        store.upsert_open_journey(stage_apply(existing, event))
        return

    if event.event_type == EventType.DELIVERED:
        existing = store.get_open_journey(event.tray_id)
        if existing is None:
            return
        journey = finalize_journey(existing, event)
        if journey is None:
            return
        store.insert_journey(journey)
        store.delete_open_journey(event.tray_id)
