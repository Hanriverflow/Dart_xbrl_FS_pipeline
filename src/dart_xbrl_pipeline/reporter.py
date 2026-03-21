from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .insight_writer import InsightWriter
from .models import AnalysisOutput, PipelineArtifacts


def to_markdown(result: AnalysisOutput) -> str:
    lines: list[str] = []
    lines.append(f"# {result.corp_name} {result.report_name} 분석")
    lines.append("")
    lines.append(f"- 접수번호: {result.rcept_no}")
    lines.append(f"- 접수일자: {result.filing_date}")
    lines.append(f"- XBRL ZIP: {result.xbrl_zip_path}")
    lines.append(f"- 추출 디렉터리: {result.extracted_dir}")
    lines.append("")
    lines.append("## 요약")
    for item in result.summary:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 손익계산서 매칭")
    lines.append("| 계정 | 당기 | 전기 | 태그 |")
    lines.append("|---|---:|---:|---|")
    for metric in result.income_statement_metrics:
        lines.append(
            f"| {metric.account_name} | {metric.current_amount or ''} | {metric.prior_amount or ''} | {metric.matched_label or ''} |"
        )
    lines.append("")
    grouped = defaultdict(list)
    for hit in result.note_hits:
        grouped[hit.category].append(hit)
    lines.append("## 주석 키워드 적중")
    for category, hits in grouped.items():
        lines.append(f"### {category}")
        for hit in hits[:20]:
            lines.append(f"- [{hit.keyword}] {hit.text}")
        lines.append("")
    return "\n".join(lines)


def save_outputs(result: PipelineArtifacts, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = result.analysis

    analysis_json_path = output_dir / f"{analysis.rcept_no}_analysis.json"
    analysis_md_path = output_dir / f"{analysis.rcept_no}_analysis.md"
    analysis_json_path.write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    analysis_md_path.write_text(to_markdown(analysis), encoding="utf-8")

    saved_paths: dict[str, Path] = {
        "json": analysis_json_path,
        "markdown": analysis_md_path,
    }

    if result.note_tables is not None:
        note_tables_path = output_dir / f"{analysis.rcept_no}_note_tables.json"
        note_tables_path.write_text(
            result.note_tables.model_dump_json(indent=2), encoding="utf-8"
        )
        saved_paths["note_tables"] = note_tables_path

    if result.memo is not None:
        memo_path = output_dir / f"{analysis.rcept_no}_profitability_memo.md"
        memo_path.write_text(
            InsightWriter.memo_to_markdown(result.memo), encoding="utf-8"
        )
        saved_paths["profitability_memo"] = memo_path

    if result.credit_memo is not None:
        credit_memo_path = output_dir / f"{analysis.rcept_no}_credit_memo.md"
        credit_memo_path.write_text(
            InsightWriter.memo_to_markdown(
                result.credit_memo, title="신용/차환 리스크 메모"
            ),
            encoding="utf-8",
        )
        saved_paths["credit_memo"] = credit_memo_path

    manifest_path = output_dir / f"{analysis.rcept_no}_run_manifest.json"
    manifest_payload = {
        "schema_version": result.schema_version,
        "execution_options": result.execution_options.model_dump(),
        "corp_name": analysis.corp_name,
        "rcept_no": analysis.rcept_no,
        "report_name": analysis.report_name,
        "filing_date": analysis.filing_date,
        "artifacts": {key: str(path) for key, path in saved_paths.items()},
        "warnings": result.warnings,
        "token_usage": result.token_usage,
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    saved_paths["manifest"] = manifest_path
    return saved_paths
