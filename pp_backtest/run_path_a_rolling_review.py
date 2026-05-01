"""
Path A rolling config review (Champion vs Challenger).

- Champion:   extension_first, max_positions=8
- Challenger: simple_composite, max_positions=12

Runs rolling 6-month and 12-month windows over recent history (2022-01-01 to 2026-02-21),
using the current Path A signal/regime/PIT/portfolio wiring, and writes:
- artifacts/path_a_rolling_review.csv
- artifacts/path_a_rolling_review.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

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
from pp_backtest.portfolio_sim import (
    PortfolioConfig,
    run_portfolio_backtest,
    DEFAULT_INITIAL_EQUITY_VND,
)
from pp_backtest.run_weekly_ema21_portfolio import load_universe

CHAMPION = ("champion", "extension_first", 8)
CHALLENGER = ("challenger", "simple_composite", 12)

FULL_START = "2012-01-01"
FULL_END = "2026-02-21"
ROLL_START = "2022-01-01"
ROLL_END = "2026-02-21"


def _build_weekly_dfs_full(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Build full-sample weekly_dfs once (Path A wiring, including regime)."""
    cfg = BacktestConfig()
    cfg.start = FULL_START
    cfg.end = FULL_END
    # Market regime
    try:
        market_daily = fetch_ohlcv_fireant("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            daily_df = fetch_ohlcv_fireant(sym, cfg.start, cfg.end)
        except Exception:
            continue
        wdf = daily_to_weekly(daily_df)
        if wdf.empty or len(wdf) < 11:
            continue
        c = wdf["close"].astype(float)
        wdf["ma10"] = sma(c, 10)
        wdf["ema21"] = ema(c, 21)
        wdf["weekly_pp"] = weekly_pocket_pivot_signal(wdf)
        wdf["exit_ma10"] = weekly_exit_ema21_ma50(wdf)
        wdf = wdf.merge(market_weekly_regime, on="date", how="left")
        wdf["regime_ftd"] = wdf["regime_ftd"].fillna(False)
        wdf["no_new_positions"] = wdf["no_new_positions"].fillna(False)
        weekly_dfs[sym] = wdf
    return weekly_dfs


def _get_eligibility(weekly_dfs: dict[str, pd.DataFrame]) -> EligibilityMap:
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


def _slice_weekly_dfs(
    weekly_dfs: dict[str, pd.DataFrame], start: str, end: str
) -> dict[str, pd.DataFrame]:
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    sliced: dict[str, pd.DataFrame] = {}
    for sym, wdf in weekly_dfs.items():
        w = wdf.copy()
        w["date"] = pd.to_datetime(w["date"])
        mask = (w["date"] >= start_dt) & (w["date"] <= end_dt)
        sub = w.loc[mask]
        if not sub.empty:
            sliced[sym] = sub
    return sliced


def _generate_month_starts(start: str, end: str, step_months: int) -> List[pd.Timestamp]:
    dates: List[pd.Timestamp] = []
    cur = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    while cur <= end_dt:
        dates.append(cur)
        # add step_months months
        year = cur.year + (cur.month - 1 + step_months) // 12
        month = (cur.month - 1 + step_months) % 12 + 1
        day = 1
        cur = pd.Timestamp(year=year, month=month, day=day)
    return dates


def _rolling_windows(
    kind: str,  # "6m" or "12m"
    step_months: int,
) -> List[Tuple[str, str, str]]:
    start_dt = pd.to_datetime(ROLL_START)
    end_dt = pd.to_datetime(ROLL_END)
    months = 6 if kind == "6m" else 12
    starts = _generate_month_starts(ROLL_START, ROLL_END, step_months)
    windows: List[Tuple[str, str, str]] = []
    for s in starts:
        e_year = s.year + (s.month - 1 + months) // 12
        e_month = (s.month - 1 + months) % 12 + 1
        # approximate end as last day of month
        e = pd.Timestamp(e_year, e_month, 1) - pd.Timedelta(days=1)
        if e < s:
            continue
        if s > end_dt:
            break
        if e > end_dt:
            e = end_dt
        label = f"{kind}_{s.strftime('%Y-%m')}"
        windows.append((s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), label))
    return windows


