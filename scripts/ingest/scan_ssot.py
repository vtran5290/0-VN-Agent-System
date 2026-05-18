"""Phase36 scan CSV load + A3 production action mapping (no signal recompute)."""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
SCAN_DIR = REPO / "data" / "research" / "portfolio_optimization" / "missing_work"
PHASE36_LATEST_NAME = "phase36_daily_scan_latest.csv"
PHASE36_LEGACY_NAME = "phase36_daily_scan_sample.csv"
STRATEGY_CONFIG = REPO / "config" / "weekly_report_strategy.yaml"

# Operator-facing action from scan final_action (production display only)
OPERATOR_ACTION_MAP: Dict[str, Tuple[str, str]] = {
    "TRAIL_EXIT": ("SELL / EXIT", "Exit on trail breach"),
    "MAX_HOLD_EXIT": ("SELL / EXIT", "Max hold exit"),
    "TP1_PARTIAL": ("TRIM", "Take profit partial"),
    "NO_T2_BREADTH": ("HOLD T1 / BLOCK ADD", "T2 blocked by breadth"),
    "HOLD_T1_ONLY": ("HOLD / MONITOR", "Hold T1 only"),
    "NEW_T1": ("BUY CANDIDATE", "New T1 if slot available"),
    "NEW_T1_MANUAL_REVIEW_BREADTH": ("MANUAL REVIEW", "Breadth defense — operator review"),
    "WAIT_PB": ("BUY ON PULLBACK", "Wait for pullback trigger"),
    "ADD_T2": ("ADD T2", "Add on pullback trigger"),
    "SKIP_LIQUIDITY": ("SKIP", "Liquidity skip"),
    "SKIP_VNINDEX_BEAR": ("SKIP", "VNINDEX bear regime skip"),
    "WATCH_ONLY": ("WATCH ONLY", "No production action"),
    "S3_RESEARCH_ONLY": ("RESEARCH ONLY", "S3 research — not production"),
}


