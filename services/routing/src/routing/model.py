"""Hierarchical Bayesian model for journey completion + transport times.

The processing model is a log-normal observation on total processing time
(sum of five stage dwells) with per-facility mean offsets (partial pooling
via a shared sigma_alpha), per-facility observation sigmas, tray-type fixed
effects, and an additive peak-hour shift in log-space.

The transport model is a separate global log-normal -- transport is the
return-trip duration, modelled independently of the reprocessing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pymc as pm
import pytensor.tensor as pt
from numpy.typing import NDArray

from routing.data import JourneyDataset

# pytensor.tensor.take lacks type annotations, so mypy flags every call
# as untyped. Wrap once here so the model code uses a typed reference.
_pt_take: Any = pt.take


@dataclass(frozen=True)
class Posterior:
    """Posterior samples for the joint (processing, transport) model.

    Shapes are ``(n_chains * n_samples,)`` for scalar params and
    ``(n_chains * n_samples, k)`` for vector params (``alpha``, ``beta``,
    ``sigma_facility``). The mappings from index back to facility_id /
    tray_type_id are captured so callers can address cells by name.
    """

    facility_ids: tuple[str, ...]
    tray_type_ids: tuple[str, ...]
    mu_global: NDArray[np.float64]
    alpha: NDArray[np.float64]
    sigma_facility: NDArray[np.float64]
    beta: NDArray[np.float64]
    gamma_peak: NDArray[np.float64]
    mu_transport: NDArray[np.float64]
    sigma_transport: NDArray[np.float64]

    def n_samples(self) -> int:
        """Return the number of posterior draws."""
        return int(self.mu_global.shape[0])


def _build_processing_model(dataset: JourneyDataset) -> pm.Model:
    """Construct the PyMC processing model from observed journey data."""
    n_facilities = len(dataset.facility_ids)
    n_trays = len(dataset.tray_type_ids)
    with pm.Model() as model:
        mu_global = pm.Normal("mu_global", mu=float(np.log(165.0)), sigma=0.5)

        sigma_alpha = pm.HalfNormal("sigma_alpha", sigma=0.3)
        alpha = pm.Normal("alpha", mu=0.0, sigma=sigma_alpha, shape=n_facilities)
        sigma_facility = pm.HalfNormal("sigma_facility", sigma=0.5, shape=n_facilities)

        sigma_beta = pm.HalfNormal("sigma_beta", sigma=0.3)
        beta = pm.Normal("beta", mu=0.0, sigma=sigma_beta, shape=n_trays)

        gamma_peak = pm.Normal("gamma_peak", mu=0.0, sigma=0.1)

        # _pt_take() (typed wrapper around pt.take) instead of bracket
        # indexing so pylint sees these as function calls on a possibly-
        # non-indexable; the wrapper also unsticks mypy's no-untyped-call.
        log_mu = (
            mu_global
            + _pt_take(alpha, dataset.facility_idx)
            + _pt_take(beta, dataset.tray_idx)
            + gamma_peak * dataset.is_peak
        )
        sigma_obs = _pt_take(sigma_facility, dataset.facility_idx)
        pm.LogNormal("y", mu=log_mu, sigma=sigma_obs, observed=dataset.total_processing_min)
    return model


def _build_transport_model(dataset: JourneyDataset) -> pm.Model:
    """Construct the PyMC transport model (global log-normal)."""
    with pm.Model() as model:
        mu_t = pm.Normal("mu_t", mu=float(np.log(30.0)), sigma=0.5)
        sigma_t = pm.HalfNormal("sigma_t", sigma=0.5)
        pm.LogNormal("t", mu=mu_t, sigma=sigma_t, observed=dataset.transport_min)
    return model


def _flatten(arr: Any) -> NDArray[np.float64]:
    """Reshape an arviz posterior tensor (chains, draws, ...) -> (chains*draws, ...)."""
    raw: NDArray[np.float64] = np.asarray(arr.values, dtype=np.float64)
    n_chains, n_draws = raw.shape[0], raw.shape[1]
    rest = raw.shape[2:]
    return raw.reshape(n_chains * n_draws, *rest)


def fit(
    dataset: JourneyDataset,
    *,
    draws: int = 1000,
    tune: int = 1000,
    chains: int = 2,
    seed: int = 42,
) -> Posterior:
    """Fit the hierarchical processing model + transport model jointly.

    Parameters
    ----------
    dataset : JourneyDataset
        Observed journey data, vectorized.
    draws : int
        NUTS draws per chain.
    tune : int
        Warmup steps per chain.
    chains : int
        Number of NUTS chains.
    seed : int
        Master RNG seed; chains use deterministic offsets.

    Returns
    -------
    Posterior
        Flattened posterior samples + the category mappings used at fit time.
    """
    proc_model = _build_processing_model(dataset)
    with proc_model:
        proc_trace = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            progressbar=False,
            compute_convergence_checks=False,
        )

    trans_model = _build_transport_model(dataset)
    with trans_model:
        trans_trace = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed + 1,
            progressbar=False,
            compute_convergence_checks=False,
        )

    return Posterior(
        facility_ids=dataset.facility_ids,
        tray_type_ids=dataset.tray_type_ids,
        mu_global=_flatten(proc_trace.posterior["mu_global"]),
        alpha=_flatten(proc_trace.posterior["alpha"]),
        sigma_facility=_flatten(proc_trace.posterior["sigma_facility"]),
        beta=_flatten(proc_trace.posterior["beta"]),
        gamma_peak=_flatten(proc_trace.posterior["gamma_peak"]),
        mu_transport=_flatten(trans_trace.posterior["mu_t"]),
        sigma_transport=_flatten(trans_trace.posterior["sigma_t"]),
    )


def save(posterior: Posterior, path: str) -> None:
    """Save a posterior to a numpy ``.npz`` archive."""
    np.savez(
        path,
        facility_ids=np.array(list(posterior.facility_ids), dtype=object),
        tray_type_ids=np.array(list(posterior.tray_type_ids), dtype=object),
        mu_global=posterior.mu_global,
        alpha=posterior.alpha,
        sigma_facility=posterior.sigma_facility,
        beta=posterior.beta,
        gamma_peak=posterior.gamma_peak,
        mu_transport=posterior.mu_transport,
        sigma_transport=posterior.sigma_transport,
    )


def load(path: str) -> Posterior:
    """Load a posterior previously written by :func:`save`."""
    with np.load(path, allow_pickle=True) as data:
        return Posterior(
            facility_ids=tuple(str(x) for x in data["facility_ids"]),
            tray_type_ids=tuple(str(x) for x in data["tray_type_ids"]),
            mu_global=data["mu_global"],
            alpha=data["alpha"],
            sigma_facility=data["sigma_facility"],
            beta=data["beta"],
            gamma_peak=data["gamma_peak"],
            mu_transport=data["mu_transport"],
            sigma_transport=data["sigma_transport"],
        )
