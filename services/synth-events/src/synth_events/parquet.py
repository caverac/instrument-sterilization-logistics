"""Parquet I/O for journey rows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from synth_events.journey import Journey

_TIMESTAMP_TYPE = pa.timestamp("us", tz="UTC")

# Explicit `list[tuple[str, pa.DataType]]` annotation because the
# concrete return types of pa.string() / pa.int32() / pa.bool_() etc.
# are different DataType subclasses; mypy unifies them to `object`
# without an annotation, which then fails to match pa.schema's overloads.
_FIELDS: list[tuple[str, pa.DataType]] = [
    ("journey_id", pa.string()),
    ("facility_id", pa.string()),
    ("tray_id", pa.string()),
    ("tray_type_id", pa.string()),
    ("client_id", pa.string()),
    ("pickup_ts", _TIMESTAMP_TYPE),
    ("required_by_ts", _TIMESTAMP_TYPE),
    ("decon_dwell_min", pa.float64()),
    ("inspection_dwell_min", pa.float64()),
    ("assembly_dwell_min", pa.float64()),
    ("sterilization_dwell_min", pa.float64()),
    ("packout_dwell_min", pa.float64()),
    ("transport_min", pa.float64()),
    ("delivered_ts", _TIMESTAMP_TYPE),
    ("on_time", pa.bool_()),
    ("delay_min", pa.float64()),
    ("hour_of_pickup", pa.int32()),
    ("day_of_week", pa.int32()),
]

SCHEMA = pa.schema(_FIELDS)


# pyarrow-stubs doesn't annotate pq.read_table / pq.write_table, so we
# isolate the calls behind typed wrappers here rather than scattering
# untyped pyarrow calls (and the casts they require) across tests and
# CLI code.


def _write_table(table: pa.Table, where: Path) -> None:
    """Typed wrapper for ``pyarrow.parquet.write_table``."""
    write_fn: Any = pq.write_table
    write_fn(table, where)


def _read_table(path: Path) -> pa.Table:
    """Typed wrapper for ``pyarrow.parquet.read_table``."""
    read_fn: Any = pq.read_table
    table: pa.Table = read_fn(path)
    return table


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
    _write_table(table, out)


def read_journeys_table(path: Path) -> pa.Table:
    """Read a journeys parquet file as a pyarrow Table.

    Parameters
    ----------
    path : Path
        Source parquet file.

    Returns
    -------
    pa.Table
        The full table including schema and row count.
    """
    return _read_table(path)


def read_journeys_records(path: Path) -> list[dict[str, Any]]:
    """Read a journeys parquet file as a list of record dicts.

    Parameters
    ----------
    path : Path
        Source parquet file.

    Returns
    -------
    list[dict[str, Any]]
        One dict per row, keyed by column name.
    """
    table = _read_table(path)
    records: list[dict[str, Any]] = table.to_pylist()
    return records
