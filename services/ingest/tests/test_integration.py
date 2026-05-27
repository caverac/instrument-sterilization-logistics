"""Integration test: exercises the real Redpanda + Schema Registry stack.

Run with ``make dev-up`` first, then ``uv run pytest services/ingest -m slow``.

These tests are excluded from coverage and from the default test run.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pytest
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext
from fastapi.testclient import TestClient

from ingest.app import create_app
from ingest.config import Settings

pytestmark = pytest.mark.slow


def _settings() -> Settings:
    return Settings(
        kafka_brokers=os.environ.get("INGEST_KAFKA_BROKERS", "localhost:19092"),
        schema_registry_url=os.environ.get("INGEST_SCHEMA_REGISTRY_URL", "http://localhost:18081"),
        kafka_topic=os.environ.get("INGEST_KAFKA_TOPIC", "events"),
    )


def test_event_published_to_kafka_with_schema_registry_wire_format() -> None:
    cfg = _settings()
    sample_source_event_id = f"int-{datetime.now(timezone.utc).timestamp()}"

    consumer = Consumer(
        {
            "bootstrap.servers": cfg.kafka_brokers,
            "group.id": f"int-test-{time.time_ns()}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([cfg.kafka_topic])
    consumer.poll(timeout=2.0)  # join group + get partition assignment

    app = create_app(cfg)
    with TestClient(app) as client:
        response = client.post(
            "/events",
            json={
                "source_system": "INTEGRATION_TEST",
                "source_event_id": sample_source_event_id,
                "tray_id": "TRAY-INT",
                "facility_id": "BOCA",
                "event_type": "CHECKED_IN",
                "timestamp_event": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert response.status_code == 202
        published_event_id = response.json()["event_id"]

    sr_client = SchemaRegistryClient({"url": cfg.schema_registry_url})
    deserializer = JSONDeserializer(schema_str=None, schema_registry_client=sr_client)

    deadline = time.time() + 10.0
    decoded: dict[str, object] | None = None
    while time.time() < deadline:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error() is not None:
            continue
        ctx = SerializationContext(cfg.kafka_topic, MessageField.VALUE)
        raw = deserializer(msg.value(), ctx)
        if raw["source_event_id"] == sample_source_event_id:
            decoded = raw
            break
    consumer.close()

    assert decoded is not None, "did not receive the published event within 10s"
    assert decoded["event_id"] == published_event_id
    assert decoded["source_system"] == "INTEGRATION_TEST"
    assert decoded["tray_id"] == "TRAY-INT"


def test_replay_produces_same_deterministic_event_id() -> None:
    """Two POSTs with the same (source_system, source_event_id) yield the same event_id."""
    cfg = _settings()
    payload = {
        "source_system": "INTEGRATION_TEST",
        "source_event_id": f"replay-{datetime.now(timezone.utc).timestamp()}",
        "tray_id": "TRAY-REPLAY",
        "facility_id": "BOCA",
        "event_type": "CHECKED_IN",
        "timestamp_event": datetime.now(timezone.utc).isoformat(),
    }
    app = create_app(cfg)
    with TestClient(app) as client:
        first = client.post("/events", json=payload)
        second = client.post("/events", json=payload)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["event_id"] == second.json()["event_id"]


def test_schema_registered_under_topic_value_subject() -> None:
    cfg = _settings()
    payload = {
        "source_system": "INTEGRATION_TEST",
        "source_event_id": f"schema-{datetime.now(timezone.utc).timestamp()}",
        "tray_id": "TRAY-SCHEMA",
        "facility_id": "BOCA",
        "event_type": "CHECKED_IN",
        "timestamp_event": datetime.now(timezone.utc).isoformat(),
    }
    with TestClient(create_app(cfg)) as client:
        assert client.post("/events", json=payload).status_code == 202

    sr_client = SchemaRegistryClient({"url": cfg.schema_registry_url})
    subjects = sr_client.get_subjects()
    assert f"{cfg.kafka_topic}-value" in subjects

    latest = sr_client.get_latest_version(f"{cfg.kafka_topic}-value")
    schema_str = latest.schema.schema_str
    assert schema_str is not None
    schema_obj = json.loads(schema_str)
    assert schema_obj["title"] == "Event"
    assert "event_id" in schema_obj["properties"]
