"""Integration tests validating acceptance criteria for InsightWriter.

Criteria:
- 0 unsupported claims in 5 sample outputs
- All claims have valid evidence references
- Memo follows required markdown format
- Proper error handling for LLM failures
"""

from __future__ import annotations
# pyright: reportMissingImports=false

import json
from pathlib import Path
from typing import Any

import pytest

from dart_xbrl_pipeline.insight_models import InsightInput, NoteTable
from dart_xbrl_pipeline.insight_writer import InsightWriter, InsightWriterError
from dart_xbrl_pipeline.note_models import UnitType


class MockLLMClient:
    """Configurable mock LLM client for testing various scenarios."""

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        self.responses = responses or []
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, config: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, "config": config})
        if self.call_count >= len(self.responses):
            raise RuntimeError("No more mock responses available")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


def create_sample_input_with_tables() -> InsightInput:
    """Create sample input with valid table and metric references."""
    return InsightInput(
        metrics={
            "매출총이익률": 35.2,
            "영업이익률": 12.1,
            "당기순이익률": 8.5,
            "roe": 15.3,
        },
        tables=[
            NoteTable(
                table_id="tbl_profit_001",
                title="수익성 지표",
                columns=["계정", "당기", "전기"],
                rows=[],
                unit=UnitType.PERCENT,
                period_context="2025-12-31",
                source_ref="note_12",
            ),
            NoteTable(
                table_id="tbl_cost_002",
                title="원가 구성",
                columns=["구분", "금액"],
                rows=[],
                unit=UnitType.MILLION_WON,
                period_context="2025-12-31",
                source_ref="note_08",
            ),
        ],
        highlights=["영업이익률 개선", "원가율 안정화"],
    )


def test_acceptance_criterion_1_valid_evidence_only(tmp_path: Path) -> None:
    """
    Sample 1: All claims have valid evidence references.
    Expected: 0 unsupported claims, all evidence valid.
    """
    mock_response = {
        "text": json.dumps(
            {
                "summary": "매출총이익률과 영업이익률 동시 개선 관찰",
                "claims": [
                    {
                        "claim": "영업이익률이 전년 대비 개선되었습니다",
                        "category": "핵심 개선 포인트",
                        "confidence": "high",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "tbl_profit_001",
                                "value": "12.1%",
                                "context": "당기",
                            },
                            {
                                "type": "metric",
                                "ref_id": "영업이익률",
                                "value": "12.1",
                            },
                        ],
                    },
                    {
                        "claim": "원가 구성이 안정화되었습니다",
                        "category": "핵심 개선 포인트",
                        "confidence": "medium",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "tbl_cost_002",
                                "value": "안정",
                                "context": "원가",
                            }
                        ],
                    },
                ],
                "risks": ["원가 상승 가능성"],
                "action_items": ["제품 믹스 분석"],
            },
            ensure_ascii=False,
        ),
        "usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
    }

    config = {
        "rcept_no": "20260101000001",
        "corp_name": "테스트기업1",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=MockLLMClient([mock_response]), config=config)
    memo = writer.generate_memo(create_sample_input_with_tables())

    # Validate 0 unsupported claims
    assert len(memo.claims) == 2
    for claim in memo.claims:
        assert len(claim.evidence) > 0, "Every claim must have evidence"

    # Validate evidence references exist
    for claim in memo.claims:
        for evidence in claim.evidence:
            assert evidence.ref_id, "Evidence must have ref_id"


def test_acceptance_criterion_2_rejects_unsupported_claim(tmp_path: Path) -> None:
    """
    Sample 2: Claims with unsupported table references.
    Expected: Rejection with InsightWriterError.
    """
    mock_response = {
        "text": json.dumps(
            {
                "summary": "요약",
                "claims": [
                    {
                        "claim": "지원되지 않는 테이블 참조",
                        "category": "핵심 개선 포인트",
                        "confidence": "high",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "non_existent_table_999",
                                "value": "999",
                            }
                        ],
                    }
                ],
                "risks": ["리스크"],
                "action_items": ["확인 필요"],
            },
            ensure_ascii=False,
        )
    }

    config = {
        "rcept_no": "20260101000002",
        "corp_name": "테스트기업2",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=MockLLMClient([mock_response]), config=config)

    with pytest.raises(InsightWriterError, match="Unsupported assertion"):
        writer.generate_memo(create_sample_input_with_tables())


