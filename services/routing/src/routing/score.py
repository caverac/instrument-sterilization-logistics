"""Posterior predictive scoring for routing decisions."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from routing.model import Posterior


def _log_mu_for_cell(
    posterior: Posterior,
    facility_idx: int,
    tray_idx: int,
    is_peak: int,
) -> NDArray[np.float64]:
    """Return per-posterior-sample log-mean for the (facility, tray, peak) cell."""
    result: NDArray[np.float64] = (
        posterior.mu_global
        + posterior.alpha[:, facility_idx]
        + posterior.beta[:, tray_idx]
        + posterior.gamma_peak * float(is_peak)
    )
    return result


def expected_completion_min(
    posterior: Posterior,
    facility_idx: int,
    tray_idx: int,
    is_peak: int,
) -> float:
    """Posterior mean of E[total + transport].

    For a log-normal, E[X] = exp(mu + sigma^2 / 2). We average that across
    posterior samples to get the policy's "expected completion" view.
    """
    log_mu = _log_mu_for_cell(posterior, facility_idx, tray_idx, is_peak)
    sigma = posterior.sigma_facility[:, facility_idx]
    expected_total = np.exp(log_mu + 0.5 * sigma * sigma)
    expected_transport = np.exp(posterior.mu_transport + 0.5 * posterior.sigma_transport**2)
    return float((expected_total + expected_transport).mean())


def p_on_time(
    posterior: Posterior,
    facility_idx: int,
    tray_idx: int,
    is_peak: int,
    deadline_min: float,
    rng: np.random.Generator,
) -> float:
    """Posterior-predictive probability that total + transport <= deadline.

    For each posterior sample we draw a single (total, transport) pair from
    the posterior predictive log-normals and check the deadline. The mean of
    those indicators is our Monte Carlo estimate of P(on-time).
    """
    log_mu = _log_mu_for_cell(posterior, facility_idx, tray_idx, is_peak)
    sigma = posterior.sigma_facility[:, facility_idx]
    total = rng.lognormal(log_mu, sigma)
    transport = rng.lognormal(posterior.mu_transport, posterior.sigma_transport)
    return float(np.mean((total + transport) <= deadline_min))
