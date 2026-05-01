"""
Concrete audit for regime_off on weekly date 2026-03-20 (Path A).

Regime logic source: pp_backtest/market_regime.py
- regime_ftd = (VN30 close > MA50) AND (MA50 slope over 20 days > 0)
- no_new_positions = (distribution_days_last_10 >= 3)
- weekly mapping = resample W-FRI, take last daily value in that week

Writes:
- artifacts/path_a_regime_off_audit_2026_03_20.csv
- artifacts/path_a_regime_off_audit_2026_03_20.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pp_backtest.data import fetch_ohlcv_fireant
from pp_backtest.market_regime import add_book_regime_columns, weekly_regime_from_daily


WEEKLY_DATE = pd.Timestamp("2026-03-20").normalize()


def main() -> None:
    artifacts = _REPO / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Need enough history for MA50 + MA50 slope (uses shift(20)), plus dist days lookback.
    start = "2025-10-01"
    end = "2026-03-21"
    vn30_daily = fetch_ohlcv_fireant("VN30", start, end)
    vn30_daily = vn30_daily.copy()
    vn30_daily["date"] = pd.to_datetime(vn30_daily["date"]).dt.normalize()
    vn30_daily = vn30_daily.sort_values("date").reset_index(drop=True)

    reg = add_book_regime_columns(vn30_daily)
    reg["date"] = pd.to_datetime(reg["date"]).dt.normalize()
    reg = reg.sort_values("date").reset_index(drop=True)

    # Recompute the exact inputs used for distribution days for transparency
    c = reg["close"].astype(float)
    v = reg["volume"].astype(float)
    prev_c = c.shift(1)
    prev_v = v.shift(1)
    pct_chg = (c - prev_c) / prev_c.replace(0, np.nan)
    is_dd = (c < prev_c) & (v > prev_v) & (pct_chg <= -0.002)

    reg["prev_close"] = prev_c
    reg["prev_volume"] = prev_v
    reg["pct_change"] = pct_chg
    reg["is_distribution_day"] = is_dd

    # Also expose MA50 and MA50 slope inputs for the target date
    ma50 = c.rolling(50, min_periods=50).mean()
    ma50_slope = (ma50 - ma50.shift(20)) / ma50.shift(20).replace(0, np.nan)
    reg["ma50"] = ma50
    reg["ma50_slope"] = ma50_slope
    reg["close_gt_ma50"] = (c > ma50)
    reg["ma50_slope_gt_0"] = (ma50_slope > 0)

    # Weekly mapping (the engine takes the last daily row of the week)
    weekly = weekly_regime_from_daily(reg, week_end="W-FRI")
    weekly["date"] = pd.to_datetime(weekly["date"]).dt.normalize()
    wk_row = weekly[weekly["date"] == WEEKLY_DATE]
    if wk_row.empty:
        raise SystemExit(f"Weekly regime row not found for {WEEKLY_DATE.date()}")

    # Identify the exact daily benchmark row used for mapping:
    # For W-FRI resample, it's the last trading day <= that Friday within the bucket.
    daily_row = reg[reg["date"] <= WEEKLY_DATE].iloc[-1]
    daily_date_used = pd.to_datetime(daily_row["date"]).normalize()

    # Extract last 15 trading days up to and including the mapped daily date
    span = reg[reg["date"] <= daily_date_used].tail(15).copy()

    out_csv = artifacts / "path_a_regime_off_audit_2026_03_20.csv"
    cols = [
        "date",
        "close",
        "prev_close",
        "volume",
        "prev_volume",
        "pct_change",
        "is_distribution_day",
        "dist_days_last_10",
        "no_new_positions",
        "ma50",
        "ma50_slope",
        "close_gt_ma50",
        "ma50_slope_gt_0",
        "regime_ftd",
    ]
    span.to_csv(out_csv, index=False, columns=cols)

    # Determine exact reason regime_ftd is False on the mapped daily row
    close_gt = bool(daily_row["close_gt_ma50"]) if not pd.isna(daily_row["close_gt_ma50"]) else False
    slope_gt = bool(daily_row["ma50_slope_gt_0"]) if not pd.isna(daily_row["ma50_slope_gt_0"]) else False
    regime_ftd = bool(daily_row["regime_ftd"])
    no_new_positions = bool(daily_row["no_new_positions"])

    reasons = []
    if not close_gt:
        reasons.append("VN30 close <= MA50")
    if not slope_gt:
        reasons.append("MA50 slope <= 0")
    if not reasons and not regime_ftd:
        reasons.append("regime_ftd computed False (insufficient MA50 history or NaN inputs)")
    reason_txt = " and ".join(reasons) if reasons else "regime_ftd=True"

    md_path = artifacts / "path_a_regime_off_audit_2026_03_20.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Path A regime_off Audit — Week ending 2026-03-20\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Weekly date used: **{WEEKLY_DATE.date()}**\n")
        f.write(f"- Daily benchmark date used for mapping: **{daily_date_used.date()}**\n")
        f.write(f"- regime_ftd on that daily row: **{regime_ftd}**\n")
        f.write(f"- no_new_positions on that daily row: **{no_new_positions}**\n")
        f.write(f"- Exact reason regime_ftd is False: **{reason_txt}**\n\n")

        f.write("## Weekly mapping proof\n\n")
        f.write("- `weekly_regime_from_daily(..., week_end='W-FRI')` takes the **last daily** value in the week bucket.\n")
        f.write(f"- For week ending **{WEEKLY_DATE.date()}**, the last available VN30 daily row is **{daily_date_used.date()}**.\n\n")

        f.write("## Concrete VN30 inputs on the mapped daily row\n\n")
        f.write(f"- VN30 close: {float(daily_row['close']):.2f}\n")
        f.write(f"- MA50: {float(daily_row['ma50']):.2f}\n" if not pd.isna(daily_row["ma50"]) else "- MA50: NaN (insufficient history)\n")
        f.write(f"- MA50 slope (20d): {float(daily_row['ma50_slope']):.6f}\n" if not pd.isna(daily_row["ma50_slope"]) else "- MA50 slope (20d): NaN\n")
        f.write(f"- close > MA50: {close_gt}\n")
        f.write(f"- MA50 slope > 0: {slope_gt}\n")
        f.write(f"- dist_days_last_10: {float(daily_row['dist_days_last_10']):.1f}\n" if not pd.isna(daily_row["dist_days_last_10"]) else "- dist_days_last_10: NaN\n")
        f.write("\n")

        f.write("## Why this blocked all Champion buy executions\n\n")
        f.write("- Portfolio entry gate requires `regime_ftd=True` and `no_new_positions=False`.\n")
        f.write(f"- On {daily_date_used.date()}, `regime_ftd={regime_ftd}` and `no_new_positions={no_new_positions}`.\n")
        if not regime_ftd:
            f.write("- Therefore **regime_off** rejected all otherwise-ranked candidates for that week.\n")
        else:
            f.write("- Therefore the blocker was not regime_off.\n")


if __name__ == "__main__":
    main()

