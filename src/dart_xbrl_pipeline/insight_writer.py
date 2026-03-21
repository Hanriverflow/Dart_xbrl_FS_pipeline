from __future__ import annotations
# pyright: reportMissingImports=false

import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .insight_models import EvidenceType, InsightInput, ProfitabilityMemo


class InsightWriterError(RuntimeError):
    pass


class InsightWriter:
    _DEFAULT_CONFIG: dict[str, Any] = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 1800,
        "cache_enabled": True,
        "cache_path": None,
        "prompt_template_path": None,
        "timeout": 30,
        "rcept_no": "unknown",
        "corp_name": "unknown",
        "report_type": "unknown",
    }

    def __init__(
        self, llm_client: Any | None = None, config: dict[str, Any] | None = None
    ):
        self._llm_client = llm_client
        self._config = dict(self._DEFAULT_CONFIG)
        if config:
            self._config.update(config)

        self._cache: dict[str, dict[str, Any]] = {}
        self._active_table_ids: set[str] = set()
        self._active_accounts: set[str] = set()
        self._active_metrics: set[str] = set()
        self.token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "cache_hits": 0,
        }

        self._template_path = self._resolve_template_path()
        self._cache_path = self._resolve_cache_path()
        self._load_cache_if_needed()

    def generate_memo(self, input: InsightInput) -> ProfitabilityMemo:
        self._index_input_references(input)
        prompt = self._build_prompt(input)
        cache_key = self._build_cache_key(prompt)

        response_payload: dict[str, Any]
        if self._config["cache_enabled"] and cache_key in self._cache:
            self.token_usage["cache_hits"] += 1
            response_payload = self._cache[cache_key]
        else:
            response_payload = self._call_llm(prompt)
            if self._config["cache_enabled"]:
                self._cache[cache_key] = response_payload
                self._persist_cache_if_needed()

        memo = self._parse_memo_response(response_payload)
        if not self._validate_claims(memo):
            raise InsightWriterError(
                "Unsupported assertion detected: every claim must reference an existing table_id or account/metric"
            )
        return memo

    def _build_prompt(self, input: InsightInput) -> str:
        template = self._template_path.read_text(encoding="utf-8")
        payload = {
            "metrics": input.metrics,
            "highlights": input.highlights,
            "tables": [
                {
                    "table_id": table.table_id,
                    "title": table.title,
                    "columns": table.columns,
                    "row_headers": [row.header for row in table.rows if row.header],
                    "unit": table.unit,
                    "period_context": table.period_context,
                    "source_ref": table.source_ref,
                }
                for table in input.tables
            ],
        }
        return template.replace(
            "{{INPUT_JSON}}", json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def _validate_claims(self, memo: ProfitabilityMemo) -> bool:
        for claim in memo.claims:
            if not claim.evidence:
                return False

            has_supported_evidence = False
            for evidence in claim.evidence:
                if not evidence.ref_id.strip():
                    continue

                ref_id = evidence.ref_id.strip()
                if (
                    evidence.type is EvidenceType.table
                    and ref_id in self._active_table_ids
                ):
                    has_supported_evidence = True
                elif (
                    evidence.type is EvidenceType.account
                    and ref_id in self._active_accounts
                ):
                    has_supported_evidence = True
                elif (
                    evidence.type is EvidenceType.metric
                    and ref_id in self._active_metrics
                ):
                    has_supported_evidence = True

            if not has_supported_evidence:
                return False

        return True

    def save_memo(
        self, memo: ProfitabilityMemo, output_path: Path, title: str | None = None
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self.memo_to_markdown(memo, title=title or "수익성 개선 포인트"),
            encoding="utf-8",
        )

    def _resolve_template_path(self) -> Path:
        configured = self._config.get("prompt_template_path")
        if configured:
            return Path(configured)
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "config" / "insight_prompt_template.txt"

    def _resolve_cache_path(self) -> Path | None:
        configured = self._config.get("cache_path")
        if not configured:
            return None
        return Path(configured)

    def _build_cache_key(self, prompt: str) -> str:
        basis = {
            "provider": self._config["provider"],
            "model": self._config["model"],
            "temperature": self._config["temperature"],
            "prompt": prompt,
        }
        encoded = json.dumps(basis, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _index_input_references(self, input: InsightInput) -> None:
        self._active_table_ids = {table.table_id for table in input.tables}
        self._active_metrics = set(input.metrics.keys())

        accounts = set(input.metrics.keys())
        for table in input.tables:
            for column in table.columns:
                if column:
                    accounts.add(column.strip())
            for row in table.rows:
                if row.header:
                    accounts.add(row.header.strip())
        self._active_accounts = {account for account in accounts if account}

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        try:
            if self._llm_client is not None:
                return self._call_injected_client(prompt)
            return self._call_provider_client(prompt)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise InsightWriterError(f"LLM request failed: {exc}") from exc

    def _call_injected_client(self, prompt: str) -> dict[str, Any]:
        client = self._llm_client
        if client is None:
            raise InsightWriterError("llm_client is not configured")

        if hasattr(client, "generate"):
            response = client.generate(prompt=prompt, config=self._config)
        elif callable(client):
            response = client(prompt)
        else:
            raise InsightWriterError(
                "llm_client must be callable or provide generate(prompt, config)"
            )

        payload = self._normalize_response_payload(response)
        self._accumulate_usage(payload.get("usage", {}))
        return payload

    def _call_provider_client(self, prompt: str) -> dict[str, Any]:
        provider = str(self._config["provider"]).lower()
        if provider == "openai":
            return self._call_openai(prompt)
        if provider == "anthropic":
            return self._call_anthropic(prompt)
        raise InsightWriterError(f"Unsupported LLM provider: {provider}")

    def _call_openai(self, prompt: str) -> dict[str, Any]:
        try:
            openai_module = importlib.import_module("openai")
            openai_cls = getattr(openai_module, "OpenAI")
        except ImportError as exc:  # pragma: no cover - dependency boundary
            raise InsightWriterError(
                "OpenAI client not installed. Add 'openai' package to use provider='openai'."
            ) from exc

        client = openai_cls()
        response = client.responses.create(
            model=self._config["model"],
            input=prompt,
            temperature=float(self._config["temperature"]),
            max_output_tokens=int(self._config["max_tokens"]),
        )
        usage = {
            "prompt_tokens": getattr(response.usage, "input_tokens", 0),
            "completion_tokens": getattr(response.usage, "output_tokens", 0),
            "total_tokens": getattr(response.usage, "total_tokens", 0),
        }
        payload = {"text": response.output_text, "usage": usage}
        self._accumulate_usage(usage)
        return payload

    def _call_anthropic(self, prompt: str) -> dict[str, Any]:
        try:
            anthropic_module = importlib.import_module("anthropic")
            anthropic_cls = getattr(anthropic_module, "Anthropic")
        except ImportError as exc:  # pragma: no cover - dependency boundary
            raise InsightWriterError(
                "Anthropic client not installed. Add 'anthropic' package to use provider='anthropic'."
            ) from exc

        client = anthropic_cls()
        response = client.messages.create(
            model=self._config["model"],
            temperature=float(self._config["temperature"]),
            max_tokens=int(self._config["max_tokens"]),
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        ]
        usage = {
            "prompt_tokens": getattr(response.usage, "input_tokens", 0),
            "completion_tokens": getattr(response.usage, "output_tokens", 0),
            "total_tokens": getattr(response.usage, "input_tokens", 0)
            + getattr(response.usage, "output_tokens", 0),
        }
        payload = {"text": "\n".join(text_parts), "usage": usage}
        self._accumulate_usage(usage)
        return payload

    def _normalize_response_payload(self, response: Any) -> dict[str, Any]:
        if isinstance(response, str):
            return {"text": response, "usage": {}}

        if isinstance(response, dict):
            if "text" in response:
                return {
                    "text": str(response.get("text", "")),
                    "usage": dict(response.get("usage", {})),
                }
            if "content" in response:
                return {
                    "text": str(response.get("content", "")),
                    "usage": dict(response.get("usage", {})),
                }

        raise InsightWriterError(
            "Unsupported LLM response shape; expected string or dict with text/content"
        )

    def _accumulate_usage(self, usage: dict[str, Any]) -> None:
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(
            usage.get("total_tokens", prompt_tokens + completion_tokens) or 0
        )
        self.token_usage["prompt_tokens"] += prompt_tokens
        self.token_usage["completion_tokens"] += completion_tokens
        self.token_usage["total_tokens"] += total_tokens
        self.token_usage["requests"] += 1

    def _parse_memo_response(
        self, response_payload: dict[str, Any]
    ) -> ProfitabilityMemo:
        text = str(response_payload.get("text", "")).strip()
        if not text:
            raise InsightWriterError("LLM returned an empty response")

        extracted_json = self._extract_json_block(text)
        if extracted_json is None:
            raise InsightWriterError(
                "LLM response must contain valid JSON for ProfitabilityMemo"
            )

        try:
            body = json.loads(extracted_json)
        except json.JSONDecodeError as exc:
            raise InsightWriterError(f"Failed to decode memo JSON: {exc}") from exc

        if "generated_at" not in body:
            body["generated_at"] = datetime.now(timezone.utc).isoformat()
        if "rcept_no" not in body:
            body["rcept_no"] = self._config["rcept_no"]
        if "corp_name" not in body:
            body["corp_name"] = self._config["corp_name"]
        if "report_type" not in body:
            body["report_type"] = self._config["report_type"]
        if "summary" not in body:
            body["summary"] = "추가 확인 필요"
        if "risks" not in body:
            body["risks"] = ["추가 확인 필요"]
        if "action_items" not in body:
            body["action_items"] = ["추가 확인 필요"]

        try:
            return ProfitabilityMemo.model_validate(body)
        except Exception as exc:
            raise InsightWriterError(f"Memo validation failed: {exc}") from exc

    @staticmethod
    def _extract_json_block(text: str) -> str | None:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        return stripped[start : end + 1]

    @staticmethod
    def memo_to_markdown(
        memo: ProfitabilityMemo, title: str = "수익성 개선 포인트"
    ) -> str:
        lines: list[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"- 접수번호: {memo.rcept_no}")
        lines.append(f"- 회사명: {memo.corp_name}")
        lines.append(f"- 보고서 유형: {memo.report_type}")
        lines.append(f"- 생성시각: {memo.generated_at.isoformat()}")
        lines.append("")
        lines.append("## 핵심 개선 포인트")
        if memo.claims:
            for claim in memo.claims:
                refs = ", ".join(
                    f"{e.type.value}:{e.ref_id or e.value}" for e in claim.evidence
                )
                lines.append(
                    f"- {claim.claim} (카테고리: {claim.category}, 신뢰도: {claim.confidence}, 근거: {refs})"
                )
        else:
            lines.append("- 추가 확인 필요")
        lines.append("")

        lines.append("## 근거 수치")
        lines.append("| 구분 | 근거 타입 | 참조 | 수치/값 | 맥락 |")
        lines.append("|---|---|---|---|---|")
        row_written = False
        for claim in memo.claims:
            for evidence in claim.evidence:
                lines.append(
                    f"| {claim.claim} | {evidence.type.value} | {evidence.ref_id} | {evidence.value} | {evidence.context or ''} |"
                )
                row_written = True
        if not row_written:
            lines.append("| 추가 확인 필요 | - | - | - | - |")
        lines.append("")

        lines.append("## 리스크")
        if memo.risks:
            for risk in memo.risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- 추가 확인 필요")
        lines.append("")

        lines.append("## 추가 확인 필요")
        low_confidence_claims = [
            claim.claim for claim in memo.claims if claim.confidence == "low"
        ]
        items = list(memo.action_items)
        for claim_text in low_confidence_claims:
            items.append(f"저신뢰 주장 재검증: {claim_text}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- 없음")

        return "\n".join(lines)

    def _load_cache_if_needed(self) -> None:
        if not self._cache_path:
            return
        if not self._cache_path.exists():
            return
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._cache = {
                    key: value
                    for key, value in raw.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
        except json.JSONDecodeError:
            self._cache = {}

    def _persist_cache_if_needed(self) -> None:
        if not self._cache_path:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
