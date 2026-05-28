"""Unit tests for the posterior-summary helper."""

from __future__ import annotations

import numpy as np

from routing.model import Posterior
from routing.model_summary import compute_summary
from routing.schemas import ModelSummaryResponse


def _names(response: ModelSummaryResponse) -> set[str]:
    return {p.name for p in response.parameters}


def test_compute_summary_covers_every_parameter(fake_posterior: Posterior) -> None:
    """Every scalar parameter on the Posterior appears in the response."""
    response = compute_summary(fake_posterior)
    expected = {
        "mu_global",
        "gamma_peak",
        "mu_transport",
        "sigma_transport",
        "alpha[BOCA]",
        "alpha[LGB]",
        "alpha[ELM]",
        "sigma_facility[BOCA]",
        "sigma_facility[LGB]",
        "sigma_facility[ELM]",
        "beta[TRAY-KNEE]",
        "beta[TRAY-LAPS]",
    }
    assert _names(response) == expected


def test_compute_summary_passes_through_metadata(fake_posterior: Posterior) -> None:
    """The response carries the facility / tray ids and total sample count."""
    response = compute_summary(fake_posterior)
    assert response.facility_ids == ["BOCA", "LGB", "ELM"]
    assert response.tray_type_ids == ["TRAY-KNEE", "TRAY-LAPS"]
    assert response.n_samples == fake_posterior.n_samples()


def test_compute_summary_alpha_boca_matches_numpy(fake_posterior: Posterior) -> None:
    """The numeric stats for alpha[BOCA] match plain numpy on the same column."""
    response = compute_summary(fake_posterior)
    alpha_boca = next(p for p in response.parameters if p.name == "alpha[BOCA]")
    samples = fake_posterior.alpha[:, 0]
    assert alpha_boca.mean == float(np.mean(samples))
    assert alpha_boca.sd == float(np.std(samples))
    assert alpha_boca.p5 == float(np.percentile(samples, 5))
    assert alpha_boca.p50 == float(np.percentile(samples, 50))
    assert alpha_boca.p95 == float(np.percentile(samples, 95))


def test_compute_summary_percentile_order(fake_posterior: Posterior) -> None:
    """For every parameter, p5 <= p50 <= p95 holds."""
    response = compute_summary(fake_posterior)
    for param in response.parameters:
        assert param.p5 <= param.p50 <= param.p95
