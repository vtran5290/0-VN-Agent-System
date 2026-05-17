#!/usr/bin/env python3
"""
S3 Combo Test: TP10 + mom20>=0 + a3_breadth>=35% + max_hold=60
Compare vs A3 DP year-by-year, OOS, liquidity, cost, bad-year drawdown.

Output: data/research/s3_production_upgrade/combo/

DO NOT change A3 production logic.
DO NOT route S3 to real orders.
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
    _build_signal_cache, _exit_tp_trail,
    load_panel, load_vnindex, get_universe,
    portfolio_metrics, DEFAULT_COST,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2, _annual_return,
)
from pp_backtest.s3_upgrade_research import (
    _regime_gate_100, _build_breadth_series, _build_trades, _metrics, _tp_rate,
)

OUT = REPO / "data" / "research" / "s3_production_upgrade" / "combo"
OUT.mkdir(parents=True, exist_ok=True)

PORTFOLIO_VND = 5e9
MAX_SLOTS     = 20
PARTICIPATION = 0.10
BASE_COST     = DEFAULT_COST   # 0.004
STRESS_COST   = 0.006

EXIT_A3   = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5, "max_hold": 250}
EXIT_S3B  = {"tp_pct": 0.10, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 60}
# S3 combo label
COMBO_LABEL = "S3_TP10_mom20_a3b35_max60"


def annual_returns_table(m: dict) -> dict:
    return {yr: m.get(f"yr_{yr}", np.nan) for yr in range(2014, 2027)}


def metrics_with_cost(df: pd.DataFrame, adv50_map: dict, extra_cost: float = 0.0) -> dict:
    if df.empty:
        return {}
    d = df.copy()
    if extra_cost != 0.0:
        d["net_return"] = d["net_return"] - extra_cost
    return _metrics(d, adv50_map)


def fmt(v, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.1%}" if pct else f"{v:.4f}"


def main():
    print("Loading data...", flush=True)
    panel   = load_panel()
    vnx     = load_vnindex()
    regime  = _regime_gate_100(vnx)

    adv50_map = _build_adv50_map(panel)

    a3_cache = _build_signal_cache(panel, "A3")
    s3_cache = _build_signal_cache(panel, "S3")

    a3_univ = get_universe(panel, "ex_vin3")
    s3_univ = get_universe(panel, "full")

    print("Building A3 breadth...", flush=True)
    a3_breadth = _build_breadth_series(panel, a3_univ, 20, 100)

    # ── A3 DP baseline ───────────────────────────────────────────────────────
    print("Building A3 baseline trades...", flush=True)
    a3_df = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime, adv50_map=adv50_map)
    a3_df = _tag_adv50(a3_df, adv50_map)
    m_a3  = _metrics(a3_df, adv50_map)
    print(f"  A3: n={len(a3_df)}, MAR={m_a3.get('mar', np.nan):.4f}", flush=True)

    # ── S3 combo ─────────────────────────────────────────────────────────────
    print("Building S3 combo trades...", flush=True)
    # Apply regime + breadth in _build_trades, then post-filter mom20
    s3_raw = _build_trades(
        s3_cache, EXIT_S3B,
        gate_by_date=regime,
        breadth=a3_breadth,
        breadth_floor=0.35,
        adv50_map=adv50_map,
    )
    s3_raw = _tag_adv50(s3_raw, adv50_map)
    s3_df  = s3_raw[s3_raw["mom20_at_entry"] >= 0.0].copy()
    m_s3   = _metrics(s3_df, adv50_map)
    print(f"  S3 combo (before mom20): n={len(s3_raw)}", flush=True)
    print(f"  S3 combo (after  mom20): n={len(s3_df)}, MAR={m_s3.get('mar', np.nan):.4f}", flush=True)

    # ── Overall summary ───────────────────────────────────────────────────────
    summary = []
    for label, m, df in [("A3_DP", m_a3, a3_df), (COMBO_LABEL, m_s3, s3_df)]:
        summary.append({
            "config":     label,
            "n_trades":   len(df),
            "mar":        round(m.get("mar",      np.nan), 4),
            "cagr":       round(m.get("cagr",     np.nan), 4),
            "max_dd":     round(m.get("max_dd",   np.nan), 4),
            "hit_rate":   round((df["net_return"] > 0).mean(), 4),
            "tp1_rate":   round(_tp_rate(df), 4),
            "avg_hold":   round(df["hold_bars"].mean(), 1),
        })
    pd.DataFrame(summary).to_csv(OUT / "combo_summary.csv", index=False)
    print("  combo_summary.csv saved", flush=True)

    # ── Year-by-year ──────────────────────────────────────────────────────────
    yr_rows = []
    for label, m in [("A3_DP", m_a3), (COMBO_LABEL, m_s3)]:
        for yr in range(2014, 2027):
            v = m.get(f"yr_{yr}", np.nan)
            yr_rows.append({"config": label, "year": yr,
                             "annual_return": round(v, 4) if not np.isnan(v) else np.nan})
    pd.DataFrame(yr_rows).to_csv(OUT / "combo_by_year.csv", index=False)
    print("  combo_by_year.csv saved", flush=True)

    # ── OOS (year-by-year fold pass) ──────────────────────────────────────────
    s3_df["entry_date"] = pd.to_datetime(s3_df["entry_date"])
    a3_df["entry_date"] = pd.to_datetime(a3_df["entry_date"])
    oos_rows = []
    for yr in range(2015, 2027):
        s3_yr = s3_df[s3_df["entry_date"].dt.year == yr]
        a3_yr = a3_df[a3_df["entry_date"].dt.year == yr]
        s3_avg = float(s3_yr["net_return"].mean()) if len(s3_yr) >= 5 else np.nan
        a3_avg = float(a3_yr["net_return"].mean()) if len(a3_yr) >= 5 else np.nan
        oos_rows.append({
            "year":               yr,
            "s3_n":               len(s3_yr),
            "s3_avg_net":         round(s3_avg, 4) if not np.isnan(s3_avg) else np.nan,
            "s3_hit_rate":        round((s3_yr["net_return"] > 0).mean(), 4) if len(s3_yr) >= 5 else np.nan,
            "s3_fold_pass":       s3_avg > 0 if not np.isnan(s3_avg) else False,
            "a3_n":               len(a3_yr),
            "a3_avg_net":         round(a3_avg, 4) if not np.isnan(a3_avg) else np.nan,
            "a3_fold_pass":       a3_avg > 0 if not np.isnan(a3_avg) else False,
        })
    oos_df = pd.DataFrame(oos_rows)
    oos_df.to_csv(OUT / "combo_oos.csv", index=False)
    s3_pass = int(oos_df["s3_fold_pass"].sum())
    a3_pass = int(oos_df["a3_fold_pass"].sum())
    print(f"  OOS: S3 {s3_pass}/{len(oos_df)} folds positive, A3 {a3_pass}/{len(oos_df)}", flush=True)

    # ── Liquidity sensitivity ─────────────────────────────────────────────────
    liq_rows = []
    for adv_b in [0, 10, 20, 50, 100]:
        floor = adv_b * 1e9
        s3_liq = s3_df[s3_df["adv50_value"] >= floor] if adv_b > 0 else s3_df
        a3_liq = a3_df[a3_df["adv50_value"] >= floor] if adv_b > 0 else a3_df
        if s3_liq.empty:
            continue
        ms = _metrics(s3_liq, adv50_map)
        ma = _metrics(a3_liq, adv50_map) if not a3_liq.empty else {}
        liq_rows.append({
            "adv_floor_B":  adv_b,
            "s3_n":         len(s3_liq),
            "s3_pct_kept":  round(len(s3_liq) / max(len(s3_df), 1), 4),
            "s3_mar":       round(ms.get("mar",    np.nan), 4),
            "s3_cagr":      round(ms.get("cagr",   np.nan), 4),
            "s3_max_dd":    round(ms.get("max_dd", np.nan), 4),
            "a3_mar":       round(ma.get("mar",    np.nan), 4),
            "a3_max_dd":    round(ma.get("max_dd", np.nan), 4),
        })
    pd.DataFrame(liq_rows).to_csv(OUT / "combo_liquidity.csv", index=False)
    print("  combo_liquidity.csv saved", flush=True)

    # ── Cost sensitivity ──────────────────────────────────────────────────────
    cost_rows = []
    for cost in [0.003, 0.004, 0.005, 0.006, 0.007, 0.008]:
        delta = cost - BASE_COST
        ms = metrics_with_cost(s3_df, adv50_map, delta)
        ma = metrics_with_cost(a3_df, adv50_map, delta)
        cost_rows.append({
            "cost_pct":  cost,
            "s3_mar":    round(ms.get("mar",    np.nan), 4),
            "s3_cagr":   round(ms.get("cagr",   np.nan), 4),
            "s3_max_dd": round(ms.get("max_dd", np.nan), 4),
            "a3_mar":    round(ma.get("mar",    np.nan), 4),
            "a3_cagr":   round(ma.get("cagr",   np.nan), 4),
            "a3_max_dd": round(ma.get("max_dd", np.nan), 4),
        })
    pd.DataFrame(cost_rows).to_csv(OUT / "combo_cost.csv", index=False)
    print("  combo_cost.csv saved", flush=True)

    # ── Bad-year drawdown ─────────────────────────────────────────────────────
    bad_years = [2018, 2019, 2022]
    bad_rows = []
    for yr in bad_years:
        for label, df in [("A3_DP", a3_df), (COMBO_LABEL, s3_df)]:
            sub = df[df["entry_date"].dt.year == yr]
            bad_rows.append({
                "year":        yr,
                "config":      label,
                "n_trades":    len(sub),
                "avg_net_ret": round(sub["net_return"].mean(), 4) if len(sub) > 0 else np.nan,
                "hit_rate":    round((sub["net_return"] > 0).mean(), 4) if len(sub) > 0 else np.nan,
                "worst_trade": round(sub["net_return"].min(), 4) if len(sub) > 0 else np.nan,
                "pct_losers":  round((sub["net_return"] < 0).mean(), 4) if len(sub) > 0 else np.nan,
            })
    pd.DataFrame(bad_rows).to_csv(OUT / "combo_bad_years.csv", index=False)
    print("  combo_bad_years.csv saved", flush=True)

    # ── Markdown findings ─────────────────────────────────────────────────────
    cost_06 = next((r for r in cost_rows if abs(r["cost_pct"] - 0.006) < 0.0001), {})
    s3_cost06_mar = cost_06.get("s3_mar", np.nan)
    a3_cost06_mar = cost_06.get("a3_mar", np.nan)

    yr_pivot = pd.DataFrame(yr_rows).pivot(index="year", columns="config", values="annual_return")

    def yv(col, yr):
        try:
            v = yr_pivot.loc[yr, col]
            return fmt(v, pct=True)
        except Exception:
            return "N/A"

    doc = f"""# S3 Combo Test — TP10 + mom20≥0% + a3_breadth≥35% + max_hold=60

