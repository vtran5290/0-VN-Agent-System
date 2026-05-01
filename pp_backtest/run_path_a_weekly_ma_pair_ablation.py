"""
Path A weekly MA/MA ablation.

Experiment-only: test SMA/SMA trend + support gates with a raw weekly pivot (volume thrust only),
without contaminating with production weekly_pp's MA50. Does not change Path B or production Path A.

- raw_weekly_pp = volume thrust only (no MA10/MA50)
- support gate = close > SMA10 or close > SMA20
- trend gate = SMA_short > SMA_long
- MA set: [5, 10, 20, 30, 40, 50] -> 15 pairs × 2 support = 30 configs
- Entry at week t+1 open, exit at week t+1 open, weekly MTM
- PIT eligibility unchanged (4bn/day equivalent)

Execution: staged (screen -> confirm -> full) with weekly data built once and incremental CSV writes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Dict, List, Set, Tuple

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
    from pp_backtest.signals_weekly import sma
    from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily
    from pp_backtest.eligibility import get_global_eligibility, EligibilityMap
    from pp_backtest.portfolio_sim import PortfolioConfig, DEFAULT_INITIAL_EQUITY_VND
except ImportError:
    from config import BacktestConfig
    from data import fetch_ohlcv_fireant
    from weekly_bars import daily_to_weekly
    from signals_weekly import sma
    from market_regime import add_book_regime_columns, weekly_regime_from_daily
    from eligibility import get_global_eligibility, EligibilityMap
    from portfolio_sim import PortfolioConfig, DEFAULT_INITIAL_EQUITY_VND


MA_SET = [5, 10, 20, 30, 40, 50]
SUPPORT_SET = [10, 20]

# Full sample: build weekly data once, slice by period in memory
FULL_START = "2012-01-01"
FULL_END = "2026-02-21"
# Screen: 2018-2021 + recent 2024-2026Q1 (closest to current conditions)
SCREEN_PERIODS = [
    ("2018-01-01", "2021-12-31", "2018-2021"),
    ("2024-01-01", "2026-02-21", "2024-2026Q1"),
]
# Confirm: 2022-2024 + full sample
CONFIRM_PERIODS = [
    ("2022-01-01", "2024-12-31", "2022-2024"),
    ("2012-01-01", "2026-02-21", "full_sample"),
]
ALL_PERIODS = SCREEN_PERIODS + CONFIRM_PERIODS
# Screen early-stop (screen stage only): if 2018-2021 has n_trades < MIN_TRADES or MAR < MAR threshold,
# skip 2024-2026Q1 for that config to save runtime. Documented in screen.md.
SCREEN_EARLY_STOP_MIN_TRADES = 5
SCREEN_EARLY_STOP_MAR = -0.5
TOP_N_CONFIRM = 8
RESULTS_COLUMNS = [
    "support_ma", "short_ma", "long_ma", "period", "start", "end",
    "cagr", "mdd", "mar", "n_trades", "trades_per_month", "final_equity",
    "avg_heat", "avg_gross_exposure",
    "skipped_ineligible", "skipped_regime_off", "skipped_no_new_positions",
    "skipped_max_positions", "skipped_liquidity",
    "post_regime_candidates", "actual_entries", "chosen_rate", "rejected_max_positions",
]


def raw_weekly_pp_volume_thrust(wdf: pd.DataFrame, vol_lookback_weeks: int = 10) -> pd.Series:
    """
    Experiment-only: pivot/accumulation part without any MA filter.
    Volume thrust: volume_week > max(down_volume last vol_lookback_weeks).
    """
    c = wdf["close"].astype(float)
    v = wdf["volume"].astype(float)
    down_vol = np.where(c < c.shift(1), v, 0.0)
    down_vol = pd.Series(down_vol, index=wdf.index)
    max_down_vol = down_vol.rolling(vol_lookback_weeks, min_periods=vol_lookback_weeks).max().shift(1)
    return (v > max_down_vol).fillna(False)


def _load_universe(path: Path) -> List[str]:
    txt = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in txt if ln.strip() and not ln.strip().startswith("#")]


def build_weekly_dfs_with_smas(
    start: str,
    end: str,
    symbols: List[str],
    market_weekly_regime: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    """Build per-symbol weekly DataFrames with SMA columns for MA_SET and raw_weekly_pp."""
    weekly_dfs: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch_ohlcv_fireant(sym, start, end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < max(MA_SET) + 1:
            continue
        wdf = wdf.copy()
        c = wdf["close"].astype(float)
        for n in MA_SET:
            wdf[f"ma{n}"] = sma(c, n)
        wdf["raw_weekly_pp"] = raw_weekly_pp_volume_thrust(wdf)
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs


def build_weekly_dfs_full_sample(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """Build weekly data once for full sample (FULL_START to FULL_END). Reused across periods via slicing."""
    try:
        market_daily = fetch_ohlcv_fireant("VN30", FULL_START, FULL_END)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])
    return build_weekly_dfs_with_smas(FULL_START, FULL_END, symbols, market_weekly_regime)


def slice_weekly_dfs_for_period(
    weekly_dfs: Dict[str, pd.DataFrame],
    start: str,
    end: str,
) -> Dict[str, pd.DataFrame]:
    """Slice full-sample weekly_dfs to date range [start, end] in memory. Drops symbols with no rows in range."""
    start_d = pd.to_datetime(start)
    end_d = pd.to_datetime(end)
    out: Dict[str, pd.DataFrame] = {}
    for sym, wdf in weekly_dfs.items():
        wdf = wdf.copy()
        wdf["date"] = pd.to_datetime(wdf["date"]).dt.normalize()
        mask = (wdf["date"] >= start_d) & (wdf["date"] <= end_d)
        sliced = wdf.loc[mask]
        if not sliced.empty:
            out[sym] = sliced
    return out


def _append_row_to_csv(csv_path: Path, row: dict, columns: List[str]) -> None:
    """Append one result row to CSV. Writes header if file missing or empty."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df_one = pd.DataFrame([{c: row.get(c) for c in columns}])
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        df_one.to_csv(csv_path, index=False)
    else:
        df_one.to_csv(csv_path, mode="a", header=False, index=False)


