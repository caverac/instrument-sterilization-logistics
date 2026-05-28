"""Tests for the three routing policies."""

from __future__ import annotations

import numpy as np

from routing.model import Posterior
from routing.policies import (
    CLIENT_FACILITY_MAP,
    mean_only,
    proximity,
    variance_aware,
)


def test_mean_only_picks_lowest_expected_facility(fake_posterior: Posterior) -> None:
    """In the fake posterior, BOCA has the lowest expected completion."""
    choice = mean_only(fake_posterior, "TRAY-KNEE", is_peak=0)
    assert choice.policy_id == "mean-only"
    assert choice.facility_id == "BOCA"
    # All three facilities should appear in the candidate scores.
    assert set(choice.candidate_scores.keys()) == set(fake_posterior.facility_ids)
    # Score should equal the chosen facility's expected completion.
    assert choice.score == choice.candidate_scores["BOCA"]


def test_variance_aware_picks_a_real_facility(fake_posterior: Posterior) -> None:
    """The variance-aware policy returns one of the known facilities."""
    rng = np.random.default_rng(0)
    choice = variance_aware(fake_posterior, "TRAY-KNEE", is_peak=0, deadline_min=220.0, rng=rng)
    assert choice.policy_id == "variance-aware"
    assert choice.facility_id in fake_posterior.facility_ids
    assert 0.0 <= (choice.score or 0.0) <= 1.0


def test_variance_aware_loose_deadline_matches_mean_only(fake_posterior: Posterior) -> None:
    """With a very loose deadline, all facilities are essentially certain on-time,
    so variance-aware and mean-only converge on the same (lowest-mean) choice."""
    rng = np.random.default_rng(1)
    va_choice = variance_aware(fake_posterior, "TRAY-KNEE", is_peak=0, deadline_min=600.0, rng=rng)
    mean_choice = mean_only(fake_posterior, "TRAY-KNEE", is_peak=0)
    assert va_choice.facility_id == mean_choice.facility_id == "BOCA"


def test_proximity_uses_the_client_map(fake_posterior: Posterior) -> None:
    choice = proximity(fake_posterior, "HOSPITAL_C")
    assert choice.policy_id == "proximity"
    assert choice.facility_id == CLIENT_FACILITY_MAP["HOSPITAL_C"]
    # candidate_scores marks the chosen facility as 1.0 and others as 0.0
    assert choice.candidate_scores[choice.facility_id] == 1.0


def test_proximity_unknown_client_falls_back(fake_posterior: Posterior) -> None:
    choice = proximity(fake_posterior, "UNKNOWN_CLIENT")
    assert choice.facility_id == fake_posterior.facility_ids[0]
