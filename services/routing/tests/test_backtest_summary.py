"""Unit tests for the SimulationReport -> BacktestSummaryResponse adapter."""

from __future__ import annotations

import numpy as np

from routing.backtest_summary import to_response
from routing.simulate import Lift, PolicyResult, SimulationReport


def _fake_report() -> SimulationReport:
    return SimulationReport(
        n=42,
        per_policy=(
            PolicyResult(
                policy_id="variance-aware",
                n=42,
                on_time_rate=0.526,
                mean_delay_min=1.5,
                p95_delay_min=124.6,
            ),
            PolicyResult(
                policy_id="mean-only",
                n=42,
                on_time_rate=0.528,
                mean_delay_min=-2.7,
                p95_delay_min=128.4,
            ),
            PolicyResult(
                policy_id="proximity",
                n=42,
                on_time_rate=0.479,
                mean_delay_min=5.9,
                p95_delay_min=129.3,
            ),
        ),
        lifts=(
            Lift(policy_id="variance-aware", vs="mean-only", point_pp=-0.2, ci_95_lo_pp=-1.6, ci_95_hi_pp=1.3),
            Lift(policy_id="variance-aware", vs="proximity", point_pp=4.7, ci_95_lo_pp=3.2, ci_95_hi_pp=6.1),
        ),
        on_time_by_policy={
            "variance-aware": np.zeros(42, dtype=np.int32),
            "mean-only": np.zeros(42, dtype=np.int32),
            "proximity": np.zeros(42, dtype=np.int32),
        },
    )


def test_to_response_preserves_fields() -> None:
    """Every field on the report maps onto the corresponding response field."""
    response = to_response(_fake_report())
    assert response.n == 42
    assert [p.policy_id for p in response.per_policy] == ["variance-aware", "mean-only", "proximity"]
    assert response.per_policy[0].on_time_rate == 0.526
    assert response.per_policy[2].mean_delay_min == 5.9


def test_to_response_lifts_match_report() -> None:
    """The lift CIs and point estimates round-trip through the adapter."""
    response = to_response(_fake_report())
    assert len(response.lifts) == 2
    va_vs_prox = next(lift for lift in response.lifts if lift.vs == "proximity")
    assert va_vs_prox.point_pp == 4.7
    assert va_vs_prox.ci_95_lo_pp == 3.2
    assert va_vs_prox.ci_95_hi_pp == 6.1


def test_to_response_drops_on_time_by_policy() -> None:
    """The raw on_time arrays are intentionally not on the wire."""
    response = to_response(_fake_report())
    assert "on_time_by_policy" not in response.model_dump()
