from __future__ import annotations
# pyright: reportMissingImports=false

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from dart_xbrl_pipeline.models import AnalysisOutput


@pytest.fixture
def sample_config() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_config.yaml"
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        return yaml.safe_load(fixture_file)


@pytest.fixture
def sample_xbrl_dir(tmp_path: Path) -> Path:
    source_dir = Path(__file__).parent / "fixtures" / "sample_xbrl"
    target_dir = tmp_path / "sample_xbrl"
    shutil.copytree(source_dir, target_dir)
    return target_dir


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def sample_analysis_output(
    temp_output_dir: Path, sample_xbrl_dir: Path
) -> AnalysisOutput:
    zip_path = temp_output_dir / "sample.zip"
    zip_path.write_bytes(b"mock-zip-content")
    return AnalysisOutput(
        corp_name="Sample Corp",
        rcept_no="20260319000032",
        report_name="사업보고서",
        filing_date="20251231",
        xbrl_zip_path=zip_path,
        extracted_dir=sample_xbrl_dir,
        income_statement_metrics=[],
        note_hits=[],
        summary=["Sample summary"],
        diagnostics={"reprt_code": "11011", "corp_code": "00000000"},
    )
