#!/usr/bin/env python3
"""
MA / EMA reaction study on VNINDEX.

For each moving average (SMA + EMA, periods 5/10/20/50/100/150/200):
  - Identifies "support touch" events: price approaches MA from above
  - Measures forward returns at 5d / 10d / 20d after touch
  - Computes: success rate, avg return, avg max drawdown into touch, touch frequency
  - Ranks each MA within each time window

Time windows: 10y, 5y, 2y, 1y, 6m, 3m

Output: data/research/ma_reaction_study.json + console table
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO    = Path(__file__).resolve().parents[1]
VNI_CSV = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT     = REPO / "data/research/ma_reaction_study.json"

PERIODS  = [5, 10, 20, 50, 100, 150, 200]
MA_TYPES = ["SMA", "EMA"]
FWD_DAYS = [5, 10, 20]

# Touch definition: close falls within this band of MA (from above)
TOUCH_TOL   = 0.015   # ±1.5% of MA value = in the zone
# Approach filter: close was above MA by at least this much at some point in lookback
APPROACH_LB = 5       # look back N bars to confirm price was above MA before

# Time windows: (label, approx trading days)
WINDOWS = [
    ("10y", 2520),
    ("5y",  1260),
    ("2y",   504),
    ("1y",   252),
    ("6m",   126),
    ("3m",    63),
]


def load_vnindex() -> pd.DataFrame:
    df = pd.read_csv(VNI_CSV, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[["date", "open", "high", "low", "close"]].dropna()
    return df


def compute_mas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for p in PERIODS:
        out[f"SMA{p}"] = df["close"].rolling(p).mean()
        out[f"EMA{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return out


def find_touch_events(df: pd.DataFrame, ma_col: str) -> pd.DataFrame:
    """
    A touch event = first day after approaching from above where close
    comes within TOUCH_TOL of the MA.

    Approach from above:
      - In the prior APPROACH_LB bars, close was above MA*(1+TOUCH_TOL)
        at least once (confirms it came from above, not just hugging MA)
      - Current close <= MA * (1 + TOUCH_TOL)  [entered the zone]

    De-duplicate: only count a new event after price leaves zone for >= 3 bars.
    """
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
        # Must be in zone now
        if not in_zone[i]:
            continue
        # Must have been clearly above the zone in recent lookback
        was_above = any(above_zone[max(0, i - APPROACH_LB): i])
        if not was_above:
            continue
        # De-dup: at least 3 bars out of zone since last event
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
        pct_gap     = (touch_close - touch_ma) / touch_ma * 100

        fwd = {}
        for fd in FWD_DAYS:
            end = idx + fd
            if end < n:
                ret = (closes[end] - touch_close) / touch_close * 100
                # max drawdown from touch to end window
                mdd = (closes[idx:end+1].min() - touch_close) / touch_close * 100
            else:
                ret = np.nan
                mdd = np.nan
            fwd[f"ret{fd}d"]  = round(ret, 3)  if not np.isnan(ret) else None
            fwd[f"mdd{fd}d"]  = round(mdd, 3)  if not np.isnan(mdd) else None

        rows.append({
            "date":       str(df["date"].iloc[idx].date()),
            "close":      round(float(touch_close), 2),
            "ma_val":     round(float(touch_ma), 2),
            "pct_gap":    round(pct_gap, 2),
            **fwd,
        })

    return pd.DataFrame(rows)


def score_events(events: pd.DataFrame) -> dict:
    if events.empty:
        return {}
    result = {}
    for fd in FWD_DAYS:
        col = f"ret{fd}d"
        mdd_col = f"mdd{fd}d"
        rets = events[col].dropna()
        mdds = events[mdd_col].dropna()
        if len(rets) == 0:
            continue
        result[f"n_events_{fd}d"]      = int(len(rets))
        result[f"success_rate_{fd}d"]  = round((rets > 0).mean() * 100, 1)
        result[f"avg_ret_{fd}d"]       = round(rets.mean(), 2)
        result[f"med_ret_{fd}d"]       = round(rets.median(), 2)
        result[f"avg_mdd_{fd}d"]       = round(mdds.mean(), 2)
        result[f"pct_ret_gt2_{fd}d"]   = round((rets > 2.0).mean() * 100, 1)
        result[f"pct_ret_gt5_{fd}d"]   = round((rets > 5.0).mean() * 100, 1)
    return result


def compute_composite_score(stats: dict, fd: int = 10) -> float:
    """Composite score for ranking: weighted success rate + avg return + consistency."""
    sr = stats.get(f"success_rate_{fd}d", 0)
    ar = stats.get(f"avg_ret_{fd}d", 0)
    p2 = stats.get(f"pct_ret_gt2_{fd}d", 0)
    mdd = abs(stats.get(f"avg_mdd_{fd}d", 0))
    n  = stats.get(f"n_events_{fd}d", 0)
    if n < 3:
        return -999.0
    # Higher success rate + avg return + reliability; penalise deep avg drawdown
    return round(0.4 * sr + 0.3 * ar + 0.2 * p2 - 0.1 * mdd, 3)


def main() -> None:
    df = load_vnindex()
    df = compute_mas(df)
    df = df.reset_index(drop=True)
    end_date = df["date"].iloc[-1]
    print(f"VNINDEX loaded: {df['date'].iloc[0].date()} -> {end_date.date()} ({len(df)} bars)")

    output = {
        "asof_date":  str(end_date.date()),
        "data_source": str(VNI_CSV.relative_to(REPO)),
        "method": (
            "Support touch = close enters ±1.5% band around MA from above. "
            "De-duped: new event only after 3+ bars outside zone. "
            "Composite score = 0.4×success_rate_10d + 0.3×avg_ret_10d + "
            "0.2×pct_ret_gt2_10d − 0.1×avg_mdd_10d (min 3 events required)."
        ),
        "windows": {},
    }

    # Per window analysis
    for win_label, win_bars in WINDOWS:
        # Subset data for this window
        start_idx = max(0, len(df) - win_bars)
        # But we need full history to compute MAs correctly — use full df for MA,
        # then slice events to the window
        win_start_date = df["date"].iloc[start_idx]

        ma_results = []
        for ma_type in MA_TYPES:
            for period in PERIODS:
                ma_col = f"{ma_type}{period}"
                # Get touch events in the full series, then filter to window
                events = find_touch_events(df, ma_col)
                if not events.empty:
                    events["date_dt"] = pd.to_datetime(events["date"])
                    events = events[events["date_dt"] >= win_start_date].copy()
                    events = events.drop(columns=["date_dt"])

                stats = score_events(events)
                score = compute_composite_score(stats)

                row = {
                    "ma":     f"{ma_type}{period}",
                    "type":   ma_type,
                    "period": period,
                    "score":  score,
                    **stats,
                }
                ma_results.append(row)

        # Sort by composite score descending
        ma_results.sort(key=lambda x: x["score"], reverse=True)

        output["windows"][win_label] = {
            "window_bars":   win_bars,
            "window_start":  str(win_start_date.date()),
            "window_end":    str(end_date.date()),
            "rankings":      ma_results,
        }

        # Print compact table
        print(f"\n{'='*70}")
        print(f"  {win_label.upper()} window: {win_start_date.date()} -> {end_date.date()}")
        print(f"{'='*70}")
        print(f"  {'MA':<10} {'Score':>7} {'N':>4} {'SR%':>6} {'Avg10d':>7} {'Med10d':>7} {'GT2%':>6} {'GT5%':>6} {'AvgMDD':>7}")
        print(f"  {'-'*70}")
        for r in ma_results[:10]:
            n   = r.get("n_events_10d", 0)
            sr  = r.get("success_rate_10d", 0)
            ar  = r.get("avg_ret_10d", 0)
            med = r.get("med_ret_10d", 0)
            gt2 = r.get("pct_ret_gt2_10d", 0)
            gt5 = r.get("pct_ret_gt5_10d", 0)
            mdd = r.get("avg_mdd_10d", 0)
            print(f"  {r['ma']:<10} {r['score']:>7.2f} {n:>4}  {sr:>5.1f}%  {ar:>+6.2f}%  {med:>+6.2f}%  {gt2:>5.1f}%  {gt5:>5.1f}%  {mdd:>+6.2f}%")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten: {OUT}")

    # Final cross-window summary: rank by average score across all windows
    print(f"\n{'='*70}")
    print("  CROSS-WINDOW COMPOSITE (avg score across all 6 windows)")
    print(f"{'='*70}")
    cross: dict[str, list[float]] = {}
    for win_data in output["windows"].values():
        for r in win_data["rankings"]:
            ma = r["ma"]
            if r["score"] > -900:
                cross.setdefault(ma, []).append(r["score"])
    cross_avg = {ma: round(np.mean(scores), 3) for ma, scores in cross.items() if len(scores) >= 3}
    for ma, avg in sorted(cross_avg.items(), key=lambda x: -x[1]):
        print(f"  {ma:<10}  avg_score={avg:>7.3f}  (across {len(cross[ma])} windows)")

    output["cross_window_avg_score"] = cross_avg
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
