"""End-to-end integration: Kafka -> projector -> Postgres.

Run with the dev stack up::

    make dev-up
    uv run pytest services/projector -m slow

Each test uses a unique tray_id so prior topic contents do not interfere,
and a unique consumer group so each run reads from offset zero. Events are
produced directly via ``confluent_kafka.Producer`` rather than POSTed
through the ingest service, so this test exercises only the projector's
Kafka-to-Postgres path; ingest has its own integration test.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg
import pytest
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

from projector.config import Settings
from projector.consumer import consume_one, make_consumer, make_deserializer
from projector.events import Event, EventType
from projector.pg_store import PgStore, init_schema
from projector.projections import JourneyRow, apply_event

pytestmark = pytest.mark.slow

# JSON Schema mirroring what ``services/ingest`` registers under
# ``events-value``. Replicated here so this test does not have a runtime
# dependency on the ingest package. If ingest's schema evolves, this needs
# to evolve in lockstep.
EVENT_SCHEMA_STR = json.dumps(
    {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Event",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string", "format": "uuid"},
            "source_system": {"type": "string", "minLength": 1, "maxLength": 64},
            "source_event_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "tray_id": {"type": "string", "minLength": 1, "maxLength": 64},
            "facility_id": {"type": "string", "minLength": 1, "maxLength": 64},
            "event_type": {"type": "string"},
            "operator_id": {"type": ["string", "null"]},
            "timestamp_event": {"type": "string", "format": "date-time"},
            "timestamp_ingest": {"type": "string", "format": "date-time"},
            "payload": {"type": "object"},
            "schema_version": {"type": "integer", "minimum": 1},
        },
        "required": [
            "event_id",
            "source_system",
            "source_event_id",
            "tray_id",
            "facility_id",
            "event_type",
            "timestamp_event",
            "timestamp_ingest",
            "schema_version",
        ],
    }
)


def _settings() -> Settings:
    return Settings()


@pytest.fixture
def db_conn() -> Iterator[psycopg.Connection[Any]]:
    """Yield a Postgres connection with schema initialised."""
    cfg = _settings()
    conn = psycopg.connect(cfg.postgres_dsn)
    init_schema(conn)
    yield conn
    conn.close()


def _produce_event(
    producer: Producer,
    serializer: JSONSerializer,
    topic: str,
    event: dict[str, Any],
) -> None:
    ctx = SerializationContext(topic, MessageField.VALUE)
    value = serializer(event, ctx)
    producer.produce(topic=topic, key=event["tray_id"].encode("utf-8"), value=value)
    producer.poll(0)


def _full_event_sequence(tray_id: str, suffix: str) -> list[dict[str, Any]]:
    """Ten event dicts forming a complete journey for one tray."""
    pickup = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)
    now_ingest = datetime.now(timezone.utc).isoformat()
    schedule = [
        (
            EventType.PICKED_UP,
            "HOSPITAL_A",
            pickup,
            {
                "client_id": "HOSPITAL_A",
                "tray_type_id": "TRAY-KNEE",
                "required_by_ts": "2026-05-27T13:00:00+00:00",
            },
        ),
        (EventType.CHECKED_IN, "BOCA", pickup.replace(minute=30), {}),
        (EventType.DECON_START, "BOCA", pickup.replace(minute=45), {}),
        (EventType.DECON_END, "BOCA", pickup.replace(hour=9, minute=5), {}),
        (EventType.INSPECTED, "BOCA", pickup.replace(hour=9, minute=25), {}),
        (EventType.ASSEMBLED, "BOCA", pickup.replace(hour=9, minute=50), {}),
        (EventType.STERILIZED, "BOCA", pickup.replace(hour=10, minute=30), {}),
        (EventType.PACKED, "BOCA", pickup.replace(hour=10, minute=45), {}),
        (EventType.LOADED, "BOCA", pickup.replace(hour=11), {}),
        (EventType.DELIVERED, "HOSPITAL_A", pickup.replace(hour=11, minute=30), {}),
    ]
    return [
        {
            "event_id": str(uuid.uuid4()),
            "source_system": "PROJECTOR_INT_TEST",
            "source_event_id": f"{suffix}-{i:02d}",
            "tray_id": tray_id,
            "facility_id": fid,
            "event_type": et.value,
            "operator_id": None,
            "timestamp_event": ts.isoformat(),
            "timestamp_ingest": now_ingest,
            "payload": payload,
            "schema_version": 1,
        }
        for i, (et, fid, ts, payload) in enumerate(schedule)
    ]


def test_full_journey_lands_in_postgres(db_conn: psycopg.Connection[Any]) -> None:
    """End-to-end: 10 produced events land one journey row + one tray row."""
    cfg = _settings()
    suffix = uuid.uuid4().hex
    tray_id = f"TRAY-INT-{suffix}"

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM journey WHERE tray_id = %s", (tray_id,))
        cur.execute("DELETE FROM journey_open WHERE tray_id = %s", (tray_id,))
        cur.execute("DELETE FROM tray WHERE tray_id = %s", (tray_id,))
    db_conn.commit()

    producer = Producer({"bootstrap.servers": cfg.kafka_brokers, "enable.idempotence": True, "acks": "all"})
    sr_client = SchemaRegistryClient({"url": cfg.schema_registry_url})
    serializer = JSONSerializer(EVENT_SCHEMA_STR, sr_client)
    for body in _full_event_sequence(tray_id, suffix):
        _produce_event(producer, serializer, cfg.kafka_topic, body)
    producer.flush(timeout=5.0)

    consumer = make_consumer(cfg.kafka_brokers, f"projector-int-{time.time_ns()}")
    consumer.subscribe([cfg.kafka_topic])
    deserializer = make_deserializer(cfg.schema_registry_url)
    store = PgStore(db_conn)

    def handle(event: Event) -> None:
        if event.tray_id != tray_id:
            return
        with db_conn.transaction():
            apply_event(store, event)

    deadline = time.time() + 30.0
    try:
        while time.time() < deadline:
            consume_one(consumer, deserializer, cfg.kafka_topic, 1.0, handle)
            with db_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM journey WHERE tray_id = %s", (tray_id,))
                fetched = cur.fetchone()
            count = fetched[0] if fetched is not None else 0
            if count >= 1:
                break
    finally:
        consumer.close()

    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT facility_id, client_id, tray_type_id, on_time, decon_dwell_min,
                   transport_min, hour_of_pickup, day_of_week
            FROM journey WHERE tray_id = %s
            """,
            (tray_id,),
        )
        row = cur.fetchone()
    assert row is not None, "journey row did not appear within 30s"
    facility_id, client_id, tray_type_id, on_time, decon_dwell, transport, hour, dow = row
    assert facility_id == "BOCA"
    assert client_id == "HOSPITAL_A"
    assert tray_type_id == "TRAY-KNEE"
    assert on_time is True
    assert decon_dwell == 20.0
    assert transport == 30.0
    assert hour == 8
    assert dow == 2

    with db_conn.cursor() as cur:
        cur.execute("SELECT current_stage FROM tray WHERE tray_id = %s", (tray_id,))
        tray_row = cur.fetchone()
    assert tray_row is not None
    assert tray_row[0] == "DELIVERED"

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM journey_open WHERE tray_id = %s", (tray_id,))
        open_row = cur.fetchone()
    assert open_row is not None
    assert open_row[0] == 0


