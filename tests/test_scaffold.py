"""Smoke tests del scaffold (Paso 1). Los 3 tests de consigna llegan en Paso 6."""

from pathlib import Path

import yaml

from src.config import get_settings

ROOT = Path(__file__).resolve().parents[1]


def test_yellow_schema_contract_exists_and_has_columns():
    path = ROOT / "contracts" / "yellow_schema.yaml"
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = {c["name"] for c in data["columns"]}
    assert "pu_location_id" in names
    assert "cbd_congestion_fee" in names


def test_dev_settings_skip_snowflake_by_default(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("SKIP_SNOWFLAKE", raising=False)
    # Forzar recarga: get_settings lee ENV
    settings = get_settings(mes="2025-03")
    assert settings.env == "dev"
    assert settings.skip_snowflake is True
    assert settings.s3_bucket
