"""Tests for the Settings model."""

from __future__ import annotations

import pytest

from ingest.config import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.kafka_brokers == "localhost:19092"
    assert s.schema_registry_url == "http://localhost:18081"
    assert s.kafka_topic == "events"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_KAFKA_BROKERS", "kafka1:9092,kafka2:9092")
    monkeypatch.setenv("INGEST_KAFKA_TOPIC", "events-staging")
    s = Settings()
    assert s.kafka_brokers == "kafka1:9092,kafka2:9092"
    assert s.kafka_topic == "events-staging"
