"""Read-only views over the projector's Postgres tables.

These power the dashboard's Operations tab. They open a fresh connection
per request (no pool). For dashboard polling traffic that's fine; if the
service ever fronts higher throughput, switch to ``psycopg.ConnectionPool``.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
from uuid import UUID

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from pydantic import BaseModel


class TrayStateView(BaseModel):
    """Current state of one tray."""

    tray_id: str
    current_facility_id: str
    current_stage: str
    last_event_ts: datetime
    last_updated: datetime


class TrayStatesResponse(BaseModel):
    """Wrapper around a list of tray current-state rows."""

    trays: list[TrayStateView]


class JourneyView(BaseModel):
    """One finalized pickup-to-delivery cycle."""

    journey_id: UUID
    tray_id: str
    facility_id: str
    tray_type_id: str
    client_id: str
    pickup_ts: datetime
    required_by_ts: datetime
    delivered_ts: datetime
    on_time: bool
    delay_min: float
    decon_dwell_min: float
    inspection_dwell_min: float
    assembly_dwell_min: float
    sterilization_dwell_min: float
    packout_dwell_min: float
    transport_min: float


class RecentJourneysResponse(BaseModel):
    """Wrapper around a list of finalized journey rows."""

    journeys: list[JourneyView]


@contextmanager
def _conn(dsn: str) -> Iterator[psycopg.Connection[Any]]:
    """Yield an open Postgres connection; close it on exit.

    Raises an HTTP 503 if Postgres is unreachable so the FastAPI handler
    surfaces a recoverable error instead of bubbling raw psycopg exceptions.
    psycopg's Connection is itself a context manager that closes on exit,
    so no explicit ``.close()`` call is needed.
    """
    try:
        with psycopg.connect(dsn) as connection:
            yield connection
    except psycopg.OperationalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"projector Postgres unreachable: {exc}",
        ) from exc


def fetch_tray_states(dsn: str, limit: int) -> TrayStatesResponse:
    """Return the ``limit`` most recently updated tray rows."""
    with _conn(dsn) as connection, connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT tray_id, current_facility_id, current_stage, last_event_ts, last_updated
            FROM tray
            ORDER BY last_updated DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return TrayStatesResponse(trays=[TrayStateView(**row) for row in rows])


def fetch_recent_journeys(dsn: str, limit: int) -> RecentJourneysResponse:
    """Return the ``limit`` most recently delivered journeys."""
    with _conn(dsn) as connection, connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT journey_id, tray_id, facility_id, tray_type_id, client_id,
                   pickup_ts, required_by_ts, delivered_ts, on_time, delay_min,
                   decon_dwell_min, inspection_dwell_min, assembly_dwell_min,
                   sterilization_dwell_min, packout_dwell_min, transport_min
            FROM journey
            ORDER BY delivered_ts DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return RecentJourneysResponse(journeys=[JourneyView(**row) for row in rows])