def test_pgstore_get_open_journey_returns_none_when_absent(
    db_conn: psycopg.Connection[Any],
) -> None:
    """``get_open_journey`` for an unknown tray_id returns ``None`` (no row)."""
    store = PgStore(db_conn)
    assert store.get_open_journey(f"TRAY-NONE-{uuid.uuid4().hex}") is None


def test_pgstore_delete_open_journey_is_no_op_when_absent(
    db_conn: psycopg.Connection[Any],
) -> None:
    """``delete_open_journey`` on a missing tray_id is a silent no-op."""
    store = PgStore(db_conn)
    store.delete_open_journey(f"TRAY-NONEXISTENT-{uuid.uuid4().hex}")
    db_conn.commit()


def test_pgstore_insert_journey_idempotent(db_conn: psycopg.Connection[Any]) -> None:
    """Re-inserting the same ``journey_id`` is a no-op via ON CONFLICT."""
    suffix = uuid.uuid4().hex
    tray_id = f"TRAY-IDEMP-{suffix}"

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM journey WHERE tray_id = %s", (tray_id,))
    db_conn.commit()

    journey_id = uuid.uuid5(uuid.NAMESPACE_DNS, suffix)
    row = JourneyRow(
        journey_id=journey_id,
        tray_id=tray_id,
        facility_id="BOCA",
        tray_type_id="TRAY-KNEE",
        client_id="HOSPITAL_A",
        pickup_ts=datetime(2026, 5, 27, 8, tzinfo=timezone.utc),
        required_by_ts=datetime(2026, 5, 27, 13, tzinfo=timezone.utc),
        decon_dwell_min=20.0,
        inspection_dwell_min=20.0,
        assembly_dwell_min=25.0,
        sterilization_dwell_min=40.0,
        packout_dwell_min=15.0,
        transport_min=30.0,
        delivered_ts=datetime(2026, 5, 27, 11, 30, tzinfo=timezone.utc),
        on_time=True,
        delay_min=-90.0,
        hour_of_pickup=8,
        day_of_week=2,
    )
    store = PgStore(db_conn)
    store.insert_journey(row)
    store.insert_journey(row)
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM journey WHERE journey_id = %s", (journey_id,))
        result = cur.fetchone()
    assert result is not None
    assert result[0] == 1
