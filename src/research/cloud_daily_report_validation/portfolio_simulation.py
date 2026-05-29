"""Portfolio simulation — section 6.

With only ~1wk of scan data: BLOCKED_BY_DATA for real simulation.
Can show reconstructed proxy simulation from OHLCV using A3 cloud signal.
All outputs labeled RECONSTRUCTED_NOT_LIVE_SCAN.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np

from .data_loader import LABEL_RECONSTRUCTED, load_ohlcv_panel, load_scan_files
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "portfolio_simulation.csv"

_WHAT_IS_NEEDED = [
    "Minimum 6 months of scan history (daily) to construct a meaningful simulation",
    "Position sizing rules matched to live trading config (config/live_trading.yaml)",
    "Portfolio NAV starting point and cash management rules",
    "T+1 execution model with realistic slippage and liquidity constraints",
    "Entry/exit matching: final_action=NEW_T1 → entry at T+1 open; TRAIL_EXIT → exit at T+1 open",
    "Breadth gate enforcement: only enter on breadth_t1_permission=True days",
    "Historical portfolio state snapshots for validation against actual P&L",
]


def run_proxy_simulation(
    scan_df: pd.DataFrame,
    ohlcv: pd.DataFrame,
    initial_nav: float = 1_000_000_000.0,  # 1 billion VND
) -> pd.DataFrame:
    """Reconstructed proxy simulation using A3 cloud signal from scan CSVs.

    Uses a3_cloud_bull=True + breadth_t1_permission=True as entry signal.
    Equal-weight position sizing, exit on a3_cloud_bull=False.

    IMPORTANT: This is RECONSTRUCTED_NOT_LIVE_SCAN — the scan files only cover
    2026-05-15 to 2026-05-28, which is ~2 weeks. This is insufficient for a
    meaningful simulation. Results are BLOCKED_BY_DATA.
    """
    if scan_df.empty:
        return pd.DataFrame([{
            "simulation": "proxy_a3_cloud_signal",
            "status": "BLOCKED_BY_DATA",
            "reason": "scan_df empty — insufficient history",
            "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
            "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
        }])

    # Get date range
    if "as_of_date" in scan_df.columns:
        dates = pd.to_datetime(scan_df["as_of_date"], errors="coerce").dropna()
        n_days = dates.nunique()
        min_date = str(dates.min().date()) if not dates.empty else "unknown"
        max_date = str(dates.max().date()) if not dates.empty else "unknown"
    else:
        n_days = 0
        min_date = max_date = "unknown"

    # Check if we have enough data for a simulation (need at least 30 trading days)
    min_required_days = 30
    if n_days < min_required_days:
        return pd.DataFrame([{
            "simulation": "proxy_a3_cloud_signal",
            "status": "BLOCKED_BY_DATA",
            "reason": (
                f"Only {n_days} trading days of scan data ({min_date} to {max_date}). "
                f"Need at least {min_required_days} days for a meaningful simulation. "
                "Accumulate 6+ months of daily scan history."
            ),
            "n_scan_days": n_days,
            "date_range": f"{min_date} to {max_date}",
            "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
            "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
            "signal_integrity": LABEL_RECONSTRUCTED,
            "research_label": RESEARCH_ONLY_LABEL,
            "requirements": " | ".join(f"[{i+1}] {r}" for i, r in enumerate(_WHAT_IS_NEEDED)),
        }])

    # If we had enough data, this is where the simulation logic would go
    # For now, placeholder:
    return pd.DataFrame([{
        "simulation": "proxy_a3_cloud_signal",
        "status": "BLOCKED_BY_DATA",
        "reason": "Simulation not implemented — insufficient scan history",
        "n_scan_days": n_days,
        "date_range": f"{min_date} to {max_date}",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "requirements": " | ".join(f"[{i+1}] {r}" for i, r in enumerate(_WHAT_IS_NEEDED)),
    }])


def run_portfolio_simulation_full() -> pd.DataFrame:
    """Load data and run portfolio simulation, writing results to CSV."""
    scan_df = load_scan_files()
    ohlcv = load_ohlcv_panel()
    result = run_proxy_simulation(scan_df, ohlcv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Portfolio simulation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
