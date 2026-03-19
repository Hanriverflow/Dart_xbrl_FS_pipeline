from __future__ import annotations

import logging
import os
import sys
import traceback
from importlib import import_module
from pathlib import Path
from typing import NoReturn

import httpx
import typer
import yaml
from rich import print
from rich.table import Table

from .analyzer import run_analysis
from .batch_models import BatchConfig, BatchJobResult
from .config import project_root
from .reporter import save_outputs

app = typer.Typer(help="OpenDART XBRL 기반 재무제표/주석 분석 CLI")


def handle_error(error: Exception, debug: bool) -> NoReturn:
    """에러를 처리하고 사용자 친화적인 메시지를 출력합니다."""
    if debug:
        print("\n[red]=== 상세 오류 정보 (디버그 모드) ===[/red]")
        traceback.print_exc()
        print("")

    # 에러 유형별 사용자 친화적인 메시지
    error_messages = {
        "missing_api_key": "[red]오류: OpenDART API 키가 설정되지 않았습니다.[/red]\n"
        "[yellow]해결 방법: .env 파일에 OPENDART_API_KEY를 설정하거나 환경변수로 설정하세요.[/yellow]",
        "company_not_found": "[red]오류: 회사를 찾을 수 없습니다.[/red]\n"
        "[yellow]해결 방법: 정확한 회사명을 입력했는지 확인하세요.[/yellow]",
        "filing_not_found": "[red]오류: 조건에 맞는 공시를 찾을 수 없습니다.[/red]\n"
        "[yellow]해결 방법: 날짜와 보고서 유형(annual/semiannual/q1/q3)을 확인하세요.[/yellow]",
        "network_error": "[red]오류: 네트워크 연결에 실패했습니다.[/red]\n"
        "[yellow]해결 방법: 인터넷 연결을 확인하고 다시 시도하세요.[/yellow]",
        "xbrl_download_error": "[red]오류: XBRL 파일 다운로드에 실패했습니다.[/red]\n"
        "[yellow]해결 방법: API 키 유효성과 공시 접수번호를 확인하세요.[/yellow]",
        "xbrl_parse_error": "[red]오류: XBRL 파일 파싱에 실패했습니다.[/red]\n"
        "[yellow]해결 방법: 다운로드된 파일이 손상되지 않았는지 확인하세요.[/yellow]",
        "file_io_error": "[red]오류: 파일 입출력 중 문제가 발생했습니다.[/red]\n"
        "[yellow]해결 방법: 디스크 공간과 파일 권한을 확인하세요.[/yellow]",
    }

    # 에러 유형 판별
    error_type = "unknown"
    error_msg = str(error)

    if isinstance(error, ValueError):
        if "OPENDART_API_KEY" in error_msg:
            error_type = "missing_api_key"
        elif "corp_code" in error_msg or "회사명" in error_msg:
            error_type = "company_not_found"
        elif "공시" in error_msg or "조건" in error_msg:
            error_type = "filing_not_found"
    elif isinstance(error, httpx.HTTPStatusError):
        error_type = "network_error"
    elif isinstance(error, httpx.ConnectError):
        error_type = "network_error"
    elif isinstance(error, httpx.TimeoutException):
        error_type = "network_error"
    elif isinstance(error, RuntimeError):
        if "XBRL" in error_msg or "다운로드" in error_msg:
            error_type = "xbrl_download_error"
    elif isinstance(error, (IOError, OSError, PermissionError)):
        error_type = "file_io_error"

    # 메시지 출력
    if error_type in error_messages:
        print(error_messages[error_type])
    else:
        print(f"[red]오류: {error_msg}[/red]")
        if not debug:
            print("[yellow]자세한 정보를 보려면 --debug 옵션을 사용하세요.[/yellow]")

    sys.exit(1)


