"""CLI: ``routing fit`` and ``routing backtest``."""

from __future__ import annotations

from pathlib import Path

import click
import numpy as np

from routing.data import load_journeys
from routing.model import fit as fit_model
from routing.model import load as load_posterior
from routing.model import save as save_posterior
from routing.simulate import run_simulation, synth_events_data_generator


@click.group()
def main() -> None:
    """routing: fit and evaluate the variance-aware routing model."""


@main.command("fit")
@click.option(
    "--in",
    "in_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Input journey parquet (e.g. produced by synth-events).",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("model.npz"),
    help="Output posterior archive (.npz).",
)
@click.option("--draws", type=int, default=1000, help="NUTS draws per chain.")
@click.option("--tune", type=int, default=1000, help="NUTS warmup per chain.")
@click.option("--chains", type=int, default=2, help="Number of NUTS chains.")
@click.option("--seed", type=int, default=42, help="RNG seed.")
def fit_cmd(
    in_path: Path,
    out_path: Path,
    draws: int,
    tune: int,
    chains: int,
    seed: int,
) -> None:
    """Fit the hierarchical Bayesian model on a journey parquet."""
    click.echo(f"loading {in_path}")
    dataset = load_journeys(in_path)
    click.echo(f"  n = {len(dataset.facility_idx)} journeys")
    click.echo(f"  facilities = {dataset.facility_ids}")
    click.echo(f"  tray types = {dataset.tray_type_ids}")
    click.echo(f"sampling: draws={draws} tune={tune} chains={chains} seed={seed}")
    posterior = fit_model(dataset, draws=draws, tune=tune, chains=chains, seed=seed)
    save_posterior(posterior, str(out_path))
    click.echo(f"wrote posterior ({posterior.n_samples()} samples) to {out_path}")


@main.command("backtest")
@click.option(
    "--model",
    "model_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Posterior .npz written by `routing fit`.",
)
@click.option("--n", "n_pickups", type=int, default=5000, help="Number of simulated pickups.")
@click.option("--seed", type=int, default=100, help="RNG seed for the simulation.")
def backtest_cmd(model_path: Path, n_pickups: int, seed: int) -> None:
    """Run a head-to-head policy comparison vs the synth-events ground truth."""
    posterior = load_posterior(str(model_path))
    rng = np.random.default_rng(seed)
    report = run_simulation(posterior, synth_events_data_generator(), n_pickups, rng)

    click.echo("")
    click.echo(f"backtest over n = {report.n} pickups")
    click.echo("")
    click.echo("  policy           on-time-rate   mean-delay (min)   p95-delay (min)")
    click.echo("  -----------------------------------------------------------------")
    for r in report.per_policy:
        click.echo(
            f"  {r.policy_id:<14}  {r.on_time_rate:>10.3f}   {r.mean_delay_min:>14.1f}   " f"{r.p95_delay_min:>14.1f}"
        )

    click.echo("")
    for lift in report.lifts:
        click.echo(
            f"  lift: {lift.policy_id} vs {lift.vs}:  "
            f"{lift.point_pp:+.1f} pp  (95% CI: {lift.ci_95_lo_pp:+.1f} -- {lift.ci_95_hi_pp:+.1f})"
        )
