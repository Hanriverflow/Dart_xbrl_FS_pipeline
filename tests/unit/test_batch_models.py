from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from dart_xbrl_pipeline.batch_models import (
    BatchConfig,
    BatchJob,
    BatchJobResult,
    BatchJobState,
)


def test_batch_job_auto_generates_job_id() -> None:
    job = BatchJob(corp_name="Sample Corp", report_type="annual")

    assert isinstance(job.job_id, str)
    assert job.job_id
    assert job.state is BatchJobState.queued


def test_batch_job_rejects_invalid_report_type() -> None:
    with pytest.raises(ValidationError):
        _ = BatchJob(corp_name="Sample Corp", report_type=cast(Any, "monthly"))


def test_batch_config_defaults() -> None:
    config = BatchConfig(jobs=[BatchJob(corp_name="Corp A", report_type="q1")])

    assert config.max_workers == 4
    assert config.retry_failed is False
    assert len(config.jobs) == 1


def test_batch_job_result_json_roundtrip() -> None:
    job = BatchJob(
        corp_name="Sample Corp",
        corp_code="00123456",
        date="2026-03-19",
        report_type="semiannual",
        state=BatchJobState.succeeded,
        output_paths={"json": Path("reports/sample.json")},
    )
    result = BatchJobResult(
        total=1,
        succeeded=1,
        failed=0,
        skipped=0,
        duration_sec=12.5,
        jobs=[job],
        failures=[],
    )

    payload = result.model_dump(mode="json")
    assert isinstance(payload["jobs"][0]["created_at"], str)
    assert Path(payload["jobs"][0]["output_paths"]["json"]) == Path(
        "reports/sample.json"
    )

    loaded = BatchJobResult.model_validate_json(result.model_dump_json())
    assert loaded.total == 1
    assert loaded.jobs[0].corp_name == "Sample Corp"
    assert loaded.jobs[0].state is BatchJobState.succeeded
