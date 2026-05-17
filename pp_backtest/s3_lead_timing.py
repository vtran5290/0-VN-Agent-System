#!/usr/bin/env python3
"""
S3→A3 Lead Timing Analysis.

For every A3 DP-first trade, find bars_since_last_S3_signal (same symbol).
Bucket by lag and compare trade quality, year-by-year, bad-year, sector.

Output: data/research/s3_production_upgrade/lead_timing/

DO NOT change A3 production logic.
DO NOT allow S3 to gate A3.
This is ranking research only.
"""
from __future__ import annotations
import sys, warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache, load_panel, load_vnindex, get_universe,
    portfolio_metrics, DEFAULT_COST,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2, _annual_return,
)
from pp_backtest.s3_upgrade_research import (
    _regime_gate_100, _build_trades, _metrics, _tp_rate,
)

OUT = REPO / "data" / "research" / "s3_production_upgrade" / "lead_timing"
OUT.mkdir(parents=True, exist_ok=True)

PORTFOLIO_VND = 5e9
MAX_SLOTS     = 20
PARTICIPATION = 0.10
BASE_COST     = DEFAULT_COST

EXIT_A3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5, "max_hold": 250}

BUCKET_ORDER = [
    "same_bar_0",
    "lead_1_2",
    "lead_3_5",
    "lead_6_10",
    "lead_11_20",
    "lead_21_30",
    "no_s3_lead",
]

BAD_YEARS = [2018, 2022, 2026]


# ── helpers ──────────────────────────────────────────────────────────────────

def bars_between(d1: pd.Timestamp, d2: pd.Timestamp) -> int:
    """Business days from d1 to d2 (d2 >= d1). Returns 0 for same day."""
    if d1 == d2:
        return 0
    try:
        return max(0, int(np.busday_count(d1.date(), d2.date())))
    except Exception:
        return max(0, int((d2 - d1).days * 5 // 7))


def assign_bucket(bars) -> str:
    if bars is None or (isinstance(bars, float) and np.isnan(bars)):
        return "no_s3_lead"
    b = int(bars)
    if b == 0:          return "same_bar_0"
    elif b <= 2:        return "lead_1_2"
    elif b <= 5:        return "lead_3_5"
    elif b <= 10:       return "lead_6_10"
    elif b <= 20:       return "lead_11_20"
    elif b <= 30:       return "lead_21_30"
    else:               return "no_s3_lead"


def fmt(v, pct=False, dec=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.1%}" if pct else f"{v:.{dec}f}"


# ── tag lead info onto A3 trades ─────────────────────────────────────────────

def tag_lead(a3_df: pd.DataFrame, s3_cache: dict, lookback_bars: int = 60) -> pd.DataFrame:
    """
    For each A3 trade, find the most recent S3 signal on the same symbol
    within lookback_bars bars before the A3 signal date.

    Adds columns: s3_last_sig_date, bars_since_s3, bucket.
    """
    lookback_days = int(lookback_bars * 1.5)   # calendar days ≈ bars × 1.5

    # Build S3 signal date lookup: sym → sorted list[Timestamp]
    s3_sigs: dict[str, list[pd.Timestamp]] = {}
    for sym, data in s3_cache.items():
        dates = [
            pd.Timestamp(data["dates"][k]).normalize()
            for k in data["sig_idxs"]
        ]
        if dates:
            s3_sigs[sym] = sorted(dates)

    df = a3_df.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])

    last_s3_dates: list = []
    bars_since:    list = []

    for _, row in df.iterrows():
        sym      = row["symbol"]
        a3_sig   = row["signal_date"]
        cutoff   = a3_sig - pd.Timedelta(days=lookback_days)

        sigs = s3_sigs.get(sym, [])
        # find latest S3 signal in (cutoff, a3_sig]
        prior = [s for s in sigs if cutoff < s <= a3_sig]

        if prior:
            latest = prior[-1]
            nb = bars_between(latest, a3_sig)
        else:
            latest = pd.NaT
            nb = np.nan

        last_s3_dates.append(latest)
        bars_since.append(nb)

    df["s3_last_sig_date"] = last_s3_dates
    df["bars_since_s3"]    = bars_since
    df["bucket"]           = [assign_bucket(b) for b in bars_since]
    return df


