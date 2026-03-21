from __future__ import annotations

import json
from pathlib import Path

from dart_xbrl_pipeline.note_models import UnitType
from dart_xbrl_pipeline.note_table_parser import NoteTableParser


def _write_presentation_fallback_fixture(xbrl_dir: Path) -> None:
    xbrl_dir.mkdir(parents=True, exist_ok=True)
    (xbrl_dir / "entity_test_2025-12-31.xbrl").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
    xmlns:entity="http://example.com/entity">
  <xbrli:context id="CFY2025_ifrs-full_BorrowingsByNameAxis_entity_BankBorrowingsMemberOfDetailedInformationAboutBorrowingsTableOfMember_ifrs-full_CounterpartiesAxis_entity_WooriBankMemberOfDetailedInformationAboutBorrowingsTableOfMember">
    <xbrli:entity><xbrli:identifier scheme="test">sample</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
    <xbrli:scenario>
      <xbrldi:explicitMember dimension="ifrs-full:BorrowingsByNameAxis">entity:BankBorrowingsMemberOfDetailedInformationAboutBorrowingsTableOfMember</xbrldi:explicitMember>
      <xbrldi:explicitMember dimension="ifrs-full:CounterpartiesAxis">entity:WooriBankMemberOfDetailedInformationAboutBorrowingsTableOfMember</xbrldi:explicitMember>
    </xbrli:scenario>
  </xbrli:context>
  <xbrli:context id="CFY2025_ifrs-full_TypesOfRisksAxis_ifrs-full_CurrencyRiskMember_entity_KrwMemberOfSensitivityAnalysisForEachTypeOfMarketRiskTableOfMember">
    <xbrli:entity><xbrli:identifier scheme="test">sample</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period>
    <xbrli:scenario>
      <xbrldi:explicitMember dimension="ifrs-full:TypesOfRisksAxis">ifrs-full:CurrencyRiskMember</xbrldi:explicitMember>
      <xbrldi:explicitMember dimension="ifrs-full:CurrencyInWhichInformationIsDisplayedAxis">entity:KrwMemberOfSensitivityAnalysisForEachTypeOfMarketRiskTableOfMember</xbrldi:explicitMember>
    </xbrli:scenario>
  </xbrli:context>
  <xbrli:unit id="KRW"><xbrli:measure>iso4217:KRW</xbrli:measure></xbrli:unit>
  <entity:BorrowingNominalAmountsOfDetailsOfLongTermBorrowingsOfDetailsOfLongTermBorrowingsTableOfItems contextRef="CFY2025_ifrs-full_BorrowingsByNameAxis_entity_BankBorrowingsMemberOfDetailedInformationAboutBorrowingsTableOfMember_ifrs-full_CounterpartiesAxis_entity_WooriBankMemberOfDetailedInformationAboutBorrowingsTableOfMember" unitRef="KRW">230000000000</entity:BorrowingNominalAmountsOfDetailsOfLongTermBorrowingsOfDetailsOfLongTermBorrowingsTableOfItems>
  <entity:BorrowingsMaturity contextRef="CFY2025_ifrs-full_BorrowingsByNameAxis_entity_BankBorrowingsMemberOfDetailedInformationAboutBorrowingsTableOfMember_ifrs-full_CounterpartiesAxis_entity_WooriBankMemberOfDetailedInformationAboutBorrowingsTableOfMember">2027-12-24</entity:BorrowingsMaturity>
  <entity:IncreaseInProfitDueToIncreaseInMarketRiskVariable contextRef="CFY2025_ifrs-full_TypesOfRisksAxis_ifrs-full_CurrencyRiskMember_entity_KrwMemberOfSensitivityAnalysisForEachTypeOfMarketRiskTableOfMember" unitRef="KRW">120000000</entity:IncreaseInProfitDueToIncreaseInMarketRiskVariable>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )
    (xbrl_dir / "entity_test_2025-12-31_lab-ko.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    <link:loc xlink:type="locator" xlink:label="loc_borrowings_table" xlink:href="entity_test_2025-12-31.xsd#dart_DetailedInformationAboutBorrowingsTable"/>
    <link:label xlink:type="resource" xlink:label="label_borrowings_table">차입금에 대한 세부 정보 [표]</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_borrowings_table" xlink:to="label_borrowings_table"/>

    <link:loc xlink:type="locator" xlink:label="loc_borrow_amount" xlink:href="entity_test_2025-12-31.xsd#BorrowingNominalAmountsOfDetailsOfLongTermBorrowingsOfDetailsOfLongTermBorrowingsTableOfItems"/>
    <link:label xlink:type="resource" xlink:label="label_borrow_amount">차입금 명목금액</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_borrow_amount" xlink:to="label_borrow_amount"/>

    <link:loc xlink:type="locator" xlink:label="loc_borrow_maturity" xlink:href="entity_test_2025-12-31.xsd#BorrowingsMaturity"/>
    <link:label xlink:type="resource" xlink:label="label_borrow_maturity">차입금 만기</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_borrow_maturity" xlink:to="label_borrow_maturity"/>

    <link:loc xlink:type="locator" xlink:label="loc_bank_member" xlink:href="entity_test_2025-12-31.xsd#BankBorrowingsMemberOfDetailedInformationAboutBorrowingsTableOfMember"/>
    <link:label xlink:type="resource" xlink:label="label_bank_member">은행차입금</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_bank_member" xlink:to="label_bank_member"/>

    <link:loc xlink:type="locator" xlink:label="loc_woori_member" xlink:href="entity_test_2025-12-31.xsd#WooriBankMemberOfDetailedInformationAboutBorrowingsTableOfMember"/>
    <link:label xlink:type="resource" xlink:label="label_woori_member">우리은행</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_woori_member" xlink:to="label_woori_member"/>

    <link:loc xlink:type="locator" xlink:label="loc_fx_table" xlink:href="entity_test_2025-12-31.xsd#dart_SensitivityAnalysisForEachTypeOfMarketRiskTable"/>
    <link:label xlink:type="resource" xlink:label="label_fx_table">보고기간 말 현재 노출된 시장위험의 각 유형별 민감도 분석 [표]</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_fx_table" xlink:to="label_fx_table"/>

    <link:loc xlink:type="locator" xlink:label="loc_fx_fact" xlink:href="entity_test_2025-12-31.xsd#IncreaseInProfitDueToIncreaseInMarketRiskVariable"/>
    <link:label xlink:type="resource" xlink:label="label_fx_fact">시장위험 변수 상승 시 이익 증가</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_fx_fact" xlink:to="label_fx_fact"/>

    <link:loc xlink:type="locator" xlink:label="loc_krw_member" xlink:href="entity_test_2025-12-31.xsd#KrwMemberOfSensitivityAnalysisForEachTypeOfMarketRiskTableOfMember"/>
    <link:label xlink:type="resource" xlink:label="label_krw_member">원화</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_krw_member" xlink:to="label_krw_member"/>

    <link:loc xlink:type="locator" xlink:label="loc_currency_risk" xlink:href="entity_test_2025-12-31.xsd#CurrencyRiskMember"/>
    <link:label xlink:type="resource" xlink:label="label_currency_risk">환율위험</link:label>
    <link:labelArc xlink:type="arc" xlink:from="loc_currency_risk" xlink:to="label_currency_risk"/>
  </link:labelLink>
</linkbase>
""",
        encoding="utf-8",
    )


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


def test_parse_directory_falls_back_to_presentation_driven_borrowings_table(
    tmp_path: Path,
) -> None:
    xbrl_dir = tmp_path / "fallback_xbrl"
    _write_presentation_fallback_fixture(xbrl_dir)

    parser = NoteTableParser(corp_name="Fallback Corp", rcept_no="20260321009999")
    output = parser.parse_directory(xbrl_dir)

    borrowings_tables = [table for table in output.tables if table.table_type == "차입금"]
    assert borrowings_tables
    table = borrowings_tables[0]
    assert "차입금" in table.title
    assert table.rows
    assert any(cell.is_numeric for row in table.rows for cell in row.cells)
    assert table.source_ref.startswith("presentation-fallback:")


def test_parse_directory_falls_back_to_fx_sensitivity_table_when_presentation_links_exist(
    tmp_path: Path,
) -> None:
    xbrl_dir = tmp_path / "fallback_xbrl_fx"
    _write_presentation_fallback_fixture(xbrl_dir)

    parser = NoteTableParser(corp_name="Fallback Corp", rcept_no="20260321009998")
    output = parser.parse_directory(xbrl_dir)

    fx_tables = [table for table in output.tables if table.table_type == "환율 민감도"]
    assert fx_tables
    table = fx_tables[0]
    assert "민감도" in table.title or "환율" in table.title
    assert table.period_context.startswith("CFY")
    assert table.rows
