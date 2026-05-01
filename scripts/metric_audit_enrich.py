"""Fill previous_value on global_metrics_audit from manual_inputs_prev.json."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]
PREV_PATH = REPO / "data" / "raw" / "manual_inputs_prev.json"

# metric_key -> key in prev global{} (legacy dxy may match dxy_ice WoW)
_PREV_GLOBAL_KEY = {
    "ust_2y": "ust_2y",
    "ust_10y": "ust_10y",
    "dxy_ice": "dxy",
    "dxy_reconstructed": "dxy",
    "dxy_third_party": "dxy_third_party_proxy",
    "usd_broad_index_fred": "usd_broad_index_fred",
    "cpi_yoy": "cpi_yoy",
    "nonfarm_payroll_level_thousands": "nonfarm_payroll_level_thousands",
    "nonfarm_payroll_change_persons": "nonfarm_payroll_change_persons",
}


def enrich_global_metrics_audit_rows(data: Dict[str, Any]) -> None:
    audit = data.get("global_metrics_audit")
    if not isinstance(audit, list):
        return
    try:
        from scripts.safe_json_io import safe_read_json

        prev = safe_read_json(PREV_PATH)
    except Exception:
        return
    pg = (prev.get("global") or {}) if prev else {}
    for row in audit:
        if not isinstance(row, dict):
            continue
        mk = row.get("metric_key")
        pkey = _PREV_GLOBAL_KEY.get(str(mk or ""))
        if not pkey:
            continue
        if row.get("previous_value") is not None:
            continue
        pv = pg.get(pkey)
        if pv is not None:
            row["previous_value"] = pv
