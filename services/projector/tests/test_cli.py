"""Tests for the projector CLI wiring."""

from __future__ import annotations

import signal
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from projector import cli
from projector.events import Event, EventType

EventFactory = Callable[..., Event]


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch every external dependency cli.run touches; return captured handles.

    Returned dict keys (populated once ``CliRunner().invoke(cli.main, ["run"])``
    finishes):
      - ``conn``: the mock psycopg connection
      - ``connect``: MagicMock for psycopg.connect
      - ``init_schema``, ``make_consumer``, ``make_deserializer``,
        ``run_consumer``: MagicMocks for the corresponding cli imports
      - ``signals``: signum -> registered handler
    """
    state: dict[str, Any] = {"signals": {}}
    fake_conn = MagicMock()
    fake_conn.transaction.return_value.__enter__ = MagicMock(return_value=None)
    fake_conn.transaction.return_value.__exit__ = MagicMock(return_value=False)
    state["conn"] = fake_conn

    connect_mock = MagicMock(return_value=fake_conn)
    init_schema_mock = MagicMock()
    make_consumer_mock = MagicMock(return_value=MagicMock())
    make_deserializer_mock = MagicMock(return_value=MagicMock())
    run_consumer_mock = MagicMock()

    state["connect"] = connect_mock
    state["init_schema"] = init_schema_mock
    state["make_consumer"] = make_consumer_mock
    state["make_deserializer"] = make_deserializer_mock
    state["run_consumer"] = run_consumer_mock

    def fake_signal(sig: int, handler: Callable[[int, Any], None]) -> None:
        state["signals"][sig] = handler

    monkeypatch.setattr("projector.cli.psycopg.connect", connect_mock)
    monkeypatch.setattr("projector.cli.init_schema", init_schema_mock)
    monkeypatch.setattr("projector.cli.make_consumer", make_consumer_mock)
    monkeypatch.setattr("projector.cli.make_deserializer", make_deserializer_mock)
    monkeypatch.setattr("projector.cli.run_consumer", run_consumer_mock)
    monkeypatch.setattr("projector.cli.signal.signal", fake_signal)
    return state


def test_run_command_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """``projector run`` exits zero after a stub run_consumer call returns."""
    state = _install_fakes(monkeypatch)
    result = CliRunner().invoke(cli.main, ["run"])
    assert result.exit_code == 0, result.output
    assert "subscribing to events" in result.output
    state["conn"].close.assert_called_once()


def test_run_command_passes_settings_to_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env-driven Settings flow through to the consumer + deserializer factories."""
    state = _install_fakes(monkeypatch)
    monkeypatch.setenv("PROJECTOR_KAFKA_BROKERS", "kafka.prod:9092")
    monkeypatch.setenv("PROJECTOR_KAFKA_GROUP_ID", "p1")
    monkeypatch.setenv("PROJECTOR_SCHEMA_REGISTRY_URL", "http://sr.prod:8081")

    result = CliRunner().invoke(cli.main, ["run"])
    assert result.exit_code == 0, result.output

    state["make_consumer"].assert_called_once_with("kafka.prod:9092", "p1")
    state["make_deserializer"].assert_called_once_with("http://sr.prod:8081")
    run_kwargs = state["run_consumer"].call_args.kwargs
    assert run_kwargs["topic"] == "events"


def test_signal_handler_sets_stop_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registered SIGINT handler flips should_stop to True."""
    state = _install_fakes(monkeypatch)
    result = CliRunner().invoke(cli.main, ["run"])
    assert result.exit_code == 0, result.output

    assert signal.SIGINT in state["signals"]
    assert signal.SIGTERM in state["signals"]
    should_stop: Callable[[], bool] = state["run_consumer"].call_args.kwargs["should_stop"]
    assert should_stop() is False

    state["signals"][signal.SIGINT](signal.SIGINT, None)
    assert should_stop() is True


def test_handle_closure_uses_transaction(monkeypatch: pytest.MonkeyPatch, make_event: EventFactory) -> None:
    """The handle closure wraps each event in a connection transaction."""
    state = _install_fakes(monkeypatch)
    result = CliRunner().invoke(cli.main, ["run"])
    assert result.exit_code == 0, result.output

    handle: Callable[[Event], None] = state["run_consumer"].call_args.kwargs["handle"]
    # CHECKED_IN exercises only upsert_tray, which works against a MagicMock
    # connection. Read paths like get_open_journey would require typed rows
    # back from the mock; the integration test covers those against real PG.
    handle(make_event(EventType.CHECKED_IN))
    state["conn"].transaction.assert_called()
