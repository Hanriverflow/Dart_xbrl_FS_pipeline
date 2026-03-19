from __future__ import annotations

import json
from pathlib import Path

from dart_xbrl_pipeline.note_models import UnitType
from dart_xbrl_pipeline.note_table_parser import NoteTableParser


def test_detect_table_type_targets() -> None:
    parser = NoteTableParser()

    assert parser.detect_table_type("차입금 현황") == "차입금"
    assert parser.detect_table_type("이자비용 내역") == "이자비용"
    assert parser.detect_table_type("Capital Expenditures (CAPEX)") == "CAPEX"
    assert parser.detect_table_type("환율 민감도 분석") == "환율 민감도"
    assert parser.detect_table_type("기타 표") is None


def test_extract_tables_parses_units_period_and_numeric_cells(tmp_path: Path) -> None:
    xbrl_file = tmp_path / "note_table.xbrl"
    xbrl_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <xbrli:context id="CFY2025ConsolidatedMember" />
  <xbrli:context id="PFY2024ConsolidatedMember" />
  <xbrli:unit id="KRW"><xbrli:measure>iso4217:KRW</xbrli:measure></xbrli:unit>
  <table title="차입금 현황">
    <tr><th>구분</th><th>당기</th><th>전기</th></tr>
    <tr>
      <th>장기차입금</th>
      <td contextRef="CFY2025ConsolidatedMember" unitRef="KRW">1,200</td>
      <td contextRef="PFY2024ConsolidatedMember" unitRef="KRW">900</td>
    </tr>
  </table>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )

    parser = NoteTableParser(corp_name="Sample Corp", rcept_no="20260319000123")
    tables = parser.extract_tables(xbrl_file)

    assert len(tables) == 1
    table = tables[0]
    assert table.title == "차입금 현황"
    assert table.table_type == "차입금"
    assert table.unit == UnitType.WON
    assert table.period_context == "CFY2025"
    assert table.rows[0].cells[0].value == 1200.0
    assert table.rows[0].cells[1].value == 900.0
    assert table.table_id == table.generate_table_id(table.title, table.columns)


def test_parse_directory_graceful_fallback_and_debug_dump(tmp_path: Path) -> None:
    xbrl_dir = tmp_path / "xbrl"
    xbrl_dir.mkdir()

    bad_file = xbrl_dir / "bad_table.xbrl"
    bad_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<root>
  <table id="broken-table">
    <tr><th>구분</th><th>값</th></tr>
    <tr><td>텍스트만</td><td>해당없음</td></tr>
  </table>
</root>
""",
        encoding="utf-8",
    )

    good_file = xbrl_dir / "good_table.xbrl"
    good_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<root>
  <table title="이자비용 내역">
    <tr><th>구분</th><th>금액</th></tr>
    <tr><td>당기</td><td>300</td></tr>
  </table>
</root>
""",
        encoding="utf-8",
    )

    debug_dir = tmp_path / "debug"
    parser = NoteTableParser(
        corp_name="Demo Corp",
        rcept_no="20260319000456",
        debug_dir=debug_dir,
    )
    output = parser.parse_directory(xbrl_dir)

    assert output.corp_name == "Demo Corp"
    assert output.rcept_no == "20260319000456"
    assert len(output.tables) == 1
    assert output.tables[0].table_type == "이자비용"

    debug_file = debug_dir / "xbrl_failed_tables.json"
    assert debug_file.exists()
    failed_payload = json.loads(debug_file.read_text(encoding="utf-8"))
    assert failed_payload
    assert failed_payload[0]["reason"] in {
        "malformed_or_empty_table",
        "xml_parse_error",
    }
