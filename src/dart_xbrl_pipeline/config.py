from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .config_models import validate_settings


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_settings() -> dict[str, Any]:
    load_dotenv(project_root() / ".env")
    with open(project_root() / "config" / "default.yaml", "r", encoding="utf-8") as f:
        raw_settings = yaml.safe_load(f)
    validated = validate_settings(raw_settings)
    return validated.to_legacy_dict()
