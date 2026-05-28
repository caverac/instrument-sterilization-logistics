"""Convert a :class:`SimulationReport` into a :class:`BacktestSummaryResponse`.

The simulation harness in :mod:`routing.simulate` returns a frozen dataclass
shaped for in-process consumers (CLI, tests). This module is the thin
adapter that maps that dataclass to the over-the-wire Pydantic schema the
dashboard consumes.
"""

from __future__ import annotations

from routing.schemas import BacktestLift, BacktestPolicySummary, BacktestSummaryResponse
from routing.simulate import SimulationReport


def to_response(report: SimulationReport) -> BacktestSummaryResponse:
    """Project a :class:`SimulationReport` onto the HTTP response shape."""
    return BacktestSummaryResponse(
        n=report.n,
        per_policy=[
            BacktestPolicySummary(
                policy_id=p.policy_id,
                on_time_rate=p.on_time_rate,
                mean_delay_min=p.mean_delay_min,
                p95_delay_min=p.p95_delay_min,
            )
            for p in report.per_policy
        ],
        lifts=[
            BacktestLift(
                policy_id=lift.policy_id,
                vs=lift.vs,
                point_pp=lift.point_pp,
                ci_95_lo_pp=lift.ci_95_lo_pp,
                ci_95_hi_pp=lift.ci_95_hi_pp,
            )
            for lift in report.lifts
        ],
    )
