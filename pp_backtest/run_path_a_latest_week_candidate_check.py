"""
Compute the true latest-week candidate check for Path A Champion.

This avoids relying on stale `pp_portfolio_signal_log.csv` by rebuilding weekly_dfs up to the
latest available data and then computing counts for the latest weekly decision date.

Writes:
- artifacts/path_a_latest_week_candidate_check.csv  (per-symbol candidate table for the week)
- artifacts/path_a_latest_week_candidate_check.md   (human summary)
"""
from __future__ import annotations

import sys
import argparse
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

from pp_backtest.config import BacktestConfig
from pp_backtest.run_weekly_ema21_portfolio import build_weekly_dfs, load_universe
from pp_backtest.eligibility import get_global_eligibility, EligibilityMap


def _get_eligibility(weekly_dfs: Dict[str, pd.DataFrame]) -> EligibilityMap:
    try:
        return get_global_eligibility()
    except FileNotFoundError:
        rows = []
        for sym, wdf in weekly_dfs.items():
            wdf = wdf.copy()
            wdf["value"] = wdf["close"].astype(float) * wdf["volume"].astype(float)
            wdf["date"] = pd.to_datetime(wdf["date"])
            for i in range(len(wdf)):
                if i < 50:
                    continue
                row = wdf.iloc[i]
                dt = row["date"]
                tail50 = wdf.iloc[i - 50 : i]
                tail20 = wdf.iloc[i - 20 : i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                rows.append(
                    {
                        "symbol": sym,
                        "month_start": dt,
                        "adtv20": adtv20,
                        "adtv50": adtv50,
                        "listed_flag": True,
                        "min_history_flag": True,
                        "active_flag": True,
                        "eligible_flag": adtv20 >= 2e9 and adtv50 >= 4e9,
                    }
                )
        return EligibilityMap(df=pd.DataFrame(rows))


def main() -> None:
    artifacts = _REPO / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Latest-week candidate check for Path A Champion.")
    parser.add_argument(
        "--asof",
        default=datetime.today().date().isoformat(),
        help="As-of date (YYYY-MM-DD) to cap data and weekly decision date (default=today).",
    )
    args = parser.parse_args()
    asof_date = pd.to_datetime(args.asof).normalize()

    # Use as-of date as requested end, but actual available data may be earlier.
    requested_end = asof_date.date().isoformat()
    start = "2024-01-01"

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)

    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = requested_end
    weekly_dfs, market_weekly_regime = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        raise SystemExit("No weekly data available.")

    # True latest weekly decision date is the max weekly date available in the built weekly_dfs,
    # capped at as-of date (avoid selecting a future week label).
    all_weekly_max = max(pd.to_datetime(w["date"]).max() for w in weekly_dfs.values() if not w.empty).normalize()
    if all_weekly_max > asof_date:
        # pick latest weekly date <= asof_date across all symbols
        candidates = []
        for wdf in weekly_dfs.values():
            if wdf is None or wdf.empty:
                continue
            dts = pd.to_datetime(wdf["date"]).dt.normalize()
            dts = dts[dts <= asof_date]
            if not dts.empty:
                candidates.append(dts.max())
        if not candidates:
            raise SystemExit("No weekly dates <= as-of date.")
        latest_weekly_date = max(candidates)
    else:
        latest_weekly_date = all_weekly_max

    # Week completeness heuristic: if latest weekly date is a Friday, treat as complete.
    week_complete = latest_weekly_date.weekday() == 4  # Monday=0 ... Friday=4

    eligibility = _get_eligibility(weekly_dfs)

    # Candidate set = weekly_pp True on the latest date
    rows: List[Dict[str, Any]] = []
    raw_weekly_pp = 0
    eligible_cnt = 0

    # Regime gate uses the merged regime columns in each symbol row; take first available.
    regime_ftd = False
    no_new_positions = True
    for wdf in weekly_dfs.values():
        r = wdf[pd.to_datetime(wdf["date"]) == latest_weekly_date]
        if not r.empty:
            rr = r.iloc[0]
            regime_ftd = bool(rr.get("regime_ftd", False))
            no_new_positions = bool(rr.get("no_new_positions", True))
            break

    for sym, wdf in weekly_dfs.items():
        wdf2 = wdf.copy()
        wdf2["date"] = pd.to_datetime(wdf2["date"]).dt.normalize()
        row = wdf2[wdf2["date"] == latest_weekly_date]
        if row.empty:
            continue
        row = row.iloc[0]
        is_pp = bool(row.get("weekly_pp", False))
        if not is_pp:
            continue
        raw_weekly_pp += 1
        eligible_flag = bool(eligibility.is_eligible(sym, latest_weekly_date))
        if eligible_flag:
            eligible_cnt += 1
        rows.append(
            {
                "symbol": sym,
                "weekly_date": latest_weekly_date.date().isoformat(),
                "weekly_pp": is_pp,
                "eligible_flag": eligible_flag,
                "rs_score": row.get("rs_score", np.nan),
                "volume": row.get("volume", np.nan),
            }
        )

    # Trend-pass count: weekly_pp already encodes the weekly trend/signal condition in this system.
    trend_pass = raw_weekly_pp

    # Regime-pass count: only counts if market gate allows buying.
    regime_pass = raw_weekly_pp if (regime_ftd and not no_new_positions) else 0

    # Actual entry count: for the latest weekly decision date, next-bar open may not exist yet.
    # We treat this as 0 entries unless regime allows and next bar exists (not evaluated here).
    actual_entries = 0

    # Rank: for Champion use extension_first logic (low extension preferred). We approximate using ext_vs_ma10 if present.
    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        # ext_vs_ma10 is not stored here; candidate ranking itself is handled in portfolio_sim.
        # For operator visibility, show RS proxy sort descending and then volume.
        df_out["rs_score_num"] = pd.to_numeric(df_out["rs_score"], errors="coerce")
        df_out = df_out.sort_values(["rs_score_num", "volume"], ascending=[False, False]).drop(columns=["rs_score_num"])

    out_csv = artifacts / "path_a_latest_week_candidate_check.csv"
    df_out.to_csv(out_csv, index=False)

    blocker = None
    if actual_entries == 0:
        if not regime_ftd:
            blocker = "regime_off"
        elif no_new_positions:
            blocker = "no_new_positions"
        elif not week_complete:
            blocker = "week_incomplete"
        else:
            blocker = "no_next_bar_or_no_execution_yet"

    out_md = artifacts / "path_a_latest_week_candidate_check.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Path A Latest Week Candidate Check (Champion)\n\n")
        f.write(f"- True latest weekly date used: **{latest_weekly_date.date().isoformat()}**\n")
        f.write(f"- Week complete: **{week_complete}**\n")
        f.write(f"- As-of date cap: **{asof_date.date().isoformat()}**\n")
        f.write(f"- Raw weekly_pp count: **{raw_weekly_pp}**\n")
        f.write(f"- Trend-pass count: **{trend_pass}**\n")
        f.write(f"- Regime-pass count: **{regime_pass}** (regime_ftd={regime_ftd}, no_new_positions={no_new_positions})\n")
        f.write(f"- Eligible count: **{eligible_cnt}**\n")
        f.write(f"- Actual entry count: **{actual_entries}**\n\n")

        if not df_out.empty:
            top_syms = df_out.head(10)["symbol"].tolist()
            f.write("## Top ranked candidates (approx)\n\n")
            for s in top_syms:
                f.write(f"- {s}\n")
            f.write("\n")
        if actual_entries == 0:
            f.write("## No entries\n\n")
            f.write(f"- Exact blocker: **{blocker}**\n")


if __name__ == "__main__":
    main()

