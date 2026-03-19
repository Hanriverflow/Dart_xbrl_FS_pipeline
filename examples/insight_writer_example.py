"""
Example: Using InsightWriter to generate 수익성 개선 포인트 memos.

This example demonstrates how to:
1. Create an InsightInput from analysis results
2. Configure InsightWriter with LLM client
3. Generate and validate a ProfitabilityMemo
4. Save the memo as markdown
"""

from __future__ import annotations
# pyright: reportMissingImports=false

from datetime import datetime
from pathlib import Path

from dart_xbrl_pipeline.insight_models import (
    EvidenceType,
    InsightInput,
    ProfitabilityClaim,
    ProfitabilityMemo,
)
from dart_xbrl_pipeline.insight_writer import InsightWriter
from dart_xbrl_pipeline.note_models import NoteTable, UnitType


def create_sample_input() -> InsightInput:
    """Create sample InsightInput from XBRL analysis results."""
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
        ],
        highlights=["영업이익률 개선", "원가율 안정화"],
    )


class ExampleLLMClient:
    """
    Example LLM client implementation.
    In production, replace with actual OpenAI, Anthropic, or other provider client.
    """

    def generate(self, prompt: str, config: dict) -> dict:
        """Generate LLM response (mock implementation for example)."""
        # In production, this would call actual LLM API
        import json

        # Mock response with valid evidence references
        mock_response = {
            "summary": "영업이익률 개선이 관찰되며 원가 구조도 안정화되었습니다.",
            "claims": [
                {
                    "claim": "영업이익률이 전년 대비 개선되었습니다",
                    "category": "핵심 개선 포인트",
                    "confidence": "high",
                    "evidence": [
                        {
                            "type": "metric",
                            "ref_id": "영업이익률",
                            "value": "12.1%",
                            "context": "당기 기준",
                        },
                        {
                            "type": "table",
                            "ref_id": "tbl_profit_001",
                            "value": "12.1%",
                        },
                    ],
                },
            ],
            "risks": ["원가 상승 가능성", "환율 변동성"],
            "action_items": ["분기별 원가율 모니터링", "환노출 현황 파악"],
        }

        return {
            "text": json.dumps(mock_response, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "total_tokens": 700,
            },
        }


def main():
    """Run the example."""
    print("=" * 60)
    print("InsightWriter Example: 수익성 개선 포인트 생성")
    print("=" * 60)

    # Step 1: Create input from analysis results
    print("\n[Step 1] Creating InsightInput from XBRL analysis...")
    insight_input = create_sample_input()
    print(f"  - Metrics: {list(insight_input.metrics.keys())}")
    print(f"  - Tables: {[t.table_id for t in insight_input.tables]}")
    print(f"  - Highlights: {insight_input.highlights}")

    # Step 2: Configure InsightWriter
    print("\n[Step 2] Configuring InsightWriter...")
    config = {
        "rcept_no": "20260319000001",
        "corp_name": "테스트기업",
        "report_type": "annual",
        "provider": "openai",  # or "anthropic"
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "cache_enabled": True,
        "cache_path": ".cache/insight_cache.json",
    }

    # Use example client (replace with real client in production)
    llm_client = ExampleLLMClient()
    writer = InsightWriter(llm_client=llm_client, config=config)
    print(f"  - Provider: {config['provider']}")
    print(f"  - Model: {config['model']}")
    print(f"  - Cache enabled: {config['cache_enabled']}")

    # Step 3: Generate memo
    print("\n[Step 3] Generating ProfitabilityMemo...")
    try:
        memo = writer.generate_memo(insight_input)
        print(f"  [OK] Generated memo with {len(memo.claims)} claims")
        print(f"  [OK] Summary: {memo.summary[:50]}...")

        # Validate evidence
        for claim in memo.claims:
            print(f"  - Claim: {claim.claim}")
            for evidence in claim.evidence:
                print(f"    └ Evidence: {evidence.type.value}={evidence.ref_id}")

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return

    # Step 4: Save as markdown
    print("\n[Step 4] Saving memo as markdown...")
    output_path = Path("reports/example_memo.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer.save_memo(memo, output_path)
    print(f"  [OK] Saved to: {output_path}")

    # Step 5: Print token usage
    print("\n[Step 5] Token usage statistics:")
    for key, value in writer.token_usage.items():
        print(f"  - {key}: {value}")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
