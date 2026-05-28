"""Journey dataclass and simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import numpy as np

from synth_events.schedule import Pickup
from synth_events.simulate import sample_stage_dwells, sample_transport_min


@dataclass(frozen=True)
class Journey:
    """One tray's pickup-to-return cycle, ready to write as a parquet row."""

    journey_id: UUID
    facility_id: str
    tray_id: str
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

    def to_record(self) -> dict[str, Any]:
        """Return a flat-dict representation suitable for parquet writing."""
        return {
            "journey_id": str(self.journey_id),
            "facility_id": self.facility_id,
            "tray_id": self.tray_id,
            "tray_type_id": self.tray_type_id,
            "client_id": self.client_id,
            "pickup_ts": self.pickup_ts,
            "required_by_ts": self.required_by_ts,
            "decon_dwell_min": self.decon_dwell_min,
            "inspection_dwell_min": self.inspection_dwell_min,
            "assembly_dwell_min": self.assembly_dwell_min,
            "sterilization_dwell_min": self.sterilization_dwell_min,
            "packout_dwell_min": self.packout_dwell_min,
            "transport_min": self.transport_min,
            "delivered_ts": self.delivered_ts,
            "on_time": self.on_time,
            "delay_min": self.delay_min,
            "hour_of_pickup": self.hour_of_pickup,
            "day_of_week": self.day_of_week,
        }


def rng_uuid(rng: np.random.Generator) -> UUID:
    """Draw a UUID worth of bits from the RNG (deterministic given seed)."""
    parts = rng.integers(0, 1 << 32, size=4, dtype=np.uint32)
    as_int = (int(parts[0]) << 96) | (int(parts[1]) << 64) | (int(parts[2]) << 32) | int(parts[3])
    return UUID(int=as_int)


def simulate_journey(rng: np.random.Generator, pickup: Pickup) -> Journey:
    """Simulate a journey for one pickup."""
    hour = pickup.pickup_ts.hour
    dwells = sample_stage_dwells(rng, pickup.facility, pickup.tray_type, hour)
    transport = sample_transport_min(rng)
    total_min = sum(dwells.values()) + transport
    delivered_ts = pickup.pickup_ts + timedelta(minutes=total_min)
    delay_min = (delivered_ts - pickup.required_by_ts).total_seconds() / 60.0
    journey_id = rng_uuid(rng)
    tray_id = f"TRAY-{rng_uuid(rng).hex[:8]}"
    return Journey(
        journey_id=journey_id,
        facility_id=pickup.facility.facility_id,
        tray_id=tray_id,
        tray_type_id=pickup.tray_type.tray_type_id,
        client_id=pickup.client_id,
        pickup_ts=pickup.pickup_ts,
        required_by_ts=pickup.required_by_ts,
        decon_dwell_min=dwells["decon"],
        inspection_dwell_min=dwells["inspection"],
        assembly_dwell_min=dwells["assembly"],
        sterilization_dwell_min=dwells["sterilization"],
        packout_dwell_min=dwells["packout"],
        transport_min=transport,
        delivered_ts=delivered_ts,
        on_time=delay_min <= 0,
        delay_min=delay_min,
        hour_of_pickup=hour,
        day_of_week=pickup.pickup_ts.weekday(),
    )