def _load_checkpoint(csv_path: Path) -> Set[Tuple[int, int, int, str]]:
    """Load set of (support_ma, short_ma, long_ma, period) already completed."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return set()
    df = pd.read_csv(csv_path)
    for c in ["support_ma", "short_ma", "long_ma", "period"]:
        if c not in df.columns:
            return set()
    return set(zip(df["support_ma"].astype(int), df["short_ma"].astype(int), df["long_ma"].astype(int), df["period"].astype(str)))


def _save_checkpoint_entry(csv_path: Path, support_ma: int, short_ma: int, long_ma: int, period: str) -> None:
    """Append one checkpoint row."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"support_ma": support_ma, "short_ma": short_ma, "long_ma": long_ma, "period": period}
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        pd.DataFrame([row]).to_csv(csv_path, index=False)
    else:
        pd.DataFrame([row]).to_csv(csv_path, mode="a", header=False, index=False)


def _compute_stop_price_ma(row: pd.Series, support_ma: int) -> float:
    """Stop for risk sizing: max(low, 0.99 * SMA_support)."""
    close = float(row["close"])
    low = float(row["low"])
    ma_val = float(row.get(f"ma{support_ma}", np.nan))
    stop_ma = ma_val * 0.99 if not np.isnan(ma_val) and ma_val > 0 else close * 0.92
    return max(low, stop_ma)


@dataclass
class MaPairConfig:
    support_ma: int
    short_ma: int
    long_ma: int
    period: str
    start: str
    end: str


