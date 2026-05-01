from __future__ import annotations

"""
Path B: DAILY Pocket Pivot MA/MA ablation.

This reuses the Path B daily framework but varies only:
- trend gate: MA_short > MA_long
- support gate: close > MA_support (MA10 or MA20)

Everything else stays fixed:
- true daily Pocket Pivot signal
- regime_ftd / no_new_positions
- PIT eligibility / liquidity / sizing / fee framework
- next-day open execution and daily mark-to-market
"""

import sys
from dataclasses import dataclass
from itertools import product
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
    from pp_backtest.config import BacktestConfig, PocketPivotParams
    from pp_backtest.data import fetch_ohlcv_fireant
    from pp_backtest.signals import pocket_pivot, sma
    from pp_backtest.market_regime import add_book_regime_columns
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
    from pp_backtest.run_daily_pp_portfolio import DailyPortfolioConfig
except ImportError:
    from config import BacktestConfig, PocketPivotParams
    from data import fetch_ohlcv_fireant
    from signals import pocket_pivot, sma
    from market_regime import add_book_regime_columns
    from eligibility import get_global_eligibility, EligibilityMap
    from run_daily_pp_portfolio import DailyPortfolioConfig


MA_SET = [10, 20, 50, 100, 150, 200]
SUPPORT_SET = [10, 20]


