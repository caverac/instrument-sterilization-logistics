"""Configuration for the ingest service, loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables.

    Variables are prefixed ``INGEST_`` (e.g. ``INGEST_KAFKA_BROKERS``).
    """

    model_config = SettingsConfigDict(
        env_prefix="INGEST_",
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
        description="Target Kafka topic for published events.",
    )
