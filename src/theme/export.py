# src/theme/export.py — Write candidates CSV and full score table
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CANDIDATES_DIR = REPO_ROOT / "data" / "raw" / "candidates"
SCORES_DIR = REPO_ROOT / "data" / "features" / "theme_scores"


def ensure_dirs() -> None:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    SCORES_DIR.mkdir(parents=True, exist_ok=True)


def write_candidates_csv(df: pd.DataFrame, asof_date: str, pack_id: str = "ai_energy_overspill") -> Path:
    """
    Write data/raw/candidates/ai_energy_overspill_candidates.csv.
    Columns: symbol, tier, total_score, lane, flags.
    """
    ensure_dirs()
    out = df[["symbol", "tier", "total_score", "lane", "flags"]].copy()
    out["total_score"] = out["total_score"].round(4)
    path = CANDIDATES_DIR / f"{pack_id}_candidates.csv"
    out.to_csv(path, index=False)
    return path


def write_scores_csv(df: pd.DataFrame, asof_date: str, pack_id: str = "ai_energy_overspill") -> Path:
    """
    Write data/features/theme_scores/ai_energy_overspill_scores_YYYYMMDD.csv.
    Full scored table (all component columns + total_score, lane, flags, tier).
    """
    ensure_dirs()
    date_str = asof_date.replace("-", "")[:8]
    path = SCORES_DIR / f"{pack_id}_scores_{date_str}.csv"
    out = df.copy()
    if "total_score" in out.columns:
        out["total_score"] = out["total_score"].round(4)
    out.to_csv(path, index=False)
    return path
