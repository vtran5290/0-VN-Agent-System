#!/usr/bin/env python3
"""
MA / EMA reaction study across liquid + institutional-favorite universe.

Aggregates touch events across all symbols for each MA/window.
Reports: aggregate score, per-symbol best MA, cross-window ranking.

Same methodology as run_ma_reaction_study.py (VNINDEX single-index).
Output: data/research/ma_reaction_stocks.json

Universe: current IA Tier 2-3 liquid names (as of 2026-05-27).
Update SYMBOLS when IA panel is re-scored.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO      = Path(__file__).resolve().parents[1]
OHLCV_PATH = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
OUT        = REPO / "data/research/ma_reaction_stocks.json"

# IA Tier 2-3 liquid names — 2026-05-27 scan
# Tier 2: MSB(62.6), VPL(61.2), TVN(58.4)
# Tier 3: HHP(57.2), SSB(51.9), NAF(51.1), DL1(50.1), PDR(47.7), C69(47.7),
#          QNS(47.7), LPB(47.1), VPI(47.1), PSI(46.7), APS(46.0), DXS(45.9),
#          VND(45.9), PET(45.8), TLD(45.4), VCB(45.0), IDJ(43.5), DCL(43.5),
#          HII(42.8), VC3(42.4), OCB(42.4), PCH(42.3), CDC(42.3), POM(42.2)
SYMBOLS = [
    # Tier 2
    "MSB", "VPL", "TVN",
    # Tier 3
    "HHP", "SSB", "NAF", "DL1", "PDR", "C69", "QNS", "LPB", "VPI", "PSI", "APS",
    "DXS", "VND", "PET", "TLD", "VCB", "IDJ", "DCL", "HII", "VC3", "OCB", "PCH", "CDC", "POM",
]

PERIODS   = [5, 10, 20, 50, 100, 150, 200]
MA_TYPES  = ["SMA", "EMA"]
FWD_DAYS  = [5, 10, 20]

TOUCH_TOL   = 0.015
APPROACH_LB = 5

WINDOWS = [
    ("10y", 2520),
    ("5y",  1260),
    ("2y",   504),
    ("1y",   252),
    ("6m",   126),
    ("3m",    63),
]


def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for p in PERIODS:
        out[f"SMA{p}"] = df["close"].rolling(p).mean()
        out[f"EMA{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return out


def find_touch_events(df: pd.DataFrame, ma_col: str) -> pd.DataFrame:
    closes = df["close"].values
    ma     = df[ma_col].values
    n      = len(df)

    in_zone    = np.abs(closes - ma) / ma <= TOUCH_TOL
    above_zone = closes > ma * (1 + TOUCH_TOL)

    events = []
    last_event_idx = -10

    for i in range(APPROACH_LB, n):
        if pd.isna(ma[i]):
            continue
        if not in_zone[i]:
            continue
        was_above = any(above_zone[max(0, i - APPROACH_LB): i])
        if not was_above:
            continue
        if i - last_event_idx < 3:
            continue
        events.append(i)
        last_event_idx = i

    if not events:
        return pd.DataFrame()

    rows = []
    for idx in events:
        touch_close = closes[idx]
        touch_ma    = ma[idx]
        fwd = {}
        for fd in FWD_DAYS:
            end = idx + fd
            if end < n:
                ret = (closes[end] - touch_close) / touch_close * 100
                mdd = (closes[idx:end+1].min() - touch_close) / touch_close * 100
            else:
                ret, mdd = np.nan, np.nan
            fwd[f"ret{fd}d"]  = None if np.isnan(ret)  else round(float(ret), 3)
            fwd[f"mdd{fd}d"]  = None if np.isnan(mdd)  else round(float(mdd), 3)
        rows.append({"date": str(df["date"].iloc[idx].date()), **fwd})
    return pd.DataFrame(rows)


def score_events(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    result = {}
    for fd in FWD_DAYS:
        col, mdd_col = f"ret{fd}d", f"mdd{fd}d"
        rets = events[col].dropna()
        mdds = events[mdd_col].dropna()
        if len(rets) == 0:
            continue
        result[f"n_{fd}d"]     = int(len(rets))
        result[f"sr_{fd}d"]    = round((rets > 0).mean() * 100, 1)
        result[f"avg_{fd}d"]   = round(rets.mean(), 2)
        result[f"med_{fd}d"]   = round(rets.median(), 2)
        result[f"mdd_{fd}d"]   = round(mdds.mean(), 2)
        result[f"gt2_{fd}d"]   = round((rets > 2.0).mean() * 100, 1)
        result[f"gt5_{fd}d"]   = round((rets > 5.0).mean() * 100, 1)
    return result


def composite_score(stats: dict, fd: int = 10) -> float:
    sr  = stats.get(f"sr_{fd}d",  0)
    ar  = stats.get(f"avg_{fd}d", 0)
    p2  = stats.get(f"gt2_{fd}d", 0)
    mdd = abs(stats.get(f"mdd_{fd}d", 0))
    n   = stats.get(f"n_{fd}d",   0)
    if n < 5:
        return -999.0
    return round(0.4 * sr + 0.3 * ar + 0.2 * p2 - 0.1 * mdd, 3)


def main() -> None:
    print("Loading OHLCV...")
    raw = pd.read_parquet(OHLCV_PATH)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw[raw["symbol"].isin(SYMBOLS)].copy()

    end_date = raw["date"].max()
    print(f"Data end: {end_date.date()} | symbols: {raw['symbol'].nunique()}")

    # Precompute MAs per symbol (full history for correctness)
    sym_dfs: dict[str, pd.DataFrame] = {}
    for sym, grp in raw.groupby("symbol"):
        g = grp.sort_values("date").reset_index(drop=True)
        sym_dfs[sym] = compute_mas(g)

    output: dict = {
        "asof_date": str(end_date.date()),
        "universe": SYMBOLS,
        "windows": {},
    }

    for win_label, win_bars in WINDOWS:
        start_idx_global = max(0, len(raw["date"].unique()) - win_bars)
        all_dates = sorted(raw["date"].unique())
        win_start_date = all_dates[max(0, len(all_dates) - win_bars)]

        # Aggregate events across all symbols for each MA
        ma_events: dict[str, list[dict]] = defaultdict(list)
        sym_coverage: dict[str, list[str]] = defaultdict(list)  # ma -> [symbols with events]

        for sym, df in sym_dfs.items():
            # Check if symbol has sufficient data in this window
            sym_in_window = df[df["date"] >= pd.Timestamp(win_start_date)]
            if len(sym_in_window) < 20:
                continue
            for ma_type in MA_TYPES:
                for period in PERIODS:
                    ma_col = f"{ma_type}{period}"
                    events = find_touch_events(df, ma_col)
                    if events.empty:
                        continue
                    events["date_dt"] = pd.to_datetime(events["date"])
                    win_events = events[events["date_dt"] >= pd.Timestamp(win_start_date)].copy()
                    win_events = win_events.drop(columns=["date_dt"])
                    if len(win_events) == 0:
                        continue
                    win_events["symbol"] = sym
                    ma_key = f"{ma_type}{period}"
                    ma_events[ma_key].append(win_events)
                    sym_coverage[ma_key].append(sym)

        # Score each MA
        ma_results = []
        for ma_type in MA_TYPES:
            for period in PERIODS:
                ma_key = f"{ma_type}{period}"
                parts = ma_events.get(ma_key, [])
                if not parts:
                    continue
                combined = pd.concat(parts, ignore_index=True)
                stats = score_events(combined)
                score = composite_score(stats)
                syms_covered = sorted(set(sym_coverage[ma_key]))
                ma_results.append({
                    "ma":           ma_key,
                    "type":         ma_type,
                    "period":       period,
                    "score":        score,
                    "n_symbols":    len(syms_covered),
                    "symbols":      syms_covered,
                    **stats,
                })

        ma_results.sort(key=lambda x: x["score"], reverse=True)

        output["windows"][win_label] = {
            "window_start":  str(pd.Timestamp(win_start_date).date()),
            "window_end":    str(end_date.date()),
            "rankings":      ma_results,
        }

        print(f"\n{'='*72}")
        print(f"  {win_label.upper()}  ({pd.Timestamp(win_start_date).date()} -> {end_date.date()})")
        print(f"{'='*72}")
        print(f"  {'MA':<10} {'Score':>7} {'N_ev':>5} {'N_sym':>6}  {'SR%':>6} {'Avg10d':>7} {'Med10d':>7} {'GT2%':>6} {'GT5%':>6} {'MDD':>7}")
        print(f"  {'-'*72}")
        for r in ma_results[:10]:
            n   = r.get("n_10d",  0)
            sr  = r.get("sr_10d", 0)
            ar  = r.get("avg_10d",0)
            med = r.get("med_10d",0)
            gt2 = r.get("gt2_10d",0)
            gt5 = r.get("gt5_10d",0)
            mdd = r.get("mdd_10d",0)
            ns  = r.get("n_symbols", 0)
            print(f"  {r['ma']:<10} {r['score']:>7.2f} {n:>5}  {ns:>5}   {sr:>5.1f}%  {ar:>+6.2f}%  {med:>+6.2f}%  {gt2:>5.1f}%  {gt5:>5.1f}%  {mdd:>+6.2f}%")

    # ── Per-symbol best MA (across 5d/10d/20d, using 2y window as anchor) ──
    print(f"\n{'='*72}")
    print("  PER-SYMBOL BEST MA (2y window, 10d forward, min 3 events)")
    print(f"{'='*72}")

    sym_best: dict[str, dict] = {}
    win_start_2y_date = sorted(raw["date"].unique())[max(0, len(raw["date"].unique()) - 504)]

    for sym, df in sym_dfs.items():
        best_score, best_ma = -999.0, None
        for ma_type in MA_TYPES:
            for period in PERIODS:
                ma_col = f"{ma_type}{period}"
                events = find_touch_events(df, ma_col)
                if events.empty:
                    continue
                events["date_dt"] = pd.to_datetime(events["date"])
                we = events[events["date_dt"] >= pd.Timestamp(win_start_2y_date)].drop(columns=["date_dt"])
                if len(we) < 3:
                    continue
                stats = score_events(we)
                s = composite_score(stats)
                if s > best_score:
                    best_score = s
                    best_ma    = f"{ma_type}{period}"
                    best_stats = stats
        if best_ma:
            sym_best[sym] = {
                "best_ma": best_ma,
                "score":   best_score,
                "n_events": best_stats.get("n_10d", 0),
                "sr_10d":   best_stats.get("sr_10d", 0),
                "avg_10d":  best_stats.get("avg_10d", 0),
            }
            print(f"  {sym:<6}  best={best_ma:<8}  score={best_score:>6.2f}  "
                  f"n={best_stats.get('n_10d',0):>3}  SR={best_stats.get('sr_10d',0):>5.1f}%  "
                  f"avg10d={best_stats.get('avg_10d',0):>+5.2f}%")

    output["per_symbol_best_2y"] = sym_best

    # ── Cross-window composite ──────────────────────────────────────────────
    cross: dict[str, list[float]] = defaultdict(list)
    for win_data in output["windows"].values():
        for r in win_data["rankings"]:
            if r["score"] > -900:
                cross[r["ma"]].append(r["score"])

    cross_avg = {ma: round(float(np.mean(s)), 3)
                 for ma, s in cross.items() if len(s) >= 3}
    output["cross_window_avg_score"] = cross_avg

    print(f"\n{'='*72}")
    print("  CROSS-WINDOW COMPOSITE (avg score, min 3 windows)")
    print(f"{'='*72}")
    for ma, avg in sorted(cross_avg.items(), key=lambda x: -x[1]):
        wins = len(cross[ma])
        print(f"  {ma:<10}  avg_score={avg:>7.3f}  ({wins} windows)")

    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten: {OUT}")


if __name__ == "__main__":
    main()
