"""Tests for posterior-predictive scoring."""

from __future__ import annotations

import numpy as np

from routing.model import Posterior
from routing.score import expected_completion_min, p_on_time


def test_expected_completion_orders_facilities_by_design(fake_posterior: Posterior) -> None:
    """ELM should have the longest expected completion, BOCA the shortest."""
    boca = expected_completion_min(fake_posterior, 0, 0, is_peak=0)
    lgb = expected_completion_min(fake_posterior, 1, 0, is_peak=0)
    elm = expected_completion_min(fake_posterior, 2, 0, is_peak=0)
    assert boca < lgb < elm


def test_peak_hour_increases_expected_completion(fake_posterior: Posterior) -> None:
    off_peak = expected_completion_min(fake_posterior, 1, 0, is_peak=0)
    on_peak = expected_completion_min(fake_posterior, 1, 0, is_peak=1)
    assert on_peak > off_peak


def test_p_on_time_returns_a_probability(fake_posterior: Posterior) -> None:
    """The on-time probability is always in [0, 1]."""
    rng = np.random.default_rng(0)
    for facility_idx in range(3):
        for deadline in (60.0, 180.0, 240.0, 600.0):
            p = p_on_time(
                fake_posterior,
                facility_idx,
                0,
                is_peak=0,
                deadline_min=deadline,
                rng=rng,
            )
            assert 0.0 <= p <= 1.0


def test_p_on_time_strictly_increases_with_deadline(fake_posterior: Posterior) -> None:
    """For any facility, looser deadlines give a higher (or equal) on-time probability."""
    rng = np.random.default_rng(2)
    p_tight = p_on_time(fake_posterior, 1, 0, is_peak=0, deadline_min=150.0, rng=rng)
    p_loose = p_on_time(fake_posterior, 1, 0, is_peak=0, deadline_min=400.0, rng=rng)
    assert p_loose >= p_tight


def test_p_on_time_extreme_deadlines_saturate(fake_posterior: Posterior) -> None:
    rng = np.random.default_rng(1)
    very_tight = p_on_time(fake_posterior, 0, 0, is_peak=0, deadline_min=10.0, rng=rng)
    very_loose = p_on_time(fake_posterior, 0, 0, is_peak=0, deadline_min=10_000.0, rng=rng)
    assert very_tight < 0.05
    assert very_loose > 0.95
