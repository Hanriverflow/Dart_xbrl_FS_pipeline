from __future__ import annotations

from typing import Any


def test_sample_config_fixture_structure(sample_config: dict[str, Any]) -> None:
    assert "reprt_codes" in sample_config
    assert sample_config["reprt_codes"]["annual"] == "11011"
    assert "analysis" in sample_config