def load_batch_config(
    job_file: Path, max_workers: int, retry_failed: bool
) -> BatchConfig:
    if not job_file.exists():
        raise FileNotFoundError(f"배치 작업 파일을 찾을 수 없습니다: {job_file}")

    with job_file.open("r", encoding="utf-8") as fp:
        raw_config = yaml.safe_load(fp) or {}

    if not isinstance(raw_config, dict):
        raise ValueError(
            "배치 작업 파일 형식이 올바르지 않습니다. YAML 객체여야 합니다."
        )

    raw_config["max_workers"] = max_workers
    raw_config["retry_failed"] = retry_failed
    return BatchConfig.model_validate(raw_config)


def print_batch_summary(result: BatchJobResult, summary_path: Path) -> None:
    print("[green]배치 실행 완료[/green]")

    table = Table(title="Batch Summary")
    table.add_column("항목", style="cyan")
    table.add_column("값", justify="right", style="white")
    table.add_row("Total", str(result.total))
    table.add_row("Succeeded", str(result.succeeded))
    table.add_row("Failed", str(result.failed))
    table.add_row("Skipped", str(result.skipped))
    table.add_row("Duration(sec)", f"{result.duration_sec:.3f}")
    print(table)

    if result.failures:
        print("[red]실패 작업[/red]")
        for failure in result.failures:
            job_id = failure.get("job_id", "unknown")
            corp_name = failure.get("corp_name", "unknown")
            error_message = failure.get("error_message", "")
            print(f"- {job_id} ({corp_name}): {error_message}")

    print(f"- summary: {summary_path}")


@app.command()
def analyze(
    corp_name: str = typer.Option(..., help="회사명 예: 하나마이크론"),
    corp_code: str | None = typer.Option(None, help="OpenDART 고유번호 8자리"),
    date: str | None = typer.Option(None, help="공시일자 YYYY-MM-DD 또는 YYYYMMDD"),
    report_type: str = typer.Option("annual", help="annual | semiannual | q1 | q3"),
    output_dir: Path = typer.Option(
        project_root() / "reports", help="결과 저장 디렉터리"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="상세 오류 정보(스택 트레이스) 표시"
    ),
):
    """XBRL 기반 재무제표 및 주석 분석을 실행합니다."""
    try:
        result = run_analysis(
            corp_name=corp_name,
            corp_code=corp_code,
            date=date,
            report_type=report_type,
            output_root=project_root() / "data",
        )
        saved = save_outputs(result, output_dir)
        print("[green]분석 완료[/green]")
        for key, path in saved.items():
            print(f"- {key}: {path}")
    except Exception as e:
        handle_error(e, debug)


@app.command()
def batch(
    job_file: Path = typer.Option(..., "--job-file", help="배치 작업 YAML 파일"),
    max_workers: int = typer.Option(4, "--max-workers", min=1, help="병렬 실행 수"),
    retry_failed: bool = typer.Option(
        False, "--retry-failed", help="실패한 작업만 재시도"
    ),
    with_note_tables: bool = typer.Option(
        False, "--with-note-tables", help="주석 테이블 파싱 포함"
    ),
    with_llm_memo: bool = typer.Option(
        False, "--with-llm-memo", help="LLM 메모 생성 포함"
    ),
    output_dir: Path = typer.Option(
        project_root() / "reports", help="결과 저장 디렉터리"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="상세 오류 정보(스택 트레이스) 표시"
    ),
):
    """YAML 기반 배치 작업을 실행합니다."""
    try:
        if debug:
            logging.basicConfig(level=logging.DEBUG)

        os.environ["DART_XBRL_WITH_NOTE_TABLES"] = "1" if with_note_tables else "0"
        os.environ["DART_XBRL_WITH_LLM_MEMO"] = "1" if with_llm_memo else "0"

        config = load_batch_config(
            job_file=job_file,
            max_workers=max_workers,
            retry_failed=retry_failed,
        )
        batch_runner_module = import_module("dart_xbrl_pipeline.batch_runner")
        batch_runner_cls = batch_runner_module.BatchRunner
        runner = batch_runner_cls(config=config, output_dir=output_dir)

        result = runner.retry_failed() if retry_failed else runner.run()
        print_batch_summary(result, runner.summary_path)
    except Exception as e:
        handle_error(e, debug)


if __name__ == "__main__":
    app()