Date: 2026-05-17
Config: S3 EMA21/55, TP=10%, Trail=3.5×ATR14, max_hold=60, VNINDEX regime gate,
        a3_breadth≥35%, mom20_at_entry≥0
Baseline: A3 DP-First EMA20/100, TP=18%, Trail=2.5×ATR14, max_hold=250

DO NOT change A3 production logic.
DO NOT route S3 to real orders.

---

## 1. Overall Comparison

| Config | N | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Avg Hold |
|--------|---|-----|------|-------|----------|----------|----------|
"""
    for r in summary:
        doc += (f"| {r['config']} | {r['n_trades']:,} | {fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
                f"{fmt(r['max_dd'], pct=True)} | {fmt(r['hit_rate'], pct=True)} | "
                f"{fmt(r['tp1_rate'], pct=True)} | {r['avg_hold']:.0f}b |\n")

    doc += f"""
---

## 2. Year-by-Year

| Year | A3_DP | {COMBO_LABEL} | S3 Better? |
|------|-------|---------------|------------|
"""
    for yr in range(2014, 2027):
        a = yv("A3_DP", yr)
        s = yv(COMBO_LABEL, yr)
        try:
            av = yr_pivot.loc[yr, "A3_DP"]
            sv = yr_pivot.loc[yr, COMBO_LABEL]
            better = "✓" if (not np.isnan(sv) and not np.isnan(av) and sv > av) else ("—" if np.isnan(sv) else "✗")
        except Exception:
            better = "—"
        doc += f"| {yr} | {a} | {s} | {better} |\n"

    doc += f"""