def run_weekly_backtest_ma(
    weekly_dfs: Dict[str, pd.DataFrame],
    config: PortfolioConfig,
    eligibility: EligibilityMap,
    ma_cfg: MaPairConfig,
) -> Tuple[pd.DataFrame, dict]:
    """
    Weekly portfolio sim for one (support_ma, short_ma, long_ma).
    Entry: raw_weekly_pp & close > SMA_support & SMA_short > SMA_long & regime & !no_new_positions.
    Exit: close < SMA_support OR SMA_short < SMA_long (at next week open).
    """
    fee_mult = config.fee_bps_per_side / 10_000.0
    cash_vnd = config.initial_equity
    all_dates = sorted(set().union(*(set(w["date"].astype(str)) for w in weekly_dfs.values())))
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
    rejected_max_positions = 0
    post_regime_candidates = 0

    sup_col = f"ma{ma_cfg.support_ma}"
    short_col = f"ma{ma_cfg.short_ma}"
    long_col = f"ma{ma_cfg.long_ma}"

    for i, dt in enumerate(all_dates):
        cur_date = pd.to_datetime(dt)

        # 1) Exits at next week open
        to_close: List[str] = []
        for sym, pos in list(positions.items()):
            wdf = weekly_dfs.get(sym)
            if wdf is None:
                continue
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            c = float(row["close"])
            ma_sup = float(row.get(sup_col, np.nan))
            ma_short = float(row.get(short_col, np.nan))
            ma_long = float(row.get(long_col, np.nan))
            exit_support = (not np.isnan(ma_sup)) and (c < ma_sup)
            exit_trend = (not np.isnan(ma_short) and not np.isnan(ma_long)) and (ma_short < ma_long)
            if not (exit_support or exit_trend):
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
            trades.append({
                "symbol": sym,
                "entry_date": pos["entry_date"],
                "exit_date": exit_date,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "shares": size,
                "pnl": pnl_vnd,
                "ret": (exit_price - entry_price) / entry_price if entry_price > 0 else np.nan,
                "risk_budget": pos["risk_budget"],
            })
        for sym in to_close:
            positions.pop(sym, None)

        # 2) Mark-to-market
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
        free_heat_vnd = max(0.0, config.max_heat * equity_vnd - open_risk_vnd)

        # 3) Regime
        regime_ftd = False
        no_new_positions = True
        for wdf in weekly_dfs.values():
            r = wdf[wdf["date"].astype(str) == dt]
            if not r.empty:
                regime_ftd = bool(r.iloc[0].get("regime_ftd", False))
                no_new_positions = bool(r.iloc[0].get("no_new_positions", True))
                break

        # 4) Candidates: raw_weekly_pp & close > SMA_support & SMA_short > SMA_long
        candidates: List[dict] = []
        for sym, wdf in weekly_dfs.items():
            row = wdf[wdf["date"].astype(str) == dt]
            if row.empty:
                continue
            row = row.iloc[0]
            if not bool(row.get("raw_weekly_pp", False)):
                continue
            c = float(row["close"])
            ma_sup = float(row.get(sup_col, np.nan))
            ma_short = float(row.get(short_col, np.nan))
            ma_long = float(row.get(long_col, np.nan))
            if np.isnan(ma_sup) or np.isnan(ma_short) or np.isnan(ma_long):
                continue
            if not (c > ma_sup and ma_short > ma_long):
                continue
            adtv20, adtv50 = eligibility.adtv(sym, cur_date)
            eligible_flag = eligibility.is_eligible(sym, cur_date)
            candidates.append({
                "symbol": sym,
                "row": row,
                "adtv20": adtv20,
                "adtv50": adtv50,
                "eligible_flag": eligible_flag,
            })

        # Count post-regime candidates (after regime gate)
        if regime_ftd and not no_new_positions:
            post_regime_candidates += len(candidates)

        # Rank by ADTV20 (simple, same as Path A style)
        candidates_sorted = sorted(candidates, key=lambda c: -(c["adtv20"] or 0.0))

        # 5) Entries at next week open
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
                rejected_max_positions += 1
                continue
            if free_heat_vnd <= 0:
                skipped_heat += 1
                continue

            next_dt = all_dates[i + 1] if i + 1 < len(all_dates) else None
            if next_dt is None:
                continue
            wdf = weekly_dfs[sym]
            next_row = wdf[wdf["date"].astype(str) == next_dt]
            if next_row.empty:
                continue
            entry_price = float(next_row["open"].iloc[0])
            if entry_price <= 0:
                continue
            stop_price = _compute_stop_price_ma(row, ma_cfg.support_ma)
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

        # 6) End-of-week equity
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

    trades_df = pd.DataFrame(trades)
    eq = np.array(equity_path, dtype=float)
    dates_arr = np.array(dates_path)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    mdd = float(dd.min())
    years = (dates_arr[-1] - dates_arr[0]).days / 365.25
    cagr = (eq[-1] / eq[0]) ** (1.0 / years) - 1.0 if years > 0 and eq[0] > 0 else np.nan
    mar = cagr / abs(mdd) if mdd < 0 else np.nan
    mean_equity = float(np.mean(eq)) if np.mean(eq) > 0 else 1.0
    period_months = max(1, (pd.to_datetime(all_dates[-1]) - pd.to_datetime(all_dates[0])).days / 30.0)
    n_trades = len(trades_df)
    trades_per_month = n_trades / period_months
    actual_entries = n_trades
    chosen_rate = actual_entries / post_regime_candidates if post_regime_candidates > 0 else np.nan

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
        "n_trades": n_trades,
        "trades_per_month": trades_per_month,
        "final_equity": float(eq[-1]),
        "avg_heat": float(np.mean(heat_path)) / mean_equity,
        "avg_gross_exposure": float(np.mean(gross_exposure_path)),
        "skipped_ineligible": skipped_ineligible,
        "skipped_regime_off": skipped_regime_off,
        "skipped_no_new_positions": skipped_no_new_positions,
        "skipped_max_positions": skipped_max_positions,
        "skipped_liquidity": skipped_liquidity,
        "post_regime_candidates": post_regime_candidates,
        "actual_entries": actual_entries,
        "chosen_rate": chosen_rate,
        "rejected_max_positions": rejected_max_positions,
    }
    return trades_df, stats


def _iter_ma_pairs() -> List[Tuple[int, int]]:
    pairs = []
    for short, long in product(MA_SET, MA_SET):
        if short < long:
            pairs.append((short, long))
    return pairs


