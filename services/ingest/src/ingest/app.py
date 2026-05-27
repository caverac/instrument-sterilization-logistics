"""FastAPI application for the ingest service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, Request, status

from ingest.bus import EventSerializer, KafkaProducer, make_producer, make_serializer, publish_event
from ingest.config import Settings
from ingest.events import EventIn, assign_server_fields


async def get_producer(request: Request) -> KafkaProducer:
    """Resolve the Kafka producer from app state."""
    producer: KafkaProducer = request.app.state.producer
    return producer


async def get_serializer(request: Request) -> EventSerializer:
    """Resolve the Schema-Registry-aware serializer from app state."""
    serializer: EventSerializer = request.app.state.serializer
    return serializer


async def get_topic(request: Request) -> str:
    """Resolve the configured Kafka topic from app state."""
    topic: str = request.app.state.topic
    return topic


ProducerDep = Annotated[KafkaProducer, Depends(get_producer)]
SerializerDep = Annotated[EventSerializer, Depends(get_serializer)]
TopicDep = Annotated[str, Depends(get_topic)]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app.

    Parameters
    ----------
    settings : Settings | None
        Optional pre-built settings. Defaults to environment-loaded settings.

    Returns
    -------
    FastAPI
        The configured app.
    """
    cfg = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.producer = make_producer(cfg.kafka_brokers)
        app.state.serializer = make_serializer(cfg.schema_registry_url)
        app.state.topic = cfg.kafka_topic
        try:
            yield
        finally:
            app.state.producer.flush(timeout=5.0)

    app = FastAPI(title="ingest", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @app.post("/events", status_code=status.HTTP_202_ACCEPTED)
    async def post_event(
        event_in: EventIn,
        producer: ProducerDep,
        serializer: SerializerDep,
        topic: TopicDep,
    ) -> dict[str, Any]:
        """Validate the event, derive the deterministic id, publish to Kafka."""
        event = assign_server_fields(event_in)
        await publish_event(producer, serializer, topic, event)
        return {"event_id": str(event.event_id)}

    return app
