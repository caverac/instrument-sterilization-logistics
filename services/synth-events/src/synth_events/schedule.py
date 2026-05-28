"""Pickup-arrival schedule generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from synth_events.parameters import (
    CLIENTS,
    DEADLINE_MEAN_MIN,
    DEADLINE_SIGMA,
    FACILITIES,
    TRAY_TYPES,
    Facility,
    TrayType,
)


@dataclass(frozen=True)
class Pickup:
    """A scheduled pickup: when, where from, what tray, by when."""

    pickup_ts: datetime
    required_by_ts: datetime
    client_id: str
    facility: Facility
    tray_type: TrayType


def generate_pickups(
    rng: np.random.Generator,
    n: int,
    start: datetime,
    end: datetime,
) -> list[Pickup]:
    """Generate ``n`` pickups uniformly across the time range.

    Each pickup gets a random facility, tray type, client, and a deadline
    sampled from a log-normal around DEADLINE_MEAN_MIN after the pickup
    time. Uniformity across hours is intentional -- it gives the model
    training data at all hours so the hour-of-day effect can be learned.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded RNG.
    n : int
        Number of pickups to generate.
    start, end : datetime
        Time range (timezone-aware). ``end`` is exclusive.

    Returns
    -------
    list[Pickup]
        ``n`` pickups in random order.
    """
    duration_sec = (end - start).total_seconds()
    deadline_mu = float(np.log(DEADLINE_MEAN_MIN)) - 0.5 * DEADLINE_SIGMA * DEADLINE_SIGMA
    pickups: list[Pickup] = []
    for _ in range(n):
        offset_sec = float(rng.uniform(0.0, duration_sec))
        pickup_ts = start + timedelta(seconds=offset_sec)
        deadline_min = float(rng.lognormal(deadline_mu, DEADLINE_SIGMA))
        required_by_ts = pickup_ts + timedelta(minutes=deadline_min)
        facility = FACILITIES[int(rng.integers(0, len(FACILITIES)))]
        tray_type = TRAY_TYPES[int(rng.integers(0, len(TRAY_TYPES)))]
        client_id = CLIENTS[int(rng.integers(0, len(CLIENTS)))]
        pickups.append(
            Pickup(
                pickup_ts=pickup_ts,
                required_by_ts=required_by_ts,
                client_id=client_id,
                facility=facility,
                tray_type=tray_type,
            )
        )
    return pickups
