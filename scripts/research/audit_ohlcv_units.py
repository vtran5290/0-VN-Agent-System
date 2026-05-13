"""
OHLCV Data Quality Audit
========================
Validates price unit consistency and value = close × volume integrity across
the full OHLCV panel.  Detects the known mixed-unit issue where some historical
rows store value = close_thousands × volume instead of close_VND × volume.

Outputs:
  data/research/unit_scaling_audit.csv   — per-symbol summary
  data/research/bad_ohlcv_rows.csv       — individual outlier rows
  data/research/data_quality_summary.md  — human-readable findings
"""
from __future__ import annotations
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from pathlib import Path
from tabulate import tabulate

ROOT   = Path(__file__).resolve().parents[2]
PANEL  = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX  = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
OUT    = ROOT / "data/research"

ADV50_LIQUID_MIN = 2_000_000_000  # 2B VND/day

RATIO_LO = 0.5   # value / (close_VND * vol) lower bound — good row
RATIO_HI = 2.0   # upper bound — good row
# Rows with ratio outside [0.001, 2000] are flagged as clearly wrong


def load_panel():
    print("Loading panel...", flush=True)
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    print(f"  {len(df):,} rows | {df['symbol'].nunique()} tickers "
          f"| {df['date'].min().date()} -> {df['date'].max().date()}", flush=True)
    return df


def detect_price_unit(df: pd.DataFrame) -> tuple[bool, float]:
    """Return (in_thousands, global_median_close)."""
    med = df.groupby("symbol")["close"].median().median()
    return med < 500, float(med)


