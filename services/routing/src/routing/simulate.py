"""Head-to-head policy simulation against synthetic ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from routing.model import Posterior
from routing.policies import PolicyChoice, mean_only, proximity, variance_aware

# A "data generator" produces a true (total_processing, transport) sample
# for a given (facility_id, tray_type_id, is_peak). The simulation harness
# calls it to score the policies' decisions against ground truth.
DataGenerator = Callable[[str, str, int, np.random.Generator], tuple[float, float]]


@dataclass(frozen=True)
class PolicyResult:
    """Aggregated policy outcomes over a simulation run."""

    policy_id: str
    n: int
    on_time_rate: float
    mean_delay_min: float
    p95_delay_min: float


@dataclass(frozen=True)
class Lift:
    """On-time-rate lift of one policy over another with a bootstrap CI."""

    policy_id: str
    vs: str
    point_pp: float
    ci_95_lo_pp: float
    ci_95_hi_pp: float


@dataclass(frozen=True)
class SimulationReport:
    """Full output of a head-to-head simulation run."""

    n: int
    per_policy: tuple[PolicyResult, ...]
    lifts: tuple[Lift, ...]
    on_time_by_policy: dict[str, NDArray[np.int32]]


def _sample_pickup(
    posterior: Posterior,
    rng: np.random.Generator,
    deadline_mean_min: float,
    deadline_sigma: float,
    clients: tuple[str, ...],
) -> tuple[str, int, str, float]:
    """Draw a random pickup: (tray_type_id, is_peak, client_id, deadline_min)."""
    tray_type_id = str(rng.choice(np.array(posterior.tray_type_ids)))
    hour = int(rng.integers(0, 24))
    is_peak = 1 if (8 <= hour < 12) or (14 <= hour < 18) else 0
    client_id = str(rng.choice(np.array(clients)))
    deadline_mu = float(np.log(deadline_mean_min)) - 0.5 * deadline_sigma * deadline_sigma
    deadline = float(rng.lognormal(deadline_mu, deadline_sigma))
    return tray_type_id, is_peak, client_id, deadline


def _percentile(values: NDArray[np.float64], q: float) -> float:
    """Plain numpy percentile cast to a python float (helps mypy)."""
    return float(np.percentile(values, q))


def _bootstrap_ci(
    on_time_a: NDArray[np.int32],
    on_time_b: NDArray[np.int32],
    rng: np.random.Generator,
    n_boot: int = 1000,
) -> tuple[float, float]:
    """Bootstrap 95% CI for the on-time-rate difference (a - b) in percentage points."""
    n = on_time_a.shape[0]
    diffs = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        diffs[i] = float(on_time_a[idx].mean() - on_time_b[idx].mean())
    lo = _percentile(diffs, 2.5) * 100.0
    hi = _percentile(diffs, 97.5) * 100.0
    return lo, hi


def run_simulation(
    posterior: Posterior,
    data_gen: DataGenerator,
    n_pickups: int,
    rng: np.random.Generator,
    *,
    deadline_mean_min: float = 220.0,
    deadline_sigma: float = 0.20,
    clients: tuple[str, ...] = ("HOSPITAL_A", "HOSPITAL_B", "HOSPITAL_C", "ASC_X", "ASC_Y"),
) -> SimulationReport:
    """Simulate ``n_pickups`` random pickups through all three policies.

    For each pickup, the three policies pick a facility; the data generator
    samples a (processing, transport) outcome at that facility; we mark
    on-time and record signed delay. Returns aggregated per-policy stats
    and bootstrap-CI lifts of variance-aware vs each baseline.
    """
    policies = ("variance-aware", "mean-only", "proximity")
    on_time: dict[str, list[int]] = {p: [] for p in policies}
    delays: dict[str, list[float]] = {p: [] for p in policies}

    for _ in range(n_pickups):
        tray_type_id, is_peak, client_id, deadline = _sample_pickup(
            posterior, rng, deadline_mean_min, deadline_sigma, clients
        )

        choices: dict[str, PolicyChoice] = {
            "variance-aware": variance_aware(posterior, tray_type_id, is_peak, deadline, rng),
            "mean-only": mean_only(posterior, tray_type_id, is_peak),
            "proximity": proximity(posterior, client_id),
        }
        for policy_id, choice in choices.items():
            processing, transport = data_gen(choice.facility_id, tray_type_id, is_peak, rng)
            total = processing + transport
            on_time[policy_id].append(1 if total <= deadline else 0)
            delays[policy_id].append(total - deadline)

    on_time_arrays = {p: np.array(on_time[p], dtype=np.int32) for p in policies}
    per_policy = tuple(
        PolicyResult(
            policy_id=p,
            n=n_pickups,
            on_time_rate=float(on_time_arrays[p].mean()),
            mean_delay_min=float(np.mean(delays[p])),
            p95_delay_min=_percentile(np.array(delays[p]), 95),
        )
        for p in policies
    )

    lift_va_vs_mean_lo, lift_va_vs_mean_hi = _bootstrap_ci(
        on_time_arrays["variance-aware"], on_time_arrays["mean-only"], rng
    )
    lift_va_vs_prox_lo, lift_va_vs_prox_hi = _bootstrap_ci(
        on_time_arrays["variance-aware"], on_time_arrays["proximity"], rng
    )

    lifts = (
        Lift(
            policy_id="variance-aware",
            vs="mean-only",
            point_pp=(float(on_time_arrays["variance-aware"].mean()) - float(on_time_arrays["mean-only"].mean()))
            * 100.0,
            ci_95_lo_pp=lift_va_vs_mean_lo,
            ci_95_hi_pp=lift_va_vs_mean_hi,
        ),
        Lift(
            policy_id="variance-aware",
            vs="proximity",
            point_pp=(float(on_time_arrays["variance-aware"].mean()) - float(on_time_arrays["proximity"].mean()))
            * 100.0,
            ci_95_lo_pp=lift_va_vs_prox_lo,
            ci_95_hi_pp=lift_va_vs_prox_hi,
        ),
    )

    return SimulationReport(
        n=n_pickups,
        per_policy=per_policy,
        lifts=lifts,
        on_time_by_policy={p: on_time_arrays[p] for p in policies},
    )


def synth_events_data_generator() -> DataGenerator:
    """Return a data generator that samples from synth-events' true distributions.

    Uses the same distribution parameters synth-events used to generate the
    training data, so the simulation's "ground truth" matches the data the
    model was fit on. Tightly couples to synth-events.parameters / simulate
    -- replace this with a real-data sampler when we have one.
    """
    from synth_events.parameters import FACILITIES, TRAY_TYPES
    from synth_events.simulate import sample_stage_dwells, sample_transport_min

    facilities_by_id = {f.facility_id: f for f in FACILITIES}
    trays_by_id = {t.tray_type_id: t for t in TRAY_TYPES}

    def gen(
        facility_id: str,
        tray_type_id: str,
        is_peak: int,
        rng: np.random.Generator,
    ) -> tuple[float, float]:
        facility = facilities_by_id[facility_id]
        tray = trays_by_id[tray_type_id]
        hour = 10 if is_peak else 2  # representative peak / off-peak
        dwells = sample_stage_dwells(rng, facility, tray, hour)
        transport = sample_transport_min(rng)
        return float(sum(dwells.values())), float(transport)

    return gen
