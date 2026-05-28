"""Configuration for the projector service, loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Variables are prefixed ``PROJECTOR_`` (e.g. ``PROJECTOR_KAFKA_BROKERS``).
    """

    model_config = SettingsConfigDict(
        env_prefix="PROJECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    kafka_brokers: str = Field(
        default="localhost:19092",
        description="Kafka bootstrap servers (comma-separated host:port pairs).",
    )
    schema_registry_url: str = Field(
        default="http://localhost:18081",
        description="Confluent-compatible Schema Registry URL.",
    )
    kafka_topic: str = Field(
        default="events",
        description="Kafka topic to consume.",
    )
    kafka_group_id: str = Field(
        default="projector",
        description="Kafka consumer group id. Shared across replicas of this service.",
    )
    postgres_dsn: str = Field(
        default="postgresql://projector:projector@localhost:5432/projector",
        description="Postgres connection string for the projection store.",
    )
    poll_timeout_sec: float = Field(
        default=1.0,
        ge=0.0,
        description="Kafka consumer poll timeout in seconds.",
    )
