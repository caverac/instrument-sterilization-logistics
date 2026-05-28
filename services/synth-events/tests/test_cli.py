"""Tests for the CLI."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

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
