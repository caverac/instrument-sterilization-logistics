"""Tests for the Kafka bus helpers."""

from __future__ import annotations

import json
from typing import Any

import pytest

from ingest.bus import make_producer, make_serializer, publish_event
from ingest.events import Event

from .conftest import FakeProducer, FakeSerializer


async def test_publish_event_uses_tray_id_as_partition_key(
    fake_producer: FakeProducer, fake_serializer: FakeSerializer, sample_event: Event
) -> None:
    await publish_event(
        fake_producer,  # type: ignore[arg-type]
        fake_serializer,  # type: ignore[arg-type]
        "events",
        sample_event,
    )
    assert len(fake_producer.produced) == 1
    msg = fake_producer.produced[0]
    assert msg["topic"] == "events"
    assert msg["key"] == sample_event.tray_id.encode("utf-8")
    body = json.loads(msg["value"])
    assert body["event_id"] == str(sample_event.event_id)
    assert body["source_system"] == sample_event.source_system
    assert fake_producer.poll_calls == 1


async def test_publish_event_invokes_serializer_with_value_context(
    fake_producer: FakeProducer, fake_serializer: FakeSerializer, sample_event: Event
) -> None:
    await publish_event(
        fake_producer,  # type: ignore[arg-type]
        fake_serializer,  # type: ignore[arg-type]
        "events",
        sample_event,
    )
    assert len(fake_serializer.calls) == 1
    value, ctx = fake_serializer.calls[0]
    assert value["event_id"] == str(sample_event.event_id)
    # Context carries the topic + value field marker.
    assert getattr(ctx, "topic", None) == "events"


def test_make_producer_delegates_to_confluent_kafka(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_ctor(config: dict[str, Any]) -> str:
        captured["config"] = config
        return "PRODUCER_SENTINEL"

    monkeypatch.setattr("ingest.bus.Producer", fake_ctor)
    result = make_producer("localhost:9092")
    assert result == "PRODUCER_SENTINEL"  # type: ignore[comparison-overlap]
    assert captured["config"]["bootstrap.servers"] == "localhost:9092"
    assert captured["config"]["enable.idempotence"] is True
    assert captured["config"]["acks"] == "all"


def test_make_serializer_wires_schema_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_sr_client(config: dict[str, Any]) -> str:
        captured["sr_config"] = config
        return "SR_CLIENT_SENTINEL"

    def fake_json_serializer(schema: str, sr_client: Any) -> str:
        captured["schema"] = schema
        captured["sr_client"] = sr_client
        return "SERIALIZER_SENTINEL"

    monkeypatch.setattr("ingest.bus.SchemaRegistryClient", fake_sr_client)
    monkeypatch.setattr("ingest.bus.JSONSerializer", fake_json_serializer)
    result = make_serializer("http://sr:8081")
    assert result == "SERIALIZER_SENTINEL"  # type: ignore[comparison-overlap]
    assert captured["sr_config"] == {"url": "http://sr:8081"}
    assert "event_id" in captured["schema"]