def _robustness_scores(df: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["support_ma", "short_ma", "long_ma"]
    rows = []
    for (sup, short, long), grp in df.groupby(key_cols):
        mars = grp["mar"].dropna().values
        if mars.size == 0:
            continue
        avg_mar = float(np.mean(mars))
        num_negative = int((mars < 0).sum())
        total_trades = int(grp["n_trades"].sum())
        penalty_neg = 0.5 * num_negative
        penalty_trades = (100 - total_trades) / 100.0 if total_trades < 100 else 0.0
        score = avg_mar - penalty_neg - penalty_trades
        rows.append({
            "support_ma": sup,
            "short_ma": short,
            "long_ma": long,
            "avg_mar": avg_mar,
            "num_negative_periods": num_negative,
            "total_trades": total_trades,
            "score": score,
        })
    return pd.DataFrame(rows)


def _write_artifacts(df: pd.DataFrame, robustness_df: pd.DataFrame, baseline_mar: float | None) -> None:
    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_weekly_ma_pair_ablation.csv"
    md_path = artifacts_dir / "path_a_weekly_ma_pair_ablation.md"
    summary_path = artifacts_dir / "path_a_weekly_ma_pair_summary.md"

    df.to_csv(csv_path, index=False)
    periods = ["2018-2021", "2024-2026Q1", "2022-2024", "full_sample"]

    def table_from_df(tdf: pd.DataFrame, cols: List[str]) -> str:
        cols = [c for c in cols if c in tdf.columns]
        if not cols or tdf.empty:
            return ""
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, row in tdf[cols].iterrows():
            vals = [row[c] for c in cols]
            fmt = [f"{v:.4g}" if isinstance(v, (int, float)) and not (isinstance(v, bool)) else str(v) for v in vals]
            lines.append("| " + " | ".join(fmt) + " |")
        return "\n".join(lines)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A – Weekly MA-pair Ablation\n\n")
        f.write("30 configs (15 SMA pairs × 2 support). Raw weekly PP (volume thrust only) + close > SMA_support + SMA_short > SMA_long.\n\n")

        # 1) Top 10 by MAR per period
        f.write("## 1. Top 10 configs by MAR per period\n\n")
        for period in periods:
            sub = df[df["period"] == period]
            if sub.empty:
                continue
            top = sub.sort_values("mar", ascending=False).head(10)
            f.write(f"### {period}\n\n")
            f.write(table_from_df(top, [
                "support_ma", "short_ma", "long_ma", "cagr", "mdd", "mar", "n_trades",
                "trades_per_month", "post_regime_candidates", "actual_entries", "chosen_rate", "rejected_max_positions",
            ]) + "\n\n")

        # 2) Top 10 by robustness
        f.write("## 2. Top 10 configs by robustness\n\n")
        top_robust = robustness_df.sort_values("score", ascending=False).head(10)
        f.write(table_from_df(top_robust, [
            "support_ma", "short_ma", "long_ma", "avg_mar", "num_negative_periods", "total_trades", "score",
        ]) + "\n\n")

        # 3) Support 10 vs 20
        f.write("## 3. Support 10 vs Support 20\n\n")
        for sup in SUPPORT_SET:
            s = df[df["support_ma"] == sup]
            if s.empty:
                continue
            f.write(f"- support_ma={sup}: mean MAR={s['mar'].mean():.4f}, mean chosen_rate={s['chosen_rate'].mean():.4f}\n")
        f.write("\n")

        # 4) Shorter pairs (5/10, 5/20, 10/20)
        f.write("## 4. Shorter pairs (5/10, 5/20, 10/20)\n\n")
        short_pairs = {(5, 10), (5, 20), (10, 20)}
        mask = df.apply(lambda r: (int(r["short_ma"]), int(r["long_ma"])) in short_pairs, axis=1)
        short_df = df[mask]
        if not short_df.empty:
            f.write(f"Mean MAR: {short_df['mar'].mean():.4f}. Mean chosen_rate: {short_df['chosen_rate'].mean():.4f}\n\n")
        else:
            f.write("No data.\n\n")

        # 5) Medium pairs (10/30, 20/40, 20/50, 30/50)
        f.write("## 5. Medium pairs (10/30, 20/40, 20/50, 30/50)\n\n")
        med_pairs = {(10, 30), (20, 40), (20, 50), (30, 50)}
        mask = df.apply(lambda r: (int(r["short_ma"]), int(r["long_ma"])) in med_pairs, axis=1)
        med_df = df[mask]
        if not med_df.empty:
            f.write(f"Mean MAR: {med_df['mar'].mean():.4f}. Mean chosen_rate: {med_df['chosen_rate'].mean():.4f}\n\n")
        else:
            f.write("No data.\n\n")

        # 6) Comparison vs current Path A baseline
        f.write("## 6. Comparison vs current Path A baseline\n\n")
        if baseline_mar is not None:
            best_full = df[df["period"] == "full_sample"].sort_values("mar", ascending=False)
            if not best_full.empty:
                best_mar = float(best_full["mar"].iloc[0])
                f.write(f"- Baseline Path A (full-sample MAR): {baseline_mar:.4f}\n")
                f.write(f"- Best MA-pair full-sample MAR: {best_mar:.4f}\n\n")
        else:
            f.write("Baseline MAR not available.\n\n")

        # 7) Max_positions pressure
        f.write("## 7. Max_positions pressure\n\n")
        f.write("Configs with highest post_regime_candidates (candidate pressure):\n\n")
        by_config = df.groupby(["support_ma", "short_ma", "long_ma"]).agg({
            "post_regime_candidates": "sum",
            "actual_entries": "sum",
            "rejected_max_positions": "sum",
        }).reset_index()
        by_config["chosen_rate_approx"] = by_config["actual_entries"] / by_config["post_regime_candidates"].replace(0, np.nan)
        top_candidates = by_config.sort_values("post_regime_candidates", ascending=False).head(10)
        f.write(table_from_df(top_candidates, [
            "support_ma", "short_ma", "long_ma", "post_regime_candidates", "actual_entries", "rejected_max_positions", "chosen_rate_approx",
        ]) + "\n\n")
        f.write("Configs with best chosen_rate (under 8-position cap):\n\n")
        by_config_valid = by_config[by_config["post_regime_candidates"] > 0]
        if not by_config_valid.empty:
            by_config_valid = by_config_valid.sort_values("chosen_rate_approx", ascending=False).head(10)
            f.write(table_from_df(by_config_valid, [
                "support_ma", "short_ma", "long_ma", "post_regime_candidates", "actual_entries", "chosen_rate_approx",
            ]) + "\n")

    # Summary
    best_robust = robustness_df.sort_values("score", ascending=False).iloc[0] if not robustness_df.empty else None
    early_df = df[df["period"] == "2018-2021"]
    best_early = early_df.sort_values("mar", ascending=False).iloc[0] if not early_df.empty else None
    support_compare = df.groupby("support_ma")["mar"].mean()
    best_support = int(support_compare.idxmax()) if len(support_compare) else None
    full_df = df[df["period"] == "full_sample"]
    best_full_row = full_df.sort_values("mar", ascending=False).iloc[0] if not full_df.empty else None
    improved = best_full_row is not None and baseline_mar is not None and float(best_full_row["mar"]) > float(baseline_mar)

    # Screen periods only (2018-2021 + 2024-2026Q1): best by screen score
    screen_periods_df = df[df["period"].isin(["2018-2021", "2024-2026Q1"])]
    screen_scores_df = _screening_score_two_periods(screen_periods_df) if not screen_periods_df.empty else pd.DataFrame()
    best_screen = screen_scores_df.sort_values("score", ascending=False).iloc[0] if not screen_scores_df.empty else None

    # Recent period (2024-2026Q1): agreement with 2018-2021 and top-config chosen_rate / rejected_max_positions
    recent_df = df[df["period"] == "2024-2026Q1"]
    agree_count = conflict_count = 0
    if not recent_df.empty and "2018-2021" in df["period"].values:
        for (sup, short, long), grp in df[df["period"].isin(["2018-2021", "2024-2026Q1"])].groupby(["support_ma", "short_ma", "long_ma"]):
            if grp.shape[0] != 2:
                continue
            mar_early = grp[grp["period"] == "2018-2021"]["mar"].iloc[0]
            mar_recent = grp[grp["period"] == "2024-2026Q1"]["mar"].iloc[0]
            if pd.isna(mar_early) or pd.isna(mar_recent):
                continue
            if (mar_early > 0 and mar_recent > 0) or (mar_early <= 0 and mar_recent <= 0):
                agree_count += 1
            else:
                conflict_count += 1
    top_configs_recent = recent_df.sort_values("mar", ascending=False).head(TOP_N_CONFIRM) if not recent_df.empty else pd.DataFrame()

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Path A Weekly MA-pair Ablation – Summary\n\n")
        f.write("Screen periods: 2018-2021 + 2024-2026Q1. Confirm periods: 2022-2024 + full_sample.\n\n")
        if best_screen is not None:
            f.write(f"- **Best config by screen score** (2018-2021 + 2024-2026Q1): support_ma={int(best_screen['support_ma'])}, short_ma={int(best_screen['short_ma'])}, long_ma={int(best_screen['long_ma'])} "
                    f"(score={best_screen['score']:.4f}, avg_mar={best_screen['avg_mar']:.4f})\n\n")
        if best_robust is not None:
            f.write(f"- Best config by robustness (all 4 periods): support_ma={int(best_robust['support_ma'])}, short_ma={int(best_robust['short_ma'])}, long_ma={int(best_robust['long_ma'])} "
                    f"(avg_mar={best_robust['avg_mar']:.4f}, score={best_robust['score']:.4f})\n\n")
        if best_early is not None:
            f.write(f"- Best for 2018-2021: support_ma={int(best_early['support_ma'])}, short_ma={int(best_early['short_ma'])}, long_ma={int(best_early['long_ma'])} "
                    f"(MAR={best_early['mar']:.4f})\n\n")
        f.write(f"- Support 10 vs 20: support_ma={best_support} better on average.\n\n")
        verdict = "Agrees" if agree_count >= conflict_count else "Conflicts"
        f.write(f"- **Recent period (2024-2026Q1) vs 2018-2021:** same MAR sign = agree: {agree_count}, opposite = conflict: {conflict_count}. {verdict} on balance.\n\n")
        if not top_configs_recent.empty and "chosen_rate" in top_configs_recent.columns and "rejected_max_positions" in top_configs_recent.columns:
            f.write("- **Top configs in 2024-2026Q1** (chosen_rate, rejected_max_positions):\n")
            for _, row in top_configs_recent.iterrows():
                cr = row.get("chosen_rate", np.nan)
                rj = row.get("rejected_max_positions", np.nan)
                f.write(f"  - {int(row['support_ma'])}/{int(row['short_ma'])}/{int(row['long_ma'])}: chosen_rate={cr:.4g}, rejected_max_positions={int(rj) if pd.notna(rj) else 'N/A'}\n")
            f.write("\n")
        best_mar_str = f"{best_full_row['mar']:.4f}" if best_full_row is not None else "N/A"
        base_mar_str = f"{baseline_mar:.4f}" if baseline_mar is not None else "N/A"
        f.write(f"- Weekly MA/MA materially improves Path A: {'Yes' if improved else 'No'} "
                f"(baseline MAR={base_mar_str}, best MA-pair full-sample MAR={best_mar_str})\n\n")
        f.write("- Max_positions pressure: see main MD section 7 (configs with most candidates vs best chosen_rate).\n")


def _screening_score_two_periods(df: pd.DataFrame) -> pd.DataFrame:
    """Score per config from screen periods: avg MAR - penalty negative - penalty few trades."""
    key_cols = ["support_ma", "short_ma", "long_ma"]
    rows = []
    for (sup, short, long), grp in df.groupby(key_cols):
        mars = grp["mar"].dropna().values
        if mars.size == 0:
            continue
        avg_mar = float(np.mean(mars))
        num_negative = int((mars < 0).sum())
        total_trades = int(grp["n_trades"].sum())
        penalty_neg = 0.5 * num_negative
        penalty_trades = (100 - total_trades) / 100.0 if total_trades < 100 else 0.0
        score = avg_mar - penalty_neg - penalty_trades
        rows.append({"support_ma": sup, "short_ma": short, "long_ma": long, "avg_mar": avg_mar, "score": score, "total_trades": total_trades})
    return pd.DataFrame(rows)


def _write_screen_md(
    artifacts_dir: Path,
    screen_df: pd.DataFrame,
    top_configs: List[Tuple[int, int, int]],
    liquid_subset_used: bool = False,
) -> None:
    """Write screen stage markdown with top 5-8 configs for confirm."""
    path = artifacts_dir / "path_a_weekly_ma_pair_screen.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Path A Weekly MA-pair – Screen stage\n\n")
        f.write("Periods: **2018-2021**, **2024-2026Q1** (recent period for current conditions). Early-stop: if 2018-2021 has n_trades < 5 or MAR < -0.5, 2024-2026Q1 skipped for that config.\n\n")
        if liquid_subset_used:
            f.write("**Liquid subset:** Symbols from `config/universe_liquid_adv20_2b.txt`. PIT eligibility (4bn) unchanged.\n\n")
        scores = _screening_score_two_periods(screen_df)
        if not scores.empty:
            top = scores.sort_values("score", ascending=False).head(TOP_N_CONFIRM)
            f.write("## Top configs for confirm stage\n\n")
            for _, row in top.iterrows():
                f.write(f"- support_ma={int(row['support_ma'])}, short_ma={int(row['short_ma'])}, long_ma={int(row['long_ma'])} "
                        f"(score={row['score']:.4f}, avg_mar={row['avg_mar']:.4f})\n")
        f.write("\n## Shortlist (use for --stage confirm)\n\n")
        for t in top_configs:
            f.write(f"- {t[0]},{t[1]},{t[2]}\n")


