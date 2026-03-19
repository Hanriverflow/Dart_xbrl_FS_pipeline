from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import load_settings
from .models import AnalysisOutput, Filing
from .opendart import OpenDartClient
from .xbrl_parser import extract_income_statement_metrics, extract_note_hits


def pick_filing(filings: list[Filing], corp_name: str, report_keyword: str | None = None, date: str | None = None) -> Filing:
    filtered = [f for f in filings if corp_name in f.corp_name]
    if report_keyword:
        filtered = [f for f in filtered if report_keyword in f.report_name]
    if date:
        normalized = date.replace("-", "")
        filtered = [f for f in filtered if f.rcept_dt == normalized]
    if not filtered:
        raise ValueError("조건에 맞는 공시를 찾지 못했습니다.")
    return filtered[0]


def build_summary(metrics, note_hits):
    summary: list[str] = []
    metric_map = {m.account_name: m for m in metrics}
    if metric_map.get("매출액") and metric_map.get("영업이익"):
        revenue = metric_map["매출액"]
        op = metric_map["영업이익"]
        summary.append(
            f"매출액 current={revenue.current_amount}, prior={revenue.prior_amount}; 영업이익 current={op.current_amount}, prior={op.prior_amount}"
        )
    bucket = defaultdict(int)
    for hit in note_hits:
        bucket[hit.category] += 1
    for category, count in sorted(bucket.items()):
        summary.append(f"주석 키워드 적중: {category} {count}건")
    return summary


def run_analysis(
    corp_name: str,
    corp_code: str | None,
    date: str | None,
    report_type: str,
    output_root: Path,
) -> AnalysisOutput:
    settings = load_settings()
    client = OpenDartClient()
    reprt_code = settings["reprt_codes"][report_type]
    resolved_corp_code = corp_code or client.find_corp_code_by_name(corp_name, output_root / "raw")
    filings = client.search_filings(corp_code=resolved_corp_code, bgn_de=(date or "20200101").replace("-", ""), end_de=(date or "99991231").replace("-", ""))
    filing = pick_filing(
        filings=filings,
        corp_name=corp_name,
        report_keyword=settings["report_name_keywords"][report_type][0],
        date=date,
    )
    raw_dir = output_root / "raw"
    parsed_dir = output_root / "parsed"
    zip_path = client.download_xbrl_zip(filing.rcept_no, reprt_code, raw_dir)
    extracted_dir = client.extract_zip(zip_path, parsed_dir)
    metrics = extract_income_statement_metrics(extracted_dir)
    note_hits = extract_note_hits(extracted_dir, settings["analysis"]["profitability_keywords"])
    return AnalysisOutput(
        corp_name=filing.corp_name,
        rcept_no=filing.rcept_no,
        report_name=filing.report_name,
        filing_date=filing.rcept_dt,
        xbrl_zip_path=zip_path,
        extracted_dir=extracted_dir,
        income_statement_metrics=metrics,
        note_hits=note_hits,
        summary=build_summary(metrics, note_hits),
        diagnostics={"reprt_code": reprt_code, "corp_code": resolved_corp_code, "matched_filing": filing.model_dump()},
    )
