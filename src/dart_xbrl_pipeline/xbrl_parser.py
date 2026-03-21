from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from .models import IncomeStatementMetric, NotesHit

NUMERIC_TAG_HINTS = {
    "매출액": ["Revenue", "SalesRevenueGoods"],
    "매출원가": ["CostOfSales", "CostOfGoodsSold"],
    "매출총이익": ["GrossProfit"],
    "판매비와관리비": ["SellingGeneralAdministrativeExpenses", "TotalSellingGeneralAdministrativeExpenses"],
    "영업이익": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "금융수익": ["FinanceIncome"],
    "금융비용": ["FinanceCosts"],
    "기타수익": ["OtherGains", "OtherIncome"],
    "기타비용": ["OtherLosses", "OtherExpenses"],
    "법인세차감전순이익": ["ProfitLossBeforeTax"],
    "법인세비용": ["IncomeTaxExpenseContinuingOperations"],
    "당기순이익": ["ProfitLoss"],
}

DISALLOWED_CONTEXT_KEYWORDS = [
    "segmentconsolidationitemsaxis",
    "segmentsaxis",
    "geographicalareasaxis",
    "majorcustomersaxis",
    "componentsofequityaxis",
    "carryingamountaccumulateddepreciationamortisationandimpairmentandgrosscarryingamountaxis",
    "reportedamountmember",
]


def iter_xml_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.suffix.lower() in {".xml", ".xsd", ".xbrl"}:
            yield path


def safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def strip_namespace(tag: str) -> str:
    return tag.split("}")[-1]


def _is_primary_statement_context(context: str) -> bool:
    c = context.lower()
    return (
        "consolidatedmember" in c
        and not any(bad in c for bad in DISALLOWED_CONTEXT_KEYWORDS)
    )


def _context_score(context: str, tag: str) -> int:
    c = context.lower()
    score = 0
    if "consolidatedmember" in c:
        score += 100
    if "separatemember" in c:
        score -= 20
    if c.startswith("cfy"):
        score += 50
    if c.startswith("pfy"):
        score += 40
    if c.startswith("bpfy"):
        score -= 30
    if any(bad in c for bad in DISALLOWED_CONTEXT_KEYWORDS):
        score -= 80
    if _is_primary_statement_context(c):
        score += 100
    if tag.lower() in {"revenue", "costofsales", "grossprofit", "operatingincomeloss", "financeincome", "financecosts", "profitlossbeforetax", "profitloss"}:
        score += 10
    return score


def extract_income_statement_metrics(root: Path) -> list[IncomeStatementMetric]:
    candidates: dict[str, list[tuple[int, str, float, str]]] = {k: [] for k in NUMERIC_TAG_HINTS}
    for xml_file in iter_xml_files(root):
        if xml_file.suffix.lower() != ".xbrl":
            continue
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue
        for elem in tree.iter():
            tag = strip_namespace(elem.tag)
            text = (elem.text or "").strip()
            if not text:
                continue
            value = safe_float(text)
            if value is None:
                continue
            context = elem.attrib.get("contextRef", "")
            for account_name, hints in NUMERIC_TAG_HINTS.items():
                if any(tag.lower() == hint.lower() for hint in hints):
                    candidates[account_name].append((_context_score(context, tag), context, value, tag))
    results: list[IncomeStatementMetric] = []
    for account_name, items in candidates.items():
        if not items:
            continue
        current = None
        prior = None
        for score, context, value, tag in sorted(items, key=lambda x: x[0], reverse=True):
            cl = context.lower()
            if current is None and cl.startswith("cfy") and _is_primary_statement_context(cl):
                current = (value, context, tag)
                continue
            if prior is None and cl.startswith("pfy") and _is_primary_statement_context(cl):
                prior = (value, context, tag)
                continue
        if current is None:
            best = sorted(items, key=lambda x: x[0], reverse=True)[0]
            current = (best[2], best[1], best[3])
        if prior is None:
            prior_candidates = [x for x in items if x[1].lower().startswith("pfy") and _is_primary_statement_context(x[1].lower())]
            if prior_candidates:
                best = sorted(prior_candidates, key=lambda x: x[0], reverse=True)[0]
                prior = (best[2], best[1], best[3])
        results.append(
            IncomeStatementMetric(
                account_name=account_name,
                current_amount=current[0] if current else None,
                prior_amount=prior[0] if prior else None,
                source_context=current[1] if current else None,
                matched_label=current[2] if current else None,
            )
        )
    return results


def extract_note_hits(root: Path, keyword_map: dict[str, list[str]]) -> list[NotesHit]:
    hits: list[NotesHit] = []
    for xml_file in iter_xml_files(root):
        if xml_file.suffix.lower() == ".xsd":
            continue
        try:
            tree = ET.parse(xml_file)
        except ET.ParseError:
            continue
        for elem in tree.iter():
            text = re.sub(r"\s+", " ", (elem.text or "").strip())
            if not text:
                continue
            if len(text) < 8:
                continue
            tag = strip_namespace(elem.tag)
            for category, keywords in keyword_map.items():
                for keyword in keywords:
                    if keyword in text or keyword.lower() in tag.lower():
                        hits.append(
                            NotesHit(
                                category=category,
                                keyword=keyword,
                                text=text[:500],
                                context_ref=elem.attrib.get("contextRef"),
                                unit_ref=elem.attrib.get("unitRef"),
                                fact_value=text[:120],
                            )
                        )
                        break
    unique: list[NotesHit] = []
    seen: set[tuple[str, str, str]] = set()
    for hit in hits:
        key = (hit.category, hit.keyword, hit.text)
        if key not in seen:
            unique.append(hit)
            seen.add(key)
    return unique