def _load_yaml_config() -> Dict[str, Any]:
    if not STRATEGY_CONFIG.exists():
        return {
            "production_classification": "A3_PRODUCTION",
            "show_research_watchlist": False,
        }
    try:
        import yaml
    except ImportError:
        return {"production_classification": "A3_PRODUCTION", "show_research_watchlist": False}
    data = yaml.safe_load(STRATEGY_CONFIG.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def resolve_scan_path() -> Optional[Path]:
    """Align with trading scan_resolver: env > latest > dated daily > legacy sample."""
    env_path = os.environ.get("PHASE36_DAILY_SCAN_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    if not SCAN_DIR.exists():
        return None

    latest = SCAN_DIR / PHASE36_LATEST_NAME
    if latest.is_file():
        return latest

    dated_pat = re.compile(r"^phase36_daily_scan_\d{8}\.csv$", re.I)
    dated = sorted(
        (p for p in SCAN_DIR.iterdir() if p.is_file() and dated_pat.match(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    if dated:
        return dated[0]

    legacy = SCAN_DIR / PHASE36_LEGACY_NAME
    if legacy.is_file():
        return legacy

    return None


def load_scan_rows(
    *,
    production_only: bool = True,
    path: Optional[Path] = None,
) -> Tuple[List[Dict[str, str]], Optional[Path], Dict[str, Any]]:
    cfg = _load_yaml_config()
    prod_class = cfg.get("production_classification", "A3_PRODUCTION")
    show_research = bool(cfg.get("show_research_watchlist", False))
    p = path or resolve_scan_path()
    if not p or not p.exists():
        return [], p, cfg

    rows: List[Dict[str, str]] = []
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sym = (row.get("symbol") or "").strip().upper()
            if not sym:
                continue
            cls = (row.get("strategy_classification") or "").strip()
            if production_only and not show_research:
                if cls != prod_class:
                    continue
            rows.append(row)
    return rows, p, cfg


def scan_by_symbol(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {(r.get("symbol") or "").upper(): r for r in rows if r.get("symbol")}


def load_scan_lookup_all(
    path: Optional[Path] = None,
) -> Tuple[Dict[str, Dict[str, str]], Optional[Path]]:
    """All scan rows (any classification) keyed by symbol — for portfolio gap diagnostics only."""
    rows, p, _ = load_scan_rows(production_only=False, path=path)
    return scan_by_symbol(rows), p


def portfolio_scan_gap_reason(
    symbol: str,
    production_map: Dict[str, Dict[str, str]],
    full_map: Dict[str, Dict[str, str]],
) -> str:
    """
    Explain why a holding has no A3_PRODUCTION scan join (display only; does not change final_action).
    """
    sym = (symbol or "").upper()
    if sym in production_map:
        return ""
    row = full_map.get(sym)
    if not row:
        return (
            "No scan row — phase36 only outputs symbols with active A3 or S3 signal "
            "within last 40 bars (not a production HOLD row)"
        )
    cls = (row.get("strategy_classification") or "UNKNOWN").strip()
    fa = (row.get("final_action") or "—").strip()
    return f"In scan as {cls} ({fa}) — excluded from A3_PRODUCTION production book"


def map_operator_action(final_action: str) -> Tuple[str, str]:
    fa = (final_action or "").strip().upper()
    if fa in OPERATOR_ACTION_MAP:
        return OPERATOR_ACTION_MAP[fa]
    if "EXIT" in fa or "TRAIL" in fa:
        return "SELL / EXIT", fa
    if "NEW_T1" in fa:
        return "BUY CANDIDATE", fa
    return "MONITOR", fa or "Missing"


def watchlist_trigger_label(final_action: str, row: Dict[str, str]) -> str:
    """Semantic trigger label by final_action (display only)."""
    fa = (final_action or "").upper()
    if fa == "WAIT_PB":
        return price_or_missing_from_scan(row.get("pb_trigger_price"), "Pullback trigger")
    if fa == "ADD_T2":
        return price_or_missing_from_scan(row.get("pb_trigger_price"), "T2 trigger")
    if fa in ("NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"):
        return "Entry review (see scan reason)"
    if fa == "TP1_PARTIAL":
        t = row.get("tp1_price")
        return f"TP1 target {t}" if t not in (None, "", "None") else "TP1 target Missing"
    if fa in ("TRAIL_EXIT", "MAX_HOLD_EXIT"):
        t = row.get("trail_price")
        return f"Trail {t}" if t not in (None, "", "None") else "Trail level Missing"
    if fa == "NO_T2_BREADTH":
        return "T2 blocked by breadth"
    if fa == "HOLD_T1_ONLY":
        return "Monitor trail"
    if fa == "WATCH_ONLY":
        return "Watch only"
    if fa == "S3_RESEARCH_ONLY":
        return "Research only"
    if fa == "SKIP_LIQUIDITY":
        return "Skip — liquidity"
    if fa == "SKIP_VNINDEX_BEAR":
        return "Skip — VNINDEX bear"
    return "—"


def price_or_missing_from_scan(v: Any, label: str) -> str:
    if v in (None, "", "None", "none", "nan", "null"):
        return "Missing"
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "Missing"


def watchlist_bucket(final_action: str, classification: str) -> str:
    fa = (final_action or "").upper()
    cls = (classification or "").upper()
    if cls == "S3_RESEARCH_ONLY" or fa == "WATCH_ONLY":
        return "Watch / Research Only"
    if "NEW_T1_MANUAL_REVIEW" in fa or "SKIP_VNINDEX" in fa:
        return "Blocked by Breadth"
    if fa in ("NEW_T1",) or "FULL_T1" in fa:
        return "Buy Now Candidate"
    if fa == "WAIT_PB":
        return "Buy on Pullback"
    if "RECLAIM" in fa:
        return "Buy on Reclaim"
    if fa in ("TRAIL_EXIT", "MAX_HOLD_EXIT", "SKIP_LIQUIDITY"):
        return "Avoid / Remove"
    if fa in ("NO_T2_BREADTH", "HOLD_T1_ONLY", "ADD_T2", "TP1_PARTIAL"):
        return "Hold / Monitor"
    return "Hold / Monitor"
