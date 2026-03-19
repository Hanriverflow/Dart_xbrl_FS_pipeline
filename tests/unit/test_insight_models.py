from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from dart_xbrl_pipeline.insight_models import (
    EvidenceRef,
    EvidenceType,
    InsightInput,
    NoteTable,
    ProfitabilityClaim,
    ProfitabilityMemo,
)


def test_claim_without_evidence_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        _ = ProfitabilityClaim(
            claim="영업이익률이 개선되었습니다.",
            category="수익성",
            evidence=[],
            confidence="high",
        )


def test_evidence_ref_validates_with_table_id_and_value() -> None:
    evidence = EvidenceRef(type=EvidenceType.table, table_id="table_123", value="1,234")
    assert evidence.ref_id == "table_123"
    assert evidence.value == "1,234"


def test_evidence_ref_requires_ref_or_value() -> None:
    with pytest.raises(ValidationError):
        _ = EvidenceRef(type=EvidenceType.account, ref_id="", value="")


def test_profitability_memo_and_input_are_json_serializable() -> None:
    claim = ProfitabilityClaim(
        claim="매출총이익률이 전년 대비 상승했습니다.",
        category="수익성",
        evidence=[
            EvidenceRef(
                type=EvidenceType.metric,
                ref_id="gross_margin",
                value="35.2%",
                context="2025 vs 2024",
            )
        ],
        confidence="medium",
    )
    memo = ProfitabilityMemo(
        rcept_no="20260319000001",
        corp_name="테스트기업",
        report_type="annual",
        generated_at=datetime(2026, 3, 19, 10, 0, 0),
        claims=[claim],
        summary="핵심 수익성이 개선되었습니다.",
        risks=["원가 변동성 확대 가능성"],
        action_items=["고마진 제품 비중 확대"],
    )

    insight_input = InsightInput(
        metrics={"gross_margin": 35.2, "operating_margin": 12.1},
        tables=[
            NoteTable(
                table_id="table_123",
                title="손익 주요 지표",
                columns=["account", "value"],
                rows=[],
                unit="원",
                period_context="2025-12-31",
                source_ref="notes_001",
            )
        ],
        highlights=["영업이익 증가", "판관비율 개선"],
    )

    memo_json = memo.model_dump_json()
    insight_input_json = insight_input.model_dump_json()

    assert "20260319000001" in memo_json
    assert "gross_margin" in insight_input_json