def _run_window(
    sliced_dfs: dict[str, pd.DataFrame],
    eligibility: EligibilityMap,
    config_name: str,
    ranking_mode: str,
    max_positions: int,
    window_start: str,
    window_end: str,
    window_label: str,
) -> dict:
    config = PortfolioConfig(
        risk_per_trade=0.005,
        max_heat=0.04,
        max_positions=max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(
        sliced_dfs, config, eligibility=eligibility, ranking_mode=ranking_mode
    )
    period_days = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    period_months = max(1, period_days / 30.0)
    n_trades = len(trades_df)
    trades_per_month = n_trades / period_months if period_months else np.nan
    return {
        "window_kind": window_label.split("_")[0],
        "window_label": window_label,
        "window_start": window_start,
        "window_end": window_end,
        "config_name": config_name,
        "ranking_mode": ranking_mode,
        "max_positions": max_positions,
        "cagr": stats.get("cagr", np.nan),
        "mdd": stats.get("mdd", np.nan),
        "mar": stats.get("mar", np.nan),
        "n_trades": n_trades,
        "trades_per_month": trades_per_month,
        "avg_heat": stats.get("avg_heat", np.nan),
        "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
        "chosen_rate": stats.get("chosen_rate", np.nan),
        "rejected_max_positions": stats.get("rejected_max_positions", 0),
    }


def _write_md(df: pd.DataFrame, md_path: Path) -> None:
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Rolling Config Review — Champion vs Challenger\n\n")
        f.write("- Champion: ranking_mode=extension_first, max_positions=8\n")
        f.write("- Challenger: ranking_mode=simple_composite, max_positions=12\n")
        f.write(f"- Windows from {ROLL_START} to {ROLL_END}, 6m and 12m, step=quarterly.\n\n")

        def _count_beats(kind: str) -> tuple[int, int]:
            sub = df[df["window_kind"] == kind]
            champ = sub[sub["config_name"] == "champion"]
            chal = sub[sub["config_name"] == "challenger"]
            beats_chal = 0
            beats_champ = 0
            for label in sorted(sub["window_label"].unique()):
                c1 = champ[champ["window_label"] == label]
                c2 = chal[chal["window_label"] == label]
                if c1.empty or c2.empty:
                    continue
                m1 = c1["mar"].iloc[0]
                m2 = c2["mar"].iloc[0]
                if pd.isna(m1) or pd.isna(m2):
                    continue
                if m1 > m2:
                    beats_chal += 1
                elif m2 > m1:
                    beats_champ += 1
            return beats_chal, beats_champ

        for kind in ["6m", "12m"]:
            champ_wins, chal_wins = _count_beats(kind)
            f.write(f"## {kind} windows — MAR win counts\n\n")
            f.write(f"- Windows where **Champion** MAR > Challenger MAR: {champ_wins}\n")
            f.write(f"- Windows where **Challenger** MAR > Champion MAR: {chal_wins}\n\n")

        for kind in ["6m", "12m"]:
            f.write(f"## Average MAR by config — {kind} windows\n\n")
            sub = df[df["window_kind"] == kind]
            if sub.empty:
                f.write("No data.\n\n")
                continue
            grp = sub.groupby("config_name")["mar"].mean()
            for cfg in ["champion", "challenger"]:
                if cfg in grp.index:
                    f.write(f"- {cfg}: mean MAR={grp[cfg]:.4f}\n")
            f.write("\n")

        f.write("## Average chosen_rate and rejected_max_positions by config (all windows)\n\n")
        grp = df.groupby("config_name").agg(
            chosen_rate=("chosen_rate", "mean"),
            rejected_max_positions=("rejected_max_positions", "mean"),
        )
        for cfg in ["champion", "challenger"]:
            if cfg in grp.index:
                row = grp.loc[cfg]
                f.write(
                    f"- {cfg}: mean chosen_rate={row['chosen_rate']:.4g}, "
                    f"mean rejected_max_positions={row['rejected_max_positions']:.1f}\n"
                )
        f.write("\n")

        # Simple promotion rule description
        f.write("## Promotion rule (for future decisions)\n\n")
        f.write(
            "- **Rule:** Only review switching the default to Challenger if, in the rolling review, "
            "Challenger beats Champion on MAR in at least **60% of the last 10 rolling windows** "
            "and does **not** materially worsen MDD (no more than 5 percentage points deeper on average).\n\n"
        )

        # Plain-English conclusion placeholder; this run is single-shot, so we infer from averages.
        sub6 = df[df["window_kind"] == "6m"]
        sub12 = df[df["window_kind"] == "12m"]
        def _mean_mar(sub, cfg):
            return float(sub[sub["config_name"] == cfg]["mar"].mean()) if not sub.empty else np.nan
        champ_mar_6 = _mean_mar(sub6, "champion")
        chal_mar_6 = _mean_mar(sub6, "challenger")
        champ_mar_12 = _mean_mar(sub12, "champion")
        chal_mar_12 = _mean_mar(sub12, "challenger")

        f.write("## Conclusion\n\n")
        if (
            not np.isnan(chal_mar_6)
            and not np.isnan(champ_mar_6)
            and not np.isnan(chal_mar_12)
            and not np.isnan(champ_mar_12)
            and chal_mar_6 > champ_mar_6
            and chal_mar_12 > champ_mar_12
        ):
            f.write(
                "- **Challenger deserves formal baseline review:** Challenger shows higher mean MAR in both 6m and 12m "
                "rolling windows; apply the promotion rule and reassess in more detail.\n"
            )
        else:
            f.write(
                "- **Champion still clearly primary; Challenger under watch only.** Rolling windows do not show "
                "a consistent MAR advantage for Challenger across both 6m and 12m windows.\n"
            )


def main() -> None:
    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[path_a_rolling_review] No symbols; aborting.")
        return

    weekly_dfs_full = _build_weekly_dfs_full(symbols)
    if not weekly_dfs_full:
        print("[path_a_rolling_review] No weekly data; aborting.")
        return
    eligibility_full = _get_eligibility(weekly_dfs_full)

    rows: List[dict] = []
    # Use quarterly steps for performance
    windows_6m = _rolling_windows("6m", step_months=3)
    windows_12m = _rolling_windows("12m", step_months=3)
    all_windows = [("6m", w) for w in windows_6m] + [("12m", w) for w in windows_12m]

    for kind, (ws, we, label) in all_windows:
        sliced = _slice_weekly_dfs(weekly_dfs_full, ws, we)
        if not sliced:
            continue
        print(f"[path_a_rolling_review] Window {label} {ws} -> {we}", flush=True)
        for config_name, ranking_mode, max_positions in [CHAMPION, CHALLENGER]:
            row = _run_window(
                sliced,
                eligibility_full,
                config_name=config_name,
                ranking_mode=ranking_mode,
                max_positions=max_positions,
                window_start=ws,
                window_end=we,
                window_label=label,
            )
            rows.append(row)
            print(
                f"  {config_name} MAR={row['mar']:.4f} n_trades={row['n_trades']}",
                flush=True,
            )

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "path_a_rolling_review.csv"
    md_path = artifacts_dir / "path_a_rolling_review.md"

    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(csv_path, index=False)
        _write_md(df, md_path)
        print(f"[path_a_rolling_review] Wrote {csv_path}, {md_path}", flush=True)
    else:
        print("[path_a_rolling_review] No rows; nothing written.", flush=True)


if __name__ == "__main__":
    main()

