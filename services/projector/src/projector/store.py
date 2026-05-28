"""Storage interface for projector state, plus an in-memory implementation.

Production uses :class:`projector.pg_store.PgStore`. Tests use
:class:`InMemoryStore`, which makes projection logic exercisable without a
running Postgres.
"""

from __future__ import annotations

from typing import Protocol

from projector.projections import JourneyRow, OpenJourney, TrayState


class Store(Protocol):
    """Storage contract for the four projection writes the projector needs."""

    def upsert_tray(self, tray: TrayState) -> None:
        """Write or replace the current-state row for a tray."""

    def get_open_journey(self, tray_id: str) -> OpenJourney | None:
        """Return the in-flight journey for a tray, or ``None`` if none."""

    def upsert_open_journey(self, journey: OpenJourney) -> None:
        """Write or replace an in-flight journey."""

    def delete_open_journey(self, tray_id: str) -> None:
        """Drop the in-flight journey for a tray (called on finalization)."""

    def insert_journey(self, journey: JourneyRow) -> None:
        """Append a finalized journey row."""


class InMemoryStore:
    """In-memory store satisfying :class:`Store`. Intended for tests.

    State is held in plain dicts and a list -- no concurrency control. Reset
    by constructing a new instance.
    """

    def __init__(self) -> None:
        """Initialise empty in-memory state."""
        self.trays: dict[str, TrayState] = {}
        self.open_journeys: dict[str, OpenJourney] = {}
        self.journeys: list[JourneyRow] = []

    def upsert_tray(self, tray: TrayState) -> None:
        """Write or replace the tray row in-memory."""
        self.trays[tray.tray_id] = tray

    def get_open_journey(self, tray_id: str) -> OpenJourney | None:
        """Return the in-flight journey for a tray, if any."""
        return self.open_journeys.get(tray_id)

    def upsert_open_journey(self, journey: OpenJourney) -> None:
        """Write or replace the in-flight journey for a tray."""
        self.open_journeys[journey.tray_id] = journey

    def delete_open_journey(self, tray_id: str) -> None:
        """Drop the in-flight journey for a tray, if present."""
        self.open_journeys.pop(tray_id, None)

    def insert_journey(self, journey: JourneyRow) -> None:
        """Append a finalized journey row."""
        self.journeys.append(journey)
