"""CLI entry point: ``synth-events generate`` and ``synth-events publish``."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click
import numpy as np

from synth_events.event_stream import journey_to_events
from synth_events.journey import simulate_journey
from synth_events.parquet import write_journeys_parquet
from synth_events.schedule import generate_pickups


@click.group()
def main() -> None:
    """synth-events: generate synthetic journey data for modeling."""


@main.command()
@click.option("--n", type=int, default=10_000, help="Number of journeys to generate.")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("journeys.parquet"),
    help="Output parquet file path.",
)
@click.option("--seed", type=int, default=42, help="RNG seed for reproducibility.")
@click.option(
    "--days",
    type=int,
    default=30,
    help="Time span (days) ending at 2026-01-01 to spread pickups across.",
)
def generate(n: int, out: Path, seed: int, days: int) -> None:
    """Generate N synthetic journeys and write them to a parquet file."""
    rng = np.random.default_rng(seed)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    start = end - timedelta(days=days)
    pickups = generate_pickups(rng, n, start, end)
    journeys = [simulate_journey(rng, p) for p in pickups]
    write_journeys_parquet(journeys, out)
    click.echo(f"wrote {len(journeys)} journeys to {out}")


@main.command()
@click.option("--n", type=int, default=200, help="Number of journeys to publish.")
@click.option(
    "--ingest-url",
    type=str,
    default="http://localhost:8000",
    help="Ingest service base URL.",
)
@click.option("--seed", type=int, default=42, help="RNG seed for reproducibility.")
@click.option(
    "--hours",
    type=int,
    default=24,
    help="Spread pickup times across the last N hours ending now.",
)
def publish(n: int, ingest_url: str, seed: int, hours: int) -> None:
    """Generate N synthetic journeys and POST every event through ingest.

    Each journey produces 10 events (PICKED_UP -> DELIVERED). Per-tray
    ordering is preserved by posting events in sequence.
    """
    rng = np.random.default_rng(seed)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    pickups = generate_pickups(rng, n, start, end)
    journeys = [simulate_journey(rng, p) for p in pickups]

    posted = 0
    for journey in journeys:
        for event in journey_to_events(journey):
            post_event(ingest_url, event)
            posted += 1
    click.echo(f"posted {posted} events from {len(journeys)} journeys to {ingest_url}")


def post_event(ingest_url: str, event: dict[str, Any]) -> None:
    """POST one event payload to the ingest service.

    Raises :class:`click.ClickException` on any HTTP or transport error
    so the surrounding CLI loop aborts loudly rather than silently
    dropping data.
    """
    url = f"{ingest_url}/events"
    body = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status != 202:
                raise click.ClickException(f"unexpected {resp.status} from {url} on {event['source_event_id']}")
    except urllib.error.URLError as exc:
        raise click.ClickException(f"transport error against {url}: {exc.reason}") from exc
