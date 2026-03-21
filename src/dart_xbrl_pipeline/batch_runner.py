from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .analyzer import run_analysis
from .batch_models import BatchConfig, BatchJob, BatchJobResult, BatchJobState
from .models import PipelineExecutionOptions
from .reporter import save_outputs

logger = logging.getLogger(__name__)


class BatchRunner:
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_BACKOFF_BASE_SEC = 1.0

    def __init__(
        self,
        config: BatchConfig,
        output_dir: Path,
        execution_options: PipelineExecutionOptions | None = None,
    ):
        self.config = config
        self.output_dir = output_dir
        self.execution_options = execution_options or PipelineExecutionOptions()
        self.batch_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.batch_dir = self.output_dir / "batch" / self.batch_id
        self.state_path = self.batch_dir / "state.json"
        self.summary_path = self.batch_dir / "summary.json"
        self._lock = threading.RLock()
        self._shutdown_requested = False
        self._loaded_existing_state = False

    def run(self) -> BatchJobResult:
        self.load_state()
        start = time.perf_counter()

        with self._lock:
            runnable = [
                job
                for job in self.config.jobs
                if job.state in {BatchJobState.queued, BatchJobState.failed}
            ]
            skipped_before_run = len(self.config.jobs) - len(runnable)

        if not runnable:
            result = self._build_result(
                time.perf_counter() - start,
                skipped_override=skipped_before_run,
            )
            self._write_summary(result)
            return result

        logger.info("Starting batch %s with %d jobs", self.batch_id, len(runnable))
        self._execute_jobs(runnable)

        skipped_override = None if self._shutdown_requested else skipped_before_run
        result = self._build_result(
            time.perf_counter() - start,
            skipped_override=skipped_override,
        )
        self._write_summary(result)
        return result

    def run_single(self, job: BatchJob) -> BatchJob:
        with self._lock:
            if self._shutdown_requested:
                return job
            job.state = BatchJobState.running
            if job.started_at is None:
                job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            self.save_state()

        last_error: Exception | None = None
        for attempt in range(1, self.DEFAULT_MAX_ATTEMPTS + 1):
            if self._shutdown_requested:
                break

            try:
                job_output_root = self.batch_dir / "jobs" / job.job_id / "data"
                report_output_dir = self.batch_dir / "jobs" / job.job_id / "reports"
                analysis_result = run_analysis(
                    corp_name=job.corp_name,
                    corp_code=job.corp_code,
                    date=job.date,
                    report_type=job.report_type,
                    output_root=job_output_root,
                    execution_options=self.execution_options,
                )
                saved_paths = save_outputs(analysis_result, report_output_dir)

                with self._lock:
                    job.output_paths = {
                        **saved_paths,
                        "xbrl_zip_path": analysis_result.analysis.xbrl_zip_path,
                        "extracted_dir": analysis_result.analysis.extracted_dir,
                    }
                    job.state = BatchJobState.succeeded
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = None
                    self.save_state()
                return job
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.DEFAULT_MAX_ATTEMPTS:
                    break

                backoff_sec = self.DEFAULT_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "Job %s failed on attempt %d/%d. Retrying in %.1fs: %s",
                    job.job_id,
                    attempt,
                    self.DEFAULT_MAX_ATTEMPTS,
                    backoff_sec,
                    exc,
                )
                time.sleep(backoff_sec)

        with self._lock:
            if self._shutdown_requested and job.state is BatchJobState.running:
                job.state = BatchJobState.queued
            else:
                job.state = BatchJobState.failed
                job.error_message = (
                    str(last_error) if last_error else "Batch interrupted"
                )
            job.completed_at = datetime.now(timezone.utc)
            self.save_state()
        return job

    def retry_failed(self) -> BatchJobResult:
        self.load_state()
        start = time.perf_counter()
        with self._lock:
            failed_jobs = [
                job for job in self.config.jobs if job.state is BatchJobState.failed
            ]
            self._shutdown_requested = False
            skipped_before_retry = len(self.config.jobs) - len(failed_jobs)

        if not failed_jobs:
            result = self._build_result(
                time.perf_counter() - start,
                skipped_override=skipped_before_retry,
            )
            self._write_summary(result)
            return result

        logger.info(
            "Retrying %d failed jobs in batch %s", len(failed_jobs), self.batch_id
        )
        for job in failed_jobs:
            with self._lock:
                job.state = BatchJobState.queued
                job.error_message = None
        self.save_state()

        self._execute_jobs(failed_jobs)
        skipped_override = None if self._shutdown_requested else skipped_before_retry
        result = self._build_result(
            time.perf_counter() - start,
            skipped_override=skipped_override,
        )
        self._write_summary(result)
        return result

    def save_state(self) -> None:
        with self._lock:
            self.batch_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "batch_id": self.batch_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "max_workers": self.config.max_workers,
                "retry_failed": self.config.retry_failed,
                "execution_options": self.execution_options.model_dump(),
                "jobs": [job.model_dump(mode="json") for job in self.config.jobs],
            }
            self._write_json_atomic(self.state_path, payload)

    def load_state(self) -> None:
        if self._loaded_existing_state:
            return

        if not self.state_path.exists():
            resume_state_path = self._find_resume_state_path()
            if resume_state_path is not None:
                self.state_path = resume_state_path
                self.batch_dir = resume_state_path.parent
                self.batch_id = self.batch_dir.name
                self.summary_path = self.batch_dir / "summary.json"

        if not self.state_path.exists():
            self.save_state()
            self._loaded_existing_state = True
            return

        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.batch_id = payload.get("batch_id", self.batch_id)
        self.batch_dir = self.output_dir / "batch" / self.batch_id
        self.state_path = self.batch_dir / "state.json"
        self.summary_path = self.batch_dir / "summary.json"

        loaded_jobs = [
            BatchJob.model_validate(item) for item in payload.get("jobs", [])
        ]
        loaded_by_id = {job.job_id: job for job in loaded_jobs}

        with self._lock:
            merged_jobs: list[BatchJob] = []
            for configured_job in self.config.jobs:
                restored_job = loaded_by_id.get(configured_job.job_id)
                merged = restored_job or configured_job
                if merged.state is BatchJobState.running:
                    merged.state = BatchJobState.queued
                merged_jobs.append(merged)
            self.config.jobs = merged_jobs
            self._loaded_existing_state = True

    def _find_resume_state_path(self) -> Path | None:
        batch_root = self.output_dir / "batch"
        if not batch_root.exists():
            return None

        configured_job_ids = {job.job_id for job in self.config.jobs}
        if not configured_job_ids:
            return None

        state_files = sorted(
            batch_root.glob("*/state.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for candidate in state_files:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                state_job_ids = {
                    item["job_id"]
                    for item in payload.get("jobs", [])
                    if isinstance(item, dict) and "job_id" in item
                }
                saved_execution_options = payload.get("execution_options", {})
                if (
                    state_job_ids == configured_job_ids
                    and saved_execution_options == self.execution_options.model_dump()
                ):
                    return candidate
            except (OSError, json.JSONDecodeError, TypeError, KeyError):
                continue

        return None

    def _execute_jobs(self, jobs: list[BatchJob]) -> None:
        futures: dict[Future[BatchJob], BatchJob] = {}
        max_workers = max(1, self.config.max_workers)
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for job in jobs:
                    futures[executor.submit(self.run_single, job)] = job

                completed = 0
                for future in as_completed(futures):
                    _ = future.result()
                    completed += 1
                    snapshot = self._build_result(0.0)
                    logger.info(
                        "Batch %s progress: %d/%d (succeeded=%d, failed=%d)",
                        self.batch_id,
                        completed,
                        len(jobs),
                        snapshot.succeeded,
                        snapshot.failed,
                    )
        except KeyboardInterrupt:
            with self._lock:
                self._shutdown_requested = True
            logger.warning("KeyboardInterrupt detected. Cancelling pending jobs...")
            for future in futures:
                future.cancel()
            self.save_state()

    def _build_result(
        self,
        duration_sec: float,
        skipped_override: int | None = None,
    ) -> BatchJobResult:
        with self._lock:
            jobs = list(self.config.jobs)
        succeeded = sum(1 for job in jobs if job.state is BatchJobState.succeeded)
        failed = sum(1 for job in jobs if job.state is BatchJobState.failed)
        skipped = (
            skipped_override
            if skipped_override is not None
            else len(jobs) - succeeded - failed
        )
        failures: list[dict[str, object]] = [
            {
                "job_id": job.job_id,
                "corp_name": job.corp_name,
                "error_message": job.error_message,
            }
            for job in jobs
            if job.state is BatchJobState.failed
        ]
        return BatchJobResult(
            total=len(jobs),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            duration_sec=round(duration_sec, 3),
            jobs=jobs,
            failures=failures,
        )

    def _write_summary(self, result: BatchJobResult) -> None:
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(self.summary_path, result.model_dump(mode="json"))

    @staticmethod
    def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        serialized = json.dumps(dict(payload), ensure_ascii=False, indent=2)
        with tmp_path.open("w", encoding="utf-8") as fp:
            fp.write(serialized)
            fp.flush()
            os.fsync(fp.fileno())
        tmp_path.replace(path)
