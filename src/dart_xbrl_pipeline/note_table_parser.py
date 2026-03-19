from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Pattern, TypedDict
from xml.etree import ElementTree as ET

from .note_models import (
    NoteTable,
    NoteTablesOutput,
    TableCell,
    TableRow,
    UnitConverter,
    UnitType,
)
from .xbrl_parser import iter_xml_files, strip_namespace


class NoteTableParser:
    class FailedTableRecord(TypedDict):
        xml_file: str
        reason: str
        title: str | None
        detail: str

    _TABLE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "차입금": ("차입금", "borrowings", "borrowing", "debt", "loan"),
        "이자비용": (
            "이자비용",
            "interest expense",
            "interest expenses",
            "finance cost",
            "finance costs",
        ),
        "CAPEX": (
            "capex",
            "capital expenditure",
            "capital expenditures",
            "자본적지출",
            "자본지출",
        ),
        "환율 민감도": (
            "환율",
            "환율민감도",
            "fx sensitivity",
            "foreign exchange",
            "exchange rate",
        ),
    }

    _PERIOD_PATTERN: Pattern[str] = re.compile(
        r"(CFY\d{4}|PFY\d{4}|BPFY\d{4})",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        corp_name: str = "UNKNOWN",
        rcept_no: str = "UNKNOWN",
        debug_dir: Path | None = None,
    ) -> None:
        self.corp_name: str = corp_name
        self.rcept_no: str = rcept_no
        self.debug_dir: Path | None = debug_dir
        self.failed_tables: list[NoteTableParser.FailedTableRecord] = []

    def parse_directory(self, xbrl_dir: Path) -> NoteTablesOutput:
        tables: list[NoteTable] = []
        self.failed_tables = []

        for xml_file in iter_xml_files(xbrl_dir):
            if xml_file.suffix.lower() not in {".xml", ".xbrl"}:
                continue
            tables.extend(self.extract_tables(xml_file))

        if self.debug_dir is not None and self.failed_tables:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = self.debug_dir / f"{xbrl_dir.name}_failed_tables.json"
            _ = debug_path.write_text(
                json.dumps(self.failed_tables, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return NoteTablesOutput(
            rcept_no=self.rcept_no,
            corp_name=self.corp_name,
            tables=tables,
            extracted_at=datetime.now(),
        )

    def extract_tables(self, xml_file: Path) -> list[NoteTable]:
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError as exc:
            self._record_failure(
                xml_file=xml_file,
                reason="xml_parse_error",
                title=None,
                detail=str(exc),
            )
            return []

        root = tree.getroot()
        unit_map = self._build_unit_map(root)
        context_ids = self._collect_context_ids(root)

        extracted: list[NoteTable] = []
        for elem in root.iter():
            if strip_namespace(elem.tag).lower() != "table":
                continue

            title = self._detect_table_title(elem)
            parsed = self._parse_table_rows(elem, unit_map)
            if parsed is None:
                self._record_failure(
                    xml_file=xml_file,
                    reason="malformed_or_empty_table",
                    title=title,
                    detail=self._sample_table_text(elem),
                )
                continue

            columns, rows, table_unit, table_contexts = parsed
            period_context = self._select_period_context(table_contexts, context_ids)
            table_type = self.detect_table_type(title)

            extracted.append(
                NoteTable(
                    title=title,
                    columns=columns,
                    rows=rows,
                    unit=table_unit,
                    period_context=period_context,
                    source_ref=str(xml_file),
                    table_type=table_type,
                )
            )

        return extracted

    def detect_table_type(self, title: str) -> str | None:
        normalized = re.sub(r"\s+", " ", title).strip().lower()
        if not normalized:
            return None

        for table_type, keywords in self._TABLE_TYPE_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return table_type
        return None

    def _build_unit_map(self, root: ET.Element) -> dict[str, UnitType]:
        unit_map: dict[str, UnitType] = {}
        for elem in root.iter():
            if strip_namespace(elem.tag).lower() != "unit":
                continue
            unit_id = elem.attrib.get("id")
            if not unit_id:
                continue

            parts: list[str] = []
            for child in elem.iter():
                text = (child.text or "").strip()
                if text:
                    parts.append(text)
            combined = " ".join(parts)
            unit = UnitConverter.parse_unit_string(combined)
            if unit == UnitType.OTHER and "krw" in combined.lower():
                unit = UnitType.WON
            unit_map[unit_id] = unit
        return unit_map

    def _collect_context_ids(self, root: ET.Element) -> list[str]:
        context_ids: list[str] = []
        for elem in root.iter():
            if strip_namespace(elem.tag).lower() == "context":
                context_id = elem.attrib.get("id")
                if context_id:
                    context_ids.append(context_id)
        return context_ids

    def _detect_table_title(self, table_elem: ET.Element) -> str:
        for attr in ("title", "name", "id", "contextRef"):
            value = (table_elem.attrib.get(attr) or "").strip()
            if value and not value.startswith("_"):
                return value

        for child in table_elem.iter():
            child_tag = strip_namespace(child.tag).lower()
            if child_tag in {"caption", "title", "thead"}:
                text = self._extract_text(child)
                if text:
                    return text

        return "Untitled Table"

    def _parse_table_rows(
        self,
        table_elem: ET.Element,
        unit_map: dict[str, UnitType],
    ) -> tuple[list[str], list[TableRow], UnitType, list[str]] | None:
        tr_nodes = [
            node
            for node in table_elem.iter()
            if strip_namespace(node.tag).lower() == "tr"
        ]
        if not tr_nodes:
            return None

        columns: list[str] = []
        rows: list[TableRow] = []
        seen_numeric = 0
        table_contexts: list[str] = []
        detected_units: list[UnitType] = []

        first_row_cells = self._extract_cell_nodes(tr_nodes[0])
        if first_row_cells and any(
            strip_namespace(cell.tag).lower() == "th" for cell in first_row_cells
        ):
            columns = [self._extract_text(cell) for cell in first_row_cells]
            data_rows = tr_nodes[1:]
        else:
            data_rows = tr_nodes

        for row_idx, tr in enumerate(data_rows):
            cell_nodes = self._extract_cell_nodes(tr)
            if not cell_nodes:
                continue

            row_header: str | None = None
            body_nodes = cell_nodes
            first_tag = strip_namespace(cell_nodes[0].tag).lower()
            if first_tag == "th":
                row_header = self._extract_text(cell_nodes[0])
                body_nodes = cell_nodes[1:]

            cells: list[TableCell] = []
            for col_idx, cell_node in enumerate(body_nodes):
                raw_value = self._extract_text(cell_node)
                context_ref = cell_node.attrib.get("contextRef")
                if context_ref:
                    table_contexts.append(context_ref)

                source_unit = UnitType.OTHER
                unit_ref = cell_node.attrib.get("unitRef")
                if unit_ref:
                    source_unit = unit_map.get(unit_ref, UnitType.OTHER)

                numeric_value = UnitConverter.parse_numeric(
                    raw_value, source_unit=source_unit
                )
                is_numeric = numeric_value is not None
                if is_numeric:
                    seen_numeric += 1

                detected_from_text = UnitConverter.parse_unit_string(raw_value)
                if source_unit != UnitType.OTHER:
                    detected_units.append(source_unit)
                elif detected_from_text != UnitType.OTHER:
                    detected_units.append(detected_from_text)

                cells.append(
                    TableCell(
                        row_idx=row_idx,
                        col_idx=col_idx,
                        value=numeric_value,
                        raw_value=raw_value,
                        is_numeric=is_numeric,
                    )
                )

            if cells:
                rows.append(TableRow(row_idx=row_idx, header=row_header, cells=cells))

        if not rows or seen_numeric == 0:
            return None

        table_unit = detected_units[0] if detected_units else UnitType.OTHER
        return columns, rows, table_unit, table_contexts

    def _extract_cell_nodes(self, tr_elem: ET.Element) -> list[ET.Element]:
        cells: list[ET.Element] = []
        for node in tr_elem:
            if strip_namespace(node.tag).lower() in {"th", "td"}:
                cells.append(node)
        return cells

    def _extract_text(self, elem: ET.Element) -> str:
        chunks: list[str] = []
        for text in elem.itertext():
            cleaned = text.strip()
            if cleaned:
                chunks.append(cleaned)
        return " ".join(chunks)

    def _select_period_context(
        self,
        table_contexts: list[str],
        all_context_ids: list[str],
    ) -> str:
        candidates = table_contexts or all_context_ids
        matches: list[str] = []
        for context in candidates:
            found = self._PERIOD_PATTERN.search(context)
            if found:
                matches.append(found.group(1).upper())

        if matches:
            return Counter(matches).most_common(1)[0][0]

        for context in candidates:
            lowered = context.lower()
            if lowered.startswith("cfy"):
                return context
        for context in candidates:
            lowered = context.lower()
            if lowered.startswith("pfy"):
                return context
        return "UNKNOWN"

    def _sample_table_text(self, table_elem: ET.Element) -> str:
        sample = self._extract_text(table_elem)
        return sample[:300]

    def _record_failure(
        self,
        *,
        xml_file: Path,
        reason: str,
        title: str | None,
        detail: str,
    ) -> None:
        self.failed_tables.append(
            {
                "xml_file": str(xml_file),
                "reason": reason,
                "title": title,
                "detail": detail,
            }
        )
