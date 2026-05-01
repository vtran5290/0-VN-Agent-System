"""
Audit freshness mismatch between ops_check and latest-week candidate checks.

Writes:
- artifacts/path_a_latest_week_freshness_audit.csv
- artifacts/path_a_latest_week_freshness_audit.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

from pp_backtest.data import fetch_ohlcv_fireant
from pp_backtest.run_weekly_ema21_portfolio import build_weekly_dfs, load_universe
from pp_backtest.config import BacktestConfig


def _max_date(df: pd.DataFrame) -> str | None:
    if df is None or df.empty or "date" not in df.columns:
        return None
    try:
        d = pd.to_datetime(df["date"]).max()
        return d.date().isoformat() if pd.notna(d) else None
    except Exception:
        return None


def main() -> None:
    artifacts = _REPO / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # What ops_check uses (artifact-based)
    mon_csv = artifacts / "path_a_monitoring_snapshot.csv"
    mon_period = None
    if mon_csv.exists():
        try:
            mdf = pd.read_csv(mon_csv)
            if not mdf.empty and "period" in mdf.columns:
                mon_period = str(mdf["period"].iloc[0])
        except Exception:
            mon_period = None

    sig_log = _REPO / "pp_backtest" / "pp_portfolio_signal_log.csv"
    sig_latest_week = None
    if sig_log.exists():
        try:
            sdf = pd.read_csv(sig_log)
            if not sdf.empty and "entry_week" in sdf.columns:
                sig_latest_week = pd.to_datetime(sdf["entry_week"]).max().date().isoformat()
        except Exception:
            sig_latest_week = None

    # Probe FireAnt raw daily data freshness (VN30 + a few liquid symbols)
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)[:5]
    if "VN30" not in symbols:
        symbols = ["VN30"] + symbols

    raw_max_dates: Dict[str, str | None] = {}
    for sym in symbols:
        try:
            ddf = fetch_ohlcv_fireant(sym, "2026-02-01", "2026-03-18")
        except Exception:
            ddf = pd.DataFrame()
        raw_max_dates[sym] = _max_date(ddf)

    vn30_daily_max = raw_max_dates.get("VN30")

    # Probe weekly resample freshness through the candidate-check path (build_weekly_dfs)
    cfg = BacktestConfig()
    cfg.start = "2024-01-01"
    cfg.end = "2026-03-18"
    weekly_dfs, market_weekly_regime = build_weekly_dfs(cfg, [s for s in symbols if s != "VN30"])
    weekly_symbol_max = None
    if weekly_dfs:
        try:
            weekly_symbol_max = max(pd.to_datetime(w["date"]).max() for w in weekly_dfs.values() if not w.empty)
            weekly_symbol_max = weekly_symbol_max.date().isoformat() if pd.notna(weekly_symbol_max) else None
        except Exception:
            weekly_symbol_max = None
    weekly_regime_max = _max_date(market_weekly_regime)

    # Root cause: if monitoring snapshot period label extends past actual available weekly dates, it's a labeling mismatch.
    # Additionally, latest-week candidate check based on pp_portfolio_signal_log is stale if that file isn't refreshed.
    root_cause = []
    if mon_period and sig_latest_week and mon_period.endswith("2026-03-16") and sig_latest_week < "2026-03-01":
        root_cause.append("candidate_check_used_stale_pp_portfolio_signal_log")
    # Compare requested end vs actual data max
    if weekly_regime_max is not None and weekly_regime_max < "2026-03-01":
        root_cause.append("fireant_raw_or_weekly_data_stops_before_requested_end")
    if mon_period is not None and ("2026-03-16" in mon_period) and weekly_regime_max and weekly_regime_max < "2026-03-16":
        root_cause.append("ops_check_reads_requested_period_label_not_actual_last_weekly_date")

    # Write audit CSV (single row + per-symbol raw dates)
    rows: List[Dict[str, Any]] = []
    for sym, mx in raw_max_dates.items():
        rows.append({"layer": "raw_daily_max_date", "symbol": sym, "value": mx})
    rows.extend(
        [
            {"layer": "ops_check_monitoring_snapshot_period", "symbol": None, "value": mon_period},
            {"layer": "candidate_check_signal_log_latest_week", "symbol": None, "value": sig_latest_week},
            {"layer": "weekly_symbol_max_date_probe", "symbol": None, "value": weekly_symbol_max},
            {"layer": "weekly_regime_max_date_probe", "symbol": None, "value": weekly_regime_max},
            {"layer": "root_cause", "symbol": None, "value": ";".join(root_cause) if root_cause else "unknown"},
        ]
    )

    out_csv = artifacts / "path_a_latest_week_freshness_audit.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    out_md = artifacts / "path_a_latest_week_freshness_audit.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Path A Latest-week Freshness Audit\n\n")
        f.write("## Key dates by layer\n\n")
        f.write(f"- Monitoring snapshot period label: **{mon_period}**\n")
        f.write(f"- Candidate-check latest `entry_week` in `pp_portfolio_signal_log.csv`: **{sig_latest_week}**\n")
        f.write(f"- Raw VN30 daily max date (probe 2026-02-01..2026-03-18): **{vn30_daily_max}**\n")
        f.write(f"- Weekly regime max date (probe build_weekly_dfs end=2026-03-18): **{weekly_regime_max}**\n")
        f.write(f"- Weekly symbol max date (probe build_weekly_dfs end=2026-03-18): **{weekly_symbol_max}**\n\n")

        f.write("## Root cause\n\n")
        if root_cause:
            for rc in root_cause:
                f.write(f"- {rc}\n")
        else:
            f.write("- unknown\n")


if __name__ == "__main__":
    main()

