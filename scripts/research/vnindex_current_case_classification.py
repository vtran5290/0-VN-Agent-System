#!/usr/bin/env python3
"""
Classify current VNINDEX context vs 8-day non-distribution framework (Cases 1–3).

Data: FireAnt HistoricalQuotes (src.intake.fireant_historical).
Run: python scripts/research/vnindex_current_case_classification.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import importlib.util

from src.intake.fireant_historical import fetch_historical  # noqa: E402

LONG_RET_HORIZONS = (30, 50, 100, 150, 200, 250)

_STUDY = _REPO / "scripts" / "research" / "vnindex_8ndd_event_study.py"
_spec = importlib.util.spec_from_file_location("vnindex_8ndd_event_study", _STUDY)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
add_distribution_day = _mod.add_distribution_day
add_mas = _mod.add_mas
build_frame = _mod.build_frame
find_events = _mod.find_events


def find_most_recent_8nd_streak_end(dist: pd.Series) -> int | None:
    """Largest index i such that dist[i-7:i+1] are all 0 and valid (8-day ND streak ending day i)."""
    n = len(dist)
    last: int | None = None
    for i in range(n - 1, 6, -1):
        w = dist.iloc[i - 7 : i + 1]
        if w.isna().any() or (w != 0).any():
            continue
        last = i
        break
    return last


def current_nd_run_length(dist: pd.Series) -> int:
    """Consecutive non-distribution days ending at last bar (0 if last is dist or NA)."""
    n = len(dist)
    run = 0
    for i in range(n - 1, -1, -1):
        v = dist.iloc[i]
        if pd.isna(v) or v != 0:
            break
        run += 1
    return run


def ma_slope_pct(series: pd.Series, bars: int) -> float:
    if len(series) < bars or pd.isna(series.iloc[-1]) or pd.isna(series.iloc[-bars]):
        return float("nan")
    a, b = float(series.iloc[-bars]), float(series.iloc[-1])
    if abs(a) < 1e-12:
        return float("nan")
    return (b - a) / abs(a)


def dist_count(dist: pd.Series, start: int, end_excl: int) -> int:
    sl = dist.iloc[start:end_excl]
    sl = sl[sl.notna()]
    return int((sl == 1).sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="VNINDEX")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument(
        "--out-json",
        default=str(_REPO / "data" / "research" / "vnindex_current_case_classification.json"),
    )
    args = ap.parse_args()

    rows = fetch_historical(args.symbol, args.start, args.end)
    df = build_frame(rows)
    df = add_distribution_day(df)
    df = add_mas(df)
    n = len(df)
    last_i = n - 1
    dlast = df.iloc[last_i]

    # --- Step 1: last 8 days streak? ---
    last8 = df.iloc[last_i - 7 : last_i + 1]
    last8_ok = last8["dist_day"].notna().all() and (last8["dist_day"] == 0).all()
    streak_start = last8["date"].iloc[0] if last8_ok else None
    streak_end = last8["date"].iloc[-1] if last8_ok else None
    nd_run = current_nd_run_length(df["dist_day"])

    close = float(dlast["close"])
    ma20 = float(dlast["ma20"]) if pd.notna(dlast["ma20"]) else float("nan")
    ma50 = float(dlast["ma50"]) if pd.notna(dlast["ma50"]) else float("nan")
    ma200 = float(dlast["ma200"]) if pd.notna(dlast["ma200"]) else float("nan")

    def pct_vs(ma: float) -> float:
        if not np.isfinite(ma) or ma <= 0:
            return float("nan")
        return close / ma - 1.0

    hi20 = df["high"].iloc[last_i - 19 : last_i + 1].max()
    lo20 = df["low"].iloc[last_i - 19 : last_i + 1].min()
    dist_hi20 = close / float(hi20) - 1.0 if hi20 else float("nan")
    dist_lo20 = close / float(lo20) - 1.0 if lo20 else float("nan")

    slope_ma20_5 = ma_slope_pct(df["ma20"], 5)
    slope_ma50_10 = ma_slope_pct(df["ma50"], 10)

    # --- Step 2: post-streak ---
    streak_end_i = find_most_recent_8nd_streak_end(df["dist_day"])
    post: dict = {
        "streak_end_index": streak_end_i,
        "streak_end_date": str(df.at[streak_end_i, "date"]) if streak_end_i is not None else None,
    }

    if streak_end_i is None:
        post["note"] = "No 8-day ND streak found in history."
        d5 = d10 = None
        broke_ma20 = broke_ma50 = broke_swing = None
        n_after = 0
    else:
        n_after = last_i - streak_end_i
        post["trading_days_after_streak_end"] = n_after
        if n_after <= 0:
            post["dist_days_next_5"] = 0
            post["dist_days_next_10"] = 0
            post["broke_below_ma20"] = None
            post["broke_below_ma50"] = None
            post["broke_below_prior10_low_close"] = None
            post["note"] = "Streak ends on latest bar; no completed days after streak in sample."
            d5 = d10 = 0
            broke_ma20 = broke_ma50 = broke_swing = False
        else:
            e = streak_end_i
            d5 = dist_count(df["dist_day"], e + 1, min(e + 6, last_i + 1))
            d10 = dist_count(df["dist_day"], e + 1, min(e + 11, last_i + 1))
            post["dist_days_next_5"] = d5
            post["dist_days_next_10"] = d10

            fwd = df.iloc[e + 1 : last_i + 1]
            post["broke_below_ma20"] = bool((fwd["close"] < fwd["ma20"]).any())
            post["broke_below_ma50"] = bool((fwd["close"] < fwd["ma50"]).any())

            ss = e - 7  # streak start index
            prior_lo = (
                float(df.loc[ss - 10 : ss - 1, "close"].min())
                if ss >= 10
                else float("nan")
            )
            if np.isfinite(prior_lo) and len(fwd):
                post["broke_below_prior10_low_close"] = bool((fwd["close"] < prior_lo).any())
                post["prior10_low_close"] = prior_lo
            else:
                post["broke_below_prior10_low_close"] = None
                post["prior10_low_close"] = prior_lo
            broke_ma20 = post["broke_below_ma20"]
            broke_ma50 = post["broke_below_ma50"]
            broke_swing = post["broke_below_prior10_low_close"]

    # Breadth: optional multi-index fetch
    breadth_note = "No breadth proxy fetched in this script (optional enhancement: VN30/HNX/UPCOM)."
    post["breadth"] = breadth_note

    # --- Step 3: Case rules ---
    above50 = np.isfinite(ma50) and close > ma50
    ma50_rising = np.isfinite(slope_ma50_10) and slope_ma50_10 > 0.0003
    ma50_flatish = np.isfinite(slope_ma50_10) and slope_ma50_10 >= -0.001

    cluster_supply = False
    if n_after > 0 and d10 is not None and d10 >= 3:
        cluster_supply = True
    if n_after > 0 and d5 is not None and d5 >= 2:
        cluster_supply = True

    meaningful_post = False
    if n_after > 0:
        meaningful_post = bool(
            (d10 or 0) >= 2
            or (broke_ma20 and broke_ma20 is not None)
            or (broke_ma50 and broke_ma50 is not None)
            or (broke_swing and broke_swing is not None)
        )

    # Case 3 signals (only when we have post-streak days)
    case3_signals = 0
    if n_after > 0:
        if cluster_supply:
            case3_signals += 1
        if broke_ma20:
            case3_signals += 1
        if broke_ma50:
            case3_signals += 1
        if broke_swing:
            case3_signals += 1

    case3_ok = n_after > 0 and (
        case3_signals >= 2 or (d10 or 0) >= 3 or (broke_ma50 is True) or (broke_ma20 is True)
    )

    case1_ok = (
        above50
        and (ma50_rising or ma50_flatish)
        and not cluster_supply
        and (n_after == 0 or not meaningful_post)
        and not case3_ok
    )

    if case3_ok:
        case_pick = 3
        conf = "high" if case3_signals >= 2 else "medium"
    elif case1_ok:
        case_pick = 1
        conf = "medium" if n_after == 0 else "high"
    else:
        case_pick = 2
        conf = "high" if not above50 else "medium"

    # --- Step 4: Historical analogs ---
    events = find_events(df["dist_day"])
    feats: list[dict] = []
    for start_i, ev_i in events:
        if ev_i + 20 >= n:
            continue
        row = df.iloc[ev_i]
        c_ = float(row["close"])
        m20 = float(row["ma20"])
        m50 = float(row["ma50"])
        if not (np.isfinite(m50) and m50 > 0 and np.isfinite(m20) and m20 > 0):
            continue
        vs50 = c_ / m50 - 1.0
        vs20 = c_ / m20 - 1.0
        s50 = ma_slope_pct(df["ma50"].iloc[: ev_i + 1], 10)
        if not np.isfinite(s50):
            s50 = 0.0
        ab = 1.0 if c_ > m50 else 0.0
        d5h = dist_count(df["dist_day"], ev_i + 1, ev_i + 6)
        d10h = dist_count(df["dist_day"], ev_i + 1, ev_i + 11)
        ret5 = float(df.at[ev_i + 5, "close"] / c_ - 1.0)
        ret10 = float(df.at[ev_i + 10, "close"] / c_ - 1.0)
        ret20 = float(df.at[ev_i + 20, "close"] / c_ - 1.0)
        long_rets: dict[str, float | None] = {}
        for hh in LONG_RET_HORIZONS:
            key = f"ret_{hh}d"
            if ev_i + hh < n:
                long_rets[key] = float(df.at[ev_i + hh, "close"] / c_ - 1.0)
            else:
                long_rets[key] = None
        det = d10h >= 2 or d5h >= 2
        if vs50 > 0 and not det and d10h < 2:
            hist_case = 1
        elif vs50 <= 0:
            hist_case = 2
        else:
            hist_case = 3

        feats.append(
            {
                "event_date": str(row["date"]),
                "vs50": vs50,
                "vs20": vs20,
                "s50": s50,
                "above50": ab,
                "d5": d5h,
                "d10": d10h,
                "ret5": ret5,
                "ret10": ret10,
                "ret20": ret20,
                **long_rets,
                "hist_case": hist_case,
            }
        )

    # Current feature vector (at last bar)
    s50_cur = ma_slope_pct(df["ma50"], 10)
    if not np.isfinite(s50_cur):
        s50_cur = 0.0
    vs50_cur = pct_vs(ma50)
    vs20_cur = pct_vs(ma20)
    ab_cur = 1.0 if above50 else 0.0
    d5_cur = float(d5) if d5 is not None else float("nan")
    d10_cur = float(d10) if d10 is not None else float("nan")

    def dist2(a: dict) -> float:
        # Scale-normalized Euclidean; deterioration dims down-weighted if NaN
        dv = (a["vs50"] - vs50_cur) ** 2 + (a["vs20"] - vs20_cur) ** 2
        dv += (a["s50"] - s50_cur) ** 2 * 4.0
        dv += (a["above50"] - ab_cur) ** 2
        if np.isfinite(d5_cur) and np.isfinite(d10_cur):
            dv += 0.15 * (a["d5"] - d5_cur) ** 2 + 0.1 * (a["d10"] - d10_cur) ** 2
        return dv

    for f in feats:
        f["similarity_dist"] = dist2(f)
    feats.sort(key=lambda x: x["similarity_dist"])
    top10 = feats[:10]

    out = {
        "asof_date": str(dlast["date"]),
        "data_end": args.end,
        "last_bar": {
            "close": close,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "close_vs_ma20_pct": vs20_cur,
            "close_vs_ma50_pct": vs50_cur,
            "close_vs_ma200_pct": pct_vs(ma200),
            "ma20_slope_5d_pct": slope_ma20_5,
            "ma50_slope_10d_pct": slope_ma50_10,
            "dist_from_20d_high_pct": dist_hi20,
            "dist_from_20d_low_pct": dist_lo20,
        },
        "streak": {
            "last_8_days_all_non_distribution": last8_ok,
            "streak_start_date": str(streak_start) if streak_start is not None else None,
            "streak_end_date": str(streak_end) if streak_end is not None else None,
            "current_non_distribution_run_length": nd_run,
        },
        "post_streak": post,
        "classification": {
            "case": case_pick,
            "confidence": conf,
            "rules": {
                "above_ma50": above50,
                "ma50_slope_10_pct": slope_ma50_10,
                "cluster_supply_heuristic": cluster_supply,
                "case3_signal_count": case3_signals,
            },
        },
        "historical_top10": top10,
    }

    def _jsonify(x):
        if isinstance(x, dict):
            return {k: _jsonify(v) for k, v in x.items()}
        if isinstance(x, list):
            return [_jsonify(v) for v in x]
        if isinstance(x, (np.floating, np.integer)):
            return float(x)
        if isinstance(x, (bool, np.bool_)):
            return bool(x)
        return x

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(_jsonify(out), indent=2), encoding="utf-8")

    # --- Layman print ---
    print("VNINDEX - current context (8-day non-distribution framework)")
    print("Data source: FireAnt HistoricalQuotes | symbol:", args.symbol)
    print("As of last trading day in sample:", dlast["date"])
    print()
    print("1) CURRENT FACTS")
    print(
        "   Price vs MA50:",
        "above" if above50 else "below",
        f"({vs50_cur*100:.2f}% vs MA50)" if np.isfinite(vs50_cur) else "",
    )
    print(
        "   Last 8 completed sessions all 'non-distribution':",
        "yes" if last8_ok else "no",
    )
    if last8_ok:
        print(f"   Streak window: {streak_start} -> {streak_end}")
    else:
        print(f"   Current run of non-distribution days (ending last bar): {nd_run}")
    print(
        "   Trend (MA50 slope ~10 sessions):",
        "rising" if (slope_ma50_10 or 0) > 0.0005 else ("flat" if (slope_ma50_10 or 0) > -0.001 else "falling"),
    )
    if n_after <= 0 and last8_ok:
        print("   Distribution days after streak: none yet (streak ends on latest bar).")
    elif d10 is not None:
        print(f"   Distribution days in first 5/10 sessions after last streak end: {d5}/{d10}")
    print()
    print("2) CASE:", case_pick, "| confidence:", conf)
    print()
    print("3) WHY (plain English)")
    if not above50:
        print("   - Price is below the 50-day average, so the main trend is still not healthy.")
    if last8_ok and n_after <= 0:
        print(
            "   - There is a clean 8-day streak, but we have no trading days after it yet to judge renewed selling pressure."
        )
    if cluster_supply and n_after > 0:
        print("   - Several distribution-style days showed up soon after the streak ended.")
    if case_pick == 3:
        print("   - This looks more like supply coming back than a stable uptrend.")
    elif case_pick == 1:
        print("   - Price holds above MA50 and the setup has not shown quick post-streak damage.")
    else:
        print("   - The market is not clearly strong; the streak alone does not prove a new bull leg.")
    print()
    print("4) HISTORICAL ANALOGS (10 most similar past streak-end setups)")
    for i, h in enumerate(top10, 1):
        long_parts = []
        for hh in LONG_RET_HORIZONS:
            k = f"ret_{hh}d"
            v = h.get(k)
            if v is None:
                long_parts.append(f"{hh}d:n/a")
            else:
                long_parts.append(f"{hh}d:{v*100:+.1f}%")
        long_str = " | ".join(long_parts)
        print(
            f"   {i}. {h['event_date']} | 5/10/20d: {h['ret5']*100:+.2f}% / {h['ret10']*100:+.2f}% / {h['ret20']*100:+.2f}% | long: {long_str} | case~ {h['hist_case']}"
        )
    avg20 = np.mean([h["ret20"] for h in top10])
    print(f"   Average 20d return of these 10: {avg20*100:.2f}%")
    for hh in LONG_RET_HORIZONS:
        k = f"ret_{hh}d"
        vals = [h[k] for h in top10 if h.get(k) is not None]
        if not vals:
            print(f"   Average {hh}d return: n/a (insufficient history for all top-10)")
        else:
            print(
                f"   Average {hh}d return (n={len(vals)}/{len(top10)}): {float(np.mean(vals))*100:.2f}%"
            )
    print()
    print("5) PRACTICAL TAKEAWAY")
    if case_pick == 1:
        print("   healthy enough to hold (with normal risk rules)")
    elif case_pick == 3:
        print("   warning: supply is returning - treat as caution")
    else:
        print("   not strong enough to buy aggressively - wait for better trend proof")
    print()
    print("JSON:", args.out_json)


if __name__ == "__main__":
    main()
