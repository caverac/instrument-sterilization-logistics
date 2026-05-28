"""Tests for the Settings model."""

from __future__ import annotations

from pathlib import Path

import pytest

from routing.config import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.model_path == Path("model.npz")
    assert s.seed == 42


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTING_MODEL_PATH", "/tmp/other.npz")
    monkeypatch.setenv("ROUTING_SEED", "99")
    s = Settings()
    assert s.model_path == Path("/tmp/other.npz")
    assert s.seed == 99
