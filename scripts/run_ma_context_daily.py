"""
MA Context Daily Enrichment
============================
Computes per-symbol MA context at today's close for the daily scan.

For each symbol in the liquid universe:
  - Best MA: from per_symbol_windows[2y] (score >= 25, n >= 5)
  - Current MA value: computed from OHLCV panel
  - dist_pct: (close - ma_val) / ma_val * 100
  - touch_flag: |dist_pct| <= 1.0 AND score >= 30  (PRIME: +9.7pp SR lift)
  - near_flag:  |dist_pct| <= 1.5 AND score >= 25  (NEAR:  +8.2pp SR lift)
  - quality: "prime" | "near" | "far"

Output: data/research/ma_context_daily.json
  {
    "asof_date": "YYYY-MM-DD",
    "symbols": {
      "ACB": {
        "best_ma": "EMA10",
        "best_ma_score": 32.5,
        "best_ma_sr10d": 55.2,
        "best_ma_avg10d": 8.1,
        "best_ma_n": 22,
        "best_ma_val_kVND": 24.5,
        "close_kVND": 24.8,
        "dist_pct": +1.2,
        "touch_flag": false,
        "near_flag": true,
        "quality": "near"
      }, ...
    }
  }

Backtest reference:
  PRIME (|dist|<=1%, score>=30): SR 48.8% vs base 39.1% (+9.7pp), MAE 8.6%
  NEAR  (|dist|<=1.5%, score>=25): SR 47.3% vs base 39.1% (+8.2pp), MAE 8.8%
  FAR: SR ~39%, MAE ~12%

Usage:
  python scripts/run_ma_context_daily.py
  # or with explicit scan date:
  python scripts/run_ma_context_daily.py --date 2026-06-10
"""

from __future__ import annotations
import argparse, json, warnings
from pathlib import Path
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parent.parent

PANEL_PQ  = REPO / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
MA_JSON   = REPO / "data/research/ma_reaction_liquid_expanded.json"
OUT_JSON  = REPO / "data/research/ma_context_daily.json"

PRIME_BAND  = 1.0    # ±% for PRIME quality
NEAR_BAND   = 1.5    # ±% for NEAR quality
MIN_SCORE   = 25.0
MIN_SCORE_PRIME = 30.0
MIN_N       = 5
PRIMARY_WIN = "2y"
FALLBACK_WIN = "1y"
MA_LOOKBACK = 210    # bars needed for SMA/EMA200


def compute_mas(close: pd.Series) -> dict[str, pd.Series]:
    out = {}
    for p in [5, 10, 20, 50, 100, 150, 200]:
        out[f"SMA{p}"] = close.rolling(p, min_periods=p).mean()
        out[f"EMA{p}"] = close.ewm(span=p, adjust=False).mean()
    return out


def load_best_ma_map(psw: dict) -> dict[str, dict]:
    result = {}
    for sym, sdata in psw.items():
        wins = sdata.get("windows", {})
        cands = wins.get(PRIMARY_WIN, []) or wins.get(FALLBACK_WIN, [])
        for c in cands:
            if c.get("score", 0) >= MIN_SCORE and c.get("n", 0) >= MIN_N:
                result[sym] = {
                    "ma":     c["ma"],
                    "score":  c["score"],
                    "sr10d":  c.get("sr_10d"),
                    "avg10d": c.get("avg_10d"),
                    "n":      c.get("n"),
                }
                break
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="As-of date YYYY-MM-DD (default: latest in panel)")
    args = parser.parse_args()

    print("Loading MA reaction JSON...")
    with open(MA_JSON, encoding="utf-8") as f:
        ma_json = json.load(f)
    psw = ma_json.get("per_symbol_windows", {})
    best_ma_map = load_best_ma_map(psw)
    print(f"  Best MA map: {len(best_ma_map)} symbols with qualified MA")

    print("Loading OHLCV panel...")
    panel = pd.read_parquet(PANEL_PQ)[["symbol", "date", "close"]].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel_end = panel["date"].max()

    asof_date: pd.Timestamp
    if args.date:
        asof_date = pd.Timestamp(args.date)
    else:
        asof_date = panel_end

    print(f"  Panel end: {panel_end.date()} | Using as-of: {asof_date.date()}")

    # Keep only data up to asof
    panel = panel[panel["date"] <= asof_date]

    results: dict[str, dict] = {}
    n_prime = n_near = n_far = n_missing = 0

    for sym, bm in best_ma_map.items():
        ma_lbl = bm["ma"]
        grp = panel[panel["symbol"] == sym].sort_values("date").tail(MA_LOOKBACK)

        if grp.empty or grp["close"].isna().all():
            n_missing += 1
            continue

        close_last = float(grp["close"].iloc[-1])
        date_last  = grp["date"].iloc[-1]

        # Compute only the needed MA
        c = grp["close"].copy()
        period = int("".join(filter(str.isdigit, ma_lbl)))
        ma_type = "EMA" if ma_lbl.startswith("E") else "SMA"

        if len(c) < period:
            n_missing += 1
            continue

        if ma_type == "SMA":
            ma_val = float(c.rolling(period, min_periods=period).mean().iloc[-1])
        else:
            ma_val = float(c.ewm(span=period, adjust=False).mean().iloc[-1])

        if np.isnan(ma_val):
            n_missing += 1
            continue

        dist_pct = (close_last - ma_val) / ma_val * 100
        abs_dist  = abs(dist_pct)
        score     = bm["score"]

        if abs_dist <= PRIME_BAND and score >= MIN_SCORE_PRIME:
            quality = "prime"
            n_prime += 1
        elif abs_dist <= NEAR_BAND and score >= MIN_SCORE:
            quality = "near"
            n_near += 1
        else:
            quality = "far"
            n_far += 1

        results[sym] = {
            "best_ma":       ma_lbl,
            "best_ma_score": round(score, 1),
            "best_ma_sr10d": bm.get("sr10d"),
            "best_ma_avg10d": bm.get("avg10d"),
            "best_ma_n":     bm.get("n"),
            "best_ma_val_kVND": round(ma_val / 1000, 3),
            "close_kVND":    round(close_last / 1000, 3),
            "data_date":     str(date_last.date()),
            "dist_pct":      round(dist_pct, 2),
            "touch_flag":    quality == "prime",
            "near_flag":     quality in ("prime", "near"),
            "quality":       quality,
        }

    print(f"\nResults: PRIME={n_prime} | NEAR={n_near} | FAR={n_far} | MISSING={n_missing}")
    print("Prime symbols:", [s for s, d in results.items() if d["quality"] == "prime"][:20])

    output = {
        "asof_date":   str(asof_date.date()),
        "panel_end":   str(panel_end.date()),
        "primary_win": PRIMARY_WIN,
        "prime_band":  PRIME_BAND,
        "near_band":   NEAR_BAND,
        "min_score":   MIN_SCORE,
        "backtest_ref": {
            "prime_sr_pct":    48.8,
            "prime_sr_lift":    9.7,
            "near_sr_pct":     47.3,
            "near_sr_lift":     8.2,
            "base_sr_pct":     39.1,
            "trades_n":     964496,
        },
        "symbols": results,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten: {OUT_JSON}  ({len(results)} symbols)")


if __name__ == "__main__":
    main()
