"""Kafka consumer loop: deserialize messages and hand them to a callback.

``consumer`` and ``deserializer`` are typed as ``Any`` because
confluent-kafka's stubs use overloaded signatures for ``Consumer.commit``
and a return type for ``JSONDeserializer.__call__`` that doesn't reflect
the dict it actually returns at runtime. Wrapping them in a Protocol
forces type-narrowing acrobatics with no real safety win; the call sites
inside ``consume_one`` are tightly scoped and easy to audit.
"""

from __future__ import annotations

from typing import Any, Callable

from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext

from projector.events import Event


def make_consumer(brokers: str, group_id: str) -> Consumer:
    """Build a confluent-kafka Consumer configured for the projector.

    ``auto.offset.reset=earliest`` so new replicas backfill the full topic.
    ``enable.auto.commit=false`` because the projector commits offsets
    manually after Postgres writes succeed.
    """
    return Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def make_deserializer(schema_registry_url: str) -> Any:
    """Build a Schema-Registry-aware JSON deserializer."""
    sr_client = SchemaRegistryClient({"url": schema_registry_url})
    return JSONDeserializer(schema_str=None, schema_registry_client=sr_client)


def consume_one(
    consumer: Any,
    deserializer: Any,
    topic: str,
    poll_timeout_sec: float,
    handle: Callable[[Event], None],
) -> bool:
    """Try to read and process one message. Returns True if one landed.

    Errors from the broker (``msg.error()`` not None) are skipped without
    committing -- the next poll will retry. Decoded payloads that fail
    Pydantic validation raise; the consumer loop stops, which is the
    intended "loud failure" behavior for poison messages.
    """
    msg = consumer.poll(poll_timeout_sec)
    if msg is None:
        return False
    if msg.error() is not None:
        return False
    ctx = SerializationContext(topic, MessageField.VALUE)
    raw = deserializer(msg.value(), ctx)
    if raw is None:
        return False
    event = Event.model_validate(raw)
    handle(event)
    consumer.commit(message=msg, asynchronous=False)
    return True


def run_consumer(
    consumer: Any,
    deserializer: Any,
    topic: str,
    poll_timeout_sec: float,
    handle: Callable[[Event], None],
    should_stop: Callable[[], bool],
) -> None:
    """Loop until ``should_stop()`` returns True, then close the consumer."""
    consumer.subscribe([topic])
    try:
        while not should_stop():
            consume_one(consumer, deserializer, topic, poll_timeout_sec, handle)
    finally:
        consumer.close()
