"""
Final validation: Champion vs tuned Challenger for Path A.

Configs:
- Champion:
  - ranking_mode = extension_first
  - max_positions = 8
  - risk_per_trade = 0.005
  - max_heat = 0.04

- Challenger_tuned:
  - ranking_mode = simple_composite
  - max_positions = 12
  - risk_per_trade = 0.004
  - max_heat = 0.04

Parts:
1) Full-sample direct comparison on three periods:
   - 2012-01-01 to 2026-02-21
   - 2022-01-01 to 2024-12-31
   - 2024-01-01 to 2026-02-21
   Writes:
   - artifacts/path_a_champion_vs_tuned_challenger.csv
   - artifacts/path_a_champion_vs_tuned_challenger.md

2) Rolling review (6m / 12m, quarterly, 2022-01-01 to 2026-02-21) for these 2 configs only.
   Writes:
   - artifacts/path_a_tuned_challenger_rolling_review.csv
   - artifacts/path_a_tuned_challenger_rolling_review.md

3) Final decision note:
   - artifacts/path_a_tuned_challenger_decision.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
import argparse
import os
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


FULL_START = "2012-01-01"
FULL_END = "2026-02-21"
ROLL_START = "2022-01-01"
ROLL_END = "2026-02-21"
CACHE_DIR = _REPO / "artifacts" / "cache"
CACHE_PATH = CACHE_DIR / "path_a_full_weekly_data.pkl"


@dataclass
class PathAConfig:
    name: str
    ranking_mode: str
    max_positions: int
    risk_per_trade: float
    max_heat: float


CHAMPION = PathAConfig(
    name="champion",
    ranking_mode="extension_first",
    max_positions=8,
    risk_per_trade=0.005,
    max_heat=0.04,
)

CHALLENGER_TUNED = PathAConfig(
    name="challenger_tuned",
    ranking_mode="simple_composite",
    max_positions=12,
    risk_per_trade=0.004,
    max_heat=0.04,
)


def _build_weekly_dfs_full(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """Build full-sample weekly_dfs once (Path A wiring, including regime)."""
    cfg = BacktestConfig()
    cfg.start = FULL_START
    cfg.end = FULL_END
    try:
        market_daily = fetch_ohlcv_fireant("VN30", cfg.start, cfg.end)
        market_daily = add_book_regime_columns(market_daily)
        market_weekly_regime = weekly_regime_from_daily(market_daily)
    except Exception:
        market_weekly_regime = pd.DataFrame(columns=["date", "regime_ftd", "no_new_positions"])

    weekly_dfs: Dict[str, pd.DataFrame] = {}
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


def _load_or_build_weekly_dfs_full(symbols: List[str], use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """Load full weekly_dfs from cache if available, otherwise build and cache."""
    if use_cache and CACHE_PATH.exists():
        try:
            obj = pd.read_pickle(CACHE_PATH)
            if isinstance(obj, dict) and obj:
                print(f"[tuned_challenger] Loaded full weekly cache from {CACHE_PATH}", flush=True)
                return obj
        except Exception:
            print("[tuned_challenger] Failed to load cache; rebuilding.", flush=True)
    print("[tuned_challenger] Building full weekly data...", flush=True)
    weekly_dfs_full = _build_weekly_dfs_full(symbols)
    if weekly_dfs_full:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            pd.to_pickle(weekly_dfs_full, CACHE_PATH)
            print(f"[tuned_challenger] Cached full weekly data to {CACHE_PATH}", flush=True)
        except Exception:
            print("[tuned_challenger] Failed to write cache (non-fatal).", flush=True)
    return weekly_dfs_full


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


def _slice_weekly_dfs(
    weekly_dfs: Dict[str, pd.DataFrame],
    start: str,
    end: str,
) -> Dict[str, pd.DataFrame]:
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    sliced: Dict[str, pd.DataFrame] = {}
    for sym, wdf in weekly_dfs.items():
        w = wdf.copy()
        w["date"] = pd.to_datetime(w["date"])
        mask = (w["date"] >= start_dt) & (w["date"] <= end_dt)
        sub = w.loc[mask]
        if not sub.empty:
            sliced[sym] = sub
    return sliced


def _run_period(
    weekly_dfs_full: Dict[str, pd.DataFrame],
    eligibility: EligibilityMap,
    cfg: PathAConfig,
    start: str,
    end: str,
) -> Tuple[pd.DataFrame, Dict]:
    sliced = _slice_weekly_dfs(weekly_dfs_full, start, end)
    if not sliced:
        return pd.DataFrame(), {}
    pconfig = PortfolioConfig(
        risk_per_trade=cfg.risk_per_trade,
        max_heat=cfg.max_heat,
        max_positions=cfg.max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(
        sliced,
        pconfig,
        eligibility=eligibility,
        ranking_mode=cfg.ranking_mode,
    )
    period_days = (pd.to_datetime(end) - pd.to_datetime(start)).days
    period_months = max(1, period_days / 30.0)
    stats = dict(stats)
    stats["trades_per_month"] = len(trades_df) / period_months if period_months else np.nan
    stats["n_trades"] = len(trades_df)
    stats["final_equity"] = stats.get("final_equity", DEFAULT_INITIAL_EQUITY_VND)
    return trades_df, stats


def _generate_month_starts(start: str, end: str, step_months: int) -> List[pd.Timestamp]:
    dates: List[pd.Timestamp] = []
    cur = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    while cur <= end_dt:
        dates.append(cur)
        year = cur.year + (cur.month - 1 + step_months) // 12
        month = (cur.month - 1 + step_months) % 12 + 1
        cur = pd.Timestamp(year=year, month=month, day=1)
    return dates


def _rolling_windows(kind: str, step_months: int) -> List[Tuple[str, str, str]]:
    months = 6 if kind == "6m" else 12
    starts = _generate_month_starts(ROLL_START, ROLL_END, step_months)
    end_dt = pd.to_datetime(ROLL_END)
    windows: List[Tuple[str, str, str]] = []
    for s in starts:
        e_year = s.year + (s.month - 1 + months) // 12
        e_month = (s.month - 1 + months) % 12 + 1
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
    sliced_dfs: Dict[str, pd.DataFrame],
    eligibility: EligibilityMap,
    cfg: PathAConfig,
    window_start: str,
    window_end: str,
    window_label: str,
) -> Dict:
    pconfig = PortfolioConfig(
        risk_per_trade=cfg.risk_per_trade,
        max_heat=cfg.max_heat,
        max_positions=cfg.max_positions,
        max_symbol_weight=0.10,
        liquidity_participation_cap=0.05,
        initial_equity=DEFAULT_INITIAL_EQUITY_VND,
        fee_bps_per_side=15.0,
    )
    trades_df, stats = run_portfolio_backtest(
        sliced_dfs,
        pconfig,
        eligibility=eligibility,
        ranking_mode=cfg.ranking_mode,
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
        "config_name": cfg.name,
        "ranking_mode": cfg.ranking_mode,
        "max_positions": cfg.max_positions,
        "cagr": stats.get("cagr", np.nan),
        "mdd": stats.get("mdd", np.nan),
        "mar": stats.get("mar", np.nan),
        "n_trades": n_trades,
        "trades_per_month": trades_per_month,
        "avg_heat": stats.get("avg_heat", np.nan),
        "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
    }


def _write_full_comparison_md(df: pd.DataFrame, md_path: Path) -> None:
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Champion vs Tuned Challenger — Full-Sample Comparison\n\n")
        f.write("Configs:\n\n")
        f.write("- **Champion**: extension_first, max_positions=8, risk_per_trade=0.005, max_heat=0.04\n")
        f.write("- **Challenger_tuned**: simple_composite, max_positions=12, risk_per_trade=0.004, max_heat=0.04\n\n")
        periods = df["period"].unique()
        for period in periods:
            sub = df[df["period"] == period]
            if sub.empty:
                continue
            f.write(f"## Period: {period}\n\n")
            f.write("| config_name | ranking_mode | max_positions | CAGR | MDD | MAR | n_trades | trades_per_month | final_equity | avg_heat | avg_gross_exposure |\n")
            f.write("|-------------|--------------|---------------|------|-----|-----|----------|------------------|--------------|----------|--------------------|\n")
            for _, r in sub.iterrows():
                f.write(
                    f"| {r['config_name']} | {r['ranking_mode']} | {int(r['max_positions'])} | "
                    f"{r['cagr']:.2%} | {r['mdd']:.2%} | {r['mar']:.4f} | {int(r['n_trades'])} | "
                    f"{r['trades_per_month']:.2f} | {r['final_equity']:.0f} | {r['avg_heat']:.4f} | {r['avg_gross_exposure']:.4f} |\n"
                )
            f.write("\n")


def _write_rolling_md(df: pd.DataFrame, md_path: Path) -> None:
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Tuned Challenger — Rolling Review (Champion vs Challenger_tuned)\n\n")
        f.write("Windows: 6m and 12m, quarterly step, coverage 2022-01-01 to 2026-02-21.\n\n")

        for kind in ["6m", "12m"]:
            sub = df[df["window_kind"] == kind]
            if sub.empty:
                continue
            f.write(f"## {kind} windows\n\n")
            # 1) Win counts on MAR
            pivot = sub.pivot_table(
                index="window_label",
                columns="config_name",
                values="mar",
                aggfunc="first",
            )
            champ_wins = 0
            chal_wins = 0
            for _, row in pivot.iterrows():
                cm = row.get("champion", np.nan)
                ct = row.get("challenger_tuned", np.nan)
                if pd.isna(cm) or pd.isna(ct):
                    continue
                if cm > ct:
                    champ_wins += 1
                elif ct > cm:
                    chal_wins += 1
            f.write(f"- Champion MAR wins: {champ_wins}\n")
            f.write(f"- Challenger_tuned MAR wins: {chal_wins}\n\n")

            # 2) Average MAR / 3) Average MDD
            avg = sub.groupby("config_name").agg(
                avg_mar=("mar", "mean"),
                avg_mdd=("mdd", "mean"),
                avg_cagr=("cagr", "mean"),
            )
            f.write("### Average metrics by config\n\n")
            f.write("| config_name | avg_CAGR | avg_MDD | avg_MAR |\n")
            f.write("|-------------|---------|--------|---------|\n")
            for cfg_name, r in avg.iterrows():
                f.write(
                    f"| {cfg_name} | {r['avg_cagr']:.2%} | {r['avg_mdd']:.2%} | {r['avg_mar']:.4f} |\n"
                )
            f.write("\n")

            # 4) Last 5 windows: who wins on MAR
            ordered = (
                sub.sort_values("window_end")
                .drop_duplicates(["window_label", "config_name"], keep="last")
            )
            last_labels = (
                ordered["window_label"]
                .drop_duplicates()
                .sort_values()
                .tolist()[-5:]
            )
            f.write("### Last 5 windows — MAR winner\n\n")
            f.write("| window_label | window_start | window_end | winner |\n")
            f.write("|--------------|--------------|------------|--------|\n")
            for label in last_labels:
                rows = ordered[ordered["window_label"] == label]
                if rows.empty:
                    continue
                cm = rows[rows["config_name"] == "champion"]["mar"]
                ct = rows[rows["config_name"] == "challenger_tuned"]["mar"]
                cm_val = float(cm.iloc[0]) if not cm.empty else np.nan
                ct_val = float(ct.iloc[0]) if not ct.empty else np.nan
                win = "tie"
                if not pd.isna(cm_val) and not pd.isna(ct_val):
                    if cm_val > ct_val:
                        win = "champion"
                    elif ct_val > cm_val:
                        win = "challenger_tuned"
                r0 = rows.iloc[0]
                f.write(
                    f"| {label} | {r0['window_start']} | {r0['window_end']} | {win} |\n"
                )
            f.write("\n")

        # 5) Simple summary line about "spirit of promotion rule"
        # (used later by decision note as well)


def _write_decision_md(
    full_df: pd.DataFrame,
    rolling_df: pd.DataFrame,
    md_path: Path,
) -> None:
    # Use full-sample period as primary risk comparison, fall back to 2022-2024 if needed
    full_period = "2012-01-01_to_2026-02-21"
    recent_period = "2024-01-01_to_2026-02-21"
    full_sub = full_df[full_df["period"] == full_period]
    recent_sub = full_df[full_df["period"] == recent_period]

    def _get_row(sub: pd.DataFrame, name: str):
        s = sub[sub["config_name"] == name]
        return s.iloc[0] if not s.empty else None

    champ_full = _get_row(full_sub, "champion")
    chal_full = _get_row(full_sub, "challenger_tuned")
    champ_recent = _get_row(recent_sub, "champion")
    chal_recent = _get_row(recent_sub, "challenger_tuned")

    # Risk improvement: prefer full-sample; if missing, use recent.
    def _mdd(row):
        return float(row["mdd"]) if row is not None and pd.notna(row["mdd"]) else np.nan

    def _mar(row):
        return float(row["mar"]) if row is not None and pd.notna(row["mar"]) else np.nan

    mdd_chal = _mdd(chal_full)
    mdd_champ = _mdd(champ_full)
    mar_chal = _mar(chal_full)
    mar_champ = _mar(champ_full)
    if pd.isna(mdd_chal) or pd.isna(mdd_champ):
        mdd_chal = _mdd(chal_recent)
        mdd_champ = _mdd(champ_recent)
    if pd.isna(mar_chal) or pd.isna(mar_champ):
        mar_chal = _mar(chal_recent)
        mar_champ = _mar(champ_recent)

    # Rolling-win evidence (may be empty if rolling not run yet)
    roll = rolling_df if rolling_df is not None else pd.DataFrame()
    if not roll.empty and {"window_label", "config_name", "mar"}.issubset(roll.columns):
        wins = (
            roll.pivot_table(
                index="window_label",
                columns="config_name",
                values="mar",
                aggfunc="first",
            )
            .dropna(how="any")
        )
    else:
        wins = pd.DataFrame()
    champ_wins = 0
    chal_wins = 0
    if not wins.empty:
        for _, row in wins.iterrows():
            cm = row.get("champion", np.nan)
            ct = row.get("challenger_tuned", np.nan)
            if pd.isna(cm) or pd.isna(ct):
                continue
            if cm > ct:
                champ_wins += 1
            elif ct > cm:
                chal_wins += 1

    # Heuristic: "spirit" of promotion rule
    # - Challenger_tuned should have MAR not dramatically worse (e.g. >= 90% of Champion)
    # - And MDD not worse than Champion by more than ~3–4 ppts, preferably better
    # - And win a decent fraction of rolling windows on MAR
    mar_ok = pd.notna(mar_chal) and pd.notna(mar_champ) and mar_chal >= 0.9 * mar_champ
    mdd_ok = pd.notna(mdd_chal) and pd.notna(mdd_champ) and mdd_chal >= mdd_champ - 0.04
    total_windows = champ_wins + chal_wins
    win_rate = chal_wins / total_windows if total_windows > 0 else 0.0
    wins_ok = win_rate >= 0.55

    satisfies_spirit = mar_ok and mdd_ok and wins_ok

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A Tuned Challenger — Final Decision\n\n")
        f.write("Configs under review:\n\n")
        f.write("- **Champion**: extension_first, 8 positions, risk_per_trade=0.005, max_heat=0.04\n")
        f.write("- **Challenger_tuned**: simple_composite, 12 positions, risk_per_trade=0.004, max_heat=0.04\n\n")

        f.write("## 1. Did the tuned Challenger materially improve risk?\n\n")
        if pd.notna(mdd_chal) and pd.notna(mdd_champ):
            f.write(
                f"- Champion MDD (ref period): {mdd_champ:.2%}\n"
                f"- Challenger_tuned MDD (ref period): {mdd_chal:.2%}\n"
            )
            if mdd_chal > mdd_champ:
                f.write("- **Result:** Tuned Challenger has shallower or similar drawdown (better risk).\n\n")
            else:
                f.write("- **Result:** Tuned Challenger does **not** improve drawdown vs Champion.\n\n")
        else:
            f.write("- **Unknown:** insufficient data to compare MDD robustly.\n\n")

        f.write("## 2. Is it still under watch only, or does it now deserve formal baseline review?\n\n")
        if total_windows > 0:
            f.write(
                f"- Rolling MAR wins — Champion: {champ_wins}, Challenger_tuned: {chal_wins} "
                f"(win rate for Challenger_tuned ≈ {win_rate:.1%}).\n"
            )
        else:
            f.write("- Rolling MAR evidence: not yet available (rolling run incomplete).\n")
        if satisfies_spirit:
            f.write(
                "- **Conclusion:** Tuned Challenger now satisfies the spirit of the promotion rule; "
                "it deserves **formal baseline review** alongside Champion.\n\n"
            )
        else:
            f.write(
                "- **Conclusion:** Tuned Challenger does **not yet** satisfy the spirit of the promotion rule; "
                "it remains **under watch only**.\n\n"
            )

        f.write("## 3. Should Champion remain default?\n\n")
        if satisfies_spirit:
            f.write(
                "- **Recommendation:** Keep Champion as default for now, but schedule a formal baseline review "
                "of Champion vs tuned Challenger before any promotion.\n"
            )
        else:
            f.write(
                "- **Recommendation:** **Keep Champion as default Path A.** Tuned Challenger stays as a monitored "
                "research branch; re-run this validation after more out-of-sample data.\n"
            )


def _run_full_compare(
    symbols: List[str],
    use_cache: bool = True,
) -> pd.DataFrame:
    universe = symbols
    weekly_dfs_full = _load_or_build_weekly_dfs_full(universe, use_cache=use_cache)
    if not weekly_dfs_full:
        print("[tuned_challenger] No weekly data; aborting full_compare.", flush=True)
        return pd.DataFrame()
    eligibility = _get_eligibility(weekly_dfs_full)

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    periods = [
        ("2012-01-01", "2026-02-21", "2012-01-01_to_2026-02-21"),
        ("2022-01-01", "2024-12-31", "2022-01-01_to_2024-12-31"),
        ("2024-01-01", "2026-02-21", "2024-01-01_to_2026-02-21"),
    ]
    rows_full: List[Dict] = []
    for start, end, label in periods:
        for cfg in (CHAMPION, CHALLENGER_TUNED):
            print(f"[tuned_challenger] Full comparison {label} — {cfg.name}", flush=True)
            trades_df, stats = _run_period(weekly_dfs_full, eligibility, cfg, start, end)
            rows_full.append(
                {
                    "period": label,
                    "config_name": cfg.name,
                    "ranking_mode": cfg.ranking_mode,
                    "max_positions": cfg.max_positions,
                    "risk_per_trade": cfg.risk_per_trade,
                    "max_heat": cfg.max_heat,
                    "cagr": stats.get("cagr", np.nan),
                    "mdd": stats.get("mdd", np.nan),
                    "mar": stats.get("mar", np.nan),
                    "n_trades": stats.get("n_trades", len(trades_df)),
                    "trades_per_month": stats.get("trades_per_month", np.nan),
                    "final_equity": stats.get("final_equity", DEFAULT_INITIAL_EQUITY_VND),
                    "avg_heat": stats.get("avg_heat", np.nan),
                    "avg_gross_exposure": stats.get("avg_gross_exposure", np.nan),
                }
            )
    full_df = pd.DataFrame(rows_full)
    full_csv = artifacts_dir / "path_a_champion_vs_tuned_challenger.csv"
    full_md = artifacts_dir / "path_a_champion_vs_tuned_challenger.md"
    full_df.to_csv(full_csv, index=False)
    _write_full_comparison_md(full_df, full_md)

    # Interim decision note (no rolling yet)
    decision_md = artifacts_dir / "path_a_tuned_challenger_decision.md"
    _write_decision_md(full_df, rolling_df=pd.DataFrame(), md_path=decision_md)
    print(f"[tuned_challenger] Wrote {full_csv}, {full_md}, {decision_md}", flush=True)
    return full_df


def _run_rolling(
    symbols: List[str],
    use_cache: bool = True,
) -> pd.DataFrame:
    weekly_dfs_full = _load_or_build_weekly_dfs_full(symbols, use_cache=use_cache)
    if not weekly_dfs_full:
        print("[tuned_challenger] No weekly data; aborting rolling.", flush=True)
        return pd.DataFrame()
    eligibility = _get_eligibility(weekly_dfs_full)

    artifacts_dir = _REPO / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    rolling_csv = artifacts_dir / "path_a_tuned_challenger_rolling_review.csv"

    # Reset rolling CSV for a clean incremental run
    if rolling_csv.exists():
        rolling_csv.unlink()

    windows_6m = _rolling_windows("6m", step_months=3)
    windows_12m = _rolling_windows("12m", step_months=3)
    all_windows = [("6m", s, e, label) for (s, e, label) in windows_6m] + [
        ("12m", s, e, label) for (s, e, label) in windows_12m
    ]

    rows_roll: List[Dict] = []
    for kind, s, e, label in all_windows:
        sliced = _slice_weekly_dfs(weekly_dfs_full, s, e)
        if not sliced:
            continue
        for cfg in (CHAMPION, CHALLENGER_TUNED):
            row = _run_window(sliced, eligibility, cfg, s, e, label)
            rows_roll.append(row)
            # Incremental append
            df_row = pd.DataFrame([row])
            header = not rolling_csv.exists()
            df_row.to_csv(rolling_csv, mode="a", header=header, index=False)

    rolling_df = pd.DataFrame(rows_roll)
    rolling_md = artifacts_dir / "path_a_tuned_challenger_rolling_review.md"
    if not rolling_df.empty:
        _write_rolling_md(rolling_df, rolling_md)
        print(f"[tuned_challenger] Wrote {rolling_csv}, {rolling_md}", flush=True)
    else:
        print("[tuned_challenger] No rolling rows; nothing written.", flush=True)

    # If full_compare already exists, refresh decision note with rolling info
    full_csv = artifacts_dir / "path_a_champion_vs_tuned_challenger.csv"
    if full_csv.exists():
        full_df = pd.read_csv(full_csv)
    else:
        full_df = pd.DataFrame()
    decision_md = artifacts_dir / "path_a_tuned_challenger_decision.md"
    _write_decision_md(full_df, rolling_df, decision_md)
    return rolling_df


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Path A final validation: Champion vs tuned Challenger (phase-based, cache-aware)."
    )
    parser.add_argument(
        "--phase",
        choices=["all", "full_compare", "rolling"],
        default="all",
        help="Which phase to run: full_compare, rolling, or all (default).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable use of cached full weekly data.",
    )
    args = parser.parse_args(argv)

    universe_path = _REPO / "config" / "universe_adv4bn_from_user.txt"
    if not universe_path.exists():
        universe_path = _REPO / "config" / "watchlist.txt"
    symbols = load_universe(universe_path)
    if not symbols:
        print("[tuned_challenger] No symbols; aborting.", flush=True)
        return

    use_cache = not args.no_cache

    full_df: pd.DataFrame | None = None
    if args.phase in ("all", "full_compare"):
        full_df = _run_full_compare(symbols, use_cache=use_cache)

    if args.phase in ("all", "rolling"):
        _run_rolling(symbols, use_cache=use_cache)


if __name__ == "__main__":
    main()