def test_acceptance_criterion_3_empty_claims_handled(tmp_path: Path) -> None:
    """
    Sample 3: Empty claims list (conservative approach).
    Expected: Valid memo with defaults, no errors.
    """
    mock_response = {
        "text": json.dumps(
            {
                "summary": "추가 확인 필요",
                "claims": [],
                "risks": ["추가 확인 필요"],
                "action_items": ["추가 확인 필요"],
            },
            ensure_ascii=False,
        )
    }

    config = {
        "rcept_no": "20260101000003",
        "corp_name": "테스트기업3",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=MockLLMClient([mock_response]), config=config)
    memo = writer.generate_memo(create_sample_input_with_tables())

    # 0 claims = 0 unsupported claims
    assert len(memo.claims) == 0
    assert "추가 확인 필요" in memo.summary


def test_acceptance_criterion_4_mixed_confidence_with_risk_items(
    tmp_path: Path,
) -> None:
    """
    Sample 4: Mixed confidence levels with proper risk/action items.
    Expected: Valid memo, markdown includes all sections.
    """
    mock_response = {
        "text": json.dumps(
            {
                "summary": "수익성 개선 관찰, 일부 불확실성 존재",
                "claims": [
                    {
                        "claim": "ROE가 양호한 수준 유지",
                        "category": "핵심 개선 포인트",
                        "confidence": "high",
                        "evidence": [
                            {
                                "type": "metric",
                                "ref_id": "roe",
                                "value": "15.3%",
                            }
                        ],
                    },
                    {
                        "claim": "원가율 개선세 지속 중",
                        "category": "핵심 개선 포인트",
                        "confidence": "low",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "tbl_cost_002",
                                "value": "개선",
                            }
                        ],
                    },
                ],
                "risks": ["원재료 가격 변동성", "환율 리스크"],
                "action_items": ["분기별 원가율 추적", "환노출 현황 파악"],
            },
            ensure_ascii=False,
        )
    }

    config = {
        "rcept_no": "20260101000004",
        "corp_name": "테스트기업4",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=MockLLMClient([mock_response]), config=config)
    memo = writer.generate_memo(create_sample_input_with_tables())

    # Validate markdown format
    output_path = tmp_path / "memo4.md"
    writer.save_memo(memo, output_path)
    markdown = output_path.read_text(encoding="utf-8")

    # Required sections
    assert "## 핵심 개선 포인트" in markdown
    assert "## 근거 수치" in markdown
    assert "## 리스크" in markdown
    assert "## 추가 확인 필요" in markdown

    # Low confidence claims should trigger follow-up items
    assert "저신뢰 주장 재검증" in markdown

    # Validate 0 unsupported claims
    assert len(memo.claims) == 2
    for claim in memo.claims:
        assert len(claim.evidence) > 0


