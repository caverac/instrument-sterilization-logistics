"""Postgres-backed implementation of :class:`projector.store.Store`."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from projector.projections import JourneyRow, OpenJourney, TrayState

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS tray (
    tray_id            TEXT        PRIMARY KEY,
    current_facility_id TEXT       NOT NULL,
    current_stage      TEXT        NOT NULL,
    last_event_id      UUID        NOT NULL,
    last_event_ts      TIMESTAMPTZ NOT NULL,
    last_updated       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS journey_open (
    tray_id          TEXT        PRIMARY KEY,
    pickup_event_id  UUID        NOT NULL,
    client_id        TEXT        NOT NULL,
    tray_type_id     TEXT        NOT NULL,
    pickup_ts        TIMESTAMPTZ NOT NULL,
    required_by_ts   TIMESTAMPTZ NOT NULL,
    facility_id      TEXT,
    decon_start_ts   TIMESTAMPTZ,
    decon_end_ts     TIMESTAMPTZ,
    inspected_ts     TIMESTAMPTZ,
    assembled_ts     TIMESTAMPTZ,
    sterilized_ts    TIMESTAMPTZ,
    packed_ts        TIMESTAMPTZ,
    loaded_ts        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS journey (
    journey_id              UUID        PRIMARY KEY,
    tray_id                 TEXT        NOT NULL,
    facility_id             TEXT        NOT NULL,
    tray_type_id            TEXT        NOT NULL,
    client_id               TEXT        NOT NULL,
    pickup_ts               TIMESTAMPTZ NOT NULL,
    required_by_ts          TIMESTAMPTZ NOT NULL,
    decon_dwell_min         DOUBLE PRECISION NOT NULL,
    inspection_dwell_min    DOUBLE PRECISION NOT NULL,
    assembly_dwell_min      DOUBLE PRECISION NOT NULL,
    sterilization_dwell_min DOUBLE PRECISION NOT NULL,
    packout_dwell_min       DOUBLE PRECISION NOT NULL,
    transport_min           DOUBLE PRECISION NOT NULL,
    delivered_ts            TIMESTAMPTZ NOT NULL,
    on_time                 BOOLEAN     NOT NULL,
    delay_min               DOUBLE PRECISION NOT NULL,
    hour_of_pickup          INTEGER     NOT NULL,
    day_of_week             INTEGER     NOT NULL
);

CREATE INDEX IF NOT EXISTS journey_facility_pickup_idx ON journey (facility_id, pickup_ts);
CREATE INDEX IF NOT EXISTS journey_tray_idx           ON journey (tray_id);
"""


_OPEN_JOURNEY_COLS = (
    "tray_id, pickup_event_id, client_id, tray_type_id, pickup_ts, required_by_ts, "
    "facility_id, decon_start_ts, decon_end_ts, inspected_ts, assembled_ts, "
    "sterilized_ts, packed_ts, loaded_ts"
)


def init_schema(conn: psycopg.Connection[Any]) -> None:
    """Create the projector's tables if they do not exist.

    Idempotent: safe to call on every startup. Uses ``CREATE TABLE IF NOT
    EXISTS`` so existing data is untouched.
    """
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()


class PgStore:
    """Postgres implementation of :class:`projector.store.Store`.

    Each method runs in the caller's transaction context. The consumer loop
    wraps event handling in a transaction and commits Kafka offsets only
    after Postgres commits, so an event is never marked consumed without
    its projection landing.
    """

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        """Wrap an already-open psycopg connection."""
        self._conn = conn

    def upsert_tray(self, tray: TrayState) -> None:
        """Insert or overwrite a tray row."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tray (tray_id, current_facility_id, current_stage,
                                  last_event_id, last_event_ts, last_updated)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (tray_id) DO UPDATE SET
                    current_facility_id = EXCLUDED.current_facility_id,
                    current_stage       = EXCLUDED.current_stage,
                    last_event_id       = EXCLUDED.last_event_id,
                    last_event_ts       = EXCLUDED.last_event_ts,
                    last_updated        = NOW()
                """,
                (
                    tray.tray_id,
                    tray.current_facility_id,
                    tray.current_stage,
                    tray.last_event_id,
                    tray.last_event_ts,
                ),
            )

    def get_open_journey(self, tray_id: str) -> OpenJourney | None:
        """Return the in-flight journey for a tray, or ``None``."""
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT {_OPEN_JOURNEY_COLS} FROM journey_open WHERE tray_id = %s",
                (tray_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return OpenJourney(**row)

    def upsert_open_journey(self, journey: OpenJourney) -> None:
        """Insert or overwrite an in-flight journey row."""
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO journey_open ({_OPEN_JOURNEY_COLS})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tray_id) DO UPDATE SET
                    pickup_event_id = EXCLUDED.pickup_event_id,
                    client_id       = EXCLUDED.client_id,
                    tray_type_id    = EXCLUDED.tray_type_id,
                    pickup_ts       = EXCLUDED.pickup_ts,
                    required_by_ts  = EXCLUDED.required_by_ts,
                    facility_id     = EXCLUDED.facility_id,
                    decon_start_ts  = EXCLUDED.decon_start_ts,
                    decon_end_ts    = EXCLUDED.decon_end_ts,
                    inspected_ts    = EXCLUDED.inspected_ts,
                    assembled_ts    = EXCLUDED.assembled_ts,
                    sterilized_ts   = EXCLUDED.sterilized_ts,
                    packed_ts       = EXCLUDED.packed_ts,
                    loaded_ts       = EXCLUDED.loaded_ts
                """,
                (
                    journey.tray_id,
                    journey.pickup_event_id,
                    journey.client_id,
                    journey.tray_type_id,
                    journey.pickup_ts,
                    journey.required_by_ts,
                    journey.facility_id,
                    journey.decon_start_ts,
                    journey.decon_end_ts,
                    journey.inspected_ts,
                    journey.assembled_ts,
                    journey.sterilized_ts,
                    journey.packed_ts,
                    journey.loaded_ts,
                ),
            )

    def delete_open_journey(self, tray_id: str) -> None:
        """Drop the in-flight journey for a tray, if present."""
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM journey_open WHERE tray_id = %s", (tray_id,))

    def insert_journey(self, journey: JourneyRow) -> None:
        """Append a finalized journey row. Idempotent on ``journey_id``."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO journey (
                    journey_id, tray_id, facility_id, tray_type_id, client_id,
                    pickup_ts, required_by_ts,
                    decon_dwell_min, inspection_dwell_min, assembly_dwell_min,
                    sterilization_dwell_min, packout_dwell_min, transport_min,
                    delivered_ts, on_time, delay_min, hour_of_pickup, day_of_week
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s)
                ON CONFLICT (journey_id) DO NOTHING
                """,
                (
                    journey.journey_id,
                    journey.tray_id,
                    journey.facility_id,
                    journey.tray_type_id,
                    journey.client_id,
                    journey.pickup_ts,
                    journey.required_by_ts,
                    journey.decon_dwell_min,
                    journey.inspection_dwell_min,
                    journey.assembly_dwell_min,
                    journey.sterilization_dwell_min,
                    journey.packout_dwell_min,
                    journey.transport_min,
                    journey.delivered_ts,
                    journey.on_time,
                    journey.delay_min,
                    journey.hour_of_pickup,
                    journey.day_of_week,
                ),
            )
