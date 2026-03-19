"""Extract structured numeric tables from XBRL notes."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree as ET

from .note_models import (
    NoteTable,
    NoteTablesOutput,
    TableCell,
    TableRow,
    UnitConverter,
    UnitType,
)


def iter_xml_files(root: Path) -> Iterable[Path]:
    """Yield XML/XBRL files from directory."""
    for path in root.rglob("*"):
        if path.suffix.lower() in {".xml", ".xbrl"}:
            yield path


def strip_namespace(tag: str) -> str:
    """Remove XML namespace from tag."""
    return tag.split("}")[-1]


def extract_text_content(elem: ET.Element) -> str:
    """Extract all text content from element and children."""
    texts: list[str] = []
    if elem.text and elem.text.strip():
        texts.append(elem.text.strip())
    for child in elem:
        if child.text and child.text.strip():
            texts.append(child.text.strip())
        if child.tail and child.tail.strip():
            texts.append(child.tail.strip())
    return " ".join(texts)


def detect_table_title(elem: ET.Element) -> str | None:
    """Try to find a table title from preceding elements or attributes."""
    # Look for title in attributes
    for attr in ["id", "name", "contextRef"]:
        if attr in elem.attrib:
            val = elem.attrib[attr]
            if val and not val.startswith("_"):
                return val
    return None


def parse_table_structure(
    table_elem: ET.Element,
) -> tuple[list[str], list[TableRow]] | None:
    """Parse an HTML-like table structure from XBRL."""
    columns: list[str] = []
    rows: list[TableRow] = []

    # Find all tr elements
    tr_elements: list[ET.Element] = []
    for tr in table_elem.iter():
        if strip_namespace(tr.tag) == "tr":
            tr_elements.append(tr)

    if not tr_elements:
        return None

    # Try to find header row - first row with all <th> elements
    header_row: ET.Element | None = None
    for tr in tr_elements:
        th_count = sum(1 for td in tr.iter() if strip_namespace(td.tag) == "th")
        td_count = sum(1 for td in tr.iter() if strip_namespace(td.tag) == "td")
        if th_count > 0 and td_count == 0:
            header_row = tr
            columns = [
                extract_text_content(td)
                for td in tr.iter()
                if strip_namespace(td.tag) == "th"
            ]
            break

    # Parse data rows (skip header row)
    row_idx = 0
    data_rows = [tr for tr in tr_elements if tr is not header_row]

    for tr in data_rows:
        cells: list[TableCell] = []
        col_idx = 0
        row_header: str | None = None

        for td in tr.iter():
            td_tag = strip_namespace(td.tag)
            if td_tag not in ("td", "th"):
                continue

            cell_text = extract_text_content(td)
            raw_value = cell_text

            # First column <th> is a row header
            if col_idx == 0 and td_tag == "th":
                row_header = cell_text
                col_idx += 1
                continue

            # Try to parse as numeric
            parsed_value = UnitConverter.parse_numeric(raw_value)
            is_numeric = parsed_value is not None

            cells.append(
                TableCell(
                    row_idx=row_idx,
                    col_idx=col_idx - (1 if row_header else 0),
                    value=parsed_value,
                    raw_value=raw_value,
                    is_numeric=is_numeric,
                )
            )
            col_idx += 1

        if cells:
            rows.append(
                TableRow(
                    row_idx=row_idx,
                    header=row_header,
                    cells=cells,
                )
            )
            row_idx += 1

    if not rows:
        return None
    return columns, rows


def extract_note_tables_from_xbrl(
    root: Path,
    corp_name: str,
    rcept_no: str,
    period_context: str = "CFY",
) -> NoteTablesOutput:
    """Extract all structured tables from XBRL notes."""
    from datetime import datetime

    tables: list[NoteTable] = []

    for xml_file in iter_xml_files(root):
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue

        # Look for table elements
        for elem in tree.iter():
            tag = strip_namespace(elem.tag)
            if tag not in ("table", "TABLE"):
                continue

            # Try to detect table title
            title = detect_table_title(elem) or f"Table_{len(tables)}"

            # Try to parse table structure
            parsed = parse_table_structure(elem)
            if not parsed:
                continue

            columns, rows = parsed

            # Detect unit from context or content
            unit = UnitType.OTHER
            for row in rows:
                for cell in row.cells:
                    if cell.is_numeric and cell.value is not None:
                        detected = UnitConverter.parse_unit_string(cell.raw_value)
                        if detected != UnitType.OTHER:
                            unit = detected
                            break
                if unit != UnitType.OTHER:
                    break

            # Determine table type from title/content
            table_type = None
            title_lower = title.lower()
            type_keywords: dict[str, tuple[str, ...]] = {
                "차입금": ("차입금", "borrowings", "debt"),
                "이자비용": ("이자비용", "interest", "finance cost"),
                "CAPEX": ("capex", "자본적지출", "자본지출", "유형자산"),
                "환율민감도": ("환율", "fx", "foreign exchange", "exchange rate"),
            }
            for ttype, keywords in type_keywords.items():
                if any(kw in title_lower for kw in keywords):
                    table_type = ttype
                    break

            tables.append(
                NoteTable(
                    title=title,
                    columns=columns,
                    rows=rows,
                    unit=unit,
                    period_context=period_context,
                    source_ref=str(xml_file.relative_to(root)),
                    table_type=table_type,
                )
            )

    return NoteTablesOutput(
        rcept_no=rcept_no,
        corp_name=corp_name,
        tables=tables,
        extracted_at=datetime.now(),
    )
