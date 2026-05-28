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
