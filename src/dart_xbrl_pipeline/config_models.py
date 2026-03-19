from __future__ import annotations

from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AnalysisConfig(BaseModel):
    profitability_keywords: dict[str, list[str]] = Field(default_factory=dict)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @field_validator("profitability_keywords")
    @classmethod
    def validate_profitability_keywords(
        cls, value: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        if not value:
            raise ValueError("analysis.profitability_keywords must not be empty")

        for category, keywords in value.items():
            if not category:
                raise ValueError(
                    "analysis.profitability_keywords category keys must be non-empty"
                )
            if not keywords:
                raise ValueError(
                    f"analysis.profitability_keywords.{category} must not be empty"
                )
            for keyword in keywords:
                if not keyword or not keyword.strip():
                    raise ValueError(
                        f"analysis.profitability_keywords.{category} contains an empty keyword"
                    )

        return value


class PipelineSettings(BaseModel):
    report_name_keywords: dict[str, list[str]] = Field(default_factory=dict)
    reprt_codes: dict[str, str] = Field(default_factory=dict)
    analysis: AnalysisConfig

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @field_validator("report_name_keywords")
    @classmethod
    def validate_report_name_keywords(
        cls, value: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        required_base = ("annual", "semiannual")
        missing_base = [key for key in required_base if key not in value]
        if missing_base:
            missing = ", ".join(missing_base)
            raise ValueError(
                f"report_name_keywords is missing required key(s): {missing}"
            )

        has_quarterly_split = "q1" in value and "q3" in value
        has_quarterly_alias = "quarterly" in value
        if not has_quarterly_split and not has_quarterly_alias:
            raise ValueError("report_name_keywords must include q1/q3 or quarterly")

        for key, keywords in value.items():
            if not keywords:
                raise ValueError(f"report_name_keywords.{key} must be a non-empty list")
            for keyword in keywords:
                if not keyword or not keyword.strip():
                    raise ValueError(
                        f"report_name_keywords.{key} contains an empty keyword"
                    )

        return value

    @field_validator("reprt_codes")
    @classmethod
    def validate_reprt_codes(cls, value: dict[str, str]) -> dict[str, str]:
        required = ("annual", "semiannual", "q1", "q3")
        missing = [key for key in required if key not in value]
        if missing:
            missing_keys = ", ".join(missing)
            raise ValueError(f"reprt_codes is missing required key(s): {missing_keys}")

        for key, code in value.items():
            if not code.isdigit() or len(code) != 5:
                raise ValueError(f"reprt_codes.{key} must be a 5-digit string")

        return value

    @model_validator(mode="after")
    def normalize_quarterly_keywords(self) -> PipelineSettings:
        quarterly = self.report_name_keywords.get("quarterly")
        if quarterly:
            _ = self.report_name_keywords.setdefault("q1", quarterly)
            _ = self.report_name_keywords.setdefault("q3", quarterly)
        return self

    def to_legacy_dict(self) -> dict[str, object]:
        return self.model_dump()


def validate_settings(data: object) -> PipelineSettings:
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping")
    return PipelineSettings.model_validate(data)
