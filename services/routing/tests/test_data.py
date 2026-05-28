"""Tests for the data loading + feature extraction."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from routing.data import PEAK_HOURS, load_journeys


def test_load_journeys_builds_feature_arrays(sample_parquet_path: Path) -> None:
    dataset = load_journeys(sample_parquet_path)
    assert dataset.facility_ids == ("BOCA", "ELM", "LGB")
    assert dataset.tray_type_ids == ("TRAY-KNEE", "TRAY-LAPS")
    assert dataset.facility_idx.shape == (12,)
    assert dataset.tray_idx.shape == (12,)
    assert dataset.is_peak.shape == (12,)
    # Each journey: 15+20+30+90+10 = 165 minutes
    assert np.allclose(dataset.total_processing_min, 165.0)
    # Transport: 30 min for all
    assert np.allclose(dataset.transport_min, 30.0)


def test_peak_hour_flag_matches_definition(sample_parquet_path: Path) -> None:
    dataset = load_journeys(sample_parquet_path)
    for hour, peak in zip(dataset.pickup_hours, dataset.is_peak, strict=True):
        assert peak == (1 if int(hour) in PEAK_HOURS else 0)


def test_facility_indices_are_consistent(sample_parquet_path: Path) -> None:
    """facility_idx[i] should point to the correct facility_id in the mapping."""
    dataset = load_journeys(sample_parquet_path)
    table = pq.read_table(sample_parquet_path).to_pylist()
    for i, row in enumerate(table):
        assert dataset.facility_ids[dataset.facility_idx[i]] == row["facility_id"]
        assert dataset.tray_type_ids[dataset.tray_idx[i]] == row["tray_type_id"]


def test_load_journeys_empty_table(tmp_path: Path) -> None:
    """Loading an empty parquet returns empty arrays + empty category tuples."""
    fields: list[tuple[str, pa.DataType]] = [
        ("journey_id", pa.string()),
        ("facility_id", pa.string()),
        ("tray_id", pa.string()),
        ("tray_type_id", pa.string()),
        ("client_id", pa.string()),
        ("pickup_ts", pa.timestamp("us")),
        ("required_by_ts", pa.timestamp("us")),
        ("decon_dwell_min", pa.float64()),
        ("inspection_dwell_min", pa.float64()),
        ("assembly_dwell_min", pa.float64()),
        ("sterilization_dwell_min", pa.float64()),
        ("packout_dwell_min", pa.float64()),
        ("transport_min", pa.float64()),
        ("delivered_ts", pa.timestamp("us")),
        ("on_time", pa.bool_()),
        ("delay_min", pa.float64()),
        ("hour_of_pickup", pa.int32()),
        ("day_of_week", pa.int32()),
    ]
    schema = pa.schema(fields)
    out = tmp_path / "empty.parquet"
    pq.write_table(pa.Table.from_pylist([], schema=schema), out)

    dataset = load_journeys(out)
    assert not dataset.facility_ids
    assert not dataset.tray_type_ids
    assert dataset.facility_idx.size == 0
    assert dataset.total_processing_min.size == 0
