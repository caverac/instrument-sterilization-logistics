"""Tests for the PyMC model fit + posterior I/O."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from routing.data import JourneyDataset
from routing.model import Posterior, fit, load, save


def test_fit_returns_posterior_with_expected_shapes(tiny_dataset: JourneyDataset) -> None:
    """Tiny NUTS fit succeeds and the posterior arrays have the right shapes."""
    posterior = fit(tiny_dataset, draws=50, tune=50, chains=1, seed=42)
    n_samples = posterior.n_samples()
    n_facilities = len(tiny_dataset.facility_ids)
    n_trays = len(tiny_dataset.tray_type_ids)
    assert n_samples == 50
    assert posterior.mu_global.shape == (n_samples,)
    assert posterior.alpha.shape == (n_samples, n_facilities)
    assert posterior.sigma_facility.shape == (n_samples, n_facilities)
    assert posterior.beta.shape == (n_samples, n_trays)
    assert posterior.gamma_peak.shape == (n_samples,)
    assert posterior.mu_transport.shape == (n_samples,)
    assert posterior.sigma_transport.shape == (n_samples,)
    assert posterior.facility_ids == tiny_dataset.facility_ids
    assert posterior.tray_type_ids == tiny_dataset.tray_type_ids


def test_save_and_load_round_trip(tmp_path: Path, fake_posterior: Posterior) -> None:
    """A saved posterior reloads with bitwise-equal arrays."""
    out = tmp_path / "model.npz"
    save(fake_posterior, str(out))
    reloaded = load(str(out))

    assert reloaded.facility_ids == fake_posterior.facility_ids
    assert reloaded.tray_type_ids == fake_posterior.tray_type_ids
    assert np.array_equal(reloaded.mu_global, fake_posterior.mu_global)
    assert np.array_equal(reloaded.alpha, fake_posterior.alpha)
    assert np.array_equal(reloaded.sigma_facility, fake_posterior.sigma_facility)
    assert np.array_equal(reloaded.beta, fake_posterior.beta)
    assert np.array_equal(reloaded.gamma_peak, fake_posterior.gamma_peak)
    assert np.array_equal(reloaded.mu_transport, fake_posterior.mu_transport)
    assert np.array_equal(reloaded.sigma_transport, fake_posterior.sigma_transport)
