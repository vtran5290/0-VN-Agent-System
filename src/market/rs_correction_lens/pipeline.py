"""Run RS correction lens and write SSOT artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .compute import compute_rs_correction_table

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "research" / "market_risk"
LATEST_JSON = OUT_DIR / "rs_correction_latest.json"
LATEST_CSV = OUT_DIR / "rs_correction_latest.csv"


def run_rs_correction_lens(
    *,
    as_of: Optional[str] = None,
    anchor_date: Optional[str] = None,
) -> dict[str, Any]:
    df, meta, warnings = compute_rs_correction_table(as_of=as_of, anchor_date=anchor_date)
    as_of_date = meta["anchor"]["end_date"]
    leaders = (
        df[df["bucket"] == "leader_strong"].sort_values("rs_pct", ascending=False).head(25)
        if not df.empty
        else pd.DataFrame()
    )
    improving = (
        df[(df["rs_pct"] > 0) & (df["rs_improving_flag"])]
        .sort_values("rs_pct", ascending=False)
        .head(25)
        if not df.empty
        else pd.DataFrame()
    )
    flat = (
        df[(df["ret_pct"] >= -1) & (df["ret_pct"] <= 2) & (df["rs_pct"] >= 1)]
        .sort_values("rs_pct", ascending=False)
        .head(25)
        if not df.empty
        else pd.DataFrame()
    )
    laggards = df.sort_values("rs_pct").head(15) if not df.empty else pd.DataFrame()

    payload: dict[str, Any] = {
        "as_of_date": as_of_date,
        "requested_as_of_date": as_of or as_of_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method_version": "rs_correction_lens_v1.1",
        "load_warnings": warnings,
        **meta,
        "leaders_top25": leaders.to_dict(orient="records"),
        "improving_top25": improving.to_dict(orient="records"),
        "defensive_flat_top25": flat.to_dict(orient="records"),
        "laggards_bottom15": laggards.to_dict(orient="records"),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.sort_values("rs_pct", ascending=False).to_csv(LATEST_CSV, index=False)
    LATEST_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_csv"] = str(LATEST_CSV)
    payload["output_json"] = str(LATEST_JSON)
    return payload
