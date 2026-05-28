"""Map a synthetic :class:`Journey` to a sequence of event-stream payloads.

Used by the ``publish`` CLI to drive the projector end-to-end without a
real client adapter. Each journey becomes 10 events whose timestamps are
chosen so the projector's computed per-stage dwells equal the Journey's
dwell fields exactly, and the projector's computed ``delivered_ts`` equals
``journey.delivered_ts``.

Timeline (all derived from ``journey.pickup_ts``):

* PICKED_UP, CHECKED_IN, DECON_START collapse onto ``pickup_ts``.
* DECON_END = pickup_ts + decon_dwell_min.
* INSPECTED  = DECON_END + inspection_dwell_min.
* ASSEMBLED  = INSPECTED + assembly_dwell_min.
* STERILIZED = ASSEMBLED + sterilization_dwell_min.
* PACKED     = STERILIZED + packout_dwell_min.
* LOADED     = PACKED (collapsed; no separate loading dwell in this model).
* DELIVERED  = LOADED + transport_min = ``journey.delivered_ts``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from synth_events.journey import Journey


def journey_to_events(journey: Journey) -> list[dict[str, Any]]:
    """Return the 10 event payloads for one journey, in publish order.

    Parameters
    ----------
    journey : Journey
        The synthetic journey to project into an event stream.

    Returns
    -------
    list[dict[str, Any]]
        Ten event payload dicts in the shape ingest's ``POST /events``
        expects, in PICKED_UP -> DELIVERED order.
    """
    ts0 = journey.pickup_ts
    ts_decon_end = ts0 + timedelta(minutes=journey.decon_dwell_min)
    ts_inspected = ts_decon_end + timedelta(minutes=journey.inspection_dwell_min)
    ts_assembled = ts_inspected + timedelta(minutes=journey.assembly_dwell_min)
    ts_sterilized = ts_assembled + timedelta(minutes=journey.sterilization_dwell_min)
    ts_packed = ts_sterilized + timedelta(minutes=journey.packout_dwell_min)
    ts_delivered = ts_packed + timedelta(minutes=journey.transport_min)

    pickup_payload = {
        "client_id": journey.client_id,
        "tray_type_id": journey.tray_type_id,
        "required_by_ts": journey.required_by_ts.isoformat(),
    }

    def _event(idx: int, etype: str, facility_id: str, ts: Any, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_system": "SYNTH_PUBLISH",
            "source_event_id": f"{journey.tray_id}-{idx:02d}",
            "tray_id": journey.tray_id,
            "facility_id": facility_id,
            "event_type": etype,
            "timestamp_event": ts.isoformat(),
            "payload": payload,
        }

    return [
        _event(0, "PICKED_UP", journey.client_id, ts0, pickup_payload),
        _event(1, "CHECKED_IN", journey.facility_id, ts0, {}),
        _event(2, "DECON_START", journey.facility_id, ts0, {}),
        _event(3, "DECON_END", journey.facility_id, ts_decon_end, {}),
        _event(4, "INSPECTED", journey.facility_id, ts_inspected, {}),
        _event(5, "ASSEMBLED", journey.facility_id, ts_assembled, {}),
        _event(6, "STERILIZED", journey.facility_id, ts_sterilized, {}),
        _event(7, "PACKED", journey.facility_id, ts_packed, {}),
        _event(8, "LOADED", journey.facility_id, ts_packed, {}),
        _event(9, "DELIVERED", journey.client_id, ts_delivered, {}),
    ]
