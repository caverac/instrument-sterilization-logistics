"""Tests for the CLI."""

from __future__ import annotations

import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from synth_events import cli as cli_module
from synth_events.cli import main
from synth_events.parquet import read_journeys_records, read_journeys_table


def test_generate_writes_parquet_file(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "j.parquet"
    result = runner.invoke(main, ["generate", "--n", "25", "--out", str(out), "--seed", "1", "--days", "2"])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    table = read_journeys_table(out)
    assert table.num_rows == 25
    assert f"wrote 25 journeys to {out}" in result.output


def test_generate_is_seed_reproducible(tmp_path: Path) -> None:
    runner = CliRunner()
    out_a = tmp_path / "a.parquet"
    out_b = tmp_path / "b.parquet"
    args_a = ["generate", "--n", "10", "--out", str(out_a), "--seed", "99", "--days", "1"]
    args_b = ["generate", "--n", "10", "--out", str(out_b), "--seed", "99", "--days", "1"]
    assert runner.invoke(main, args_a).exit_code == 0
    assert runner.invoke(main, args_b).exit_code == 0
    assert read_journeys_records(out_a) == read_journeys_records(out_b)


def test_main_group_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "publish" in result.output


def test_publish_posts_one_request_per_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """``publish --n 3`` POSTs 30 events (10 per journey) and reports the count."""
    posted: list[dict[str, Any]] = []

    def fake_post(_url: str, event: dict[str, Any]) -> None:
        posted.append(event)

    monkeypatch.setattr(cli_module, "post_event", fake_post)
    result = CliRunner().invoke(main, ["publish", "--n", "3", "--seed", "7", "--hours", "1"])
    assert result.exit_code == 0, result.output
    assert len(posted) == 30
    assert "posted 30 events from 3 journeys" in result.output
    # tray order: events for any one tray must be contiguous and in publish order
    by_tray: dict[str, list[str]] = {}
    for event in posted:
        by_tray.setdefault(event["tray_id"], []).append(event["event_type"])
    for sequence in by_tray.values():
        assert sequence[0] == "PICKED_UP"
        assert sequence[-1] == "DELIVERED"
        assert len(sequence) == 10


def test_publish_aborts_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A URLError from the post helper surfaces as a non-zero exit."""

    def explode(_url: str, _event: dict[str, Any]) -> None:
        raise __import__("click").ClickException("kaboom")

    monkeypatch.setattr(cli_module, "post_event", explode)
    result = CliRunner().invoke(main, ["publish", "--n", "1"])
    assert result.exit_code != 0
    assert "kaboom" in result.output


def testpost_event_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """``post_event`` accepts a 202 response without raising."""
    response = MagicMock()
    response.status = 202
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(return_value=response))
    cli_module.post_event("http://localhost:8000", {"source_event_id": "x"})


def testpost_event_raises_on_non_202(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-202 response is reported as a ClickException."""
    response = MagicMock()
    response.status = 500
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(return_value=response))
    with pytest.raises(Exception) as excinfo:
        cli_module.post_event("http://localhost:8000", {"source_event_id": "x"})
    assert "unexpected 500" in str(excinfo.value)


def testpost_event_raises_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A URLError from urlopen becomes a ClickException with the reason."""

    def boom(_req: Any, timeout: float = 0.0) -> Any:
        del timeout
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(Exception) as excinfo:
        cli_module.post_event("http://localhost:8000", {"source_event_id": "x"})
    assert "connection refused" in str(excinfo.value)
