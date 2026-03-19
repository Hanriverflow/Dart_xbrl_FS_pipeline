"""Tests for note extractor functionality."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest

from dart_xbrl_pipeline.note_extractor import (
    detect_table_title,
    extract_text_content,
    parse_table_structure,
    strip_namespace,
)
from dart_xbrl_pipeline.note_models import TableCell, TableRow


class TestStripNamespace:
    def test_removes_namespace(self) -> None:
        assert strip_namespace("{http://www.w3.org/1999/xhtml}table") == "table"

    def test_no_namespace_unchanged(self) -> None:
        assert strip_namespace("table") == "table"


class TestExtractTextContent:
    def test_extracts_text(self) -> None:
        elem = ET.Element("td")
        elem.text = "  Hello World  "
        assert extract_text_content(elem) == "Hello World"

    def test_extracts_from_children(self) -> None:
        elem = ET.Element("td")
        elem.text = "Start"
        child = ET.SubElement(elem, "span")
        child.text = "Middle"
        child.tail = "End"
        assert extract_text_content(elem) == "Start Middle End"


class TestDetectTableTitle:
    def test_finds_id_attribute(self) -> None:
        elem = ET.Element("table")
        elem.set("id", "MyTable")
        assert detect_table_title(elem) == "MyTable"

    def test_skips_underscore_prefix(self) -> None:
        elem = ET.Element("table")
        elem.set("id", "_internal")
        assert detect_table_title(elem) is None

    def test_returns_none_for_empty(self) -> None:
        elem = ET.Element("table")
        assert detect_table_title(elem) is None


class TestParseTableStructure:
    def test_parses_simple_table(self) -> None:
        # Create a simple HTML-like table
        table_xml = """
        <table>
            <tr>
                <th>Header1</th>
                <th>Header2</th>
            </tr>
            <tr>
                <td>100</td>
                <td>200</td>
            </tr>
        </table>
        """
        table_elem = ET.fromstring(table_xml)
        result = parse_table_structure(table_elem)

        assert result is not None
        columns, rows = result
        assert columns == ["Header1", "Header2"]
        assert len(rows) == 1
        assert rows[0].row_idx == 0
        assert len(rows[0].cells) == 2

    def test_parses_with_row_header(self) -> None:
        table_xml = """
        <table>
            <tr>
                <th>구분</th>
                <th>당기</th>
                <th>전기</th>
            </tr>
            <tr>
                <th>차입금</th>
                <td>1,000</td>
                <td>2,000</td>
            </tr>
        </table>
        """
        table_elem = ET.fromstring(table_xml)
        result = parse_table_structure(table_elem)

        assert result is not None
        columns, rows = result
        assert rows[0].header == "차입금"
        assert len(rows[0].cells) == 2  # Excludes row header

    def test_parses_numeric_values(self) -> None:
        table_xml = """
        <table>
            <tr>
                <td>1,234</td>
                <td>(567)</td>
            </tr>
        </table>
        """
        table_elem = ET.fromstring(table_xml)
        result = parse_table_structure(table_elem)

        assert result is not None
        columns, rows = result
        # No header row with <th>, so all rows are data and columns is empty
        assert len(columns) == 0
        assert len(rows) == 1
        assert rows[0].cells[0].value == 1234.0
        assert rows[0].cells[0].is_numeric is True
        assert rows[0].cells[1].value == -567.0
        assert rows[0].cells[1].is_numeric is True

    def test_returns_none_for_empty_table(self) -> None:
        table_xml = "<table></table>"
        table_elem = ET.fromstring(table_xml)
        result = parse_table_structure(table_elem)
        assert result is None

    def test_handles_non_numeric_cells(self) -> None:
        table_xml = """
        <table>
            <tr>
                <td>Some text</td>
                <td>100</td>
            </tr>
        </table>
        """
        table_elem = ET.fromstring(table_xml)
        result = parse_table_structure(table_elem)

        assert result is not None
        columns, rows = result
        # No header row with <th>, so all rows are data and columns is empty
        assert len(columns) == 0
        assert len(rows) == 1
        assert rows[0].cells[0].value is None
        assert rows[0].cells[0].is_numeric is False
        assert rows[0].cells[1].value == 100.0
        assert rows[0].cells[1].is_numeric is True
