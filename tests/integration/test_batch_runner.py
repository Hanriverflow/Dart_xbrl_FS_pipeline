from __future__ import annotations


def test_fixture_wiring_for_integration(
    sample_analysis_output, temp_output_dir
) -> None:
    assert sample_analysis_output.rcept_no
    assert temp_output_dir.exists()
