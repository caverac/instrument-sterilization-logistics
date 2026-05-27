"""Tests for the FastAPI app: endpoints, dependency injection, and lifespan."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from ingest.app import create_app, get_producer, get_serializer, get_topic
from ingest.config import Settings

from .conftest import FakeProducer, FakeSerializer


def _app_with_fakes(producer: FakeProducer, serializer: FakeSerializer) -> FastAPI:
    app = create_app(Settings())
    app.dependency_overrides[get_producer] = lambda: producer
    app.dependency_overrides[get_serializer] = lambda: serializer
    app.dependency_overrides[get_topic] = lambda: "test-topic"
    return app


def _sample_payload() -> dict[str, Any]:
    return {
        "source_system": "CENSITRAC_BOCA",
        "source_event_id": "abc-123",
        "tray_id": "TRAY-001",
        "facility_id": "BOCA",
        "event_type": "CHECKED_IN",
        "timestamp_event": "2026-05-25T14:30:00+00:00",
    }


async def test_healthz(fake_producer: FakeProducer, fake_serializer: FakeSerializer) -> None:
    app = _app_with_fakes(fake_producer, fake_serializer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_post_event_publishes_to_topic(fake_producer: FakeProducer, fake_serializer: FakeSerializer) -> None:
    app = _app_with_fakes(fake_producer, fake_serializer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/events", json=_sample_payload())
    assert response.status_code == 202
    body = response.json()
    assert "event_id" in body
    assert len(fake_producer.produced) == 1
    assert fake_producer.produced[0]["topic"] == "test-topic"


async def test_post_event_returns_deterministic_event_id_on_retry(
    fake_producer: FakeProducer, fake_serializer: FakeSerializer
) -> None:
    app = _app_with_fakes(fake_producer, fake_serializer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        first = await client.post("/events", json=_sample_payload())
        second = await client.post("/events", json=_sample_payload())
    assert first.json()["event_id"] == second.json()["event_id"]
    # Both publishes happen -- Kafka and consumers handle dedup downstream.
    assert len(fake_producer.produced) == 2


async def test_post_event_validation_error(fake_producer: FakeProducer, fake_serializer: FakeSerializer) -> None:
    app = _app_with_fakes(fake_producer, fake_serializer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/events", json={"source_system": "X"})
    assert response.status_code == 422


def test_lifespan_wires_state_and_flushes_producer(
    monkeypatch: pytest.MonkeyPatch, fake_producer: FakeProducer, fake_serializer: FakeSerializer
) -> None:
    def fake_make_producer(_brokers: str) -> FakeProducer:
        return fake_producer

    def fake_make_serializer(_url: str) -> FakeSerializer:
        return fake_serializer

    monkeypatch.setattr("ingest.app.make_producer", fake_make_producer)
    monkeypatch.setattr("ingest.app.make_serializer", fake_make_serializer)

    app = create_app(Settings(kafka_topic="lifespan-topic"))
    with TestClient(app) as client:
        assert app.state.producer is fake_producer
        assert app.state.serializer is fake_serializer
        assert app.state.topic == "lifespan-topic"
        assert client.get("/healthz").status_code == 200
    assert fake_producer.flush_calls == 1


async def test_dependency_resolvers_read_from_app_state(
    fake_producer: FakeProducer, fake_serializer: FakeSerializer
) -> None:
    request = MagicMock()
    request.app.state.producer = fake_producer
    request.app.state.serializer = fake_serializer
    request.app.state.topic = "resolved-topic"
    assert await get_producer(request) is fake_producer  # type: ignore[comparison-overlap]
    assert await get_serializer(request) is fake_serializer  # type: ignore[comparison-overlap]
    assert await get_topic(request) == "resolved-topic"


def test_create_app_uses_environment_when_no_settings(
    monkeypatch: pytest.MonkeyPatch, fake_producer: FakeProducer, fake_serializer: FakeSerializer
) -> None:
    monkeypatch.setenv("INGEST_KAFKA_TOPIC", "env-topic")

    def fake_make_producer(_brokers: str) -> FakeProducer:
        return fake_producer

    def fake_make_serializer(_url: str) -> FakeSerializer:
        return fake_serializer

    monkeypatch.setattr("ingest.app.make_producer", fake_make_producer)
    monkeypatch.setattr("ingest.app.make_serializer", fake_make_serializer)

    app = create_app()
    with TestClient(app):
        assert app.state.topic == "env-topic"
