"""Tests for the routing CLI."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from routing.cli import main


def test_main_group_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "fit" in result.output
    assert "backtest" in result.output


def test_fit_then_backtest_end_to_end(tmp_path: Path, sample_parquet_path: Path) -> None:
    runner = CliRunner()
    model_path = tmp_path / "model.npz"
    fit_result = runner.invoke(
        main,
        [
            "fit",
            "--in",
            str(sample_parquet_path),
            "--out",
            str(model_path),
            "--draws",
            "50",
            "--tune",
            "50",
            "--chains",
            "1",
            "--seed",
            "0",
        ],
    )
    assert fit_result.exit_code == 0, fit_result.output
    assert model_path.is_file()

    backtest_result = runner.invoke(
        main,
        ["backtest", "--model", str(model_path), "--n", "100", "--seed", "1"],
    )
    assert backtest_result.exit_code == 0, backtest_result.output
    assert "variance-aware" in backtest_result.output
    assert "lift:" in backtest_result.output
