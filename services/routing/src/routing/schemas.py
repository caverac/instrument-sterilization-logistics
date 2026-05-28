"""Pydantic request/response models for the routing HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DecideRequest(BaseModel):
    """Inputs to a single routing decision."""

    model_config = ConfigDict(extra="forbid")

    tray_type_id: str = Field(min_length=1, max_length=64)
    hour_of_pickup: int = Field(ge=0, le=23)
    deadline_min: float = Field(gt=0.0, le=2400.0)
    client_id: str = Field(min_length=1, max_length=64)


class FacilityCell(BaseModel):
    """Per-facility summary for the (tray, hour) cell in the request."""

    facility_id: str
    name: str
    profile: str
    expected_completion_min: float
    p_on_time: float


class PolicyDecision(BaseModel):
    """One policy's choice plus its candidate scores."""

    policy_id: str
    facility_id: str
    score: float | None
    score_metric: str | None
    candidate_scores: dict[str, float]


class DecideResponse(BaseModel):
    """Response body for ``POST /decide``."""

    facilities: list[FacilityCell]
    policies: list[PolicyDecision]


class BacktestPolicySummary(BaseModel):
    """Aggregated per-policy outcomes from the cached backtest run."""

    policy_id: str
    on_time_rate: float
    mean_delay_min: float
    p95_delay_min: float


class BacktestLift(BaseModel):
    """On-time-rate lift of one policy over another with a 95% bootstrap CI.

    All three pp fields are percentage points, not fractions: ``+4.7`` means
    "4.7 percentage points higher on-time rate".
    """

    policy_id: str
    vs: str
    point_pp: float
    ci_95_lo_pp: float
    ci_95_hi_pp: float


class BacktestSummaryResponse(BaseModel):
    """Response body for ``GET /backtest/summary``."""

    n: int
    per_policy: list[BacktestPolicySummary]
    lifts: list[BacktestLift]


class ParameterSummary(BaseModel):
    """Posterior summary for one scalar model parameter.

    ``p5`` / ``p50`` / ``p95`` are the 5th / 50th / 95th posterior
    percentiles -- a 90% central credible interval plus the median.
    """

    name: str
    mean: float
    sd: float
    p5: float
    p50: float
    p95: float


class ModelSummaryResponse(BaseModel):
    """Response body for ``GET /model/summary``."""

    n_samples: int
    facility_ids: list[str]
    tray_type_ids: list[str]
    parameters: list[ParameterSummary]
