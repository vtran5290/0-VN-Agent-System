from __future__ import annotations

"""
run_trade_scarcity_diagnosis.py

Path A (weekly Pocket Pivot) scarcity diagnosis.

Reads:
- weekly_dfs built exactly like run_weekly_ema21_portfolio.build_weekly_dfs
- PIT eligibility map
- pp_backtest/pp_portfolio_signal_log.csv (per-candidate reject_reason / chosen_flag)
- pp_backtest/pp_weekly_ema21_portfolio_trades.csv (trade ledger)

Outputs:
- artifacts/trade_scarcity_diagnosis.csv
- artifacts/trade_scarcity_diagnosis.md
"""

import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

try:
    from pp_backtest.config import BacktestConfig
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.weekly_bars import daily_to_weekly
    from pp_backtest.signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant
    from weekly_bars import daily_to_weekly
    from signals_weekly import (
        weekly_pocket_pivot_signal,
        weekly_exit_ema21_ma50,
        sma,
        ema,
    )
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from eligibility import get_global_eligibility, EligibilityMap


def _load_universe(path: Path) -> list[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs_full(start: str, end: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Build full-sample weekly_dfs once for all symbols over [start, end]."""
    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = end
    fetch = fetch_ohlcv_fireant
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    print(f"[scarcity] building weekly_dfs full-sample {start}->{end} symbols={len(symbols)}", flush=True)
    for sym in symbols:
        try:
            daily_df = fetch(sym, cfg.start, cfg.end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ma50"] = sma(c, 50)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    print(f"[scarcity] built weekly_dfs for {len(weekly_dfs)} symbols", flush=True)
    return weekly_dfs


def diagnosis_for_period(start: str, end: str, symbols: list[str], eligibility, weekly_dfs: dict[str, pd.DataFrame]) -> dict[str, object]:
    period_label = f"{start}_to_{end}"
    if not weekly_dfs:
        return {
            "period": period_label,
            "avg_eligible_per_week": 0.0,
            "weeks_low_eligible": 0,
            "total_weekly_pp": 0,
            "unique_pp_symbols": 0,
            "avg_weekly_pp_per_week": 0.0,
            "pp_trend_pass": 0,
            "pp_trend_reject": 0,
            "avg_trend_pass_per_week": 0.0,
            "regime_off_reject": 0,
            "no_new_positions_reject": 0,
            "pct_blocked_by_regime": 0.0,
            # portfolio / trade metrics will stay at zero
        }

    # Build global weekly date range for this period (from prebuilt weekly_dfs)
    all_dates = sorted(
        d
        for d in set().union(*(set(w["date"].astype(str)) for w in weekly_dfs.values()))
        if pd.to_datetime(d) >= pd.to_datetime(start) and pd.to_datetime(d) <= pd.to_datetime(end)
    )
    if not all_dates:
        return {}

    weeks = [pd.to_datetime(d) for d in all_dates]

    # A. eligibility
    eligible_counts = []
    for dt in weeks:
        cnt = 0
        for sym in weekly_dfs.keys():
            if eligibility.is_eligible(sym, dt):
                cnt += 1
        eligible_counts.append(cnt)
    avg_eligible = float(np.mean(eligible_counts)) if eligible_counts else 0.0
    weeks_low_eligible = sum(1 for c in eligible_counts if c < 20)

    # B/C/D: per (sym, week) funnel based on weekly_dfs + regime
    total_weekly_pp = 0
    unique_pp_syms = set()
    pp_trend_pass = 0
    pp_trend_reject = 0
    regime_off_reject = 0
    no_new_positions_reject = 0

    weekly_pp_counts = defaultdict(int)  # for avg per week

    for sym, wdf in weekly_dfs.items():
        wdf_local = wdf.copy()
        wdf_local["date"] = pd.to_datetime(wdf_local["date"])
        for _, row in wdf_local.iterrows():
            dt = row["date"]
            if dt < pd.to_datetime(start) or dt > pd.to_datetime(end):
                continue
            weekly_pp = bool(row.get("weekly_pp", False))
            if not weekly_pp:
                continue
            total_weekly_pp += 1
            unique_pp_syms.add(sym)
            weekly_pp_counts[dt] += 1

            ema21 = float(row.get("ema21", np.nan))
            ma50 = float(row.get("ma50", np.nan))
            if np.isnan(ema21) or np.isnan(ma50) or not (ema21 > ma50):
                pp_trend_reject += 1
                continue
            pp_trend_pass += 1

            regime_ftd = bool(row.get("regime_ftd", False))
            no_new = bool(row.get("no_new_positions", False))
            if not regime_ftd:
                regime_off_reject += 1
                continue
            if no_new:
                no_new_positions_reject += 1
                continue

    n_weeks = len(weeks)
    avg_weekly_pp_per_week = float(total_weekly_pp / n_weeks) if n_weeks else 0.0
    avg_trend_pass_per_week = float(pp_trend_pass / n_weeks) if n_weeks else 0.0
    denom_regime = max(pp_trend_pass, 1)
    pct_blocked_by_regime = float(
        (regime_off_reject + no_new_positions_reject) / denom_regime
    )

    # E/F: read from existing logs (full-sample), filter by date window
    sig_log_path = _PP / "pp_portfolio_signal_log.csv"
    trades_path = _PP / "pp_weekly_ema21_portfolio_trades.csv"
    rejected_counts = defaultdict(int)
    actual_entries = 0
    opened_trades = 0
    closed_trades = 0
    avg_hold_weeks = np.nan
    trades_per_month = np.nan

    if sig_log_path.exists():
        sig_df = pd.read_csv(sig_log_path)
        # entry_week is weekly date string; convert to Timestamp
        sig_df["entry_week"] = pd.to_datetime(sig_df["entry_week"])
        mask = (sig_df["entry_week"] >= pd.to_datetime(start)) & (
            sig_df["entry_week"] <= pd.to_datetime(end)
        )
        sig_df = sig_df[mask]
        for _, row in sig_df.iterrows():
            reason = str(row.get("reject_reason", "") or "")
            chosen = bool(row.get("chosen_flag", False))
            if chosen:
                actual_entries += 1
            elif reason:
                rejected_counts[reason] += 1

    if trades_path.exists():
        tdf = pd.read_csv(trades_path)
        tdf["entry_date"] = pd.to_datetime(tdf["entry_date"])
        tdf["exit_date"] = pd.to_datetime(tdf["exit_date"])
        mask = (tdf["entry_date"] >= pd.to_datetime(start)) & (
            tdf["entry_date"] <= pd.to_datetime(end)
        )
        tdf_p = tdf[mask]
        opened_trades = len(tdf_p)
        closed_trades = tdf_p["exit_date"].notna().sum()
        if closed_trades > 0:
            holds = (tdf_p["exit_date"] - tdf_p["entry_date"]).dt.days / 7.0
            avg_hold_weeks = float(holds.mean())
        period_months = max(
            1,
            (pd.to_datetime(end).year - pd.to_datetime(start).year) * 12
            + (pd.to_datetime(end).month - pd.to_datetime(start).month)
            + 1,
        )
        trades_per_month = float(opened_trades / period_months)

    out = {
        "period": period_label,
        "start": start,
        "end": end,
        # A
        "avg_eligible_per_week": avg_eligible,
        "weeks_low_eligible": weeks_low_eligible,
        # B
        "total_weekly_pp": total_weekly_pp,
        "unique_pp_symbols": len(unique_pp_syms),
        "avg_weekly_pp_per_week": avg_weekly_pp_per_week,
        # C
        "pp_trend_pass": pp_trend_pass,
        "pp_trend_reject": pp_trend_reject,
        "avg_trend_pass_per_week": avg_trend_pass_per_week,
        # D
        "regime_off_reject": regime_off_reject,
        "no_new_positions_reject": no_new_positions_reject,
        "pct_blocked_by_regime": pct_blocked_by_regime,
        # E (portfolio admission)
        "rejected_max_positions": rejected_counts.get("max_positions", 0),
        "rejected_already_open": rejected_counts.get("already_open", 0),
        "rejected_no_heat": rejected_counts.get("no_heat", 0),
        "rejected_liquidity_cap": rejected_counts.get("liquidity_cap", 0),
        "rejected_invalid_stop": rejected_counts.get("invalid_stop", 0),
        "rejected_no_next_bar": rejected_counts.get("no_next_bar", 0),
        "rejected_ineligible": rejected_counts.get("ineligible", 0),
        "rejected_regime_off": rejected_counts.get("regime_off", 0),
        "rejected_no_new_positions": rejected_counts.get("no_new_positions", 0),
        "actual_entries": actual_entries,
        # F (trades)
        "opened_trades": opened_trades,
        "closed_trades": closed_trades,
        "avg_hold_weeks": avg_hold_weeks,
        "trades_per_month": trades_per_month,
    }
    return out


def _build_eligibility_from_weekly_dfs(weekly_dfs: dict) -> "EligibilityMap":
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
            eligible = adtv20 >= 2e9 and adtv50 >= 4e9
            rows.append({
                "symbol": sym,
                "month_start": dt,
                "adtv20": adtv20,
                "adtv50": adtv50,
                "listed_flag": True,
                "min_history_flag": True,
                "active_flag": True,
                "eligible_flag": eligible,
            })
    if not rows:
        raise FileNotFoundError("No eligibility rows from weekly_dfs")
    return EligibilityMap(df=pd.DataFrame(rows))


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    symbols = _load_universe(universe_path)

    # Build full-sample weekly_dfs once for all diagnosis periods
    global_start = "2012-01-01"
    global_end = "2026-02-21"
    weekly_dfs_full = build_weekly_dfs_full(global_start, global_end, symbols)

    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        print("[scarcity] building eligibility fallback from weekly_dfs_full...", flush=True)
        eligibility = _build_eligibility_from_weekly_dfs(weekly_dfs_full)

    periods = [
        ("2018-01-01", "2021-12-31", "2018-2021"),
        ("2022-01-01", "2024-12-31", "2022-2024"),
        ("2025-01-01", "2026-02-21", "2025-2026Q1"),
        ("2024-01-01", "2026-02-21", "2024-2026Q1"),
        ("2012-01-01", "2026-02-21", "full_sample"),
    ]

    rows = []
    for idx, (start, end, label) in enumerate(periods, start=1):
        print(f"[scarcity] period {idx}/{len(periods)} label={label} {start}->{end}", flush=True)
        stats = diagnosis_for_period(start, end, symbols, eligibility, weekly_dfs_full)
        stats["label"] = label
        rows.append(stats)

    df = pd.DataFrame(rows)
    csv_path = artifacts_dir / "trade_scarcity_diagnosis.csv"
    df.to_csv(csv_path, index=False)

    # Simple heuristic for 2024-2026 reason
    reason_2024 = "unknown"
    row_2024 = df[df["label"] == "2024-2026Q1"]
    if not row_2024.empty:
        r = row_2024.iloc[0]
        if r["total_weekly_pp"] < 5:
            reason_2024 = "very few raw weekly_pp signals"
        elif r["pp_trend_pass"] < r["total_weekly_pp"] * 0.3:
            reason_2024 = "trend gate (weekly EMA21>MA50) blocking most signals"
        elif r["pct_blocked_by_regime"] > 0.5:
            reason_2024 = "regime_ftd / no_new_positions blocking majority of trend-pass signals"
        elif r["actual_entries"] == 0 and r["opened_trades"] == 0:
            reason_2024 = "portfolio constraints or pipeline producing no entries despite signals"

    md_path = artifacts_dir / "trade_scarcity_diagnosis.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Trade Scarcity Diagnosis (Path A – Weekly System)\n\n")
        f.write("## Funnel summary by period\n\n")
        f.write(
            df[
                [
                    "label",
                    "avg_eligible_per_week",
                    "weeks_low_eligible",
                    "total_weekly_pp",
                    "pp_trend_pass",
                    "regime_off_reject",
                    "no_new_positions_reject",
                    "actual_entries",
                    "opened_trades",
                    "trades_per_month",
                ]
            ].to_string(index=False)
        )
        f.write("\n\n")
        f.write("## Plain-English conclusion\n\n")
        f.write(
            f'The main reason 2024-2026 had few trades is {reason_2024}.'
        )

    print(f"[scarcity] wrote {csv_path}")
    print(f"[scarcity] wrote {md_path}")


if __name__ == "__main__":
    main()