# ── per-bucket metrics ────────────────────────────────────────────────────────

def bucket_metrics(sub: pd.DataFrame, adv50_map: dict) -> dict:
    if sub.empty:
        return {}
    m = _metrics(sub, adv50_map)
    med = float(sub["net_return"].median())
    avg = float(sub["net_return"].mean())
    return {
        **m,
        "avg_net_return":    round(avg, 4),
        "median_net_return": round(med, 4),
        "hit_rate":          round((sub["net_return"] > 0).mean(), 4),
        "tp1_rate":          round(_tp_rate(sub), 4),
        "avg_ed":            round(sub["ema_dist_at_entry"].mean(), 4),
        "avg_adv50_B":       round(sub["adv50_value"].mean() / 1e9, 3),
        "avg_hold_bars":     round(sub["hold_bars"].mean(), 1),
    }


def bucket_bad_year(sub: pd.DataFrame, yr: int) -> dict:
    sub["entry_date"] = pd.to_datetime(sub["entry_date"])
    yr_sub = sub[sub["entry_date"].dt.year == yr]
    if len(yr_sub) < 3:
        return {"n": len(yr_sub), "avg_net": np.nan, "hit_rate": np.nan}
    return {
        "n":        len(yr_sub),
        "avg_net":  round(yr_sub["net_return"].mean(), 4),
        "hit_rate": round((yr_sub["net_return"] > 0).mean(), 4),
    }


# ── sector concentration ──────────────────────────────────────────────────────