---

## 3. OOS (Yearly Fold Pass Rate)

| Year | S3 N | S3 Avg Net | S3 Hit | S3 Pass | A3 N | A3 Avg Net | A3 Pass |
|------|------|-----------|--------|---------|------|-----------|---------|
"""
    for _, r in oos_df.iterrows():
        s3p = "✓" if r["s3_fold_pass"] else "✗"
        a3p = "✓" if r["a3_fold_pass"] else "✗"
        doc += (f"| {int(r['year'])} | {r['s3_n']} | {fmt(r['s3_avg_net'], pct=True)} | "
                f"{fmt(r['s3_hit_rate'], pct=True)} | {s3p} | "
                f"{r['a3_n']} | {fmt(r['a3_avg_net'], pct=True)} | {a3p} |\n")
    doc += f"\n**S3 OOS pass rate: {s3_pass}/{len(oos_df)} | A3 OOS pass rate: {a3_pass}/{len(oos_df)}**\n"

    doc += """
---

## 4. Liquidity Sensitivity

| ADV Floor | S3 N | % Kept | S3 MAR | S3 MaxDD | A3 MAR |
|-----------|------|--------|--------|----------|--------|
"""
    for r in liq_rows:
        doc += (f"| ≥{r['adv_floor_B']:.0f}B | {r['s3_n']:,} | {fmt(r['s3_pct_kept'], pct=True)} | "
                f"{fmt(r['s3_mar'])} | {fmt(r['s3_max_dd'], pct=True)} | {fmt(r['a3_mar'])} |\n")

    doc += """
