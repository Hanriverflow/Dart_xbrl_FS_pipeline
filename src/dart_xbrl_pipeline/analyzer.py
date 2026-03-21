from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path
import re

from tenacity import RetryError

from .config import load_settings, project_root
from .insight_models import InsightInput
from .insight_writer import InsightWriter
from .models import (
    AnalysisOutput,
    Filing,
    PipelineArtifacts,
    PipelineExecutionOptions,
)
from .note_table_parser import NoteTableParser
from .opendart import OpenDartClient
from .xbrl_parser import extract_income_statement_metrics, extract_note_hits


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _build_report_name_hints(report_type: str, date: str | None) -> list[str]:
    normalized_date = (date or "").replace("-", "")
    hints: list[str] = []
    if report_type == "annual":
        hints.extend(["사업보고서"])
    elif report_type == "semiannual":
        hints.extend(["반기보고서"])
    elif report_type == "q1":
        hints.extend(["1분기", "1분기보고서", "03", "031", "0331"])
    elif report_type == "q3":
        hints.extend(["3분기", "3분기보고서", "09", "093", "0930"])

    if normalized_date:
        hints.extend(
            [
                normalized_date[:6],
                normalized_date[:4] + "." + normalized_date[4:6],
                normalized_date[4:6],
            ]
        )
    return [hint for hint in hints if hint]


def _score_filing(
    filing: Filing,
    corp_name: str,
    corp_code: str | None,
    report_keywords: list[str],
    report_type: str,
    date: str | None,
) -> tuple[int, int, str]:
    score = 0
    normalized_corp_name = _normalize_text(corp_name)
    filing_corp_name = _normalize_text(filing.corp_name)
    report_name = filing.report_name
    normalized_report_name = _normalize_text(report_name)
    normalized_date = (date or "").replace("-", "")

    if filing_corp_name == normalized_corp_name:
        score += 1000
    elif normalized_corp_name in filing_corp_name:
        score += 300
    else:
        score -= 1000

    if corp_code and filing.corp_code == corp_code:
        score += 500

    if normalized_date:
        if filing.rcept_dt == normalized_date:
            score += 400
        else:
            score -= 200

    for keyword in report_keywords:
        normalized_keyword = _normalize_text(keyword)
        if normalized_keyword and normalized_keyword in normalized_report_name:
            score += 180

    for hint in _build_report_name_hints(report_type, date):
        if _normalize_text(hint) in normalized_report_name:
            score += 40

    if report_type == "q1" and "3분기" in report_name:
        score -= 120
    if report_type == "q3" and "1분기" in report_name:
        score -= 120

    if "정정" in report_name:
        score -= 80

    return score, int(filing.rcept_dt or "0"), filing.rcept_no


def pick_filing(
    filings: list[Filing],
    corp_name: str,
    corp_code: str | None = None,
    report_keywords: list[str] | None = None,
    report_type: str = "annual",
    date: str | None = None,
) -> Filing:
    keywords = report_keywords or []
    candidates = [
        filing
        for filing in filings
        if _score_filing(
            filing=filing,
            corp_name=corp_name,
            corp_code=corp_code,
            report_keywords=keywords,
            report_type=report_type,
            date=date,
        )[0]
        > 0
    ]
    if not candidates:
        raise ValueError("조건에 맞는 공시를 찾지 못했습니다.")
    ranked = sorted(
        candidates,
        key=lambda filing: _score_filing(
            filing=filing,
            corp_name=corp_name,
            corp_code=corp_code,
            report_keywords=keywords,
            report_type=report_type,
            date=date,
        ),
        reverse=True,
    )
    return ranked[0]


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


def build_insight_input(
    metrics: list,
    summary: list[str],
    note_tables,
) -> InsightInput:
    return InsightInput(
        metrics={
            metric.account_name: metric.current_amount
            for metric in metrics
            if metric.current_amount is not None
        },
        tables=note_tables.tables if note_tables is not None else [],
        highlights=summary,
    )


def merge_token_usage(*usage_maps: dict[str, int]) -> dict[str, int]:
    merged = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "requests": 0,
        "cache_hits": 0,
    }
    for usage_map in usage_maps:
        for key, value in usage_map.items():
            merged[key] = merged.get(key, 0) + int(value)
    return merged


def build_search_windows(date: str | None) -> list[tuple[str, str, str]]:
    if not date:
        return [("default", "20200101", "99991231")]

    normalized_date = date.replace("-", "")
    year = int(normalized_date[:4])
    return [
        ("exact", normalized_date, normalized_date),
        ("fiscal_fallback", f"{year}0101", f"{year + 1}1231"),
    ]


