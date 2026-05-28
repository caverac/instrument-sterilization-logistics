"""CLI entry point: ``projector run``."""

from __future__ import annotations

import signal
import threading
from types import FrameType

import click
import psycopg

from projector.config import Settings
from projector.consumer import make_consumer, make_deserializer, run_consumer
from projector.events import Event
from projector.pg_store import PgStore, init_schema
from projector.projections import apply_event


@click.group()
def main() -> None:
    """projector: project events into Postgres tray and journey tables."""


@main.command("run")
def run_cmd() -> None:
    """Start the consumer loop. Runs until SIGINT or SIGTERM."""
    cfg = Settings()
    click.echo(f"connecting to postgres at {cfg.postgres_dsn}")
    conn = psycopg.connect(cfg.postgres_dsn)
    init_schema(conn)
    store = PgStore(conn)

    click.echo(f"subscribing to {cfg.kafka_topic} as group {cfg.kafka_group_id}")
    consumer = make_consumer(cfg.kafka_brokers, cfg.kafka_group_id)
    deserializer = make_deserializer(cfg.schema_registry_url)

    stop_event = threading.Event()

    def _request_stop(_signum: int, _frame: FrameType | None) -> None:
        click.echo("stop requested; finishing in-flight message...")
        stop_event.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    def _handle(event: Event) -> None:
        with conn.transaction():
            apply_event(store, event)

    try:
        run_consumer(
            consumer=consumer,
            deserializer=deserializer,
            topic=cfg.kafka_topic,
            poll_timeout_sec=cfg.poll_timeout_sec,
            handle=_handle,
            should_stop=stop_event.is_set,
        )
    finally:
        conn.close()
    click.echo("stopped cleanly")
