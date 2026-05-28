"""Tests for projector configuration loading."""

from __future__ import annotations

import pytest

from projector.config import Settings


def test_defaults() -> None:
    """All settings have sensible defaults usable against the dev stack."""
    cfg = Settings()
    assert cfg.kafka_brokers == "localhost:19092"
    assert cfg.schema_registry_url == "http://localhost:18081"
    assert cfg.kafka_topic == "events"
    assert cfg.kafka_group_id == "projector"
    assert cfg.postgres_dsn.startswith("postgresql://")
    assert cfg.poll_timeout_sec == 1.0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``PROJECTOR_`` env vars override defaults."""
    monkeypatch.setenv("PROJECTOR_KAFKA_BROKERS", "kafka.prod:9092")
    monkeypatch.setenv("PROJECTOR_POSTGRES_DSN", "postgresql://x:y@host/db")
    monkeypatch.setenv("PROJECTOR_POLL_TIMEOUT_SEC", "0.5")
    cfg = Settings()
    assert cfg.kafka_brokers == "kafka.prod:9092"
    assert cfg.postgres_dsn == "postgresql://x:y@host/db"
    assert cfg.poll_timeout_sec == 0.5
