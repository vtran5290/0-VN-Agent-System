# src/theme/loaders.py — Load watchlist/universe and fundamentals snapshot
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .schema import LANES, validate_lane, validate_missing_policy

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FUNDAMENTALS_DEFAULT = REPO_ROOT / "data" / "sources" / "company" / "fundamentals_snapshot.csv"


def load_pack_config(path: Path) -> dict:
    """Load and validate theme pack JSON. Returns dict with lanes, weights_by_lane, thresholds, missing_policy."""
    raw = path.read_text(encoding="utf-8")
    cfg = json.loads(raw)
    for lane in cfg.get("lanes", []):
        validate_lane(lane)
    if "missing_policy" in cfg:
        validate_missing_policy(cfg["missing_policy"])
    return cfg


def load_fundamentals(path: Path | None = None) -> pd.DataFrame:
    """
    Load fundamentals snapshot CSV. Best-effort: allow missing columns.
    Required columns (optional): symbol, roe_5y_median, roic_5y_median, fcf_margin_5y_median,
    fcf_positive_years_5y, net_debt_to_ebitda, interest_coverage, working_capital_days,
    capex_to_sales_5y, pe_ttm, pb_ttm, ev_ebitda_ttm, fwd_pe, gross_margin_stability.
    """
    p = path or FUNDAMENTALS_DEFAULT
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, dtype=str)
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    return df


def load_watchlist(path: Path | None, repo_root: Path | None = None) -> list[str]:
    """Load symbol list from watchlist file (one per line, # comment)."""
    root = repo_root or REPO_ROOT
    if path is None:
        p = root / "config" / "watchlist.txt"
    else:
        p = path if path.is_absolute() else root / path
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def load_symbols_from_args(
    watchlist_path: str | None,
    symbols: list[str] | None,
    universe: str,
    candidates_path: str | None,
    repo_root: Path | None = None,
) -> list[str]:
    """
    Resolve initial symbol list: watchlist file, or explicit --symbols, or candidates (txt) for liquidity_topn.
    Does NOT load ThemePack CSV (that is done in run_theme_pack only).
    """
    root = repo_root or REPO_ROOT
    if symbols:
        return [s.strip().upper() for s in symbols if s.strip()]
    if watchlist_path:
        p = Path(watchlist_path) if Path(watchlist_path).is_absolute() else root / watchlist_path
        return load_watchlist(p, root)
    if universe == "liquidity_topn" and candidates_path:
        return load_candidates_txt(Path(candidates_path) if Path(candidates_path).is_absolute() else root / candidates_path)
    return load_watchlist(None, root)


def load_candidates_txt(path: Path) -> list[str]:
    """Load one symbol per line (no header)."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
