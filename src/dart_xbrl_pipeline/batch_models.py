from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ReportType


class BatchJobState(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class BatchJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    corp_name: str
    corp_code: str | None = None
    date: str | None = None
    report_type: ReportType
    state: BatchJobState = BatchJobState.queued
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    output_paths: dict[str, Path] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, value: ReportType) -> ReportType:
        allowed = {"annual", "semiannual", "q1", "q3"}
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"report_type must be one of: {allowed_text}")
        return value


class BatchConfig(BaseModel):
    jobs: list[BatchJob] = Field(default_factory=list)
    max_workers: int = 4
    retry_failed: bool = False

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class BatchJobResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    skipped: int
    duration_sec: float
    jobs: list[BatchJob] = Field(default_factory=list)
    failures: list[dict[str, object]] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