def _write_confirm_md(artifacts_dir: Path, confirm_df: pd.DataFrame) -> None:
    """Write confirm stage markdown."""
    path = artifacts_dir / "path_a_weekly_ma_pair_confirm.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Path A Weekly MA-pair – Confirm stage\n\n")
        f.write("Periods: 2022-2024, full_sample. Configs: top 8 from screen.\n\n")
        if not confirm_df.empty:
            for period in ["2022-2024", "full_sample"]:
                sub = confirm_df[confirm_df["period"] == period]
                if sub.empty:
                    continue
                f.write(f"### {period}\n\n")
                for _, row in sub.sort_values("mar", ascending=False).head(5).iterrows():
                    f.write(f"  {int(row['support_ma'])}/{int(row['short_ma'])}/{int(row['long_ma'])} MAR={row['mar']:.4f} n_trades={int(row['n_trades'])}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Path A weekly MA-pair ablation (staged)")
    parser.add_argument("--stage", choices=["screen", "confirm", "full"], default="screen",
                        help="screen=2018-2021+2024-2026Q1 all 30 configs; confirm=top 8 on 2022-2024+full; full=all 4 periods all 30")
    parser.add_argument("--liquid-subset", action="store_true",
                        help="screen only: use symbols from config/universe_liquid_adv20_2b.txt if exists (fewer symbols, faster). PIT 4bn unchanged.")
    args = parser.parse_args()
    stage = args.stage

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    screen_csv = artifacts_dir / "path_a_weekly_ma_pair_screen.csv"
    screen_checkpoint = artifacts_dir / "path_a_weekly_ma_pair_screen_checkpoint.csv"
    confirm_csv = artifacts_dir / "path_a_weekly_ma_pair_confirm.csv"
    confirm_checkpoint = artifacts_dir / "path_a_weekly_ma_pair_confirm_checkpoint.csv"
    ablation_csv = artifacts_dir / "path_a_weekly_ma_pair_ablation.csv"

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = _load_universe(universe_path)
    liquid_subset_used = False
    if stage == "screen" and getattr(args, "liquid_subset", False):
        liquid_path = _REPO / "config" / "universe_liquid_adv20_2b.txt"
        if liquid_path.exists():
            symbols = _load_universe(liquid_path)
            liquid_subset_used = True
    if not symbols:
        print("[path_a_weekly_ma_ablation] No symbols; aborting.")
        return
    try:
        eligibility = get_global_eligibility()
    except FileNotFoundError:
        print("[path_a_weekly_ma_ablation] Eligibility not found; aborting.")
        return

    pconfig = PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=8,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    ma_pairs = _iter_ma_pairs()

    if stage == "screen":
        print("[path_a_weekly_ma_ablation] Building full-sample weekly data once...", flush=True)
        weekly_dfs_full = build_weekly_dfs_full_sample(symbols)
        if not weekly_dfs_full:
            print("No weekly data; aborting.")
            return
        print(f"  {len(weekly_dfs_full)} symbols.", flush=True)
        done = _load_checkpoint(screen_checkpoint)
        screened_out: Set[Tuple[int, int, int]] = set()
        for period_idx, (start, end, label) in enumerate(SCREEN_PERIODS):
            sliced = slice_weekly_dfs_for_period(weekly_dfs_full, start, end)
            if not sliced:
                print(f"  No data for {label}; skip.")
                continue
            print(f"[path_a_weekly_ma_ablation] Screen period {label} ({len(sliced)} symbols)...", flush=True)
            for support_ma in SUPPORT_SET:
                for short_ma, long_ma in ma_pairs:
                    key = (support_ma, short_ma, long_ma, label)
                    if key in done:
                        continue
                    if period_idx == 1 and (support_ma, short_ma, long_ma) in screened_out:
                        continue
                    ma_cfg = MaPairConfig(support_ma=support_ma, short_ma=short_ma, long_ma=long_ma, period=label, start=start, end=end)
                    _, stats = run_weekly_backtest_ma(sliced, pconfig, eligibility, ma_cfg)
                    if stats:
                        _append_row_to_csv(screen_csv, stats, RESULTS_COLUMNS)
                        _save_checkpoint_entry(screen_checkpoint, support_ma, short_ma, long_ma, label)
                    if period_idx == 0 and stats:
                        mar_val = stats.get("mar")
                        n_trades = stats.get("n_trades", 0)
                        if (isinstance(mar_val, (int, float)) and mar_val < SCREEN_EARLY_STOP_MAR) or (n_trades < SCREEN_EARLY_STOP_MIN_TRADES):
                            screened_out.add((support_ma, short_ma, long_ma))
        if screen_csv.exists():
            screen_df = pd.read_csv(screen_csv)
            scores = _screening_score_two_periods(screen_df)
            top_configs = []
            if not scores.empty:
                top = scores.sort_values("score", ascending=False).head(TOP_N_CONFIRM)
                top_configs = [(int(r["support_ma"]), int(r["short_ma"]), int(r["long_ma"])) for _, r in top.iterrows()]
            _write_screen_md(artifacts_dir, screen_df, top_configs, liquid_subset_used)
        print(f"[path_a_weekly_ma_ablation] Screen done. Results: {screen_csv}")

    elif stage == "confirm":
        if not screen_csv.exists():
            print("[path_a_weekly_ma_ablation] Run --stage screen first.")
            return
        screen_df = pd.read_csv(screen_csv)
        scores = _screening_score_two_periods(screen_df)
        if scores.empty:
            print("No screen scores; aborting.")
            return
        top = scores.sort_values("score", ascending=False).head(TOP_N_CONFIRM)
        shortlist = [(int(r["support_ma"]), int(r["short_ma"]), int(r["long_ma"])) for _, r in top.iterrows()]
        print(f"[path_a_weekly_ma_ablation] Confirm shortlist: {shortlist}", flush=True)
        print("Building full-sample weekly data once...", flush=True)
        weekly_dfs_full = build_weekly_dfs_full_sample(symbols)
        if not weekly_dfs_full:
            print("No weekly data; aborting.")
            return
        done = _load_checkpoint(confirm_checkpoint)
        for start, end, label in CONFIRM_PERIODS:
            sliced = slice_weekly_dfs_for_period(weekly_dfs_full, start, end)
            if not sliced:
                continue
            print(f"  Confirm period {label}...", flush=True)
            for (support_ma, short_ma, long_ma) in shortlist:
                key = (support_ma, short_ma, long_ma, label)
                if key in done:
                    continue
                ma_cfg = MaPairConfig(support_ma=support_ma, short_ma=short_ma, long_ma=long_ma, period=label, start=start, end=end)
                _, stats = run_weekly_backtest_ma(sliced, pconfig, eligibility, ma_cfg)
                if stats:
                    _append_row_to_csv(confirm_csv, stats, RESULTS_COLUMNS)
                    _save_checkpoint_entry(confirm_checkpoint, support_ma, short_ma, long_ma, label)
        if confirm_csv.exists():
            _write_confirm_md(artifacts_dir, pd.read_csv(confirm_csv))
        combined_rows = []
        for _, r in screen_df.iterrows():
            t = (int(r["support_ma"]), int(r["short_ma"]), int(r["long_ma"]))
            if t in shortlist:
                combined_rows.append(r.to_dict())
        if confirm_csv.exists():
            confirm_df = pd.read_csv(confirm_csv)
            for _, r in confirm_df.iterrows():
                combined_rows.append(r.to_dict())
        if combined_rows:
            combined_df = pd.DataFrame(combined_rows)
            combined_df = combined_df[RESULTS_COLUMNS] if all(c in combined_df.columns for c in RESULTS_COLUMNS) else combined_df
            combined_df.to_csv(ablation_csv, index=False)
            baseline_mar = None
            try:
                from pp_backtest.run_weekly_ema21_portfolio import run_weekly_period
                _, base_stats = run_weekly_period(FULL_START, FULL_END, symbols=symbols)
                if base_stats and "mar" in base_stats:
                    baseline_mar = float(base_stats["mar"])
            except Exception:
                pass
            robustness_df = _robustness_scores(combined_df)
            _write_artifacts(combined_df, robustness_df, baseline_mar)
        print(f"[path_a_weekly_ma_ablation] Confirm done. Results: {confirm_csv}; ablation/summary updated.")

    else:
        assert stage == "full"
        print("[path_a_weekly_ma_ablation] Full stage: building weekly data once...", flush=True)
        weekly_dfs_full = build_weekly_dfs_full_sample(symbols)
        if not weekly_dfs_full:
            print("No weekly data; aborting.")
            return
        done: Set[Tuple[int, int, int, str]] = set()
        if ablation_csv.exists() and ablation_csv.stat().st_size > 0:
            existing = pd.read_csv(ablation_csv)
            if all(c in existing.columns for c in ["support_ma", "short_ma", "long_ma", "period"]):
                done = set(zip(existing["support_ma"].astype(int), existing["short_ma"].astype(int), existing["long_ma"].astype(int), existing["period"].astype(str)))
        for start, end, label in ALL_PERIODS:
            sliced = slice_weekly_dfs_for_period(weekly_dfs_full, start, end)
            if not sliced:
                continue
            print(f"  Full period {label}...", flush=True)
            for support_ma in SUPPORT_SET:
                for short_ma, long_ma in ma_pairs:
                    if (support_ma, short_ma, long_ma, label) in done:
                        continue
                    ma_cfg = MaPairConfig(support_ma=support_ma, short_ma=short_ma, long_ma=long_ma, period=label, start=start, end=end)
                    _, stats = run_weekly_backtest_ma(sliced, pconfig, eligibility, ma_cfg)
                    if stats:
                        _append_row_to_csv(ablation_csv, stats, RESULTS_COLUMNS)
                        done.add((support_ma, short_ma, long_ma, label))
        if ablation_csv.exists():
            df = pd.read_csv(ablation_csv)
            baseline_mar = None
            try:
                from pp_backtest.run_weekly_ema21_portfolio import run_weekly_period
                _, base_stats = run_weekly_period(FULL_START, FULL_END, symbols=symbols)
                if base_stats and "mar" in base_stats:
                    baseline_mar = float(base_stats["mar"])
            except Exception:
                pass
            _write_artifacts(df, _robustness_scores(df), baseline_mar)
        print(f"[path_a_weekly_ma_ablation] Full done. Results: {ablation_csv}")


if __name__ == "__main__":
    main()
