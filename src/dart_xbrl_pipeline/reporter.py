from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import AnalysisOutput


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


def save_outputs(result: AnalysisOutput, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{result.rcept_no}_analysis.json"
    md_path = output_dir / f"{result.rcept_no}_analysis.md"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
