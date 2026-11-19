"""Portable paths in .env: ~ and relative paths resolve the same way on Windows, Linux and macOS."""
from __future__ import annotations

from pathlib import Path

from src.config import ROOT, Settings, resolve_path


def test_tilde_is_the_home_folder(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "~/nyc_taxi_data")
    assert Settings.from_env().data_dir == (Path.home() / "nyc_taxi_data").resolve()


def test_relative_paths_are_relative_to_the_repository(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "data")
    assert Settings.from_env().data_dir == (ROOT / "data").resolve()
    monkeypatch.setenv("DATA_DIR", "")
    assert Settings.from_env().data_dir == (ROOT / "data").resolve()


def test_absolute_paths_are_kept(tmp_path):
    assert resolve_path(str(tmp_path)) == tmp_path.resolve()


def test_months_go_back_to_the_first_tlc_parquet_file():
    import pytest

    from src.config import Month, months_for

    assert months_for("2010-01") == [Month(2010, 1), Month(2009, 1)]      # 2009-01 is the first TLC file
    assert months_for("2026-09") == [Month(2026, 9), Month(2025, 9)]
    with pytest.raises(ValueError, match="start in 2009-01"):
        months_for("2009-12")
    with pytest.raises(ValueError, match="future"):
        months_for("2999-01")
