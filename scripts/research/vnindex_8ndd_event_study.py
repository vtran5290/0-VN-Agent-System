#!/usr/bin/env python3
"""
VNINDEX event study: 8 consecutive non-distribution days (Gil Morales / O'Neil-style).

Data: FireAnt HistoricalQuotes (see src.intake.fireant_historical).
Run from repo root:  python scripts/research/vnindex_8ndd_event_study.py

No look-ahead: dist_day uses t vs t-1 only; MAs are trailing; forward metrics use future rows only.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.intake.fireant_historical import fetch_historical  # noqa: E402


def _valid_volume(x: float | None) -> bool:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return False
    return float(x) > 0.0


def build_frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(r.d),
                "open": r.o,
                "high": r.h,
                "low": r.l,
                "close": r.c,
                "volume": float(r.v) if r.v is not None else np.nan,
            }
            for r in rows
        ]
    )
    df = df.sort_values("date").reset_index(drop=True)
    return df


def add_distribution_day(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["close"].astype(float)
    v = out["volume"].astype(float)
    out["pct_change_close"] = c / c.shift(1) - 1.0

    dist = pd.Series(np.nan, index=out.index, dtype=float)
    for i in range(1, len(out)):
        c0, c1 = c.iloc[i - 1], c.iloc[i]
        v0, v1 = v.iloc[i - 1], v.iloc[i]
        if not (_valid_volume(v0) and _valid_volume(v1)):
            dist.iloc[i] = np.nan
            continue
        if np.isnan(c0) or np.isnan(c1):
            dist.iloc[i] = np.nan
            continue
        down = c1 <= c0 * (1.0 - 0.002)
        vol_up = v1 > v0
        if down and vol_up:
            dist.iloc[i] = 1.0
        else:
            dist.iloc[i] = 0.0
    out["dist_day"] = dist
    return out


def add_mas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["close"]
    out["ma20"] = c.rolling(20, min_periods=20).mean()
    out["ma50"] = c.rolling(50, min_periods=50).mean()
    out["ma200"] = c.rolling(200, min_periods=200).mean()
    return out


def find_events(dist: pd.Series) -> list[tuple[int, int]]:
    """Return list of (event_start_idx, event_date_idx) for non-overlapping 8-day streaks."""
    events: list[tuple[int, int]] = []
    i = 0
    n = len(dist)
    while i <= n - 8:
        w = dist.iloc[i : i + 8]
        if w.isna().any() or (w != 0).any():
            i += 1
            continue
        events.append((i, i + 7))
        i += 8
    return events


def extension_bucket(close: float, ma20: float) -> str | None:
    if np.isnan(close) or np.isnan(ma20) or ma20 <= 0:
        return None
    if close <= 1.03 * ma20:
        return "not_extended"
    if close <= 1.07 * ma20:
        return "moderately_extended"
    return "highly_extended"


def trend_state(close: float, ma50: float) -> str | None:
    if np.isnan(close) or np.isnan(ma50):
        return None
    return "above_ma50" if close > ma50 else "below_ma50"


def c_metric_reliable(dist_fwd: pd.Series) -> bool:
    return dist_fwd.isna().sum() <= 4


def compute_b_strict(close_fwd: np.ndarray, ma50_fwd: np.ndarray) -> bool | None:
    """True if two consecutive closes below MA50 in forward window."""
    ok = ~(np.isnan(close_fwd) | np.isnan(ma50_fwd))
    if ok.sum() < 2:
        return None
    below = close_fwd < ma50_fwd
    below = np.where(ok, below, False)
    for j in range(len(below) - 1):
        if below[j] and below[j + 1]:
            return True
    return False


def summarize_returns(sub: pd.DataFrame, label: str) -> list[dict]:
    rows = []
    for h in (5, 10, 20):
        col = f"ret_{h}d"
        s = sub[col].dropna()
        n = len(s)
        if n == 0:
            rows.append(
                {
                    "group": label,
                    "horizon": f"{h}d",
                    "n": 0,
                    "avg": np.nan,
                    "median": np.nan,
                    "win_rate": np.nan,
                    "avg_mdd": np.nan,
                    "avg_up": np.nan,
                }
            )
            continue
        win = (s > 0).mean()
        rows.append(
            {
                "group": label,
                "horizon": f"{h}d",
                "n": n,
                "avg": s.mean(),
                "median": s.median(),
                "win_rate": win,
                "avg_mdd": sub.loc[s.index, "max_drawdown_20d"].mean(),
                "avg_up": sub.loc[s.index, "max_upside_20d"].mean(),
            }
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="VNINDEX")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument(
        "--out-csv",
        default=str(_REPO / "data" / "research" / "vnindex_8ndd_event_study_events.csv"),
    )
    args = ap.parse_args()

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = fetch_historical(args.symbol, args.start, args.end)
    df = build_frame(rows)
    df = add_distribution_day(df)
    df = add_mas(df)

    events = find_events(df["dist_day"])
    ev_rows: list[dict] = []

    excluded_insufficient = 0

    for start_i, ev_i in events:
        if ev_i + 20 >= len(df):
            excluded_insufficient += 1
            continue

        event_close = float(df.at[ev_i, "close"])
        ma20_e = float(df.at[ev_i, "ma20"])
        ma50_e = float(df.at[ev_i, "ma50"])
        ma200_e = float(df.at[ev_i, "ma200"])

        ts = trend_state(event_close, ma50_e)
        eb = extension_bucket(event_close, ma20_e)

        fwd = slice(ev_i + 1, ev_i + 21)
        lows = df.loc[fwd, "low"].astype(float).values
        highs = df.loc[fwd, "high"].astype(float).values
        closes_f = df.loc[fwd, "close"].astype(float).values
        ma50_f = df.loc[fwd, "ma50"].astype(float).values
        dist_f = df.loc[fwd, "dist_day"]

        min_low = float(np.nanmin(lows))
        max_high = float(np.nanmax(highs))
        max_drawdown_20d = min_low / event_close - 1.0
        max_upside_20d = max_high / event_close - 1.0

        ret_5d = float(df.at[ev_i + 5, "close"] / event_close - 1.0)
        ret_10d = float(df.at[ev_i + 10, "close"] / event_close - 1.0)
        ret_20d = float(df.at[ev_i + 20, "close"] / event_close - 1.0)

        outcome_a = min_low <= event_close * 0.95
        outcome_a_strict = min_low <= event_close * 0.93

        b_ok = np.isfinite(ma50_f) & np.isfinite(closes_f)
        if not b_ok.any():
            outcome_b = None
            outcome_b_strict = None
        else:
            outcome_b = bool(np.any((closes_f < ma50_f) & b_ok))
            outcome_b_strict = compute_b_strict(closes_f, ma50_f)

        if not c_metric_reliable(dist_f):
            outcome_c = None
            outcome_c_strict = None
        else:
            valid = dist_f.notna()
            n_dist = int((dist_f[valid] == 1).sum())
            outcome_c = n_dist >= 4
            outcome_c_strict = n_dist >= 5

        ev_rows.append(
            {
                "event_start": df.at[start_i, "date"],
                "event_date": df.at[ev_i, "date"],
                "event_close": event_close,
                "ma20_event": ma20_e,
                "ma50_event": ma50_e,
                "ma200_event": ma200_e,
                "event_close_vs_ma20": event_close / ma20_e - 1.0 if ma20_e > 0 and np.isfinite(ma20_e) else np.nan,
                "event_close_vs_ma50": event_close / ma50_e - 1.0 if ma50_e > 0 and np.isfinite(ma50_e) else np.nan,
                "event_close_vs_ma200": event_close / ma200_e - 1.0 if ma200_e > 0 and np.isfinite(ma200_e) else np.nan,
                "trend_state": ts,
                "extension_bucket": eb,
                "ret_5d": ret_5d,
                "ret_10d": ret_10d,
                "ret_20d": ret_20d,
                "max_drawdown_20d": max_drawdown_20d,
                "max_upside_20d": max_upside_20d,
                "outcome_A": outcome_a,
                "outcome_B": outcome_b,
                "outcome_C": outcome_c,
                "outcome_A_strict": outcome_a_strict,
                "outcome_B_strict": outcome_b_strict,
                "outcome_C_strict": outcome_c_strict,
            }
        )

    ev = pd.DataFrame(ev_rows)
    ev.to_csv(out_csv, index=False)

    core_cols = [
        "event_start",
        "event_date",
        "event_close",
        "trend_state",
        "extension_bucket",
        "ret_5d",
        "ret_10d",
        "ret_20d",
        "max_drawdown_20d",
        "max_upside_20d",
        "outcome_A",
        "outcome_B",
        "outcome_C",
        "outcome_A_strict",
        "outcome_B_strict",
        "outcome_C_strict",
    ]
    core_path = out_csv.with_name(out_csv.stem + "_core" + out_csv.suffix)
    ev[core_cols].to_csv(core_path, index=False)

    n_raw = len(events)
    n_fwd = len(ev)
    n_c = ev["outcome_C"].notna().sum()
    n_c_den = n_c

    def prob(series: pd.Series) -> tuple[int, int, float]:
        s = series.dropna()
        if len(s) == 0:
            return 0, 0, float("nan")
        return int(s.sum()), len(s), float(s.mean())

    a_sum, a_n, a_p = prob(ev["outcome_A"].astype(float))  # bool
    b_sum, b_n, b_p = prob(ev["outcome_B"].dropna().astype(float))
    c_series = ev["outcome_C"]
    c_valid = c_series.dropna()
    c_sum = int((c_valid.astype(bool)).sum())
    c_p = c_sum / n_c_den if n_c_den else float("nan")

    as_sum, as_n, as_p = prob(ev["outcome_A_strict"].astype(float))
    bs_s = ev["outcome_B_strict"]
    bs_valid = bs_s.notna()
    bs_sum = int(bs_s[bs_valid].astype(bool).sum())
    bs_n = int(bs_valid.sum())
    bs_p = bs_sum / bs_n if bs_n else float("nan")

    cs = ev["outcome_C_strict"]
    cs_valid = cs.notna()
    cs_sum = int(cs[cs_valid].astype(bool).sum())
    cs_n = int(cs_valid.sum())
    cs_p = cs_sum / cs_n if cs_n else float("nan")

    print("=" * 72)
    print("VNINDEX 8-day non-distribution streak — event study")
    print("=" * 72)
    print(f"Data source: FireAnt HistoricalQuotes API (symbol={args.symbol})")
    print(f"Sample: {args.start} .. {args.end} | trading rows={len(df)}")
    print(f"Events (raw 8-day streaks): {n_raw}")
    print(f"Excluded (insufficient forward 20d): {excluded_insufficient}")
    print(f"Events in forward-return sample: {n_fwd}")
    print(f"Events with reliable C-metric (<=4 NA dist in fwd window): {n_c}")
    print(f"Output CSV (full): {out_csv}")
    print(f"Output CSV (core columns): {core_path}")
    print()

    summary = pd.DataFrame(
        [
            {"Definition": "A_price_5pct", "Total_Events": a_n, "Downtrend_Events": a_sum, "Probability": a_p},
            {"Definition": "B_close_below_MA50", "Total_Events": b_n, "Downtrend_Events": b_sum, "Probability": b_p},
            {"Definition": "C_4_distribution_days", "Total_Events": n_c_den, "Downtrend_Events": c_sum, "Probability": c_p},
            {"Definition": "A_strict_7pct", "Total_Events": as_n, "Downtrend_Events": as_sum, "Probability": as_p},
            {"Definition": "B_strict_2day_below_MA50", "Total_Events": bs_n, "Downtrend_Events": bs_sum, "Probability": bs_p},
            {"Definition": "C_strict_5_distribution_days", "Total_Events": cs_n, "Downtrend_Events": cs_sum, "Probability": cs_p},
        ]
    )
    print("1) Main summary table")
    print(summary.to_string(index=False))
    print()

    # Return profile (full 20d sample)
    rp: list[dict] = []
    for h in (5, 10, 20):
        col = f"ret_{h}d"
        s = ev[col]
        rp.append(
            {
                "Horizon": f"{h}d",
                "n": len(s),
                "Avg_Return": s.mean(),
                "Median_Return": s.median(),
                "Win_Rate": (s > 0).mean(),
                "Avg_Max_Drawdown_20d": ev["max_drawdown_20d"].mean(),
                "Avg_Max_Upside_20d": ev["max_upside_20d"].mean(),
            }
        )
    print("2) Return profile (events with full 20d forward data)")
    print(pd.DataFrame(rp).to_string(index=False))
    print()

    def block(name: str, subset: pd.DataFrame) -> None:
        print(f"--- {name} (n={len(subset)}) ---")
        if len(subset) == 0:
            print("(empty)")
            return
        summ = summarize_returns(subset, name)
        print(pd.DataFrame(summ).to_string(index=False))
        a1, n1, p1 = prob(subset["outcome_A"].astype(float))
        _, n2, p2 = prob(subset["outcome_B"].dropna().astype(float))
        csub = subset["outcome_C"]
        c1 = int(csub.dropna().astype(bool).sum())
        cn = int(csub.notna().sum())
        cp = c1 / cn if cn else float("nan")
        print(f"  P(A)={p1:.4f} (n={n1})  P(B)={p2:.4f}  P(C)={cp:.4f} (n_C={cn})")

    print("3) By trend_state")
    for k in ("above_ma50", "below_ma50"):
        block(k, ev[ev["trend_state"] == k])
    print()

    print("4) By extension_bucket")
    for k in ("not_extended", "moderately_extended", "highly_extended"):
        block(k, ev[ev["extension_bucket"] == k])
    print()

    pcts = [10, 25, 50, 75, 90]
    print("6) Percentiles (forward sample)")
    for col in ("ret_20d", "max_drawdown_20d"):
        s = ev[col].dropna()
        qs = np.percentile(s, pcts)
        print(f"  {col}: " + ", ".join(f"p{p}={qs[i]:.6f}" for i, p in enumerate(pcts)))
    print()
    print("Done.")


if __name__ == "__main__":
    main()
