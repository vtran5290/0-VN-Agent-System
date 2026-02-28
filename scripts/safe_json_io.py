"""
Safe JSON read/update/write. Never wipe keys not provided.
Idempotent; atomic write to avoid partial overwrite.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def safe_read_json(path: Path) -> Dict[str, Any]:
    """Return dict; empty dict if missing or invalid."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("safe_read_json %s: %s", path, e)
        return {}


def safe_update_nested(data: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """
    Merge updates into data in-place. Only overwrite keys present in updates.
    Nested dicts are merged recursively; lists/other values are replaced.
    """
    for key, val in updates.items():
        if key not in data:
            data[key] = val
            continue
        if isinstance(val, dict) and isinstance(data.get(key), dict):
            safe_update_nested(data[key], val)
        else:
            data[key] = val


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON to temp file then rename. Parent dir created if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        Path(tmp).replace(path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
