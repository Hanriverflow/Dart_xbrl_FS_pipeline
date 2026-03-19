from __future__ import annotations
# pyright: reportMissingImports=false

import json
from pathlib import Path
from typing import Literal

import pytest

from dart_xbrl_pipeline.batch_models import BatchConfig, BatchJob, BatchJobState
from dart_xbrl_pipeline.batch_runner import BatchRunner
from dart_xbrl_pipeline.models import AnalysisOutput


def _job(
    job_id: str,
    corp_name: str,
    report_type: Literal["annual", "semiannual", "q1", "q3"] = "annual",
) -> BatchJob:
    return BatchJob(
        job_id=job_id,
        corp_name=corp_name,
        corp_code="00000000",
        date="2025-12-31",
        report_type=report_type,
    )


def _analysis_output(corp_name: str, output_root: Path) -> AnalysisOutput:
    raw_dir = output_root / "raw"
    parsed_dir = output_root / "parsed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / f"{corp_name}.zip"
    zip_path.write_bytes(b"zip")
    return AnalysisOutput(
        corp_name=corp_name,
        rcept_no=f"{corp_name}-001",
        report_name="사업보고서",
        filing_date="20251231",
        xbrl_zip_path=zip_path,
        extracted_dir=parsed_dir,
        income_statement_metrics=[],
        note_hits=[],
        summary=["ok"],
        diagnostics={"mock": True},
    )


def test_run_executes_all_jobs_and_writes_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = BatchConfig(
        jobs=[
            _job("job-1", "corp-a"),
            _job("job-2", "corp-b", "semiannual"),
            _job("job-3", "corp-c", "q1"),
        ],
        max_workers=2,
    )

    def fake_run_analysis(
        corp_name: str,
        corp_code: str | None,
        date: str | None,
        report_type: str,
        output_root: Path,
    ) -> AnalysisOutput:
        assert corp_code == "00000000"
        assert date == "2025-12-31"
        assert report_type in {"annual", "semiannual", "q1"}
        return _analysis_output(corp_name, output_root)

    def fake_save_outputs(result: AnalysisOutput, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{result.corp_name}.json"
        md_path = output_dir / f"{result.corp_name}.md"
        json_path.write_text("{}", encoding="utf-8")
        md_path.write_text("# test", encoding="utf-8")
        return {"json": json_path, "markdown": md_path}

    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.run_analysis", fake_run_analysis
    )
    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.save_outputs", fake_save_outputs
    )
    runner = BatchRunner(config=config, output_dir=tmp_path / "reports")

    result = runner.run()

    assert result.total == 3
    assert result.succeeded == 3
    assert result.failed == 0
    assert result.skipped == 0
    assert runner.state_path.exists()
    assert runner.summary_path.exists()

    state_payload = json.loads(runner.state_path.read_text(encoding="utf-8"))
    assert state_payload["batch_id"] == runner.batch_id
    assert len(state_payload["jobs"]) == 3
    assert {item["state"] for item in state_payload["jobs"]} == {"succeeded"}


def test_retry_failed_retries_only_failed_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = BatchConfig(
        jobs=[
            _job("job-1", "corp-a"),
            _job("job-2", "corp-b"),
            _job("job-3", "corp-c"),
        ],
        max_workers=2,
    )
    attempts: dict[str, int] = {"corp-a": 0, "corp-b": 0, "corp-c": 0}
    fail_b = {"enabled": True}

    def fake_run_analysis(
        corp_name: str,
        corp_code: str | None,
        date: str | None,
        report_type: str,
        output_root: Path,
    ) -> AnalysisOutput:
        attempts[corp_name] += 1
        if corp_name == "corp-b" and fail_b["enabled"]:
            raise RuntimeError("temporary failure")
        return _analysis_output(corp_name, output_root)

    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.run_analysis", fake_run_analysis
    )
    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.save_outputs",
        lambda result, output_dir: {
            "json": output_dir / "a.json",
            "markdown": output_dir / "a.md",
        },
    )
    monkeypatch.setattr(BatchRunner, "DEFAULT_MAX_ATTEMPTS", 1)

    runner = BatchRunner(config=config, output_dir=tmp_path / "reports")
    first = runner.run()

    assert first.succeeded == 2
    assert first.failed == 1
    assert attempts == {"corp-a": 1, "corp-b": 1, "corp-c": 1}

    fail_b["enabled"] = False
    second = runner.retry_failed()

    assert second.succeeded == 3
    assert second.failed == 0
    assert attempts == {"corp-a": 1, "corp-b": 2, "corp-c": 1}


def test_load_state_resumes_and_skips_completed_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reports_dir = tmp_path / "reports"
    jobs = [_job("job-1", "corp-a"), _job("job-2", "corp-b")]

    fail_b = {"enabled": True}

    def flaky_run_analysis(
        corp_name: str,
        corp_code: str | None,
        date: str | None,
        report_type: str,
        output_root: Path,
    ) -> AnalysisOutput:
        if corp_name == "corp-b" and fail_b["enabled"]:
            raise RuntimeError("first pass failure")
        return _analysis_output(corp_name, output_root)

    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.run_analysis", flaky_run_analysis
    )
    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.save_outputs",
        lambda result, output_dir: {
            "json": output_dir / "a.json",
            "markdown": output_dir / "a.md",
        },
    )
    monkeypatch.setattr(BatchRunner, "DEFAULT_MAX_ATTEMPTS", 1)

    first_runner = BatchRunner(config=BatchConfig(jobs=jobs), output_dir=reports_dir)
    first_result = first_runner.run()
    assert first_result.succeeded == 1
    assert first_result.failed == 1

    fail_b["enabled"] = False
    called: list[str] = []

    def resumed_run_analysis(
        corp_name: str,
        corp_code: str | None,
        date: str | None,
        report_type: str,
        output_root: Path,
    ) -> AnalysisOutput:
        called.append(corp_name)
        return _analysis_output(corp_name, output_root)

    monkeypatch.setattr(
        "dart_xbrl_pipeline.batch_runner.run_analysis", resumed_run_analysis
    )

    resumed_jobs = [_job("job-1", "corp-a"), _job("job-2", "corp-b")]
    resumed_runner = BatchRunner(
        config=BatchConfig(jobs=resumed_jobs),
        output_dir=reports_dir,
    )
    resumed_result = resumed_runner.run()

    assert resumed_result.succeeded == 2
    assert resumed_result.failed == 0
    assert resumed_result.skipped == 1
    assert called == ["corp-b"]


def test_keyboard_interrupt_is_handled_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = BatchConfig(jobs=[_job("job-1", "corp-a")], max_workers=1)
    runner = BatchRunner(config=config, output_dir=tmp_path / "reports")

    def interrupted_run_single(job: BatchJob) -> BatchJob:
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_single", interrupted_run_single)

    result = runner.run()

    assert result.total == 1
    assert result.succeeded == 0
    assert result.failed == 0
    assert result.skipped == 1
    assert runner.state_path.exists()
    payload = json.loads(runner.state_path.read_text(encoding="utf-8"))
    assert payload["jobs"][0]["state"] in {BatchJobState.queued, "queued"}
