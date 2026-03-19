from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .note_models import NoteTable


class EvidenceType(str, Enum):
    table = "table"
    account = "account"
    metric = "metric"
    external = "external"


class EvidenceRef(BaseModel):
    type: EvidenceType
    ref_id: str = ""
    value: str = ""
    context: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def normalize_table_id_alias(cls, data: object) -> object:
        if isinstance(data, dict) and "ref_id" not in data and "table_id" in data:
            normalized = dict(data)
            normalized["ref_id"] = normalized.pop("table_id")
            return normalized
        return data

    @model_validator(mode="after")
    def validate_reference_or_value(self) -> EvidenceRef:
        if not self.ref_id.strip() and not self.value.strip():
            raise ValueError("EvidenceRef requires at least one of ref_id or value")
        return self


class ProfitabilityClaim(BaseModel):
    claim: str
    category: str
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: str

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_claim_constraints(self) -> ProfitabilityClaim:
        if not self.evidence:
            raise ValueError("Every claim must include at least one evidence reference")

        allowed_confidence = {"high", "medium", "low"}
        if self.confidence not in allowed_confidence:
            raise ValueError("confidence must be one of high, medium, low")

        return self


class ProfitabilityMemo(BaseModel):
    rcept_no: str
    corp_name: str
    report_type: str
    generated_at: datetime
    claims: list[ProfitabilityClaim] = Field(default_factory=list)
    summary: str
    risks: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_claim_support(self) -> ProfitabilityMemo:
        unsupported_claims = sum(1 for claim in self.claims if not claim.evidence)
        if unsupported_claims != 0:
            raise ValueError("unsupported_claims must be 0; every claim needs evidence")
        return self


class InsightInput(BaseModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    tables: list[NoteTable] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
