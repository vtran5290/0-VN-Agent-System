"""Compact JSON, hashing, atomic writes, size guards."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.mcp_server.config import MAX_JSON_CHARS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def file_sha256(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def file_mtime_iso(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()


def parquet_max_date(path: Path, date_col: str = "date") -> Optional[str]:
    if not path.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_parquet(path, columns=[date_col])
        if df.empty:
            return None
        return pd.to_datetime(df[date_col]).max().strftime("%Y-%m-%d")
    except Exception:
        return None


def compact_json(payload: Dict[str, Any], max_chars: int = MAX_JSON_CHARS) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) <= max_chars:
        return text
    return json.dumps(
        {
            "truncated": True,
            "original_chars": len(text),
            "preview": payload,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )[:max_chars]


def ok(tool: str, data: Dict[str, Any], **meta: Any) -> str:
    return compact_json({"ok": True, "tool": tool, "asof": utc_now_iso(), "data": data, **meta})


def err(tool: str, code: str, message: str, **extra: Any) -> str:
    return compact_json(
        {"ok": False, "tool": tool, "error_code": code, "message": message, "asof": utc_now_iso(), **extra}
    )


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