def top_sector(sub: pd.DataFrame, sector_map: pd.DataFrame) -> str:
    if sub.empty or sector_map.empty:
        return "N/A"
    merged = sub.merge(sector_map[["symbol", "primary_sector"]], on="symbol", how="left")
    counts = merged["primary_sector"].value_counts()
    if counts.empty:
        return "N/A"
    top = counts.index[0]
    pct = counts.iloc[0] / counts.sum()
    return f"{top} ({pct:.0%})"


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...", flush=True)
    panel     = load_panel()
    vnx       = load_vnindex()
    regime    = _regime_gate_100(vnx)
    adv50_map = _build_adv50_map(panel)

    a3_cache = _build_signal_cache(panel, "A3")
    s3_cache = _build_signal_cache(panel, "S3")

    # Load sector map
    sector_path = REPO / "data" / "master" / "sector_map.csv"
    sector_map  = pd.read_csv(sector_path) if sector_path.exists() else pd.DataFrame()
    print(f"  Sector map: {len(sector_map)} symbols", flush=True)

    # Build A3 baseline trades
    print("Building A3 trades...", flush=True)
    a3_df = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime, adv50_map=adv50_map)
    a3_df = _tag_adv50(a3_df, adv50_map)
    print(f"  A3 trades: {len(a3_df)}", flush=True)

    # Tag S3 lead info
    print("Tagging S3 lead lag (lookback=60 bars)...", flush=True)
    a3_df = tag_lead(a3_df, s3_cache, lookback_bars=60)
    print(f"  Trades with S3 lead: {(a3_df['bucket'] != 'no_s3_lead').sum()} / {len(a3_df)}", flush=True)
    print(f"  Bucket distribution:\n{a3_df['bucket'].value_counts()[BUCKET_ORDER]}", flush=True)

    # Save tagged trade ledger
    a3_df.to_csv(OUT / "lead_tagged_trades.csv", index=False)

    # ── Per-bucket summary ────────────────────────────────────────────────────
    print("\nComputing per-bucket metrics...", flush=True)
    summary_rows   = []
    year_rows      = []
    bad_year_rows  = []
    sector_rows    = []

    for bucket in BUCKET_ORDER:
        sub = a3_df[a3_df["bucket"] == bucket].copy()
        n   = len(sub)
        print(f"  {bucket}: n={n}", flush=True)
        if n < 5:
            summary_rows.append({
                "bucket": bucket, "n_trades": n,
                "mar": np.nan, "cagr": np.nan, "max_dd": np.nan,
                "avg_net_return": np.nan, "median_net_return": np.nan,
                "hit_rate": np.nan, "tp1_rate": np.nan,
                "avg_ed": np.nan, "avg_adv50_B": np.nan, "avg_hold_bars": np.nan,
            })
            continue

        m = bucket_metrics(sub, adv50_map)

        summary_rows.append({
            "bucket":            bucket,
            "n_trades":          n,
            "mar":               round(m.get("mar",      np.nan), 4),
            "cagr":              round(m.get("cagr",     np.nan), 4),
            "max_dd":            round(m.get("max_dd",   np.nan), 4),
            "avg_net_return":    m.get("avg_net_return",    np.nan),
            "median_net_return": m.get("median_net_return", np.nan),
            "hit_rate":          m.get("hit_rate",          np.nan),
            "tp1_rate":          m.get("tp1_rate",          np.nan),
            "avg_ed":            m.get("avg_ed",            np.nan),
            "avg_adv50_B":       m.get("avg_adv50_B",       np.nan),
            "avg_hold_bars":     m.get("avg_hold_bars",     np.nan),
        })

        # Year-by-year
        for yr in range(2014, 2027):
            v = m.get(f"yr_{yr}", np.nan)
            year_rows.append({"bucket": bucket, "year": yr,
                              "annual_return": round(v, 4) if not np.isnan(v) else np.nan})

        # Bad years (trade-level avg, not equity)
        sub["entry_date"] = pd.to_datetime(sub["entry_date"])
        for yr in BAD_YEARS:
            by = bucket_bad_year(sub, yr)
            bad_year_rows.append({
                "bucket": bucket, "year": yr,
                "n": by["n"], "avg_net": by["avg_net"], "hit_rate": by["hit_rate"],
            })

        # Sector
        sector_rows.append({
            "bucket":       bucket,
            "n_trades":     n,
            "top_sector":   top_sector(sub, sector_map),
        })

    # ── Bars-since distribution ───────────────────────────────────────────────
    lead_only = a3_df[a3_df["bucket"] != "no_s3_lead"]
    dist_rows = []
    for bars_val, grp in lead_only.groupby("bars_since_s3"):
        bars_val = int(bars_val)
        dist_rows.append({
            "bars_since_s3": bars_val,
            "n":             len(grp),
            "avg_net":       round(grp["net_return"].mean(), 4),
            "hit_rate":      round((grp["net_return"] > 0).mean(), 4),
            "tp1_rate":      round(_tp_rate(grp), 4),
        })
    dist_df = pd.DataFrame(dist_rows).sort_values("bars_since_s3")

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    summary_df   = pd.DataFrame(summary_rows)
    year_df      = pd.DataFrame(year_rows)
    bad_year_df  = pd.DataFrame(bad_year_rows)
    sector_df    = pd.DataFrame(sector_rows)

    summary_df.to_csv(OUT / "bucket_summary.csv",   index=False)
    year_df.to_csv(   OUT / "bucket_by_year.csv",   index=False)
    bad_year_df.to_csv(OUT / "bucket_bad_years.csv", index=False)
    sector_df.to_csv( OUT / "bucket_sector.csv",    index=False)
    dist_df.to_csv(   OUT / "bars_distribution.csv", index=False)
    print("  CSVs saved.", flush=True)

    # ── Findings document ─────────────────────────────────────────────────────
    print("\nWriting findings...", flush=True)

    # Pivot year table
    yr_pivot = year_df.pivot(index="year", columns="bucket", values="annual_return")

    # Best MAR bucket (excluding no_s3_lead and same_bar_0 if tiny)
    ranked = summary_df.dropna(subset=["mar"]).sort_values("mar", ascending=False)
    best_bucket = ranked.iloc[0]["bucket"] if not ranked.empty else "N/A"
    best_mar    = ranked.iloc[0]["mar"]    if not ranked.empty else np.nan

    # Is 3-5 the best?
    mar_35 = float(summary_df[summary_df["bucket"] == "lead_3_5"]["mar"].iloc[0]) \
        if not summary_df[summary_df["bucket"] == "lead_3_5"].empty else np.nan
    mar_nolead = float(summary_df[summary_df["bucket"] == "no_s3_lead"]["mar"].iloc[0]) \
        if not summary_df[summary_df["bucket"] == "no_s3_lead"].empty else np.nan

    # Monotonic trend check: does MAR decline as lag increases?
    mar_series = [
        summary_df[summary_df["bucket"] == b]["mar"].values
        for b in BUCKET_ORDER
    ]
    mar_vals = [float(v[0]) if len(v) > 0 and not np.isnan(v[0]) else np.nan
                for v in mar_series]

    doc = f"""# S3→A3 Lead Timing Analysis

Date: 2026-05-17
Universe: A3 DP-First (EMA20/100, ex-VIN3), S3 EMA21/55 (full)
Lookback: 60 bars for S3 lead detection

DO NOT change A3 production logic.
DO NOT allow S3 to gate A3.
This is ranking research only.

---

## 1. Bucket Distribution

| Bucket | N | % of A3 |
|--------|---|---------|
"""
    total_n = len(a3_df)
    for r in summary_rows:
        pct = r["n_trades"] / max(total_n, 1)
        doc += f"| {r['bucket']} | {r['n_trades']:,} | {pct:.1%} |\n"

    doc += f"""
Total A3 trades: {total_n:,}
Trades with any S3 lead (≤30 bars): {(a3_df['bucket'] != 'no_s3_lead').sum():,} ({(a3_df['bucket'] != 'no_s3_lead').mean():.1%})

---

## 2. Per-Bucket Performance Summary

| Bucket | N | MAR | CAGR | MaxDD | Avg Net | Median Net | Hit% | TP1% | Avg ED | Avg ADV50 |
|--------|---|-----|------|-------|---------|-----------|------|------|--------|-----------|
"""
    for r in summary_rows:
        doc += (f"| {r['bucket']} | {r['n_trades']:,} | {fmt(r['mar'])} | "
                f"{fmt(r['cagr'], pct=True)} | {fmt(r['max_dd'], pct=True)} | "
                f"{fmt(r['avg_net_return'], pct=True)} | {fmt(r['median_net_return'], pct=True)} | "
                f"{fmt(r['hit_rate'], pct=True)} | {fmt(r['tp1_rate'], pct=True)} | "
                f"{fmt(r['avg_ed'], pct=True)} | {fmt(r['avg_adv50_B'], dec=1)}B |\n")

    doc += f"""
---

## 3. Year-by-Year by Bucket (Portfolio Annual Return)

| Year |"""
    for b in BUCKET_ORDER:
        doc += f" {b} |"
    doc += "\n|------|" + "|".join(["---"] * len(BUCKET_ORDER)) + "|\n"

    for yr in range(2014, 2027):
        if yr not in yr_pivot.index:
            continue
        row_vals = [fmt(yr_pivot.loc[yr].get(b, np.nan), pct=True) for b in BUCKET_ORDER]
        doc += f"| {yr} | " + " | ".join(row_vals) + " |\n"

    doc += """
---

## 4. Bad-Year Breakdown (Trade-Level Avg — 2018, 2022, 2026)

| Year | Bucket | N | Avg Net | Hit% |
|------|--------|---|---------|------|
"""
    for _, r in bad_year_df.iterrows():
        doc += (f"| {int(r['year'])} | {r['bucket']} | {int(r['n'])} | "
                f"{fmt(r['avg_net'], pct=True)} | {fmt(r['hit_rate'], pct=True)} |\n")

    doc += """
---

## 5. Top Sector Concentration by Bucket

| Bucket | N | Top Sector |
|--------|---|-----------|
"""
    for _, r in sector_df.iterrows():
        doc += f"| {r['bucket']} | {r['n_trades']:,} | {r['top_sector']} |\n"

    doc += """
---

## 6. Bars-Since Distribution (lead trades only, first 30 bars)

| Bars Since S3 | N | Avg Net | Hit% | TP1% |
|--------------|---|---------|------|------|
"""
    for _, r in dist_df[dist_df["bars_since_s3"] <= 30].iterrows():
        doc += (f"| {int(r['bars_since_s3'])} | {int(r['n'])} | "
                f"{fmt(r['avg_net'], pct=True)} | {fmt(r['hit_rate'], pct=True)} | "
                f"{fmt(r['tp1_rate'], pct=True)} |\n")

    # ── Answer the 5 questions ────────────────────────────────────────────────

    # Q1: Is shorter lag better?
    lead_mars = [(b, v) for b, v in zip(BUCKET_ORDER[:-1], mar_vals[:-1])
                 if not np.isnan(v)]
    monotone_decline = all(
        lead_mars[i][1] >= lead_mars[i+1][1]
        for i in range(len(lead_mars) - 1)
    ) if len(lead_mars) > 1 else False

    if lead_mars:
        best_lead = max(lead_mars, key=lambda x: x[1])
    else:
        best_lead = ("N/A", np.nan)

    # Q2: same_bar_0 — too stretched?
    mar_0    = float(summary_df[summary_df["bucket"] == "same_bar_0"]["mar"].values[0]) \
        if not summary_df[summary_df["bucket"] == "same_bar_0"].empty else np.nan
    n_0      = int(summary_df[summary_df["bucket"] == "same_bar_0"]["n_trades"].values[0]) \
        if not summary_df[summary_df["bucket"] == "same_bar_0"].empty else 0

    # Q3: 3-5 best?
    mar_12   = float(summary_df[summary_df["bucket"] == "lead_1_2"]["mar"].values[0]) \
        if not summary_df[summary_df["bucket"] == "lead_1_2"].empty else np.nan

    # Q4: show LeadAge instead of boolean?
    # Assess: is there meaningful MAR spread across non-zero lead buckets?
    non_zero_lead_mars = [v for b, v in zip(BUCKET_ORDER[1:-1], mar_vals[1:-1]) if not np.isnan(v)]
    mar_spread = max(non_zero_lead_mars) - min(non_zero_lead_mars) if len(non_zero_lead_mars) > 1 else 0.0

    # Q5: Best ranking signal?
    ed_vals = {r["bucket"]: r["avg_ed"] for _, r in summary_df.iterrows()}
    # Check if lead_3_5 has tighter ED than no_s3_lead
    ed_35     = ed_vals.get("lead_3_5", np.nan)
    ed_nolead = ed_vals.get("no_s3_lead", np.nan)

    doc += f"""
---

## 7. Answers to Research Questions

### Q1. Is shorter S3→A3 lag better?

Best performing bucket: **{best_lead[0]}** (MAR={fmt(best_lead[1])})
MAR by lag (shorter → longer): {', '.join(f"{b}={fmt(v)}" for b, v in lead_mars)}

Monotone improvement as lag decreases: **{'YES' if monotone_decline else 'NO — non-monotone'}**

"""
    if monotone_decline:
        doc += "MAR increases consistently as lag shortens. Shorter lag = better A3 setup quality.\n"
    else:
        doc += (f"Relationship is non-monotone. The peak is at **{best_lead[0]}**, not at 0 bars. "
                "This suggests same-bar or very short lag is not automatically better — "
                "the S3 signal needs a brief consolidation before A3 fires.\n")

    doc += f"""
### Q2. Is 0-bar / same-bar (same_bar_0) confirmation too stretched?

same_bar_0: N={n_0:,}, MAR={fmt(mar_0)}
lead_1_2:   N={int(summary_df[summary_df['bucket']=='lead_1_2']['n_trades'].values[0]) if not summary_df[summary_df['bucket']=='lead_1_2'].empty else 0:,}, MAR={fmt(mar_12)}
lead_3_5:   N={int(summary_df[summary_df['bucket']=='lead_3_5']['n_trades'].values[0]) if not summary_df[summary_df['bucket']=='lead_3_5'].empty else 0:,}, MAR={fmt(mar_35)}

"""
    if not np.isnan(mar_0) and not np.isnan(mar_35) and mar_0 < mar_35:
        doc += (f"**YES — same_bar_0 underperforms lead_3_5 by {mar_35 - mar_0:+.3f} MAR.** "
                "When S3 and A3 fire simultaneously, the A3 signal may be chasing an already-extended move. "
                "The best setups have S3 firing 3–5 bars BEFORE A3.\n")
    elif not np.isnan(mar_0) and not np.isnan(mar_35) and mar_0 >= mar_35:
        doc += (f"same_bar_0 MAR={fmt(mar_0)} is competitive with lead_3_5 MAR={fmt(mar_35)}. "
                "Same-bar confirmation is not a red flag. Both fire near the same cloud crossover event.\n")
    else:
        doc += "Insufficient data in same_bar_0 to draw a conclusion.\n"

    doc += f"""
### Q3. Is 3–5 bars the best window?

lead_3_5 MAR={fmt(mar_35)} vs best bucket MAR={fmt(best_lead[1])} ({best_lead[0]})

"""
    if not np.isnan(mar_35) and not np.isnan(best_mar):
        if abs(mar_35 - best_mar) < 0.03:
            doc += ("**YES — lead_3_5 is at or near the peak.** The 3–5 bar window captures "
                    "the sweet spot: S3 has fired and the initial momentum burst is confirmed, "
                    "but the A3 cloud crossover hasn't overshot yet.\n")
        elif mar_35 < best_mar:
            doc += (f"**PARTIAL** — {best_lead[0]} (MAR={fmt(best_lead[1])}) outperforms lead_3_5 "
                    f"(MAR={fmt(mar_35)}) by {best_lead[1] - mar_35:+.3f}. "
                    f"The 3–5 bar window is good but not optimal.\n")
        else:
            doc += f"lead_3_5 is the best window (MAR={fmt(mar_35)}).\n"

    doc += f"""
### Q4. Should AFL show S3LeadAge instead of only S3Lead5=Y/N?

MAR spread across non-zero lead buckets: {mar_spread:.3f}

"""
    if mar_spread >= 0.05:
        doc += (f"**YES — show S3LeadAge.** The MAR spread across lead buckets is {mar_spread:.3f}, "
                "meaning the age of the lead matters materially. A boolean S3Lead5=Y/N collapses "
                "this information. An AFL plot showing bars_since_s3 (color-coded by bucket) "
                "lets the operator see whether the lead is fresh (1–5 bars = strong) or stale "
                "(20–30 bars = weaker). Suggested: show a numeric badge or color gradient on the A3 signal bar.\n")
    else:
        doc += (f"**MARGINAL** — MAR spread across lead buckets is only {mar_spread:.3f}. "
                "A boolean S3Lead5 captures most of the information. LeadAge adds detail "
                "but the ranking benefit is small.\n")

    doc += f"""
### Q5. Best A3 ranking signal?

Options:
A. S3Lead5 boolean (existing)
B. S3LeadAge bucket (new)
C. S3Lead5 + ED filter (combined)

ED at entry by bucket:
"""
    for b in BUCKET_ORDER:
        ed_v = ed_vals.get(b, np.nan)
        doc += f"- {b}: avg ED = {fmt(ed_v, pct=True)}\n"

    doc += f"""
Recommendation:
"""
    if not np.isnan(ed_35) and not np.isnan(ed_nolead):
        if ed_35 < ed_nolead - 0.01:
            doc += (f"**Use S3LeadAge bucket as primary ranking, with ED as secondary filter.**\n\n"
                    f"Rationale: lead_3_5 shows tighter ED ({fmt(ed_35, pct=True)}) vs no_s3_lead "
                    f"({fmt(ed_nolead, pct=True)}). Combining S3LeadAge + ED filters the best setups: "
                    "fresh lead (3–5 bars) + not overextended (ED ≤ 10%).\n\n"
                    "Implementation in ranking:\n"
                    "1. Primary sort: S3LeadAge bucket (lead_3_5 > lead_1_2 > lead_6_10 > ... > no_s3_lead)\n"
                    "2. Secondary sort: ED ascending (tighter = higher rank)\n"
                    "3. Keep as RANKING ONLY — does not block any A3 signal\n")
        else:
            doc += (f"**Use S3Lead5 boolean + ED filter (Option C).**\n\n"
                    "ED within the lead group does not vary sharply enough to justify full bucket ranking. "
                    "Keep S3Lead5 boolean to flag the lead, and rank by ED ascending within each group.\n")
    else:
        doc += "**Use S3Lead5 boolean (Option A)** — insufficient data to distinguish bucket ranking from boolean.\n"

    doc += """
---

## 8. Proposed AFL Change (If Q4/Q5 Support LeadAge)

Current AFL: plots S3Lead5=Y/N at A3 signal bar.

Proposed addition (non-breaking):
```afl
// S3LeadAge display on A3 signal bars
// Does NOT change A3 entry logic. Does NOT gate A3.
// Ranking annotation only.
S3LeadAge = bars_since_s3_signal;   // compute in scan, not AFL
Plot(IIf(A3_signal AND S3LeadAge <= 5,  S3LeadAge, Null), "S3Age", colorGreen,  styleHistogram);
Plot(IIf(A3_signal AND S3LeadAge <= 10, S3LeadAge, Null), "S3Age", colorYellow, styleHistogram);
Plot(IIf(A3_signal AND S3LeadAge <= 30, S3LeadAge, Null), "S3Age", colorGray,   styleHistogram);
```

Scan output: add `s3_lead_age_bars` integer column alongside existing `a3_s3_lead_5d` boolean.
s3_lead_age_bars = 0 if no S3 signal within 60 bars.

---

## 9. Implementation Note

The `a3_s3_lead_5d` field in Phase35 scan is correct and unchanged.
`s3_lead_age_bars` is an ADDITIVE field — it supplements, not replaces, the boolean.

No change to:
- A3 entry rules
- A3 sizing
- A3 TP/trail/max_hold
- Order routing
"""

    (OUT / "LEAD_TIMING_FINDINGS.md").write_text(doc, encoding="utf-8")
    print("  LEAD_TIMING_FINDINGS.md saved", flush=True)

    # ── Terminal summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}", flush=True)
    print("BUCKET SUMMARY:", flush=True)
    for r in summary_rows:
        print(f"  {r['bucket']:20s}  n={r['n_trades']:4d}  MAR={fmt(r['mar'])}  "
              f"CAGR={fmt(r.get('cagr', np.nan), pct=True)}  "
              f"MaxDD={fmt(r.get('max_dd', np.nan), pct=True)}  "
              f"hit={fmt(r.get('hit_rate', np.nan), pct=True)}", flush=True)
    print(f"\nBest bucket: {best_bucket} (MAR={fmt(best_mar)})", flush=True)
    print(f"Output: {OUT}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
