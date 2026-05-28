"""The three routing policies that consume a fitted Posterior."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from routing.model import Posterior
from routing.score import expected_completion_min, p_on_time

# Static client -> facility map used by the proximity policy. Approximates
# what we would read from a real distance/transport table once it exists.
CLIENT_FACILITY_MAP: dict[str, str] = {
    "HOSPITAL_A": "BOCA",
    "HOSPITAL_B": "LGB",
    "HOSPITAL_C": "ELM",
    "ASC_X": "BOCA",
    "ASC_Y": "LGB",
}


@dataclass(frozen=True)
class PolicyChoice:
    """The output of a policy: which facility to route to, with diagnostics.

    ``score`` is the raw decision-criterion value for the chosen facility
    (predicted P(on-time) for variance-aware, expected completion for
    mean-only, ``None`` for proximity which has no scalar score).
    ``candidate_scores`` is the full per-facility score dict, useful for
    surfacing in the UI.
    """

    policy_id: str
    facility_id: str
    score: float | None
    candidate_scores: dict[str, float]


def variance_aware(
    posterior: Posterior,
    tray_type_id: str,
    is_peak: int,
    deadline_min: float,
    rng: np.random.Generator,
) -> PolicyChoice:
    """Pick the facility with the highest posterior-predictive P(on-time)."""
    tray_idx = posterior.tray_type_ids.index(tray_type_id)
    scores: dict[str, float] = {}
    for f_idx, f_id in enumerate(posterior.facility_ids):
        scores[f_id] = p_on_time(posterior, f_idx, tray_idx, is_peak, deadline_min, rng)
    chosen = max(scores, key=lambda fid: scores[fid])
    return PolicyChoice(
        policy_id="variance-aware",
        facility_id=chosen,
        score=scores[chosen],
        candidate_scores=scores,
    )


def mean_only(
    posterior: Posterior,
    tray_type_id: str,
    is_peak: int,
) -> PolicyChoice:
    """Pick the facility with the lowest expected (total + transport) completion."""
    tray_idx = posterior.tray_type_ids.index(tray_type_id)
    scores: dict[str, float] = {}
    for f_idx, f_id in enumerate(posterior.facility_ids):
        scores[f_id] = expected_completion_min(posterior, f_idx, tray_idx, is_peak)
    chosen = min(scores, key=lambda fid: scores[fid])
    return PolicyChoice(
        policy_id="mean-only",
        facility_id=chosen,
        score=scores[chosen],
        candidate_scores=scores,
    )


def proximity(
    posterior: Posterior,
    client_id: str,
) -> PolicyChoice:
    """Pick the client's nearest facility from a hardcoded map.

    Falls back to the first facility in the posterior's category list if
    the client is unknown.
    """
    chosen = CLIENT_FACILITY_MAP.get(client_id, posterior.facility_ids[0])
    return PolicyChoice(
        policy_id="proximity",
        facility_id=chosen,
        score=None,
        candidate_scores={fid: float(fid == chosen) for fid in posterior.facility_ids},
    )