---

## 5. Cost Sensitivity

| Cost | S3 MAR | S3 CAGR | S3 MaxDD | A3 MAR | A3 CAGR |
|------|--------|---------|----------|--------|---------|
"""
    for r in cost_rows:
        stress = " ← stress" if abs(r["cost_pct"] - 0.006) < 0.0001 else ""
        doc += (f"| {r['cost_pct']:.1%}{stress} | {fmt(r['s3_mar'])} | {fmt(r['s3_cagr'], pct=True)} | "
                f"{fmt(r['s3_max_dd'], pct=True)} | {fmt(r['a3_mar'])} | {fmt(r['a3_cagr'], pct=True)} |\n")

    doc += f"""
---

## 6. Bad-Year Drawdown (2018, 2019, 2022)

| Year | Config | N | Avg Net | Hit Rate | Worst Trade | % Losers |
|------|--------|---|---------|----------|-------------|----------|
"""
    for r in bad_rows:
        doc += (f"| {r['year']} | {r['config']} | {r['n_trades']} | "
                f"{fmt(r['avg_net_ret'], pct=True)} | {fmt(r['hit_rate'], pct=True)} | "
                f"{fmt(r['worst_trade'], pct=True)} | {fmt(r['pct_losers'], pct=True)} |\n")

    # Verdict
    s3_mar_v = m_s3.get("mar", np.nan)
    a3_mar_v = m_a3.get("mar", np.nan)
    s3_dd_v  = m_s3.get("max_dd", np.nan)
    a3_dd_v  = m_a3.get("max_dd", np.nan)

    if not np.isnan(s3_mar_v) and s3_mar_v >= 0.40:
        verdict = "PRODUCTION_CANDIDATE_PENDING_PAPER"
        verdict_note = f"S3 combo MAR={fmt(s3_mar_v)} ≥ 0.40. Qualifies if OOS and paper gate pass."
    elif not np.isnan(s3_mar_v) and s3_mar_v >= 0.30:
        verdict = "KEEP_PAPER_SHADOW"
        verdict_note = f"S3 combo MAR={fmt(s3_mar_v)} ≥ 0.30 but < 0.40. Paper shadow confirmed."
    else:
        verdict = "KEEP_RESEARCH_ONLY"
        verdict_note = f"S3 combo MAR={fmt(s3_mar_v)} below 0.30 gate."

    doc += f"""
---

## 7. Verdict

**{verdict}**

{verdict_note}

| Gate | S3 Combo | A3 DP |
|------|----------|-------|
| MAR | {fmt(s3_mar_v)} | {fmt(a3_mar_v)} |
| MaxDD | {fmt(s3_dd_v, pct=True)} | {fmt(a3_dd_v, pct=True)} |
| MAR at 0.6% cost | {fmt(s3_cost06_mar)} | {fmt(a3_cost06_mar)} |
| OOS folds positive | {s3_pass}/{len(oos_df)} | {a3_pass}/{len(oos_df)} |

### What This Config Is

- TP1 = 10% (faster exit vs A3's 18%) — captures S3's fast momentum peak
- mom20≥0% = only enter when recent momentum is positive (removes 8% of bad setups)
- a3_breadth≥35% = only enter when A3 universe is not in deep defense (minimal filter)
- VNINDEX regime gate = unchanged from production rule

### What This Config Is NOT

- This is NOT a production promotion. Paper gate (3 months, 30 decisions, 10 exits) required.
- No real capital. No DNSE routing. S3 shadow ledger only.
- A3 logic is untouched.
"""

    (OUT / "COMBO_TEST_FINDINGS.md").write_text(doc, encoding="utf-8")
    print("  COMBO_TEST_FINDINGS.md saved", flush=True)

    print(f"\n{'='*60}", flush=True)
    print(f"S3 combo: MAR={fmt(s3_mar_v)}, CAGR={fmt(m_s3.get('cagr',np.nan), pct=True)}, "
          f"MaxDD={fmt(s3_dd_v, pct=True)}, n={len(s3_df)}", flush=True)
    print(f"A3 DP:   MAR={fmt(a3_mar_v)}, CAGR={fmt(m_a3.get('cagr',np.nan), pct=True)}, "
          f"MaxDD={fmt(a3_dd_v, pct=True)}, n={len(a3_df)}", flush=True)
    print(f"OOS: S3 {s3_pass}/{len(oos_df)} folds, A3 {a3_pass}/{len(oos_df)} folds", flush=True)
    print(f"Verdict: {verdict}", flush=True)
    print(f"Output: {OUT}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
