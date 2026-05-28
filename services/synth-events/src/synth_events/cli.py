"""CLI entry point: ``synth-events generate --n ...``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
import numpy as np

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
