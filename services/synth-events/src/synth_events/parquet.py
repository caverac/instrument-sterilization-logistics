"""Parquet writer for journey rows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from synth_events.journey import Journey

_TIMESTAMP_TYPE = pa.timestamp("us", tz="UTC")

SCHEMA = pa.schema(
    [
        pa.field("journey_id", pa.string()),
        pa.field("facility_id", pa.string()),
        pa.field("tray_id", pa.string()),
        pa.field("tray_type_id", pa.string()),
        pa.field("client_id", pa.string()),
        pa.field("pickup_ts", _TIMESTAMP_TYPE),
        pa.field("required_by_ts", _TIMESTAMP_TYPE),
        pa.field("decon_dwell_min", pa.float64()),
        pa.field("inspection_dwell_min", pa.float64()),
        pa.field("assembly_dwell_min", pa.float64()),
        pa.field("sterilization_dwell_min", pa.float64()),
        pa.field("packout_dwell_min", pa.float64()),
        pa.field("transport_min", pa.float64()),
        pa.field("delivered_ts", _TIMESTAMP_TYPE),
        pa.field("on_time", pa.bool_()),
        pa.field("delay_min", pa.float64()),
        pa.field("hour_of_pickup", pa.int32()),
        pa.field("day_of_week", pa.int32()),
    ]
)


def write_journeys_parquet(journeys: Iterable[Journey], out: Path) -> None:
    """Write journeys to a parquet file at ``out``.

    Parameters
    ----------
    journeys : Iterable[Journey]
        Journeys to serialize.
    out : Path
        Output file path. Parent directory must exist.
    """
    records = [j.to_record() for j in journeys]
    table = pa.Table.from_pylist(records, schema=SCHEMA)
    pq.write_table(table, out)
