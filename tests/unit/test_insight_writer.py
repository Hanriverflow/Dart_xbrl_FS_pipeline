from __future__ import annotations
# pyright: reportMissingImports=false

import json
from pathlib import Path
from typing import Any

import pytest

from dart_xbrl_pipeline.insight_models import InsightInput, NoteTable
from dart_xbrl_pipeline.note_models import UnitType
from dart_xbrl_pipeline.insight_writer import InsightWriter, InsightWriterError


class FakeLLMClient:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.call_count = 0

    def generate(self, prompt: str, config: dict[str, object]) -> dict[str, Any]:
        del prompt
        del config
        self.call_count += 1
        return self.payload


class FailingLLMClient:
    def generate(self, prompt: str, config: dict[str, object]) -> dict[str, object]:
        del prompt
        del config
        raise RuntimeError("simulated provider outage")


def _sample_input() -> InsightInput:
    return InsightInput(
        metrics={"매출총이익률": 35.2, "영업이익률": 12.1},
        tables=[
            NoteTable(
                table_id="tbl_profit_01",
                title="수익성 지표",
                columns=["계정", "당기", "전기"],
                rows=[],
                unit=UnitType.PERCENT,
                period_context="2025-12-31",
                source_ref="note_12",
            )
        ],
        highlights=["영업이익률 개선"],
    )


def _writer_config(tmp_path: Path) -> dict[str, object]:
    return {
        "rcept_no": "20260319000001",
        "corp_name": "테스트기업",
        "report_type": "annual",
        "cache_enabled": True,
        "cache_path": str(tmp_path / "insight_cache.json"),
    }


def test_generate_memo_with_valid_evidence_and_usage_tracking(tmp_path: Path) -> None:
    payload = {
        "text": json.dumps(
            {
                "summary": "매출총이익률과 영업이익률의 동시 개선이 관찰됩니다.",
                "claims": [
                    {
                        "claim": "영업이익률이 개선되어 수익성 레버리지가 강화되었습니다.",
                        "category": "핵심 개선 포인트",
                        "confidence": "high",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "tbl_profit_01",
                                "value": "영업이익률 12.1%",
                                "context": "당기 기준",
                            },
                            {
                                "type": "metric",
                                "ref_id": "영업이익률",
                                "value": "12.1",
                            },
                        ],
                    }
                ],
                "risks": ["원가 상승 시 마진 회복세 둔화 가능"],
                "action_items": ["제품 믹스별 마진 기여도 재검증"],
            },
            ensure_ascii=False,
        ),
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }
    client = FakeLLMClient(payload)
    writer = InsightWriter(llm_client=client, config=_writer_config(tmp_path))

    memo = writer.generate_memo(_sample_input())

    assert memo.summary.startswith("매출총이익률")
    assert memo.claims[0].evidence[0].ref_id == "tbl_profit_01"
    assert writer.token_usage["total_tokens"] == 200
    assert writer.token_usage["requests"] == 1


def test_generate_memo_uses_cache_for_identical_prompt(tmp_path: Path) -> None:
    payload = {
        "text": json.dumps(
            {
                "summary": "요약",
                "claims": [
                    {
                        "claim": "매출총이익률 개선",
                        "category": "핵심 개선 포인트",
                        "confidence": "medium",
                        "evidence": [
                            {
                                "type": "metric",
                                "ref_id": "매출총이익률",
                                "value": "35.2",
                            }
                        ],
                    }
                ],
                "risks": ["원가율 반등"],
                "action_items": ["추가 확인 필요"],
            },
            ensure_ascii=False,
        ),
        "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
    }
    client = FakeLLMClient(payload)
    writer = InsightWriter(llm_client=client, config=_writer_config(tmp_path))
    sample_input = _sample_input()

    _ = writer.generate_memo(sample_input)
    _ = writer.generate_memo(sample_input)

    assert client.call_count == 1
    assert writer.token_usage["cache_hits"] == 1


def test_generate_memo_rejects_unsupported_claims(tmp_path: Path) -> None:
    payload = {
        "text": json.dumps(
            {
                "summary": "요약",
                "claims": [
                    {
                        "claim": "지원되지 않는 근거 참조",
                        "category": "핵심 개선 포인트",
                        "confidence": "high",
                        "evidence": [
                            {
                                "type": "table",
                                "ref_id": "tbl_not_exist",
                                "value": "999",
                            }
                        ],
                    }
                ],
                "risks": ["리스크"],
                "action_items": ["추가 확인 필요"],
            },
            ensure_ascii=False,
        )
    }
    writer = InsightWriter(
        llm_client=FakeLLMClient(payload), config=_writer_config(tmp_path)
    )

    with pytest.raises(InsightWriterError, match="Unsupported assertion"):
        _ = writer.generate_memo(_sample_input())


def test_save_memo_writes_required_markdown_sections(tmp_path: Path) -> None:
    payload = {
        "text": json.dumps(
            {
                "summary": "요약",
                "claims": [
                    {
                        "claim": "영업이익률 개선",
                        "category": "핵심 개선 포인트",
                        "confidence": "low",
                        "evidence": [
                            {
                                "type": "account",
                                "ref_id": "계정",
                                "value": "개선",
                            }
                        ],
                    }
                ],
                "risks": ["수요 변동"],
                "action_items": ["세부 계정 재확인"],
            },
            ensure_ascii=False,
        )
    }
    writer = InsightWriter(
        llm_client=FakeLLMClient(payload), config=_writer_config(tmp_path)
    )
    memo = writer.generate_memo(_sample_input())

    output_path = tmp_path / "memo.md"
    writer.save_memo(memo, output_path)
    markdown = output_path.read_text(encoding="utf-8")

    assert "## 핵심 개선 포인트" in markdown
    assert "## 근거 수치" in markdown
    assert "## 리스크" in markdown
    assert "## 추가 확인 필요" in markdown
    assert "저신뢰 주장 재검증" in markdown


def test_generate_memo_wraps_provider_failures(tmp_path: Path) -> None:
    writer = InsightWriter(
        llm_client=FailingLLMClient(), config=_writer_config(tmp_path)
    )

    with pytest.raises(InsightWriterError, match="LLM request failed"):
        _ = writer.generate_memo(_sample_input())


def test_build_prompt_contains_strict_requirements(tmp_path: Path) -> None:
    payload = {
        "text": json.dumps(
            {
                "summary": "요약",
                "claims": [],
                "risks": ["추가 확인 필요"],
                "action_items": ["추가 확인 필요"],
            },
            ensure_ascii=False,
        )
    }
    writer = InsightWriter(
        llm_client=FakeLLMClient(payload), config=_writer_config(tmp_path)
    )

    prompt = writer._build_prompt(_sample_input())

    assert "근거 우선(Evidence-first)" in prompt
    assert "모든 claim은 evidence를 포함해야 함" in prompt
    assert "tbl_profit_01" in prompt