def search_filings_with_fallback(
    client: OpenDartClient,
    corp_code: str,
    date: str | None,
) -> tuple[list[Filing], str]:
    last_error: Exception | None = None
    for window_name, bgn_de, end_de in build_search_windows(date):
        try:
            filings = client.search_filings(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
            )
            return filings, window_name
        except RetryError as exc:
            last_error = exc
            cause = exc.last_attempt.exception()
            if (
                cause is not None
                and "조회된 데이타가 없습니다." in str(cause)
                and window_name != "fiscal_fallback"
            ):
                continue
            raise
    if last_error is not None:
        raise last_error
    raise ValueError("조건에 맞는 공시를 찾지 못했습니다.")


def resolve_llm_provider(options: PipelineExecutionOptions) -> str:
    provider = options.llm_provider
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if provider == "auto":
        if openai_key:
            return "openai"
        if anthropic_key:
            return "anthropic"
        raise ValueError(
            "LLM 메모를 생성하려면 OPENAI_API_KEY 또는 ANTHROPIC_API_KEY가 필요합니다."
        )

    if provider == "openai" and not openai_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
    if provider == "anthropic" and not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    return provider


def run_analysis(
    corp_name: str,
    corp_code: str | None,
    date: str | None,
    report_type: str,
    output_root: Path,
    execution_options: PipelineExecutionOptions | None = None,
) -> PipelineArtifacts:
    options = execution_options or PipelineExecutionOptions()
    settings = load_settings()
    client = OpenDartClient()
    reprt_code = settings["reprt_codes"][report_type]
    resolved_corp_code = corp_code or client.find_corp_code_by_name(
        corp_name, output_root / "raw"
    )
    filings, search_window = search_filings_with_fallback(
        client=client,
        corp_code=resolved_corp_code,
        date=date,
    )
    filing = pick_filing(
        filings=filings,
        corp_name=corp_name,
        corp_code=resolved_corp_code,
        report_keywords=settings["report_name_keywords"][report_type],
        report_type=report_type,
        date=date,
    )
    raw_dir = output_root / "raw"
    parsed_dir = output_root / "parsed"
    zip_path = client.download_xbrl_zip(filing.rcept_no, reprt_code, raw_dir)
    extracted_dir = client.extract_zip(zip_path, parsed_dir)
    metrics = extract_income_statement_metrics(extracted_dir)
    note_hits = extract_note_hits(
        extracted_dir, settings["analysis"]["profitability_keywords"]
    )
    analysis = AnalysisOutput(
        corp_name=filing.corp_name,
        rcept_no=filing.rcept_no,
        report_name=filing.report_name,
        filing_date=filing.rcept_dt,
        xbrl_zip_path=zip_path,
        extracted_dir=extracted_dir,
        income_statement_metrics=metrics,
        note_hits=note_hits,
        summary=build_summary(metrics, note_hits),
        diagnostics={
            "reprt_code": reprt_code,
            "corp_code": resolved_corp_code,
            "search_window": search_window,
            "matched_filing": filing.model_dump(),
        },
    )

    warnings: list[str] = []
    parsed_note_tables = None
    if options.with_note_tables or options.with_llm_memo:
        parsed_note_tables = NoteTableParser(
            corp_name=filing.corp_name,
            rcept_no=filing.rcept_no,
            debug_dir=output_root / "debug",
        ).parse_directory(extracted_dir)
        if not parsed_note_tables.tables:
            warnings.append("No note tables were extracted from the XBRL directory.")

    memo = None
    credit_memo = None
    token_usage: dict[str, int] = {}
    if options.with_llm_memo:
        llm_provider = resolve_llm_provider(options)
        base_model = options.llm_model
        profitability_writer = InsightWriter(
            config={
                "provider": llm_provider,
                "rcept_no": filing.rcept_no,
                "corp_name": filing.corp_name,
                "report_type": report_type,
                "cache_path": str(output_root / "cache" / "insight_cache.json"),
                **({"model": base_model} if base_model else {}),
            }
        )
        insight_input = build_insight_input(metrics, analysis.summary, parsed_note_tables)
        memo = profitability_writer.generate_memo(
            insight_input
        )
        credit_writer = InsightWriter(
            config={
                "provider": llm_provider,
                "rcept_no": filing.rcept_no,
                "corp_name": filing.corp_name,
                "report_type": report_type,
                "cache_path": str(output_root / "cache" / "credit_insight_cache.json"),
                "prompt_template_path": str(
                    project_root() / "config" / "credit_insight_prompt_template.txt"
                ),
                **({"model": base_model} if base_model else {}),
            }
        )
        credit_memo = credit_writer.generate_memo(
            build_insight_input(metrics, analysis.summary, parsed_note_tables)
        )
        token_usage = merge_token_usage(
            {key: int(value) for key, value in profitability_writer.token_usage.items()},
            {key: int(value) for key, value in credit_writer.token_usage.items()},
        )

    return PipelineArtifacts(
        execution_options=options,
        analysis=analysis,
        note_tables=parsed_note_tables if options.with_note_tables else None,
        memo=memo,
        credit_memo=credit_memo,
        token_usage=token_usage,
        warnings=warnings,
    )
