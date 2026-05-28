"""Load journey parquet into the feature arrays the model expects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

_DWELL_COLUMNS: tuple[str, ...] = (
    "decon_dwell_min",
    "inspection_dwell_min",
    "assembly_dwell_min",
    "sterilization_dwell_min",
    "packout_dwell_min",
)

# Hours considered "peak" on the reprocessing floor; matches synth-events.
PEAK_HOURS: frozenset[int] = frozenset(range(8, 12)) | frozenset(range(14, 18))


@dataclass(frozen=True)
class JourneyDataset:
    """Vector form of a journey set, ready for PyMC.

    ``facility_ids`` / ``tray_type_ids`` capture the stable category ordering
    that the model's ``facility_idx`` / ``tray_idx`` arrays index into. We
    persist these alongside the posterior so policies can be evaluated for a
    given (facility_id, tray_type_id) at decision time.
    """

    facility_ids: tuple[str, ...]
    tray_type_ids: tuple[str, ...]
    facility_idx: NDArray[np.int32]
    tray_idx: NDArray[np.int32]
    is_peak: NDArray[np.int32]
    total_processing_min: NDArray[np.float64]
    transport_min: NDArray[np.float64]
    delay_min: NDArray[np.float64]
    on_time: NDArray[np.bool_]
    pickup_hours: NDArray[np.int32]


def _read_table(path: Path) -> pa.Table:
    """Typed wrapper around the (untyped) pyarrow.parquet.read_table."""
    read_fn: Any = pq.read_table
    table: pa.Table = read_fn(path)
    return table


def load_journeys(path: Path) -> JourneyDataset:
    """Load a journey parquet file into a JourneyDataset.

    Stage dwells are summed into ``total_processing_min``. The facility and
    tray-type id columns are encoded as integer indices into a stable
    (sorted) category list returned alongside the arrays.
    """
    table = _read_table(path)
    records: list[dict[str, Any]] = table.to_pylist()
    if not records:
        return JourneyDataset(
            facility_ids=(),
            tray_type_ids=(),
            facility_idx=np.array([], dtype=np.int32),
            tray_idx=np.array([], dtype=np.int32),
            is_peak=np.array([], dtype=np.int32),
            total_processing_min=np.array([], dtype=np.float64),
            transport_min=np.array([], dtype=np.float64),
            delay_min=np.array([], dtype=np.float64),
            on_time=np.array([], dtype=bool),
            pickup_hours=np.array([], dtype=np.int32),
        )

    facility_ids = tuple(sorted({str(r["facility_id"]) for r in records}))
    tray_type_ids = tuple(sorted({str(r["tray_type_id"]) for r in records}))
    facility_to_idx = {fid: i for i, fid in enumerate(facility_ids)}
    tray_to_idx = {tid: i for i, tid in enumerate(tray_type_ids)}

    facility_idx = np.array([facility_to_idx[str(r["facility_id"])] for r in records], dtype=np.int32)
    tray_idx = np.array([tray_to_idx[str(r["tray_type_id"])] for r in records], dtype=np.int32)
    pickup_hours = np.array([int(r["hour_of_pickup"]) for r in records], dtype=np.int32)
    is_peak = np.array([1 if h in PEAK_HOURS else 0 for h in pickup_hours], dtype=np.int32)

    total = np.zeros(len(records), dtype=np.float64)
    for col in _DWELL_COLUMNS:
        total += np.array([float(r[col]) for r in records], dtype=np.float64)

    transport_min = np.array([float(r["transport_min"]) for r in records], dtype=np.float64)
    delay_min = np.array([float(r["delay_min"]) for r in records], dtype=np.float64)
    on_time = np.array([bool(r["on_time"]) for r in records], dtype=bool)

    return JourneyDataset(
        facility_ids=facility_ids,
        tray_type_ids=tray_type_ids,
        facility_idx=facility_idx,
        tray_idx=tray_idx,
        is_peak=is_peak,
        total_processing_min=total,
        transport_min=transport_min,
        delay_min=delay_min,
        on_time=on_time,
        pickup_hours=pickup_hours,
    )
