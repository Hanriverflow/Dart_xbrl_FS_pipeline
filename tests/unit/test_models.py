from __future__ import annotations

from pathlib import Path

from dart_xbrl_pipeline.models import AnalysisOutput


def test_sample_analysis_output_fixture(sample_analysis_output: AnalysisOutput) -> None:
    assert isinstance(sample_analysis_output, AnalysisOutput)
    assert sample_analysis_output.corp_name == "Sample Corp"
    assert isinstance(sample_analysis_output.xbrl_zip_path, Path)
    assert sample_analysis_output.extracted_dir.exists()
