from __future__ import annotations

"""
Path A weekly entry debug (2024-01-01 to 2026-02-21).

Goal: For the Path A weekly Pocket Pivot portfolio:
- Reproduce the weekly portfolio simulation state.
- After regime-pass (weekly_pp True, EMA21_week > MA50_week, regime_ftd True, no_new_positions False),
  collect exact candidate-level chosen/reject breakdown and state for 2024-01-01 to 2026-02-21.

This module does NOT change the strategy logic; it mirrors `run_portfolio_backtest` from
`portfolio_sim` with additional logging for analysis only.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

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
    from pp_backtest.portfolio_sim import PortfolioConfig, _compute_stop_price
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
    from portfolio_sim import PortfolioConfig, _compute_stop_price


def _load_universe(path: Path) -> List[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs(cfg: BacktestConfig, symbols: List[str]) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Mirror `run_weekly_ema21_portfolio.build_weekly_dfs` to preserve Path A identity.
    """
    fetch = fetch_ohlcv_fireant
    try:
        market_daily = fetch("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: Dict[str, pd.DataFrame] = {}
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
        # EMA21 is recomputed inside weekly_exit_ema21_ma50; we keep ma10 and weekly_pp as in Path A.
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs, market_weekly_regime


def run_path_a_entry_debug(
    start: str = "2024-01-01",
    end: str = "2026-02-21",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run Path A weekly portfolio simulation over [start, end] and log, for each
    candidate that passes:
      - weekly_pp == True
      - ema21_week > ma50_week
      - regime_ftd == True
      - no_new_positions == False
    the chosen/reject breakdown and key state variables.

    Returns:
      - candidates_df: per-candidate debug rows for that filtered set
      - trades_df: actual trades opened (for before/after entry counts)
    """
    cfg = BacktestConfig()
    cfg.start = start
    cfg.end = end

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = _load_universe(universe_path)
    if not symbols:
        return pd.DataFrame(), pd.DataFrame()

    weekly_dfs, _ = build_weekly_dfs(cfg, symbols)
    if not weekly_dfs:
        return pd.DataFrame(), pd.DataFrame()

    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        # Fallback: rebuild from weekly_dfs using same rule as Path A
        rows = []
        for sym, wdf in weekly_dfs.items():
            df = wdf.copy()
            df["value"] = df["close"].astype(float) * df["volume"].astype(float)
            df["date"] = pd.to_datetime(df["date"])
            for i in range(len(df)):
                if i < 50:
                    continue
                row = df.iloc[i]
                dt = row["date"]
                tail50 = df.iloc[i - 50 : i]
                tail20 = df.iloc[i - 20 : i]
                adtv50 = float(tail50["value"].mean())
                adtv20 = float(tail20["value"].mean())
                rows.append(
                    {
                        "symbol": sym,
                        "month_start": dt,
                        "adtv20": adtv20,
                        "adtv50": adtv50,
                        "eligible_flag": adtv20 >= 2e9 and adtv50 >= 4e9,
                    }
                )
        eligibility = EligibilityMap(df=pd.DataFrame(rows))

    pconfig = PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=8,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        fee_bps_per_side=15.0,
    )

    # Precompute EMA21 and MA50 per symbol for trend gate check
    ema21_map: Dict[str, pd.Series] = {}
    ma50_map: Dict[str, pd.Series] = {}
    for sym, wdf in weekly_dfs.items():
        c = wdf["close"].astype(float)
        ema21_map[sym] = ema(c, 21)
        ma50_map[sym] = sma(c, 50)

    fee_mult = pconfig.fee_bps_per_side / 10_000.0
    nav_vnd = pconfig.initial_equity
    cash_vnd = nav_vnd
    all_dates = sorted(set().union(*(set(w["date"].astype(str)) for w in weekly_dfs.values())))
    if not all_dates:
        return pd.DataFrame(), pd.DataFrame()

    positions: Dict[str, dict] = {}
    equity_path = [nav_vnd]
    heat_path = [0.0]
    gross_exposure_path = [0.0]
    dates_path = [pd.to_datetime(all_dates[0])]
    trades: List[dict] = []
    debug_rows: List[dict] = []

    skipped_ineligible = 0
    skipped_heat = 0
    skipped_max_positions = 0
    skipped_liquidity = 0
    skipped_regime_off = 0
    skipped_no_new_positions = 0

    for i, dt in enumerate(all_dates):
        cur_date = pd.to_datetime(dt)

        # --- 1) Exits first (same as Path A) ---
        to_close: List[str] = []
        for sym, pos in list(positions.items()):
            wdf = weekly_dfs.get(sym)
            if wdf is None:
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            exit_sig = bool(row.get("exit_ma10", False))
            if not exit_sig:
                continue

            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is not None:
                next_row = wdf[wdf["date"].astype(str) == next_dt]
                if not next_row.empty:
                    exit_price = float(next_row["open"].iloc[0])
                    exit_date = pd.to_datetime(next_dt)
                else:
                    exit_price = float(row["close"])
                    exit_date = cur_date
            else:
                exit_price = float(row["close"])
                exit_date = cur_date

            size = pos["shares"]
            entry_price = pos["entry_price"]
            exit_value_vnd = exit_price * size
            entry_value_vnd = entry_price * size
            entry_fee = entry_value_vnd * fee_mult
            exit_fee = exit_value_vnd * fee_mult
            pnl_vnd = exit_value_vnd - entry_value_vnd - entry_fee - exit_fee
            cash_vnd += exit_value_vnd - exit_fee

            to_close.append(sym)
            ret_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else np.nan
            trades.append(
                {
                    "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "exit_date": exit_date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "shares": size,
                    "pnl": pnl_vnd,
                    "ret": ret_pct,
                    "risk_budget": pos["risk_budget"],
                }
            )
        for sym in to_close:
            positions.pop(sym, None)

        # --- 2) Mark-to-market + free heat ---
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            wdf = weekly_dfs.get(sym)
            if wdf is None or wdf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        open_risk_vnd = sum(p["risk_budget"] for p in positions.values())
        free_heat_vnd = max(0.0, pconfig.max_heat * equity_vnd - open_risk_vnd)

        # --- 3) Regime for this week ---
        regime_ftd = False
        no_new_positions = True
        regime_row = None
        for wdf in weekly_dfs.values():
            r = wdf[wdf["date"].astype(str) == dt]
            if not r.empty:
                regime_row = r.iloc[0]
                break
        if regime_row is not None:
            regime_ftd = bool(regime_row.get("regime_ftd", False))
            no_new_positions = bool(regime_row.get("no_new_positions", True))

        # --- 4) Candidates (weekly_pp True) + ranking (default mode) ---
        candidates: List[dict] = []
        for sym, wdf in weekly_dfs.items():
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("weekly_pp", False)):
                continue
            idx = row.name
            # Base features (same logic as portfolio_sim._compute_base_features)
            if idx <= 0 or wdf.empty:
                base_len = 0
                base_depth = np.nan
                tight_3w = np.nan
            else:
                start_idx = max(0, idx - 30)
                base = wdf.iloc[start_idx:idx]
                if base.empty:
                    base_len = 0
                    base_depth = np.nan
                    tight_3w = np.nan
                else:
                    high = base["high"].astype(float).values
                    low = base["low"].astype(float).values
                    base_len = len(base)
                    peak = float(high.max())
                    trough = float(low.min())
                    base_depth = (peak - trough) / peak if peak > 0 else np.nan
                    tail = base.tail(3)
                    if len(tail) < 3:
                        tight_3w = np.nan
                    else:
                        t_high = float(tail["high"].astype(float).max())
                        t_low = float(tail["low"].astype(float).min())
                        last_close = float(tail["close"].astype(float).iloc[-1])
                        tight_3w = (t_high - t_low) / last_close if last_close > 0 else np.nan
            # Extension vs MA10
            close_val = float(row["close"])
            ma10_val = float(row.get("ma10", np.nan))
            ext_ma10 = (
                (close_val - ma10_val) / ma10_val
                if not np.isnan(ma10_val) and ma10_val > 0
                else np.nan
            )
            rs_score = row.get("rs_score", np.nan)
            rs_val = float(rs_score) if rs_score is not None and not (isinstance(rs_score, float) and np.isnan(rs_score)) else np.nan
            if isinstance(rs_val, (int, float)) and np.isnan(rs_val):
                rs_val = np.nan
            adtv20, adtv50 = eligibility.adtv(sym, cur_date)
            eligible_flag = eligibility.is_eligible(sym, cur_date)
            candidates.append(
                {
                    "symbol": sym,
                    "row": row,
                    "idx": idx,
                    "base_len": base_len,
                    "base_depth": base_depth,
                    "tight_3w": tight_3w,
                    "ext_ma10": ext_ma10,
                    "rs": rs_val,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "eligible_flag": eligible_flag,
                }
            )

        def _rank_key_default(c: dict) -> tuple:
            rs = c["rs"]
            tight = c["tight_3w"]
            ext = c["ext_ma10"]
            adtv20 = c["adtv20"] if c["adtv20"] is not None else 0.0
            rs_sort = -rs if not (isinstance(rs, float) and np.isnan(rs)) else 0.0
            tight_sort = tight if not (isinstance(tight, float) and np.isnan(tight)) else 1e6
            ext_sort = ext if not (isinstance(ext, float) and np.isnan(ext)) else 1e6
            return (rs_sort, tight_sort, ext_sort, -adtv20)

        candidates_sorted = sorted(candidates, key=_rank_key_default)

        # --- 5) Entries with detailed debug rows ---
        for rank, c in enumerate(candidates_sorted, start=1):
            sym = c["symbol"]
            row = c["row"]
            idx = c["idx"]
            base_len = c["base_len"]
            base_depth = c["base_depth"]
            tight_3w = c["tight_3w"]
            ext_ma10 = c["ext_ma10"]
            rs_val = c["rs"]
            adtv20 = c["adtv20"]
            adtv50 = c["adtv50"]
            eligible_flag = c["eligible_flag"]

            # Trend gate for debug only (does not gate actual logic)
            ema21_series = ema21_map[sym]
            ma50_series = ma50_map[sym]
            ema21_val = float(ema21_series.iloc[idx]) if not np.isnan(ema21_series.iloc[idx]) else np.nan
            ma50_val = float(ma50_series.iloc[idx]) if not np.isnan(ma50_series.iloc[idx]) else np.nan
            trend_pass = (
                not np.isnan(ema21_val)
                and not np.isnan(ma50_val)
                and ema21_val > ma50_val
            )

            passes_signal_trend_regime = (
                bool(row.get("weekly_pp", False))
                and trend_pass
                and regime_ftd
                and not no_new_positions
            )

            open_positions_count = len(positions)

            chosen_flag = False
            reject_reason = ""
            stop_dist = np.nan

            # Actual gating logic (unchanged)
            if sym in positions:
                reject_reason = "already_open"
            elif not regime_ftd:
                reject_reason = "regime_off"
                skipped_regime_off += 1
            elif no_new_positions:
                reject_reason = "no_new_positions"
                skipped_no_new_positions += 1
            elif not eligible_flag or adtv20 is None or adtv50 is None:
                reject_reason = "ineligible"
                skipped_ineligible += 1
            elif len(positions) >= pconfig.max_positions:
                reject_reason = "max_positions"
                skipped_max_positions += 1
            elif free_heat_vnd <= 0:
                reject_reason = "no_heat"
                skipped_heat += 1
            else:
                next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
                if next_dt is None:
                    reject_reason = "no_next_bar"
                else:
                    wdf = weekly_dfs[sym]
                    next_row = wdf[wdf["date"].astype(str) == next_dt]
                    if next_row.empty:
                        reject_reason = "no_next_bar"
                    else:
                        entry_price = float(next_row["open"].iloc[0])
                        if entry_price <= 0:
                            reject_reason = "bad_entry_price"
                        else:
                            stop_price = _compute_stop_price(row)
                            stop_dist = (entry_price - stop_price) / entry_price
                            if stop_dist <= 0:
                                reject_reason = "invalid_stop"
                            else:
                                stop_dist = min(stop_dist, 0.10)
                                risk_budget_vnd = min(pconfig.risk_per_trade * equity_vnd, free_heat_vnd)
                                if risk_budget_vnd <= 0:
                                    reject_reason = "no_heat"
                                    skipped_heat += 1
                                else:
                                    nominal_value_vnd = risk_budget_vnd / stop_dist
                                    nominal_value_vnd = min(nominal_value_vnd, pconfig.max_symbol_weight * equity_vnd)
                                    max_by_liq_vnd = (
                                        pconfig.liquidity_participation_cap * adtv20 if adtv20 else 0.0
                                    )
                                    if max_by_liq_vnd <= 0:
                                        reject_reason = "liquidity_cap"
                                        skipped_liquidity += 1
                                    else:
                                        nominal_value_vnd = min(nominal_value_vnd, max_by_liq_vnd)
                                        shares = int(nominal_value_vnd / entry_price)
                                        if shares <= 0:
                                            reject_reason = "liquidity_cap"
                                            skipped_liquidity += 1
                                        else:
                                            entry_value_vnd = shares * entry_price
                                            entry_fee_vnd = entry_value_vnd * fee_mult
                                            if cash_vnd < entry_value_vnd + entry_fee_vnd:
                                                reject_reason = "insufficient_cash"
                                            else:
                                                cash_vnd -= entry_value_vnd + entry_fee_vnd
                                                positions[sym] = {
                                                    "entry_date": pd.to_datetime(next_dt),
                                                    "entry_price": entry_price,
                                                    "shares": shares,
                                                    "risk_budget": risk_budget_vnd,
                                                }
                                                free_heat_vnd -= risk_budget_vnd
                                                chosen_flag = True
                                                reject_reason = ""

            if passes_signal_trend_regime:
                debug_rows.append(
                    {
                        "date": cur_date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "candidate_rank": rank,
                        "weekly_pp": bool(row.get("weekly_pp", False)),
                        "ema21_gt_ma50": trend_pass,
                        "regime_ftd": regime_ftd,
                        "no_new_positions": no_new_positions,
                        "chosen_flag": chosen_flag,
                        "reject_reason": reject_reason or ("chosen" if chosen_flag else ""),
                        "adtv20": adtv20,
                        "adtv50": adtv50,
                        "ext_vs_ma10": ext_ma10,
                        "tightness_3w": tight_3w,
                        "stop_dist": stop_dist,
                        "free_heat_vnd": free_heat_vnd,
                        "open_positions_count": open_positions_count,
                        "cash_vnd": cash_vnd,
                    }
                )

        # --- 6) End-of-week equity series ---
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            wdf = weekly_dfs.get(sym)
            if wdf is None or wdf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        equity_path.append(equity_vnd)
        heat_path.append(sum(p["risk_budget"] for p in positions.values()))
        gross_exposure_path.append(position_value_vnd / equity_vnd if equity_vnd > 0 else 0.0)
        dates_path.append(cur_date)

    candidates_df = pd.DataFrame(debug_rows)
    trades_df = pd.DataFrame(trades)
    return candidates_df, trades_df


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    start = "2024-01-01"
    end = "2026-02-21"
    candidates_df, trades_df = run_path_a_entry_debug(start=start, end=end)

    csv_path = artifacts_dir / "path_a_entry_debug_2024_2026.csv"
    md_path = artifacts_dir / "path_a_entry_debug_2024_2026.md"

    if candidates_df.empty:
        candidates_df.to_csv(csv_path, index=False)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Path A Weekly Entry Debug 2024–2026\n\n")
            f.write("No candidates passed signal + trend + regime filters in this period.\n")
        print("[path_a_entry_debug] No candidates; wrote empty artifacts.")
        return

    candidates_df.to_csv(csv_path, index=False)

    # Breakdown by chosen_flag / reject_reason
    chosen_count = int(candidates_df["chosen_flag"].sum())
    reject_counts = (
        candidates_df[~candidates_df["chosen_flag"]]
        .assign(rr=candidates_df.loc[~candidates_df["chosen_flag"], "reject_reason"].fillna(""))
        .groupby("rr")
        .size()
        .rename("count")
        .reset_index()
        .rename(columns={"rr": "reject_reason"})
        .sort_values("count", ascending=False)
    )

    # First 20 failed cases
    failed_examples = candidates_df[~candidates_df["chosen_flag"]].head(20).copy()

    # Identify main blocker (by count)
    main_blocker = ""
    if not reject_counts.empty:
        main_row = reject_counts.iloc[0]
        main_blocker = str(main_row["reject_reason"])

    # Classification heuristic
    classification = "genuine portfolio constraint"
    if main_blocker in {"already_open", "max_positions", "no_heat", "insufficient_cash", "liquidity_cap"}:
        classification = "genuine portfolio constraint"
    elif main_blocker in {"no_next_bar", "bad_entry_price", "invalid_stop"}:
        classification = "state handling issue"
    elif main_blocker in {"ineligible"}:
        classification = "data / pipeline issue"
    elif main_blocker in {"regime_off", "no_new_positions"}:
        classification = "regime / policy constraint"

    # Simple English conclusion + recommended next step
    conclusion_line = f"The main downstream blocker is '{main_blocker}'." if main_blocker else "The main downstream blocker is unclear from this debug run."

    recommended_next_step = "- Next step: Inspect representative failed candidates for the dominant reject_reason to decide whether it reflects a design choice or a correctable bug."

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Weekly Entry Debug 2024–2026\n\n")
        f.write(f"Period: {start} to {end}.\n\n")
        f.write("## A. Reject breakdown after signal + trend + regime\n\n")
        f.write(f"- Total candidates after filters: {len(candidates_df)}\n")
        f.write(f"- chosen_flag == True: {chosen_count}\n\n")
        if not reject_counts.empty:
            f.write("| reject_reason | count |\n")
            f.write("|---------------|-------|\n")
            for _, row in reject_counts.iterrows():
                f.write(f"| {row['reject_reason']} | {int(row['count'])} |\n")
            f.write("\n")
        else:
            f.write("No rejected candidates in this filtered set.\n\n")

        f.write("## B. First 20 failed cases\n\n")
        cols = [
            "date",
            "symbol",
            "candidate_rank",
            "adtv20",
            "ext_vs_ma10",
            "tightness_3w",
            "stop_dist",
            "free_heat_vnd",
            "open_positions_count",
            "cash_vnd",
            "reject_reason",
        ]
        cols = [c for c in cols if c in failed_examples.columns]
        if not failed_examples.empty and cols:
            # Simple markdown table without tabulate dependency
            f.write("| " + " | ".join(cols) + " |\n")
            f.write("|" + "|".join(["---"] * len(cols)) + "|\n")
            for _, row in failed_examples[cols].iterrows():
                vals = [row[c] for c in cols]
                fmt_vals = []
                for v in vals:
                    if isinstance(v, float):
                        fmt_vals.append(f"{v:.4g}")
                    else:
                        fmt_vals.append(str(v))
                f.write("| " + " | ".join(fmt_vals) + " |\n")
            f.write("\n\n")
        else:
            f.write("No failed cases available.\n\n")

        f.write("## C. Plain-English conclusion\n\n")
        f.write(conclusion_line + "\n\n")

        f.write("## D. Classification\n\n")
        f.write(f"- Classified as: **{classification}**\n\n")

        f.write("## E. Recommended next step\n\n")
        f.write(recommended_next_step + "\n")

    print(f"[path_a_entry_debug] wrote {csv_path} and {md_path}")


if __name__ == "__main__":
    main()

