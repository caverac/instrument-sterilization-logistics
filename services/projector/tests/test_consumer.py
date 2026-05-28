"""Tests for the Kafka consumer loop and its factories."""

from __future__ import annotations

from typing import Any

from confluent_kafka import Consumer
from confluent_kafka.schema_registry.json_schema import JSONDeserializer

from projector.consumer import consume_one, make_consumer, make_deserializer, run_consumer
from projector.events import Event, EventType


class FakeMessage:
    """Stand-in for confluent_kafka.Message."""

    def __init__(self, *, raw: bytes | None = b"{}", err: object | None = None) -> None:
        self._raw = raw
        self._err = err

    def value(self) -> bytes | None:
        """Return the raw wire-format payload."""
        return self._raw

    def error(self) -> object | None:
        """Return the Kafka error, if any."""
        return self._err


class FakeConsumer:
    """In-memory stand-in for confluent_kafka.Consumer.

    Duck-typed; consumed by ``consume_one`` which expects ``Any``.
    """

    def __init__(self, messages: list[Any]) -> None:
        self._messages = list(messages)
        self.subscribed: list[str] | None = None
        self.committed: list[Any] = []
        self.closed = False

    def subscribe(self, topics: list[str]) -> None:
        """Record the subscribe call."""
        self.subscribed = topics

    def poll(self, timeout: float) -> Any:
        """Return the next queued message, or ``None`` if exhausted."""
        del timeout
        if not self._messages:
            return None
        return self._messages.pop(0)

    def commit(self, *, message: Any, asynchronous: bool = False) -> None:
        """Record the offset commit."""
        del asynchronous
        self.committed.append(message)

    def close(self) -> None:
        """Mark the consumer as closed."""
        self.closed = True


class FakeDeserializer:
    """Stand-in for JSONDeserializer."""

    def __init__(self, decoded: list[dict[str, Any] | None]) -> None:
        self._decoded = list(decoded)
        self.calls = 0

    def __call__(self, value: bytes | None, ctx: Any) -> dict[str, Any] | None:
        """Pop and return the next prepared decode result."""
        del value, ctx
        self.calls += 1
        return self._decoded.pop(0)


def _sample_decoded() -> dict[str, Any]:
    return {
        "event_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "source_system": "TEST",
        "source_event_id": "src-1",
        "tray_id": "TRAY-1",
        "facility_id": "BOCA",
        "event_type": EventType.CHECKED_IN.value,
        "timestamp_event": "2026-05-27T14:00:00+00:00",
        "timestamp_ingest": "2026-05-27T14:01:00+00:00",
    }


def test_consume_one_no_message() -> None:
    """No message ready -> returns False, no commit, no handle."""
    consumer = FakeConsumer([None])
    deser = FakeDeserializer([])
    handled: list[Event] = []

    result = consume_one(consumer, deser, "events", 0.1, handled.append)

    assert result is False
    assert consumer.committed == []
    assert handled == []


def test_consume_one_message_with_error() -> None:
    """Broker error -> message is skipped, no commit."""
    consumer = FakeConsumer([FakeMessage(err=object())])
    deser = FakeDeserializer([])
    handled: list[Event] = []

    result = consume_one(consumer, deser, "events", 0.1, handled.append)

    assert result is False
    assert consumer.committed == []


def test_consume_one_deserializer_returns_none() -> None:
    """Deserializer returning ``None`` skips the message."""
    consumer = FakeConsumer([FakeMessage()])
    deser = FakeDeserializer([None])
    handled: list[Event] = []

    result = consume_one(consumer, deser, "events", 0.1, handled.append)

    assert result is False
    assert deser.calls == 1
    assert consumer.committed == []


def test_consume_one_happy_path() -> None:
    """A decodable message is handled, then committed."""
    msg = FakeMessage()
    consumer = FakeConsumer([msg])
    deser = FakeDeserializer([_sample_decoded()])
    handled: list[Event] = []

    result = consume_one(consumer, deser, "events", 0.1, handled.append)

    assert result is True
    assert len(handled) == 1
    assert handled[0].tray_id == "TRAY-1"
    assert consumer.committed == [msg]


def test_run_consumer_subscribes_loops_and_closes() -> None:
    """``run_consumer`` subscribes once, loops until stop, closes on exit."""
    consumer = FakeConsumer([FakeMessage(), None])
    deser = FakeDeserializer([_sample_decoded()])
    handled: list[Event] = []

    iterations = {"n": 0}

    def should_stop() -> bool:
        # Stop after the second poll returns None.
        iterations["n"] += 1
        return iterations["n"] > 2

    run_consumer(
        consumer=consumer,
        deserializer=deser,
        topic="events",
        poll_timeout_sec=0.1,
        handle=handled.append,
        should_stop=should_stop,
    )

    assert consumer.subscribed == ["events"]
    assert len(handled) == 1
    assert consumer.closed is True


def test_run_consumer_closes_even_when_handle_raises() -> None:
    """An exception from ``handle`` propagates but the consumer is still closed."""
    consumer = FakeConsumer([FakeMessage()])
    deser = FakeDeserializer([_sample_decoded()])

    def boom(_event: Event) -> None:
        raise RuntimeError("kaboom")

    try:
        run_consumer(
            consumer=consumer,
            deserializer=deser,
            topic="events",
            poll_timeout_sec=0.1,
            handle=boom,
            should_stop=lambda: False,
        )
    except RuntimeError:
        pass

    assert consumer.closed is True
    assert consumer.committed == []


def test_make_consumer_returns_kafka_consumer() -> None:
    """Factory returns a confluent_kafka.Consumer configured for the projector."""
    consumer = make_consumer("localhost:19092", "test-projector")
    assert isinstance(consumer, Consumer)
    consumer.close()


def test_make_deserializer_returns_json_deserializer() -> None:
    """Factory returns a Schema-Registry-aware JSONDeserializer."""
    deserializer = make_deserializer("http://localhost:18081")
    assert isinstance(deserializer, JSONDeserializer)
