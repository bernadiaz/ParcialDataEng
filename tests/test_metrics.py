"""Formato de métricas Prometheus (sin Pushgateway)."""

from src.metrics import _sample, render_exposition


def test_metric_line_escapes_quotes():
    line = _sample(
        "nyc_taxi_ingest_last_status",
        1.0,
        {"archivo": 'a"b', "mes": "2025-03"},
    )
    assert 'archivo="a\\"b"' in line
    assert line.endswith(" 1.0")


def test_render_exposition_types_once():
    body = render_exposition(
        {
            "nyc_taxi_quality_rows_read": [
                'nyc_taxi_quality_rows_read{mes="2025-03"} 1',
                'nyc_taxi_quality_rows_read{mes="2024-03"} 2',
            ]
        }
    )
    assert body.count("# TYPE nyc_taxi_quality_rows_read gauge") == 1

