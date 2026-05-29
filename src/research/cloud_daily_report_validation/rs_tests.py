"""RS Correction lens tests — section 5.7.

References data/research/rs_vs_vnindex_correction_20260515_20260525.csv as partial evidence.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    _REPO,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_RS_CSV = _REPO / "data" / "research" / "rs_vs_vnindex_correction_20260515_20260525.csv"
_OUTPUT_FILE = OUTPUT_DIR / "rs_correction_validation.csv"


def run_rs_correction_validation() -> pd.DataFrame:
    """Load and summarize existing RS correction evidence.

    The rs_vs_vnindex_correction CSV already contains an event study.
    This function reads it and returns a labelled summary.

    Evidence label: DIRECTIONALLY_SUPPORTED (PARTIALLY_VALIDATED).
    """
    rows: list[dict] = []
    base = {
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "source_file": str(_RS_CSV),
    }

    if not _RS_CSV.is_file():
        rows.append({
            **base,
            "test": "rs_leaders_correction",
            "n_events": 0,
            "mean_ret": None,
            "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
            "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
            "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
            "notes": f"BLOCKED_BY_DATA: RS correction CSV not found at {_RS_CSV}",
        })
        return pd.DataFrame(rows)

    try:
        df = pd.read_csv(_RS_CSV)
    except Exception as exc:
        rows.append({
            **base,
            "test": "rs_leaders_correction",
            "n_events": 0,
            "mean_ret": None,
            "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
            "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
            "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
            "notes": f"BLOCKED_BY_DATA: failed to read RS correction CSV: {exc}",
        })
        return pd.DataFrame(rows)

    n_rows = len(df)
    logger.info("RS correction CSV loaded: %d rows", n_rows)

    # Summarize each numeric return column found
    ret_cols = [c for c in df.columns if "ret" in c.lower() or "return" in c.lower()]
    if not ret_cols:
        ret_cols = [c for c in df.columns if df[c].dtype in ("float64", "float32")]

    for col in ret_cols[:4]:  # Summarize up to 4 return columns
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        rows.append({
            **base,
            "test": f"rs_leaders_{col}",
            "n_events": len(vals),
            "mean_ret": round(float(vals.mean()), 6) if len(vals) > 0 else None,
            "pct_positive": round(float((vals > 0).mean()), 4) if len(vals) > 0 else None,
            "evidence_status": EvidenceStatus.PARTIALLY_VALIDATED.value,
            "evidence_label": EvidenceLabel.INCONCLUSIVE_DIRECTIONAL_ONLY.value,
            "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
            "notes": (
                "INCONCLUSIVE_DIRECTIONAL_ONLY: RS correction event study exists "
                f"(2026-05-15 to 2026-05-25); 10-day window is insufficient for "
                "DIRECTIONALLY_SUPPORTED label. Need ≥90 trading days / ≥3 correction events."
            ),
        })

    if not rows:
        rows.append({
            **base,
            "test": "rs_leaders_correction",
            "n_events": n_rows,
            "mean_ret": None,
            "evidence_status": EvidenceStatus.PARTIALLY_VALIDATED.value,
            "evidence_label": EvidenceLabel.DIRECTIONALLY_SUPPORTED.value,
            "dashboard_recommendation": DashboardRecommendation.KEEP_AS_RISK_CONTROL.value,
            "notes": "RS correction CSV found; no numeric return columns to summarize",
        })

    return pd.DataFrame(rows)


def run_rs_correction_validation_full() -> pd.DataFrame:
    """Run RS correction validation, writing results to CSV."""
    result = run_rs_correction_validation()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("RS correction validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
