from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class UnitType(StrEnum):
    WON = "원"
    THOUSAND_WON = "천원"
    MILLION_WON = "백만원"
    HUNDRED_MILLION_WON = "억원"
    PERCENT = "percent"
    RATIO = "ratio"
    OTHER = "other"


class UnitConverter:
    _CURRENCY_FACTORS_IN_WON: dict[UnitType, float] = {
        UnitType.WON: 1.0,
        UnitType.THOUSAND_WON: 1_000.0,
        UnitType.MILLION_WON: 1_000_000.0,
        UnitType.HUNDRED_MILLION_WON: 100_000_000.0,
    }

    _UNIT_ALIASES: dict[UnitType, tuple[str, ...]] = {
        UnitType.WON: ("원", "krw", "won", "원단위", "단위:원"),
        UnitType.THOUSAND_WON: (
            "천원",
            "천 원",
            "thousand won",
            "k krw",
            "단위:천원",
        ),
        UnitType.MILLION_WON: (
            "백만원",
            "백만 원",
            "million won",
            "mn krw",
            "mm krw",
            "단위:백만원",
        ),
        UnitType.HUNDRED_MILLION_WON: (
            "억원",
            "억 원",
            "hundred million won",
            "100 million won",
            "단위:억원",
        ),
        UnitType.PERCENT: ("%", "percent", "percentage", "퍼센트", "비율(%)"),
        UnitType.RATIO: ("ratio", "배", "times", "x"),
    }

    _NON_NUMERIC_MARKERS: set[str] = {"", "-", "--", "n/a", "na", "none"}

    @classmethod
    def parse_unit_string(cls, unit_text: str | None) -> UnitType:
        if not unit_text:
            return UnitType.OTHER

        normalized = unit_text.strip().lower()
        if not normalized:
            return UnitType.OTHER

        matched_unit = UnitType.OTHER
        matched_length = -1
        for unit, aliases in cls._UNIT_ALIASES.items():
            for alias in aliases:
                if alias in normalized and len(alias) > matched_length:
                    matched_unit = unit
                    matched_length = len(alias)
        if matched_length >= 0:
            return matched_unit
        return UnitType.OTHER

    @classmethod
    def convert(cls, value: float, from_unit: UnitType, to_unit: UnitType) -> float:
        if from_unit == to_unit:
            return value

        if (
            from_unit in cls._CURRENCY_FACTORS_IN_WON
            and to_unit in cls._CURRENCY_FACTORS_IN_WON
        ):
            in_won = value * cls._CURRENCY_FACTORS_IN_WON[from_unit]
            return in_won / cls._CURRENCY_FACTORS_IN_WON[to_unit]

        raise ValueError(f"Unsupported unit conversion: {from_unit} -> {to_unit}")

    @classmethod
    def parse_numeric(
        cls,
        raw_value: str,
        source_unit: UnitType | None = None,
        target_unit: UnitType | None = None,
    ) -> float | None:
        text = raw_value.strip()
        if text.lower() in cls._NON_NUMERIC_MARKERS:
            return None

        detected_unit = cls.parse_unit_string(text)
        effective_source_unit = source_unit or detected_unit
        effective_target_unit = target_unit or effective_source_unit

        stripped = cls._strip_unit_aliases(text)
        stripped = stripped.replace(",", "")
        stripped = stripped.replace(" ", "")

        is_parentheses_negative = stripped.startswith("(") and stripped.endswith(")")
        if is_parentheses_negative:
            stripped = stripped[1:-1]

        if not re.fullmatch(r"[+-]?\d+(\.\d+)?", stripped):
            return None

        numeric = float(stripped)
        if is_parentheses_negative:
            numeric *= -1

        if effective_source_unit == UnitType.OTHER:
            converted = numeric
        else:
            converted = cls.convert(
                value=numeric,
                from_unit=effective_source_unit,
                to_unit=effective_target_unit,
            )
        cls.validate_numeric(converted)
        return converted

    @classmethod
    def validate_numeric(cls, value: float) -> None:
        if not math.isfinite(value):
            raise ValueError("Numeric value must be finite after conversion")

    @classmethod
    def _strip_unit_aliases(cls, text: str) -> str:
        result = text
        aliases = [
            alias
            for unit_aliases in cls._UNIT_ALIASES.values()
            for alias in unit_aliases
        ]
        aliases.sort(key=len, reverse=True)
        for alias in aliases:
            result = re.sub(re.escape(alias), "", result, flags=re.IGNORECASE)
        return result.strip()


class TableCell(BaseModel):
    row_idx: int
    col_idx: int
    value: float | None
    raw_value: str
    is_numeric: bool

    @model_validator(mode="after")
    def validate_numeric_consistency(self) -> TableCell:
        if self.is_numeric and self.value is None:
            raise ValueError("value must be provided when is_numeric is True")
        if self.value is not None:
            UnitConverter.validate_numeric(self.value)
        return self


class TableRow(BaseModel):
    row_idx: int
    header: str | None = None
    cells: list[TableCell] = Field(default_factory=list)


class NoteTable(BaseModel):
    table_id: str = ""
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)
    unit: UnitType
    period_context: str
    source_ref: str
    table_type: str | None = None

    @model_validator(mode="after")
    def ensure_table_id(self) -> NoteTable:
        if not self.table_id:
            self.table_id = self.generate_table_id(self.title, self.columns)
        return self

    @staticmethod
    def generate_table_id(title: str, columns: list[str]) -> str:
        base = f"{title.strip()}|{'|'.join(col.strip() for col in columns)}"
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
        return f"tbl_{digest}"


class NoteTablesOutput(BaseModel):
    rcept_no: str
    corp_name: str
    tables: list[NoteTable] = Field(default_factory=list)
    extracted_at: datetime
