"""Posterior summary statistics for the loaded model.

These are the standard moments + percentiles you would get from
``arviz.summary`` minus the chain-aware diagnostics (R-hat, ESS) -- the
``Posterior`` dataclass holds a flattened (chain * draw) sample, so the
chain structure is gone by the time we get here.

Parameter naming uses NumPy-style indexing so the dashboard can split on
the prefix to group rows: ``alpha[BOCA]``, ``sigma_facility[ELM]``,
``beta[TRAY-KNEE]``, etc.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from routing.model import Posterior
from routing.schemas import ModelSummaryResponse, ParameterSummary


def _summarize(name: str, samples: NDArray[np.float64]) -> ParameterSummary:
    """Compute (mean, sd, 5/50/95 percentile) for one parameter."""
    return ParameterSummary(
        name=name,
        mean=float(np.mean(samples)),
        sd=float(np.std(samples)),
        p5=float(np.percentile(samples, 5)),
        p50=float(np.percentile(samples, 50)),
        p95=float(np.percentile(samples, 95)),
    )


def compute_summary(posterior: Posterior) -> ModelSummaryResponse:
    """Return per-parameter posterior summaries for the loaded model."""
    parameters: list[ParameterSummary] = [
        _summarize("mu_global", posterior.mu_global),
        _summarize("gamma_peak", posterior.gamma_peak),
        _summarize("mu_transport", posterior.mu_transport),
        _summarize("sigma_transport", posterior.sigma_transport),
    ]
    for f_idx, f_id in enumerate(posterior.facility_ids):
        parameters.append(_summarize(f"alpha[{f_id}]", posterior.alpha[:, f_idx]))
        parameters.append(_summarize(f"sigma_facility[{f_id}]", posterior.sigma_facility[:, f_idx]))
    for t_idx, t_id in enumerate(posterior.tray_type_ids):
        parameters.append(_summarize(f"beta[{t_id}]", posterior.beta[:, t_idx]))

    return ModelSummaryResponse(
        n_samples=posterior.n_samples(),
        facility_ids=list(posterior.facility_ids),
        tray_type_ids=list(posterior.tray_type_ids),
        parameters=parameters,
    )
