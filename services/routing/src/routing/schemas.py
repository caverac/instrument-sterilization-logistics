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
