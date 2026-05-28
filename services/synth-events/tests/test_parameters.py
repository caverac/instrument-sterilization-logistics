"""Tests for the static parameter tables."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from synth_events.parameters import (
    BASE_STAGE_TOTAL_MIN,
    CLIENTS,
    DEADLINE_MEAN_MIN,
    DEADLINE_SIGMA,
    FACILITIES,
    PEAK_HOUR_OFFSET_MIN,
    PEAK_HOURS,
    STAGES,
    TRANSPORT_MEAN_MIN,
    TRANSPORT_SIGMA,
    TRAY_TYPES,
    Facility,
    Stage,
    TrayType,
)


def test_stages_total_matches_base_constant() -> None:
    assert sum(s.mean_min for s in STAGES) == BASE_STAGE_TOTAL_MIN


def test_facilities_have_distinct_variance_profiles() -> None:
    by_id = {f.facility_id: f for f in FACILITIES}
    assert by_id["BOCA"].sigma_multiplier > by_id["LGB"].sigma_multiplier > by_id["ELM"].sigma_multiplier
    assert by_id["BOCA"].mu_offset_min < by_id["LGB"].mu_offset_min < by_id["ELM"].mu_offset_min


def test_tray_complexity_multipliers_span_a_useful_range() -> None:
    multipliers = sorted(t.complexity_multiplier for t in TRAY_TYPES)
    assert multipliers[0] < 1.0 < multipliers[-1]


def test_dataclasses_are_frozen() -> None:
    stage = Stage("x", 1.0, 0.1)
    facility = Facility("X", 0.0, 1.0)
    tray = TrayType("X", "x", 1.0)
    for obj, attr in [(stage, "name"), (facility, "facility_id"), (tray, "tray_type_id")]:
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, "mutated")


def test_constants_have_sensible_values() -> None:
    assert PEAK_HOURS == frozenset(range(8, 12)) | frozenset(range(14, 18))
    assert PEAK_HOUR_OFFSET_MIN > 0
    assert TRANSPORT_MEAN_MIN > 0
    assert TRANSPORT_SIGMA > 0
    assert DEADLINE_MEAN_MIN > BASE_STAGE_TOTAL_MIN
    assert DEADLINE_SIGMA > 0
    assert len(CLIENTS) >= 2