def _load_universe(path: Path) -> List[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_daily_dfs_with_mas(
    start: str,
    end: str,
    symbols: List[str],
    market_daily: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """
    Build per-symbol daily DataFrames with:
    - daily OHLCV
    - true daily Pocket Pivot signal (pp)
    - SMA columns for MA_SET
    - regime_ftd / no_new_positions from market_daily
    """
    regime = market_daily[["date", "regime_ftd", "no_new_positions"]].copy()
    regime["date"] = pd.to_datetime(regime["date"]).dt.normalize()

    daily_dfs: Dict[str, pd.DataFrame] = {}
    pp_params = PocketPivotParams()

    for sym in symbols:
        try:
            df = fetch_ohlcv_fireant(sym, start, end)
        except Exception:
            continue
        if df is None or df.empty or len(df) < max(MA_SET) + 1:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = pocket_pivot(df, pp_params)
        c = df["close"].astype(float)
        for ma_len in MA_SET:
            df[f"ma{ma_len}"] = sma(c, ma_len)
        df = df.merge(regime, on="date", how="left")
        df["regime_ftd"] = df["regime_ftd"].fillna(False)
        df["no_new_positions"] = df["no_new_positions"].fillna(False)
        daily_dfs[sym] = df
    return daily_dfs


def _compute_stop_price(row: pd.Series, support_len: int) -> float:
    """
    Simple stop for risk budget sizing:
    max(low, 0.99 * MA_support) or 0.92 * close as a fallback.
    """
    close = float(row["close"])
    low = float(row["low"])
    ma_support = float(row.get(f"ma{support_len}", np.nan))
    stop_ma = ma_support * 0.99 if not np.isnan(ma_support) and ma_support > 0 else close * 0.92
    return max(low, stop_ma)


@dataclass
class MaPairConfig:
    support_ma: int
    short_ma: int
    long_ma: int
    period: str
    start: str
    end: str


def run_daily_backtest_ma(
    daily_dfs: Dict[str, pd.DataFrame],
    config: DailyPortfolioConfig,
    eligibility: EligibilityMap,
    ma_cfg: MaPairConfig,
) -> Tuple[pd.DataFrame, dict]:
    """
    Daily portfolio sim for a specific (support_ma, short_ma, long_ma) config.

    Entry (on signal day, executed at next-day open):
      - pp == True
      - close > MA_support
      - MA_short > MA_long
      - regime_ftd == True
      - no_new_positions == False

    Exit (signal on day t, executed at next-day open):
      - close < MA_support OR MA_short < MA_long
    """
    fee_mult = config.fee_bps_per_side / 10_000.0
    cash_vnd = config.initial_equity

    all_dates = sorted(
        set().union(*(set(d["date"].astype(str)) for d in daily_dfs.values()))
    )
    if not all_dates:
        return pd.DataFrame(), {}

    positions: Dict[str, dict] = {}
    equity_path = [config.initial_equity]
    heat_path = [0.0]
    gross_exposure_path = [0.0]
    dates_path = [pd.to_datetime(all_dates[0])]
    trades: List[dict] = []

    skipped_ineligible = 0
    skipped_heat = 0
    skipped_max_positions = 0
    skipped_liquidity = 0
    skipped_regime_off = 0
    skipped_no_new_positions = 0

    sup_col = f"ma{ma_cfg.support_ma}"
    short_col = f"ma{ma_cfg.short_ma}"
    long_col = f"ma{ma_cfg.long_ma}"

    for i, dt in enumerate(all_dates):
        cur_date = pd.to_datetime(dt)

        # 1) Exits at next day open
        to_close: List[str] = []
        for sym, pos in list(positions.items()):
            ddf = daily_dfs.get(sym)
            if ddf is None:
                continue
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]

            c = float(row["close"])
            ma_support = float(row.get(sup_col, np.nan))
            ma_short = float(row.get(short_col, np.nan))
            ma_long = float(row.get(long_col, np.nan))
            cond_support = (not np.isnan(ma_support)) and (c < ma_support)
            cond_trend = (not np.isnan(ma_short) and not np.isnan(ma_long)) and (ma_short < ma_long)
            if not (cond_support or cond_trend):
                continue

            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is not None:
                next_row = ddf[ddf["date"].astype(str) == next_dt]
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

        # 2) Mark-to-market
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            ddf = daily_dfs.get(sym)
            if ddf is None or ddf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
                continue
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        open_risk_vnd = sum(p["risk_budget"] for p in positions.values())
        free_heat_vnd = max(0.0, config.max_heat * equity_vnd - open_risk_vnd)

        # 3) Regime for this day
        regime_ftd = False
        no_new_positions = True
        for ddf in daily_dfs.values():
            r = ddf[ddf["date"].astype(str) == dt]
            if not r.empty:
                regime_ftd = bool(r.iloc[0].get("regime_ftd", False))
                no_new_positions = bool(r.iloc[0].get("no_new_positions", True))
                break

        # 4) Candidates: pp True, close > MA_support, MA_short > MA_long
        candidates: List[dict] = []
        for sym, ddf in daily_dfs.items():
            row = ddf[ddf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("pp", False)):
                continue
            c = float(row["close"])
            ma_support = float(row.get(sup_col, np.nan))
            ma_short = float(row.get(short_col, np.nan))
            ma_long = float(row.get(long_col, np.nan))
            if np.isnan(ma_support) or np.isnan(ma_short) or np.isnan(ma_long):
                continue
            if not (c > ma_support and ma_short > ma_long):
                continue
            adtv20, adtv50 = eligibility.adtv(sym, cur_date)
            eligible_flag = eligibility.is_eligible(sym, cur_date)
            candidates.append(
                {
                    "symbol": sym,
                    "row": row,
                    "adtv20": adtv20,
                    "adtv50": adtv50,
                    "eligible_flag": eligible_flag,
                }
            )

        candidates_sorted = sorted(
            candidates,
            key=lambda c: -(c["adtv20"] or 0.0),
        )

        # 5) Entries at next day open
        for c in candidates_sorted:
            sym = c["symbol"]
            row = c["row"]
            adtv20 = c["adtv20"]
            adtv50 = c["adtv50"]
            eligible_flag = c["eligible_flag"]

            if sym in positions:
                continue
            if not regime_ftd:
                skipped_regime_off += 1
                continue
            if no_new_positions:
                skipped_no_new_positions += 1
                continue
            if not eligible_flag or adtv20 is None or adtv50 is None:
                skipped_ineligible += 1
                continue
            if len(positions) >= config.max_positions:
                skipped_max_positions += 1
                continue
            if free_heat_vnd <= 0:
                skipped_heat += 1
                continue

            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is None:
                continue
            ddf = daily_dfs[sym]
            next_row = ddf[ddf["date"].astype(str) == next_dt]
            if next_row.empty:
                continue
            entry_price = float(next_row["open"].iloc[0])
            if entry_price <= 0:
                continue
            stop_price = _compute_stop_price(row, ma_cfg.support_ma)
            stop_dist = (entry_price - stop_price) / entry_price
            if stop_dist <= 0:
                continue
            stop_dist = min(stop_dist, 0.10)
            risk_budget_vnd = min(config.risk_per_trade * equity_vnd, free_heat_vnd)
            if risk_budget_vnd <= 0:
                skipped_heat += 1
                continue
            nominal_value_vnd = risk_budget_vnd / stop_dist
            nominal_value_vnd = min(nominal_value_vnd, config.max_symbol_weight * equity_vnd)
            max_by_liq_vnd = config.liquidity_participation_cap * adtv20 if adtv20 else 0.0
            if max_by_liq_vnd <= 0:
                skipped_liquidity += 1
                continue
            nominal_value_vnd = min(nominal_value_vnd, max_by_liq_vnd)
            shares = int(nominal_value_vnd / entry_price)
            if shares <= 0:
                skipped_liquidity += 1
                continue
            entry_value_vnd = shares * entry_price
            entry_fee_vnd = entry_value_vnd * fee_mult
            if cash_vnd < entry_value_vnd + entry_fee_vnd:
                continue
            cash_vnd -= entry_value_vnd + entry_fee_vnd
            positions[sym] = {
                "entry_date": pd.to_datetime(next_dt),
                "entry_price": entry_price,
                "shares": shares,
                "risk_budget": risk_budget_vnd,
            }
            free_heat_vnd -= risk_budget_vnd

        # 6) Equity series
        position_value_vnd = 0.0
        for sym, pos in positions.items():
            ddf = daily_dfs.get(sym)
            if ddf is None or ddf.empty:
                position_value_vnd += pos["entry_price"] * pos["shares"]
            else:
                row = ddf[ddf["date"].astype(str) == dt]
                if row.empty:
                    position_value_vnd += pos["entry_price"] * pos["shares"]
                else:
                    position_value_vnd += float(row.iloc[0]["close"]) * pos["shares"]
        equity_vnd = cash_vnd + position_value_vnd
        equity_path.append(equity_vnd)
        heat_path.append(sum(p["risk_budget"] for p in positions.values()))
        gross_exposure_path.append(
            position_value_vnd / equity_vnd if equity_vnd > 0 else 0.0
        )
        dates_path.append(cur_date)

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, {}

    eq = np.array(equity_path, dtype=float)
    dates_arr = np.array(dates_path)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = float(dd.min())
    years = (dates_arr[-1] - dates_arr[0]).days / 365.25
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 and eq[0] > 0 else np.nan
    mar = cagr / abs(mdd) if mdd < 0 else np.nan
    mean_equity = float(np.mean(eq)) if np.mean(eq) > 0 else 1.0
    period_months = max(
        1,
        (pd.to_datetime(all_dates[-1]) - pd.to_datetime(all_dates[0])).days / 30.0,
    )
    trades_per_month = len(trades_df) / period_months

    stats = {
        "support_ma": ma_cfg.support_ma,
        "short_ma": ma_cfg.short_ma,
        "long_ma": ma_cfg.long_ma,
        "period": ma_cfg.period,
        "start": ma_cfg.start,
        "end": ma_cfg.end,
        "cagr": cagr,
        "mdd": mdd,
        "mar": mar,
        "n_trades": len(trades_df),
        "final_equity": float(eq[-1]),
        "avg_heat": float(np.mean(heat_path)) / mean_equity,
        "avg_gross_exposure": float(np.mean(gross_exposure_path)),
        "skipped_ineligible": skipped_ineligible,
        "skipped_regime_off": skipped_regime_off,
        "skipped_no_new_positions": skipped_no_new_positions,
        "skipped_max_positions": skipped_max_positions,
        "skipped_liquidity": skipped_liquidity,
        "trades_per_month": trades_per_month,
    }
    return trades_df, stats


def _iter_ma_configs() -> List[Tuple[int, int, int]]:
    pairs = []
    for short, long in product(MA_SET, MA_SET):
        if short < long:
            pairs.append((short, long))
    return pairs


def _compute_robustness_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute a simple robustness score per (support_ma, short_ma, long_ma):
    - base = average MAR across periods
    - penalty 0.5 per negative-MAR period
    - penalty (100 - total_trades)/100 if total_trades < 100
    """
    key_cols = ["support_ma", "short_ma", "long_ma"]
    periods = df["period"].unique().tolist()

    rows = []
    for (sup, short, long), grp in df.groupby(key_cols):
        mars = grp["mar"].dropna().values
        if mars.size == 0:
            continue
        avg_mar = float(np.mean(mars))
        num_negative = int((mars < 0).sum())
        total_trades = int(grp["n_trades"].sum())
        base = avg_mar
        penalty_neg = 0.5 * num_negative
        penalty_trades = (100 - total_trades) / 100.0 if total_trades < 100 else 0.0
        score = base - penalty_neg - penalty_trades
        rows.append(
            {
                "support_ma": sup,
                "short_ma": short,
                "long_ma": long,
                "avg_mar": avg_mar,
                "num_negative_periods": num_negative,
                "total_trades": total_trades,
                "score": score,
            }
        )
    return pd.DataFrame(rows)


def _write_markdown_artifacts(
    df: pd.DataFrame,
    robustness_df: pd.DataFrame,
) -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_b_daily_ma_pair_ablation.csv"
    md_path = artifacts_dir / "path_b_daily_ma_pair_ablation.md"
    summary_path = artifacts_dir / "path_b_daily_ma_pair_summary.md"

    df.to_csv(csv_path, index=False)

    periods = ["2018-2021", "2022-2024", "2025-2026Q1", "full_sample"]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path B – Daily MA-pair Ablation\n\n")
        f.write("30 configs (15 MA_short/MA_long pairs × 2 support MAs) on true daily Pocket Pivot Path B.\n\n")

        # 1) Top 10 configs by MAR for each period
        f.write("## Top 10 configs by MAR per period\n\n")
        for period in periods:
            sub = df[df["period"] == period].copy()
            if sub.empty:
                continue
            top = sub.sort_values("mar", ascending=False).head(10)
            f.write(f"### Period {period}\n\n")
            cols = [
                "support_ma",
                "short_ma",
                "long_ma",
                "cagr",
                "mdd",
                "mar",
                "n_trades",
                "trades_per_month",
                "final_equity",
                "avg_heat",
                "avg_gross_exposure",
                "skipped_ineligible",
                "skipped_regime_off",
                "skipped_no_new_positions",
                "skipped_max_positions",
                "skipped_liquidity",
            ]
            cols = [c for c in cols if c in top.columns]
            f.write(top[cols].to_markdown(index=False))
            f.write("\n\n")

        # 2) Top 10 configs by robustness across periods
        f.write("## Top 10 configs by robustness across periods\n\n")
        top_robust = robustness_df.sort_values("score", ascending=False).head(10)
        f.write(top_robust.to_markdown(index=False))
        f.write("\n\n")

        # 3) Support MA preference
        f.write("## Support MA preference (10 vs 20)\n\n")
        support_summary = (
            df.groupby("support_ma")["mar"]
            .agg(["mean", "median", "count"])
            .rename(columns={"mean": "mar_mean", "median": "mar_median"})
        )
        support_summary["positive_frac"] = (
            df.assign(pos=df["mar"] > 0)
            .groupby("support_ma")["pos"]
            .mean()
        )
        f.write(support_summary.to_markdown())
        f.write("\n\n")

        # 4) Very slow pairs behaviour
        f.write("## Very slow MA pairs (100/150, 100/200, 150/200)\n\n")
        slow_pairs = {(100, 150), (100, 200), (150, 200)}
        is_slow = df.apply(
            lambda r: (int(r["short_ma"]), int(r["long_ma"])) in slow_pairs, axis=1
        )
        slow_df = df[is_slow]
        fast_df = df[~is_slow]
        if not slow_df.empty:
            slow_stats = slow_df["mar"].describe()
            fast_stats = fast_df["mar"].describe()
            f.write("### MAR distribution – slow vs others\n\n")
            comp = pd.DataFrame(
                {
                    "slow_mean_mar": [slow_stats["mean"]],
                    "slow_median_mar": [slow_stats["50%"]],
                    "slow_count": [slow_stats["count"]],
                    "fast_mean_mar": [fast_stats["mean"]],
                    "fast_median_mar": [fast_stats["50%"]],
                    "fast_count": [fast_stats["count"]],
                }
            )
            f.write(comp.to_markdown(index=False))
            f.write("\n\n")

        # 5) Comparison placeholders (filled below using existing artifacts)
        f.write("## Comparison vs current Path B daily baseline\n\n")
        f.write("See summary file for plain-language conclusion and numeric comparison.\n\n")
        f.write("## Comparison vs Path A weekly baseline\n\n")
        f.write("See summary file for high-level comparison vs Path A weekly.\n")

    # Summary answer file
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path B Daily MA/MA Ablation – Summary\n\n")
        # These textual answers are filled by main() after it compares against baselines.
        f.write("Results will be appended by main().\n")


def main() -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = _load_universe(universe_path)
    if not symbols:
        print("[ma_ablation] No symbols; aborting.")
        return

    periods = [
        ("2018-01-01", "2021-12-31", "2018-2021"),
        ("2022-01-01", "2024-12-31", "2022-2024"),
        ("2025-01-01", "2026-02-21", "2025-2026Q1"),
        ("2012-01-01", "2026-02-21", "full_sample"),
    ]

    try:
        market_daily_full = fetch_ohlcv_fireant("VN30", periods[0][0], periods[-1][1])
        market_daily_full = add_book_regime_columns(market_daily_full)
        market_daily_full["date"] = pd.to_datetime(market_daily_full["date"]).dt.normalize()
    except Exception:
        market_daily_full = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
        market_daily_full["date"] = pd.to_datetime(market_daily_full["date"])

    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        eligibility = None  # let it fail loudly if missing; should exist for main runs

    all_rows: List[dict] = []
    ma_pairs = _iter_ma_configs()

    for start, end, label in periods:
        print(f"[ma_ablation] Building daily data for period {label}...", flush=True)
        # Slice market regime for this period
        if not market_daily_full.empty:
            mask = (market_daily_full["date"] >= pd.to_datetime(start)) & (
                market_daily_full["date"] <= pd.to_datetime(end)
            )
            market_daily = market_daily_full.loc[mask].copy()
        else:
            market_daily = market_daily_full

        daily_dfs = build_daily_dfs_with_mas(start, end, symbols, market_daily)
        if not daily_dfs:
            print(f"[ma_ablation] No daily data for period {label}; skipping.", flush=True)
            continue

        if eligibility is None:
            print("[ma_ablation] Eligibility map missing; aborting.", flush=True)
            return

        port_cfg = DailyPortfolioConfig()
        for support_ma in SUPPORT_SET:
            for short_ma, long_ma in ma_pairs:
                ma_cfg = MaPairConfig(
                    support_ma=support_ma,
                    short_ma=short_ma,
                    long_ma=long_ma,
                    period=label,
                    start=start,
                    end=end,
                )
                _, stats = run_daily_backtest_ma(daily_dfs, port_cfg, eligibility, ma_cfg)
                if stats:
                    all_rows.append(stats)

    if not all_rows:
        print("[ma_ablation] No results; aborting.", flush=True)
        return

    df = pd.DataFrame(all_rows)
    robustness_df = _compute_robustness_scores(df)

    _write_markdown_artifacts(df, robustness_df)

    # --- Fill summary answers vs baselines ---
    pb_baseline_csv = artifacts_dir / "path_b_daily_baseline.csv"
    path_a_cmp_csv = artifacts_dir / "path_a_vs_path_b_comparison.csv"
    summary_path = artifacts_dir / "path_b_daily_ma_pair_summary.md"

    best_robust = robustness_df.sort_values("score", ascending=False).iloc[0]
    best_robust_cfg = (
        int(best_robust["support_ma"]),
        int(best_robust["short_ma"]),
        int(best_robust["long_ma"]),
    )

    # Best config for 2018-2021 by MAR
    early = df[df["period"] == "2018-2021"].copy()
    best_early = early.sort_values("mar", ascending=False).iloc[0] if not early.empty else None

    # Support MA comparison
    support_group = (
        df.groupby("support_ma")["mar"].mean().to_dict() if "support_ma" in df.columns else {}
    )

    # Compare against daily baseline (Path B) full-sample MAR
    baseline_mar_full = None
    if pb_baseline_csv.exists():
        pb_df = pd.read_csv(pb_baseline_csv)
        row_full = pb_df[pb_df["period"] == "full_sample"]
        if not row_full.empty and "mar" in row_full.columns:
            baseline_mar_full = float(row_full["mar"].iloc[0])

    best_full = df[df["period"] == "full_sample"].copy()
    best_full = best_full.sort_values("mar", ascending=False).iloc[0] if not best_full.empty else None

    # Compare against Path A weekly full-sample MAR
    path_a_mar_full = None
    if path_a_cmp_csv.exists():
        cmp_df = pd.read_csv(path_a_cmp_csv)
        row_full_a = cmp_df[cmp_df["period"] == "full_sample"]
        if not row_full_a.empty and "mar_a" in row_full_a.columns:
            path_a_mar_full = float(row_full_a["mar_a"].iloc[0])

    # Plain-language summary
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path B Daily MA/MA Ablation – Summary\n\n")

        # 1) Did MA/MA filtering materially improve Path B?
        if baseline_mar_full is not None and best_full is not None:
            improv = best_full["mar"] - baseline_mar_full
            improved = improv > 0.05  # arbitrary but clear threshold
            f.write("## Did MA/MA daily filtering materially improve Path B?\n\n")
            f.write(
                f"- Baseline daily Path B full-sample MAR: {baseline_mar_full:.3f}\n"
            )
            f.write(
                f"- Best MA-pair full-sample MAR: {best_full['mar']:.3f} "
                f"(Δ = {improv:.3f})\n"
            )
            if improved:
                f.write("- Conclusion: MA/MA daily filtering **materially improved** Path B.\n\n")
            else:
                f.write("- Conclusion: MA/MA daily filtering **did not materially improve** Path B.\n\n")
        else:
            f.write("## Did MA/MA daily filtering materially improve Path B?\n\n")
            f.write("- Unknown (missing baseline or ablation full-sample MAR).\n\n")

        # 2) Which pair currently looks best?
        f.write("## Which MA/MA pair looks best?\n\n")
        f.write(
            f"- Best robust config (by score): support_ma={best_robust_cfg[0]}, "
            f"short_ma={best_robust_cfg[1]}, long_ma={best_robust_cfg[2]}, "
            f"avg_MAR={best_robust['avg_mar']:.3f}, "
            f"score={best_robust['score']:.3f}, "
            f"neg_periods={int(best_robust['num_negative_periods'])}, "
            f"total_trades={int(best_robust['total_trades'])}.\n\n"
        )
        if best_early is not None:
            f.write(
                "- Best config for 2018–2021 (by MAR): "
                f"support_ma={int(best_early['support_ma'])}, "
                f"short_ma={int(best_early['short_ma'])}, "
                f"long_ma={int(best_early['long_ma'])}, "
                f"MAR={best_early['mar']:.3f}, "
                f"n_trades={int(best_early['n_trades'])}.\n\n"
            )

        # 3) Support MA preference
        f.write("## Support MA: 10 vs 20\n\n")
        if support_group:
            for sup, mar_mean in sorted(support_group.items()):
                f.write(f"- support_ma={sup}: average MAR across configs/periods = {mar_mean:.3f}\n")
            better = max(support_group, key=support_group.get)
            f.write(f"- On average, support_ma={better} looks better in this run.\n\n")
        else:
            f.write("- Unable to compute support MA preference.\n\n")

        # 4) Is daily Path B now competitive with weekly Path A?
        f.write("## Is daily Path B now competitive with weekly Path A?\n\n")
        if path_a_mar_full is not None and best_full is not None:
            delta_pa = best_full["mar"] - path_a_mar_full
            f.write(
                f"- Path A weekly full-sample MAR: {path_a_mar_full:.3f}\n"
            )
            f.write(
                f"- Best MA-pair daily Path B full-sample MAR: {best_full['mar']:.3f} "
                f"(Δ vs Path A = {delta_pa:.3f}).\n"
            )
            if delta_pa >= -0.05:
                f.write(
                    "- Conclusion: Daily Path B with MA/MA filtering is **roughly competitive** with weekly Path A on MAR.\n"
                )
            else:
                f.write(
                    "- Conclusion: Daily Path B with MA/MA filtering is **still clearly weaker** than weekly Path A.\n"
                )
        else:
            f.write("- Unknown (missing Path A or ablation MAR for full_sample).\n")


if __name__ == "__main__":
    main()

