"""Distribution parameters for synthetic journey generation.

Each per-stage dwell time is log-normal. Per-facility we shift the total
expected time and scale the sigma so that the three facilities have
different (mean, variance) trade-offs -- the property variance-aware
routing exploits in the modeling work that consumes this data.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    """Per-stage nominal mean (minutes) and log-space sigma."""

    name: str
    mean_min: float
    sigma: float


@dataclass(frozen=True)
class Facility:
    """Per-facility offsets on the journey distribution."""

    facility_id: str
    mu_offset_min: float
    sigma_multiplier: float


@dataclass(frozen=True)
class TrayType:
    """Tray complexity expressed as a multiplicative shift on total mean."""

    tray_type_id: str
    name: str
    complexity_multiplier: float


STAGES: tuple[Stage, ...] = (
    Stage("decon", 15.0, 0.25),
    Stage("inspection", 20.0, 0.25),
    Stage("assembly", 30.0, 0.30),
    Stage("sterilization", 90.0, 0.15),
    Stage("packout", 10.0, 0.25),
)

FACILITIES: tuple[Facility, ...] = (
    Facility("BOCA", mu_offset_min=-10.0, sigma_multiplier=1.5),
    Facility("LGB", mu_offset_min=0.0, sigma_multiplier=1.0),
    Facility("ELM", mu_offset_min=20.0, sigma_multiplier=0.5),
)

TRAY_TYPES: tuple[TrayType, ...] = (
    TrayType("TRAY-SMALL", "Small instrument tray", 0.75),
    TrayType("TRAY-KNEE", "Knee arthroscopy", 1.00),
    TrayType("TRAY-LAPS", "Laparoscopic", 1.10),
    TrayType("TRAY-CARDIO", "Cardiac major", 1.40),
    TrayType("TRAY-SPINE", "Spine instrumentation", 1.60),
)

CLIENTS: tuple[str, ...] = ("HOSPITAL_A", "HOSPITAL_B", "HOSPITAL_C", "ASC_X", "ASC_Y")

# Reprocessing-floor "busy hours" -- pickups arriving in these hours
# experience additional queueing delay.
PEAK_HOURS: frozenset[int] = frozenset(range(8, 12)) | frozenset(range(14, 18))
PEAK_HOUR_OFFSET_MIN: float = 15.0

# One-way return transport (facility back to client), log-normal in minutes.
TRANSPORT_MEAN_MIN: float = 30.0
TRANSPORT_SIGMA: float = 0.30

# Deadline slack from pickup: required_by_ts - pickup_ts, log-normal in minutes.
# Chosen so a meaningful fraction of journeys are at risk -- otherwise routing
# has no problem to solve.
DEADLINE_MEAN_MIN: float = 220.0
DEADLINE_SIGMA: float = 0.20

# Sum of all stage nominal means; used as the journey-mean baseline.
BASE_STAGE_TOTAL_MIN: float = sum(s.mean_min for s in STAGES)
