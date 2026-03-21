from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from .insight_models import ProfitabilityMemo
from .note_models import NoteTablesOutput

ReportType: TypeAlias = Literal["annual", "semiannual", "q1", "q3"]
LLMProvider: TypeAlias = Literal["auto", "openai", "anthropic"]


class Filing(BaseModel):
    corp_name: str
    corp_code: str | None = None
    stock_code: str | None = None
    report_name: str
    rcept_no: str
    rcept_dt: str
    corp_cls: str | None = None
    flr_nm: str | None = None


class IncomeStatementMetric(BaseModel):
    account_name: str
    current_amount: float | None = None
    prior_amount: float | None = None
    source_context: str | None = None
    matched_label: str | None = None


class NotesHit(BaseModel):
    category: str
    keyword: str
    text: str
    context_ref: str | None = None
    unit_ref: str | None = None
    fact_value: str | None = None


class AnalysisOutput(BaseModel):
    corp_name: str
    rcept_no: str
    report_name: str
    filing_date: str
    xbrl_zip_path: Path
    extracted_dir: Path
    income_statement_metrics: list[IncomeStatementMetric] = Field(default_factory=list)
    note_hits: list[NotesHit] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class PipelineExecutionOptions(BaseModel):
    with_note_tables: bool = False
    with_llm_memo: bool = False
    llm_provider: LLMProvider = "auto"
    llm_model: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class PipelineArtifacts(BaseModel):
    schema_version: str = "pipeline_artifacts/v1"
    execution_options: PipelineExecutionOptions = Field(
        default_factory=PipelineExecutionOptions
    )
    analysis: AnalysisOutput
    note_tables: NoteTablesOutput | None = None
    memo: ProfitabilityMemo | None = None
    credit_memo: ProfitabilityMemo | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
