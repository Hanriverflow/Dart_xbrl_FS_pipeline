from __future__ import annotations

from dart_xbrl_pipeline.xbrl_parser import (
    extract_income_statement_metrics,
    extract_note_hits,
)


def test_extract_income_statement_metrics_with_sample_fixture(sample_xbrl_dir) -> None:
    metrics = extract_income_statement_metrics(sample_xbrl_dir)
    metric_map = {metric.account_name: metric for metric in metrics}
    assert "매출액" in metric_map
    assert metric_map["매출액"].current_amount == 100000000.0


def test_extract_note_hits_with_sample_fixture(sample_xbrl_dir) -> None:
    keyword_map = {"revenue": ["Revenue"]}
    hits = extract_note_hits(sample_xbrl_dir, keyword_map)
    assert hits
    assert hits[0].category == "revenue"
