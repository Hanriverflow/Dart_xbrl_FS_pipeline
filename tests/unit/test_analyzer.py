from __future__ import annotations

from pathlib import Path

import pytest

from dart_xbrl_pipeline.insight_models import ProfitabilityMemo
from dart_xbrl_pipeline.analyzer import pick_filing, resolve_llm_provider
from dart_xbrl_pipeline.models import (
    Filing,
    IncomeStatementMetric,
    NotesHit,
    PipelineExecutionOptions,
)
from dart_xbrl_pipeline.note_models import NoteTable, NoteTablesOutput, UnitType


class FakeOpenDartClient:
    def find_corp_code_by_name(self, corp_name: str, cache_dir: Path) -> str:
        assert corp_name == "테스트기업"
        assert cache_dir.name == "raw"
        return "00000000"

    def search_filings(
        self,
        corp_code: str | None = None,
        bgn_de: str | None = None,
        end_de: str | None = None,
        **_: object,
    ) -> list[Filing]:
        assert corp_code == "00000000"
        assert bgn_de == "20251231"
        assert end_de == "20251231"
        return [
            Filing(
                corp_name="테스트기업",
                corp_code="00000000",
                report_name="사업보고서",
                rcept_no="20260321000001",
                rcept_dt="20251231",
            )
        ]

    def download_xbrl_zip(self, rcept_no: str, reprt_code: str, output_dir: Path) -> Path:
        assert rcept_no == "20260321000001"
        assert reprt_code == "11011"
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / "sample.zip"
        zip_path.write_bytes(b"zip")
        return zip_path

    def extract_zip(self, zip_path: Path, output_dir: Path) -> Path:
        assert zip_path.exists()
        extracted_dir = output_dir / "sample"
        extracted_dir.mkdir(parents=True, exist_ok=True)
        return extracted_dir


class FakeNoteTableParser:
    def __init__(self, *, corp_name: str, rcept_no: str, debug_dir: Path | None = None):
        assert corp_name == "테스트기업"
        assert rcept_no == "20260321000001"
        assert debug_dir is not None

    def parse_directory(self, xbrl_dir: Path) -> NoteTablesOutput:
        assert xbrl_dir.exists()
        return NoteTablesOutput(
            rcept_no="20260321000001",
            corp_name="테스트기업",
            tables=[
                NoteTable(
                    title="차입금 현황",
                    columns=["구분", "당기"],
                    rows=[],
                    unit=UnitType.WON,
                    period_context="CFY2025",
                    source_ref="note_1",
                    table_type="차입금",
                )
            ],
            extracted_at="2026-03-21T00:00:00Z",
        )


class FakeInsightWriter:
    seen_configs: list[dict[str, object]] = []

    def __init__(self, config: dict[str, object]):
        assert config["rcept_no"] == "20260321000001"
        self.__class__.seen_configs.append(config)
        self.prompt_template_path = config.get("prompt_template_path")
        self.token_usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "requests": 1,
            "cache_hits": 0,
        }

    def generate_memo(self, input_data) -> ProfitabilityMemo:
        assert input_data.tables
        assert input_data.metrics["매출액"] == 1000.0
        summary = "신용 메모" if self.prompt_template_path else "요약"
        return ProfitabilityMemo.model_validate(
            {
                "rcept_no": "20260321000001",
                "corp_name": "테스트기업",
                "report_type": "annual",
                "generated_at": "2026-03-21T00:00:00Z",
                "summary": summary,
                "claims": [],
                "risks": ["리스크"],
                "action_items": ["추가 확인 필요"],
            }
        )


def test_run_analysis_orchestrates_note_tables_and_memo(monkeypatch, tmp_path: Path) -> None:
    from dart_xbrl_pipeline import analyzer
    FakeInsightWriter.seen_configs = []
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    monkeypatch.setattr(
        analyzer,
        "load_settings",
        lambda: {
            "reprt_codes": {
                "annual": "11011",
                "semiannual": "11012",
                "q1": "11013",
                "q3": "11014",
            },
            "report_name_keywords": {
                "annual": ["사업보고서"],
                "semiannual": ["반기보고서"],
                "q1": ["분기보고서"],
                "q3": ["분기보고서"],
            },
            "analysis": {"profitability_keywords": {"finance": ["차입금"]}},
        },
    )
    monkeypatch.setattr(analyzer, "OpenDartClient", FakeOpenDartClient)
    monkeypatch.setattr(
        analyzer,
        "extract_income_statement_metrics",
        lambda root: [
            IncomeStatementMetric(
                account_name="매출액",
                current_amount=1000.0,
                prior_amount=900.0,
                matched_label="Revenue",
            )
        ],
    )
    monkeypatch.setattr(
        analyzer,
        "extract_note_hits",
        lambda root, keywords: [
            NotesHit(category="finance", keyword="차입금", text="차입금 주석")
        ],
    )
    monkeypatch.setattr(analyzer, "NoteTableParser", FakeNoteTableParser)
    monkeypatch.setattr(analyzer, "InsightWriter", FakeInsightWriter)

    artifacts = analyzer.run_analysis(
        corp_name="테스트기업",
        corp_code=None,
        date="2025-12-31",
        report_type="annual",
        output_root=tmp_path / "data",
        execution_options=PipelineExecutionOptions(
            with_note_tables=True,
            with_llm_memo=True,
        ),
    )

    assert artifacts.execution_options.with_note_tables is True
    assert artifacts.execution_options.with_llm_memo is True
    assert artifacts.note_tables is not None
    assert artifacts.memo is not None
    assert artifacts.credit_memo is not None
    assert artifacts.credit_memo.summary == "신용 메모"
    assert artifacts.token_usage["total_tokens"] == 300
    assert artifacts.analysis.rcept_no == "20260321000001"
    assert {config["provider"] for config in FakeInsightWriter.seen_configs} == {"openai"}


def test_resolve_llm_provider_auto_prefers_available_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert resolve_llm_provider(PipelineExecutionOptions(with_llm_memo=True)) == "openai"


def test_resolve_llm_provider_allows_explicit_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    assert (
        resolve_llm_provider(
            PipelineExecutionOptions(with_llm_memo=True, llm_provider="anthropic")
        )
        == "anthropic"
    )


def test_resolve_llm_provider_requires_selected_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_llm_provider(
            PipelineExecutionOptions(with_llm_memo=True, llm_provider="openai")
        )


def test_pick_filing_prefers_exact_corp_date_and_quarter_match() -> None:
    filings = [
        Filing(
            corp_name="테스트기업",
            corp_code="00000000",
            report_name="분기보고서 (2025.03)",
            rcept_no="20250331000001",
            rcept_dt="20250331",
        ),
        Filing(
            corp_name="테스트기업",
            corp_code="00000000",
            report_name="3분기보고서 (2025.09)",
            rcept_no="20250930000001",
            rcept_dt="20250930",
        ),
        Filing(
            corp_name="테스트기업홀딩스",
            corp_code="99999999",
            report_name="3분기보고서 (2025.09)",
            rcept_no="20250930000002",
            rcept_dt="20250930",
        ),
    ]

    selected = pick_filing(
        filings=filings,
        corp_name="테스트기업",
        corp_code="00000000",
        report_keywords=["3분기보고서", "분기보고서"],
        report_type="q3",
        date="2025-09-30",
    )

    assert selected.rcept_no == "20250930000001"
