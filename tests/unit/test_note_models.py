from __future__ import annotations

from datetime import datetime

import pytest

from dart_xbrl_pipeline.note_models import (
    NoteTable,
    NoteTablesOutput,
    TableCell,
    TableRow,
    UnitConverter,
    UnitType,
)


def test_unit_conversion_won_to_million_won() -> None:
    converted = UnitConverter.convert(1_000_000, UnitType.WON, UnitType.MILLION_WON)
    assert converted == 1.0


def test_unit_conversion_million_won_to_won() -> None:
    converted = UnitConverter.convert(3.5, UnitType.MILLION_WON, UnitType.WON)
    assert converted == 3_500_000.0


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1,234", 1234.0),
        ("(567)", -567.0),
        ("1,234 백만원", 1234.0),
    ],
)
def test_parse_numeric_formats(raw_value: str, expected: float) -> None:
    parsed = UnitConverter.parse_numeric(raw_value, target_unit=UnitType.MILLION_WON)
    assert parsed == expected


def test_parse_numeric_with_conversion() -> None:
    parsed = UnitConverter.parse_numeric(
        "1,000,000 원", target_unit=UnitType.MILLION_WON
    )
    assert parsed == 1.0


@pytest.mark.parametrize(
    ("unit_text", "expected"),
    [
        ("단위: 원", UnitType.WON),
        ("단위 : 천원", UnitType.THOUSAND_WON),
        ("백만원", UnitType.MILLION_WON),
        ("hundred million won", UnitType.HUNDRED_MILLION_WON),
        ("비율(%)", UnitType.PERCENT),
        ("ratio", UnitType.RATIO),
        ("unknown-unit", UnitType.OTHER),
    ],
)
def test_parse_unit_string(unit_text: str, expected: UnitType) -> None:
    assert UnitConverter.parse_unit_string(unit_text) is expected


def test_table_id_is_deterministic() -> None:
    columns = ["구분", "당기", "전기"]
    table_a = NoteTable(
        title="차입금 현황",
        columns=columns,
        rows=[],
        unit=UnitType.MILLION_WON,
        period_context="CFY2025",
        source_ref="sample.xbrl",
    )
    table_b = NoteTable(
        title="차입금 현황",
        columns=columns,
        rows=[],
        unit=UnitType.MILLION_WON,
        period_context="PFY2024",
        source_ref="sample2.xbrl",
    )
    assert table_a.table_id == table_b.table_id


def test_note_tables_output_serialization() -> None:
    table = NoteTable(
        title="CAPEX",
        columns=["항목", "금액"],
        rows=[
            TableRow(
                row_idx=0,
                header="유형자산",
                cells=[
                    TableCell(
                        row_idx=0,
                        col_idx=1,
                        value=100.0,
                        raw_value="100",
                        is_numeric=True,
                    )
                ],
            )
        ],
        unit=UnitType.MILLION_WON,
        period_context="CFY2025",
        source_ref="report_2025.xbrl",
        table_type="CAPEX",
    )

    output = NoteTablesOutput(
        rcept_no="20260319000123",
        corp_name="Sample Corp",
        tables=[table],
        extracted_at=datetime(2026, 3, 19, 10, 0, 0),
    )

    assert output.tables[0].title == "CAPEX"
    assert output.tables[0].rows[0].cells[0].value == 100.0
