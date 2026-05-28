"""Configuration for the routing service, loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Variables are prefixed ``ROUTING_`` (e.g. ``ROUTING_MODEL_PATH``).
    """

    model_config = SettingsConfigDict(
        env_prefix="ROUTING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_path: Path = Field(
        default=Path("model.npz"),
        description="Path to the saved posterior produced by `routing fit`.",
    )
    seed: int = Field(
        default=42,
        description="RNG seed for the posterior-predictive sampling at decide time.",
    )
    postgres_dsn: str = Field(
        default="postgresql://projector:projector@localhost:5432/projector",
        description="Postgres DSN for the projector's projection store; read-only.",
    )
    operations_limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Row cap for the /operations endpoints.",
    )
    backtest_n: int = Field(
        default=3000,
        ge=10,
        le=20000,
        description="Pickups simulated at startup for the cached /backtest/summary response.",
    )
    backtest_seed: int = Field(
        default=100,
        description="RNG seed for the startup-cached backtest. Deterministic given posterior + seed + n.",
    )