def test_acceptance_criterion_5_error_handling_for_llm_failure(tmp_path: Path) -> None:
    """
    Sample 5: LLM API failure scenario.
    Expected: Proper error handling with InsightWriterError.
    """

    class FailingLLMClient:
        def generate(self, prompt: str, config: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("API rate limit exceeded")

    config = {
        "rcept_no": "20260101000005",
        "corp_name": "테스트기업5",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=FailingLLMClient(), config=config)

    with pytest.raises(InsightWriterError, match="LLM request failed"):
        writer.generate_memo(create_sample_input_with_tables())


def test_comprehensive_five_sample_validation(tmp_path: Path) -> None:
    """
    Comprehensive test: Generate 5 samples and validate all acceptance criteria.
    """
    samples = [
        # Sample 1: Valid high-confidence claims
        {
            "text": json.dumps(
                {
                    "summary": "매출총이익률 개선",
                    "claims": [
                        {
                            "claim": "매출총이익률 상승",
                            "category": "핵심 개선 포인트",
                            "confidence": "high",
                            "evidence": [
                                {
                                    "type": "metric",
                                    "ref_id": "매출총이익률",
                                    "value": "35.2%",
                                }
                            ],
                        }
                    ],
                    "risks": ["원가 상승"],
                    "action_items": ["원가 모니터링"],
                },
                ensure_ascii=False,
            )
        },
        # Sample 2: Valid medium-confidence with table reference
        {
            "text": json.dumps(
                {
                    "summary": "영업이익률 개선",
                    "claims": [
                        {
                            "claim": "영업이익률 개선",
                            "category": "핵심 개선 포인트",
                            "confidence": "medium",
                            "evidence": [
                                {
                                    "type": "table",
                                    "ref_id": "tbl_profit_001",
                                    "value": "12.1%",
                                }
                            ],
                        }
                    ],
                    "risks": ["시장 변동성"],
                    "action_items": ["시장 모니터링"],
                },
                ensure_ascii=False,
            )
        },
        # Sample 3: Multiple valid claims
        {
            "text": json.dumps(
                {
                    "summary": "복합 개선",
                    "claims": [
                        {
                            "claim": "ROE 양호",
                            "category": "핵심 개선 포인트",
                            "confidence": "high",
                            "evidence": [
                                {"type": "metric", "ref_id": "roe", "value": "15.3%"}
                            ],
                        },
                        {
                            "claim": "당기순이익률 양호",
                            "category": "핵심 개선 포인트",
                            "confidence": "medium",
                            "evidence": [
                                {
                                    "type": "metric",
                                    "ref_id": "당기순이익률",
                                    "value": "8.5%",
                                }
                            ],
                        },
                    ],
                    "risks": ["리스크1", "리스크2"],
                    "action_items": ["액션1"],
                },
                ensure_ascii=False,
            )
        },
        # Sample 4: Empty claims (conservative)
        {
            "text": json.dumps(
                {
                    "summary": "추가 확인 필요",
                    "claims": [],
                    "risks": ["불확실성"],
                    "action_items": ["데이터 보완"],
                },
                ensure_ascii=False,
            )
        },
        # Sample 5: Low confidence with table reference
        {
            "text": json.dumps(
                {
                    "summary": "일부 개선 관찰",
                    "claims": [
                        {
                            "claim": "원가 구조 개선 가능성",
                            "category": "핵심 개선 포인트",
                            "confidence": "low",
                            "evidence": [
                                {
                                    "type": "table",
                                    "ref_id": "tbl_cost_002",
                                    "value": "구조",
                                }
                            ],
                        }
                    ],
                    "risks": ["추가 확인 필요"],
                    "action_items": ["상세 분석"],
                },
                ensure_ascii=False,
            )
        },
    ]

    client = MockLLMClient(samples)
    config = {
        "rcept_no": "20260101000000",
        "corp_name": "테스트기업",
        "report_type": "annual",
        "cache_enabled": False,
    }
    writer = InsightWriter(llm_client=client, config=config)
    input_data = create_sample_input_with_tables()

    # Generate 5 samples
    memos: list[Any] = []
    for i in range(5):
        memo = writer.generate_memo(input_data)
        memos.append(memo)

    # Validate: 0 unsupported claims across all samples
    total_claims = 0
    unsupported_claims = 0

    for memo in memos:
        total_claims += len(memo.claims)
        for claim in memo.claims:
            if not claim.evidence:
                unsupported_claims += 1

    # Assertions
    assert unsupported_claims == 0, f"Found {unsupported_claims} unsupported claims"
    assert total_claims > 0, "Should have generated some claims"

    # Validate markdown format for a sample
    output_path = tmp_path / "final_memo.md"
    writer.save_memo(memos[-1], output_path)
    markdown = output_path.read_text(encoding="utf-8")

    # Required sections present
    assert "# 수익성 개선 포인트" in markdown
    assert "## 핵심 개선 포인트" in markdown
    assert "## 근거 수치" in markdown
    assert "## 리스크" in markdown
    assert "## 추가 확인 필요" in markdown

    # Metadata present
    assert "접수번호:" in markdown
    assert "회사명:" in markdown
    assert "보고서 유형:" in markdown
