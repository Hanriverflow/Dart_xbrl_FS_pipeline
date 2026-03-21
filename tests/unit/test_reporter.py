from __future__ import annotations

import json

from dart_xbrl_pipeline.insight_models import ProfitabilityMemo
from dart_xbrl_pipeline.models import PipelineArtifacts, PipelineExecutionOptions
from dart_xbrl_pipeline.note_models import NoteTable, NoteTablesOutput, UnitType
from dart_xbrl_pipeline.reporter import save_outputs


def test_save_outputs_writes_manifest_note_tables_and_memo(
    sample_analysis_output,
    temp_output_dir,
) -> None:
    note_tables = NoteTablesOutput(
        rcept_no=sample_analysis_output.rcept_no,
        corp_name=sample_analysis_output.corp_name,
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
    memo = ProfitabilityMemo.model_validate(
        {
            "rcept_no": sample_analysis_output.rcept_no,
            "corp_name": sample_analysis_output.corp_name,
            "report_type": "annual",
            "generated_at": "2026-03-21T00:00:00Z",
            "summary": "요약",
            "claims": [],
            "risks": ["리스크"],
            "action_items": ["추가 확인 필요"],
        }
    )
    artifacts = PipelineArtifacts(
        execution_options=PipelineExecutionOptions(
            with_note_tables=True,
            with_llm_memo=True,
        ),
        analysis=sample_analysis_output,
        note_tables=note_tables,
        memo=memo,
        credit_memo=memo,
        token_usage={"total_tokens": 20, "requests": 1},
        warnings=["warning"],
    )

    saved = save_outputs(artifacts, temp_output_dir)

    assert saved["json"].exists()
    assert saved["markdown"].exists()
    assert saved["note_tables"].exists()
    assert saved["profitability_memo"].exists()
    assert saved["credit_memo"].exists()
    assert saved["manifest"].exists()

    manifest = json.loads(saved["manifest"].read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "pipeline_artifacts/v1"
    assert manifest["execution_options"]["with_note_tables"] is True
    assert manifest["execution_options"]["with_llm_memo"] is True
    assert "note_tables" in manifest["artifacts"]
    assert "profitability_memo" in manifest["artifacts"]
    assert "credit_memo" in manifest["artifacts"]


def test_save_outputs_preserves_profitability_memo_contract_for_credit_use_case(
    sample_analysis_output,
    temp_output_dir,
) -> None:
    note_tables = NoteTablesOutput(
        rcept_no=sample_analysis_output.rcept_no,
        corp_name=sample_analysis_output.corp_name,
        tables=[
            NoteTable(
                title="차입금 및 만기 구조",
                columns=["구분", "당기", "전기"],
                rows=[],
                unit=UnitType.MILLION_WON,
                period_context="CFY2025",
                source_ref="note_03",
                table_type="차입금",
            )
        ],
        extracted_at="2026-03-21T00:00:00Z",
    )
    memo = ProfitabilityMemo.model_validate(
        {
            "rcept_no": sample_analysis_output.rcept_no,
            "corp_name": sample_analysis_output.corp_name,
            "report_type": "annual",
            "generated_at": "2026-03-21T00:00:00Z",
            "summary": "차입금 만기, 이자비용, CAPEX, FX 민감도를 함께 점검해야 합니다.",
            "claims": [
                {
                    "claim": "차입금 만기 압박이 단기 유동성 관리 부담으로 이어질 수 있습니다.",
                    "category": "핵심 개선 포인트",
                    "confidence": "high",
                    "evidence": [
                        {
                            "type": "table",
                            "ref_id": "tbl_debt_001",
                            "value": "880.5",
                            "context": "당기",
                        }
                    ],
                },
                {
                    "claim": "이자비용과 CAPEX 집행은 현금흐름 압박 요인입니다.",
                    "category": "핵심 개선 포인트",
                    "confidence": "medium",
                    "evidence": [
                        {
                            "type": "metric",
                            "ref_id": "이자비용",
                            "value": "128.7",
                        },
                        {
                            "type": "table",
                            "ref_id": "tbl_debt_001",
                            "value": "차입금 및 만기 구조",
                            "context": "CAPEX",
                        },
                    ],
                }
            ],
            "risks": ["환율 변동성 확대", "이자비용 부담 확대"],
            "action_items": ["만기 구조 재점검", "CAPEX와 CFO 갭 추적"],
        }
    )
    artifacts = PipelineArtifacts(
        execution_options=PipelineExecutionOptions(
            with_note_tables=True,
            with_llm_memo=True,
        ),
        analysis=sample_analysis_output,
        note_tables=note_tables,
        memo=memo,
        credit_memo=memo,
        token_usage={"total_tokens": 20, "requests": 1},
        warnings=["credit-oriented content"],
    )

    saved = save_outputs(artifacts, temp_output_dir)

    assert saved["profitability_memo"].name.endswith("_profitability_memo.md")
    assert saved["credit_memo"].name.endswith("_credit_memo.md")
    memo_text = saved["profitability_memo"].read_text(encoding="utf-8")
    credit_memo_text = saved["credit_memo"].read_text(encoding="utf-8")
    assert "차입금 만기 압박" in memo_text
    assert "이자비용과 CAPEX" in memo_text
    assert "환율 변동성 확대" in memo_text
    assert "신용/차환 리스크 메모" in credit_memo_text
    assert "manifest" in saved
