"""Tests for the parquet writer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from synth_events.journey import simulate_journey
from synth_events.parameters import FACILITIES, TRAY_TYPES
from synth_events.parquet import SCHEMA, write_journeys_parquet
from synth_events.schedule import Pickup


def _journeys(n: int) -> list:
    rng = np.random.default_rng(101)
    pickup = Pickup(
        pickup_ts=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        required_by_ts=datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc),
        client_id="HOSPITAL_A",
        facility=FACILITIES[0],
        tray_type=TRAY_TYPES[0],
    )
    return [simulate_journey(rng, pickup) for _ in range(n)]


def test_write_and_read_round_trip(tmp_path: Path) -> None:
    journeys = _journeys(20)
    out = tmp_path / "j.parquet"
    write_journeys_parquet(journeys, out)
    assert out.is_file()

    table = pq.read_table(out)
    assert table.num_rows == 20
    assert table.schema.equals(SCHEMA)


def test_round_trip_preserves_values(tmp_path: Path) -> None:
    journeys = _journeys(5)
    out = tmp_path / "j.parquet"
    write_journeys_parquet(journeys, out)
    table = pq.read_table(out).to_pylist()
    for original, restored in zip(journeys, table, strict=True):
        assert restored["journey_id"] == str(original.journey_id)
        assert restored["facility_id"] == original.facility_id
        assert restored["decon_dwell_min"] == original.decon_dwell_min
        assert restored["on_time"] == original.on_time
