"""FastAPI application for the routing decision service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

import numpy as np
from fastapi import Depends, FastAPI, Request

from routing.config import Settings
from routing.model import Posterior, load
from routing.operations import (
    RecentJourneysResponse,
    TrayStatesResponse,
    fetch_recent_journeys,
    fetch_tray_states,
)
from routing.policies import mean_only, proximity, variance_aware
from routing.schemas import DecideRequest, DecideResponse, FacilityCell, PolicyDecision
from routing.score import expected_completion_min, p_on_time

# Static facility metadata for the UI. Mirrors synth-events' design story so
# the cards on the dashboard always have a one-line profile next to the
# computed completion stats.
FACILITY_METADATA: dict[str, dict[str, str]] = {
    "BOCA": {
        "name": "Boca Raton",
        "profile": "Newest -- fast on average but unpredictable.",
    },
    "LGB": {
        "name": "Long Beach",
        "profile": "Mature operation, consistent dwell times.",
    },
    "ELM": {
        "name": "Elmhurst",
        "profile": "Constrained but very steady.",
    },
}

# Peak-hour definition matches synth-events / score.py.
_PEAK_HOURS = frozenset(range(8, 12)) | frozenset(range(14, 18))


def _is_peak(hour: int) -> int:
    """Return 1 if the hour falls inside the peak window, else 0."""
    return 1 if hour in _PEAK_HOURS else 0


async def get_posterior(request: Request) -> Posterior:
    """Resolve the loaded posterior from app state."""
    posterior: Posterior = request.app.state.posterior
    return posterior


async def get_rng(request: Request) -> np.random.Generator:
    """Resolve the request-scoped RNG from app state."""
    rng: np.random.Generator = request.app.state.rng
    return rng


PosteriorDep = Annotated[Posterior, Depends(get_posterior)]
RngDep = Annotated[np.random.Generator, Depends(get_rng)]


def _build_facility_cells(
    posterior: Posterior,
    tray_type_id: str,
    is_peak: int,
    deadline_min: float,
    rng: np.random.Generator,
) -> list[FacilityCell]:
    """Compute per-facility cell stats (expected completion + P(on-time))."""
    tray_idx = posterior.tray_type_ids.index(tray_type_id)
    cells: list[FacilityCell] = []
    for f_idx, f_id in enumerate(posterior.facility_ids):
        metadata = FACILITY_METADATA.get(f_id, {"name": f_id, "profile": ""})
        cells.append(
            FacilityCell(
                facility_id=f_id,
                name=metadata["name"],
                profile=metadata["profile"],
                expected_completion_min=expected_completion_min(posterior, f_idx, tray_idx, is_peak),
                p_on_time=p_on_time(posterior, f_idx, tray_idx, is_peak, deadline_min, rng),
            )
        )
    return cells


def _build_policy_decisions(
    posterior: Posterior,
    body: DecideRequest,
    is_peak: int,
    rng: np.random.Generator,
) -> list[PolicyDecision]:
    """Run all three policies and package their choices for the response."""
    va = variance_aware(posterior, body.tray_type_id, is_peak, body.deadline_min, rng)
    mo = mean_only(posterior, body.tray_type_id, is_peak)
    pr = proximity(posterior, body.client_id)
    return [
        PolicyDecision(
            policy_id=va.policy_id,
            facility_id=va.facility_id,
            score=va.score,
            score_metric="p_on_time",
            candidate_scores=va.candidate_scores,
        ),
        PolicyDecision(
            policy_id=mo.policy_id,
            facility_id=mo.facility_id,
            score=mo.score,
            score_metric="expected_completion_min",
            candidate_scores=mo.candidate_scores,
        ),
        PolicyDecision(
            policy_id=pr.policy_id,
            facility_id=pr.facility_id,
            score=pr.score,
            score_metric=None,
            candidate_scores=pr.candidate_scores,
        ),
    ]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app.

    Parameters
    ----------
    settings : Settings | None
        Optional pre-built settings. Defaults to environment-loaded settings.

    Returns
    -------
    FastAPI
        The configured app.
    """
    cfg = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.posterior = load(str(cfg.model_path))
        app.state.rng = np.random.default_rng(cfg.seed)
        yield

    app = FastAPI(title="routing", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @app.post("/decide")
    async def decide(
        body: DecideRequest,
        posterior: PosteriorDep,
        rng: RngDep,
    ) -> DecideResponse:
        """Score every facility for the cell + run the three routing policies."""
        is_peak = _is_peak(body.hour_of_pickup)
        return DecideResponse(
            facilities=_build_facility_cells(posterior, body.tray_type_id, is_peak, body.deadline_min, rng),
            policies=_build_policy_decisions(posterior, body, is_peak, rng),
        )

    @app.get("/operations/tray-states")
    def operations_tray_states() -> TrayStatesResponse:
        """Return the most recently updated tray rows from the projector store."""
        return fetch_tray_states(cfg.postgres_dsn, cfg.operations_limit)

    @app.get("/operations/recent-journeys")
    def operations_recent_journeys() -> RecentJourneysResponse:
        """Return the most recently delivered journey rows from the projector store."""
        return fetch_recent_journeys(cfg.postgres_dsn, cfg.operations_limit)

    return app
