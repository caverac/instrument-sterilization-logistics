"""Kafka producer + JSON-Schema serializer for the ingest service.

Named ``bus`` rather than ``kafka`` to avoid shadowing the third-party
``kafka`` package namespace in IDE autocompletion.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

from ingest.events import Event

if TYPE_CHECKING:
    pass

# JSON Schema for events as they go on the wire. Mirrors the Pydantic Event
# model. Registered to Schema Registry on first publish (handled by the
# JSONSerializer with auto.register.schemas defaulting to true).
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


def make_producer(brokers: str) -> Producer:
    """Create an idempotent Kafka producer.

    Parameters
    ----------
    brokers : str
        Comma-separated ``host:port`` bootstrap servers.

    Returns
    -------
    Producer
        Configured confluent-kafka Producer.
    """
    return Producer(
        {
            "bootstrap.servers": brokers,
            "client.id": "ingest",
            "enable.idempotence": True,
            "acks": "all",
            "compression.type": "snappy",
            "linger.ms": 5,
        }
    )


def make_serializer(schema_registry_url: str) -> JSONSerializer:
    """Create a JSON-Schema serializer wired to a Schema Registry.

    Parameters
    ----------
    schema_registry_url : str
        Confluent-compatible Schema Registry URL.

    Returns
    -------
    JSONSerializer
        Serializer that registers and wraps payloads in the Confluent
        wire format (magic byte + schema ID + JSON body).
    """
    sr_client = SchemaRegistryClient({"url": schema_registry_url})
    serializer: JSONSerializer = JSONSerializer(EVENT_SCHEMA_STR, sr_client)
    return serializer


async def publish_event(
    producer: Producer,
    serializer: JSONSerializer,
    topic: str,
    event: Event,
) -> None:
    """Serialize and publish one event.

    The sync ``producer.produce`` and ``producer.poll`` calls run in a worker
    thread so the event loop is not blocked.

    Parameters
    ----------
    producer : Producer
        Configured Kafka producer.
    serializer : JSONSerializer
        Schema-Registry-aware serializer.
    topic : str
        Target topic.
    event : Event
        Event to publish. Partition key is ``tray_id`` so per-tray ordering
        is preserved across consumer instances.
    """
    key = event.tray_id.encode("utf-8")
    ctx = SerializationContext(topic, MessageField.VALUE)
    value: Any = serializer(event.model_dump(mode="json"), ctx)

    def _produce() -> None:
        producer.produce(topic=topic, key=key, value=value)
        producer.poll(0)

    await asyncio.to_thread(_produce)
