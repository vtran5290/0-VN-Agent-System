"""Validation helpers for weekly report schema and payload."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def validate_weekly_report_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Lightweight validation: required metadata fields and types.
    Returns (ok, list of error messages).
    """
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["Payload must be a JSON object"]
    meta = payload.get("metadata")
    if meta is None or not isinstance(meta, dict):
        errors.append("metadata is required and must be an object")
    else:
        if not meta.get("asof_date"):
            errors.append("metadata.asof_date is required")
        if not meta.get("schema_version"):
            errors.append("metadata.schema_version is required")
        conf = meta.get("data_confidence")
        if conf is not None and conf not in ("High", "Medium", "Low"):
            errors.append("metadata.data_confidence must be High, Medium, or Low")
    return len(errors) == 0, errors


def validate_weekly_report_file(path: Path) -> Tuple[bool, List[str]]:
    """Load JSON from path and validate; return (ok, errors)."""
    path = Path(path)
    if not path.exists():
        return False, [f"File not found: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return False, [str(e)]
    return validate_weekly_report_payload(data)


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load JSON schema file; return {} on failure."""
    if not schema_path.exists():
        return {}
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