def audit(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    in_thousands, med_c = detect_price_unit(df)
    print(f"  Price unit: {'thousand VND (raw)' if in_thousands else 'VND'}  "
          f"(global median close = {med_c:.2f})")

    close_vnd = df["close"] * 1000 if in_thousands else df["close"]

    # Expected value in VND = close_VND × volume
    expected_vnd = close_vnd * df["volume"]

    # Ratio: actual value / expected VND
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(expected_vnd > 0, df["value"] / expected_vnd, np.nan)

    df = df.copy()
    df["close_vnd"]    = close_vnd
    df["expected_vnd"] = expected_vnd
    df["ratio"]        = ratio

    # ── Per-symbol summary ───────────────────────────────────────────────────
    print("  Computing per-symbol statistics...", flush=True)

    records = []
    bad_rows_list = []

    for sym, sg in df.groupby("symbol"):
        r = sg["ratio"].dropna()
        if len(r) == 0:
            continue

        med_r   = float(r.median())
        mean_r  = float(r.mean())
        pct_bad = float(((r < RATIO_LO) | (r > RATIO_HI)).mean() * 100)

        # Determine predominant unit for this symbol
        n_vnd       = int((r.between(0.5,  2.0)).sum())   # value ≈ close_VND × vol
        n_thousands = int((r.between(0.0005, 0.005)).sum()) # value ≈ close_k × vol (off by 1000)
        n_inflated  = int((r > 900).sum())                  # value ≈ close_VND × vol × 1000 (off x1000 other dir)

        # Correct ADV50 using close_VND × volume (the ground truth)
        ev50  = sg["expected_vnd"].iloc[-50:].mean() if len(sg) >= 50 else sg["expected_vnd"].mean()
        adv50_b_correct = round(ev50 / 1e9, 2)

        # What the current scripts compute (value × 1000 if median_value < 1e8)
        med_val = df["value"].median()
        scale   = 1000 if med_val < 1e8 else 1
        adv50_as_computed = round(sg["value"].iloc[-50:].mean() * scale / 1e9, 2) if len(sg) >= 50 else None

        records.append({
            "symbol":               sym,
            "n_rows":               len(sg),
            "median_ratio":         round(med_r, 4),
            "mean_ratio":           round(mean_r, 4),
            "pct_bad_rows":         round(pct_bad, 2),
            "n_ratio_ok":           n_vnd,
            "n_ratio_x1000_low":    n_thousands,
            "n_ratio_x1000_high":   n_inflated,
            "adv50_B_correct":      adv50_b_correct,
            "adv50_B_as_computed":  adv50_as_computed,
            "adv50_error_factor":   round(adv50_as_computed / adv50_b_correct, 2) if adv50_b_correct and adv50_as_computed else None,
        })

        # Collect individual bad rows
        bad = sg[(sg["ratio"] < RATIO_LO) | (sg["ratio"] > RATIO_HI)].copy()
        if not bad.empty:
            bad["symbol"] = sym
            bad_rows_list.append(bad[["symbol", "date", "close", "close_vnd", "volume",
                                      "value", "expected_vnd", "ratio"]])

    sym_df   = pd.DataFrame(records)
    bad_rows = pd.concat(bad_rows_list, ignore_index=True) if bad_rows_list else pd.DataFrame()

    return sym_df, bad_rows


def adv50_sanity(sym_df: pd.DataFrame) -> pd.DataFrame:
    """Flag symbols where adv50_error_factor is far from 1.0."""
    s = sym_df.dropna(subset=["adv50_error_factor"]).copy()
    s["adv50_inflated"]  = s["adv50_error_factor"] > 10
    s["adv50_deflated"]  = s["adv50_error_factor"] < 0.1
    return s


def print_summary(sym_df: pd.DataFrame, bad_rows: pd.DataFrame) -> str:
    n_sym  = len(sym_df)
    n_bad  = int((sym_df["pct_bad_rows"] > 5).sum())
    n_rows = int(sym_df["n_rows"].sum())
    n_bad_rows = len(bad_rows)

    s = sym_df.dropna(subset=["adv50_error_factor"])
    n_inflated = int((s["adv50_error_factor"] > 10).sum())
    n_deflated = int((s["adv50_error_factor"] < 0.1).sum())

    lines = []
    lines.append("# OHLCV Data Quality Audit")
    lines.append(f"\n**Date:** {pd.Timestamp.now().date()}")
    lines.append(f"\n## Overview")
    lines.append(f"| Item | Value |")
    lines.append(f"|------|-------|")
    lines.append(f"| Total rows | {n_rows:,} |")
    lines.append(f"| Tickers | {n_sym} |")
    lines.append(f"| Rows with bad value/close/vol ratio | {n_bad_rows:,} |")
    lines.append(f"| Tickers with >5% bad rows | {n_bad} |")
    lines.append(f"| ADV50 inflated (>10x) | {n_inflated} |")
    lines.append(f"| ADV50 deflated (<0.1x) | {n_deflated} |")

    lines.append(f"\n## Root Cause")
    lines.append("""
The raw panel stores `value = close_thousands × volume` (NOT `close_VND × volume`).
Scripts that multiply `value × 1000` to convert to VND produce the correct number
for recent data, but historical rows from the original bulk-build may have been
stored as `value = close_VND × volume` already — giving a mix of units across
different date ranges.  This causes ADV50 to be inflated by up to 1000× for some
symbols when the mixed rows dominate the 50-day window.

**Correct formula:** `ADV50_VND = mean(close_VND × volume, last 50 days)`
where `close_VND = close × 1000` (price was stored in thousand-VND units).
""")

    lines.append("## Worst ADV50 Error Cases (top 20)")
    top20 = sym_df.dropna(subset=["adv50_error_factor"])\
                  .sort_values("adv50_error_factor", ascending=False).head(20)
    tbl = top20[["symbol","adv50_B_correct","adv50_B_as_computed","adv50_error_factor","pct_bad_rows"]].values.tolist()
    tbl = [[r[0], f"{r[1]:.1f}B", f"{r[2]:.1f}B", f"{r[3]:.1f}x", f"{r[4]:.1f}%"] for r in tbl]
    lines.append(tabulate(tbl, headers=["Symbol","ADV50_correct","ADV50_computed","Error_factor","Pct_bad"],
                          tablefmt="github"))

    lines.append("\n## Liquid Universe ADV50 Sanity (correct values, ADV50>=2B VND)")
    liquid = sym_df[sym_df["adv50_B_correct"] >= 2].sort_values("adv50_B_correct", ascending=False).head(30)
    tbl2 = liquid[["symbol","adv50_B_correct","adv50_B_as_computed","adv50_error_factor"]].values.tolist()
    tbl2 = [[r[0], f"{r[1]:.1f}B", f"{r[2]:.1f}B" if r[2] else "—",
             f"{r[3]:.2f}x" if r[3] else "—"] for r in tbl2]
    lines.append(tabulate(tbl2, headers=["Symbol","ADV50_B_correct","ADV50_B_computed","Error_factor"],
                          tablefmt="github"))

    lines.append("\n## Recommendation")
    lines.append("""
All scripts should compute ADV50 as:

```python
close_vnd = df["close"] * 1000   # always, since panel close is in thousand-VND
adv50_vnd = (close_vnd * df["volume"]).rolling(50).mean()
adv50_B   = adv50_vnd / 1e9
```

Do NOT rely on `df["value"]` for ADV50 calculation until the value column has been
fully re-derived from `close_VND × volume` across the entire history.
""")

    return "\n".join(lines)


def main():
    df = load_panel()

    print("Running unit audit...", flush=True)
    sym_df, bad_rows = audit(df)

    # Print console summary
    n_bad = int((sym_df["pct_bad_rows"] > 5).sum())
    print(f"\n  Tickers with >5% bad ratio rows: {n_bad}")
    print(f"  Total bad rows: {len(bad_rows):,}")
    print(f"\n  ADV50 error distribution:")
    ef = sym_df["adv50_error_factor"].dropna()
    print(f"    median error factor: {ef.median():.2f}x")
    print(f"    >10x (inflated):     {(ef > 10).sum()}")
    print(f"    <0.1x (deflated):    {(ef < 0.1).sum()}")
    print(f"    within [0.8, 1.2]:   {ef.between(0.8, 1.2).sum()}")

    # Save
    sym_out  = OUT / "unit_scaling_audit.csv"
    bad_out  = OUT / "bad_ohlcv_rows.csv"
    md_out   = OUT / "data_quality_summary.md"

    sym_df.to_csv(sym_out, index=False)
    print(f"\nSaved: {sym_out}")

    if not bad_rows.empty:
        bad_rows.to_csv(bad_out, index=False)
        print(f"Saved: {bad_out}  ({len(bad_rows):,} rows)")
    else:
        print("No bad rows found — skipping bad_ohlcv_rows.csv")

    md_text = print_summary(sym_df, bad_rows)
    md_out.write_text(md_text, encoding="utf-8")
    print(f"Saved: {md_out}")
    print("\nDone.")


if __name__ == "__main__":
    main()
