"""Write v2 research outputs."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
OUT_JSON = _REPO / "data" / "research" / "vnindex_dist_v2_summary.json"
OUT_CSV = _REPO / "data" / "research" / "vnindex_dist_v2_anchors.csv"
OUT_DECISION_CSV = _REPO / "data" / "research" / "vnindex_dist_v2_decision_table.csv"
OUT_MD = _REPO / "data" / "research" / "vnindex_dist_v2_methods_note.md"


def ensure_outdir() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)


def write_json(payload: dict) -> None:
    ensure_outdir()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def write_csv(df: pd.DataFrame) -> None:
    ensure_outdir()
    df.to_csv(OUT_CSV, index=False)


def write_decision_csv(df: pd.DataFrame) -> None:
    ensure_outdir()
    df.to_csv(OUT_DECISION_CSV, index=False)


def write_methods_md(content: str) -> None:
    ensure_outdir()
    OUT_MD.write_text(content, encoding="utf-8")


def _json_default(o: object) -> object:
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))
