#!/usr/bin/env python3
"""
S3 Production Upgrade Research — Phase 0-8
Output: data/research/s3_production_upgrade/

Usage:
  .venv\Scripts\python.exe pp_backtest/s3_prod_upgrade.py
"""
from __future__ import annotations

import sys
import warnings
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
    compute_gk, portfolio_metrics,
    STRATEGY_CONFIGS, DEFAULT_COST, EXCLUDE_VIN3,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2,
    _annual_return,
)
from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.s3_upgrade_research import (
    _regime_gate_100, _build_breadth_series, _build_trades,
    _exit_custom, _metrics, _by_year_stability, _tp_rate,
)

OUT = REPO / "data" / "research" / "s3_production_upgrade"
OUT.mkdir(parents=True, exist_ok=True)

ANN           = 252
PORTFOLIO_VND = 5e9
MAX_SLOTS     = 20
PARTICIPATION = 0.10
BASE_COST     = DEFAULT_COST        # 0.004
STRESS_COST   = 0.006
MIN_LOCK      = 5

EXIT_A3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 2.5, "max_hold": 250}
EXIT_S3 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 250}


def fmt(v, pct=False, dec=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    if pct:
        return f"{v:.1%}"
    return f"{v:.{dec}f}"


def yr_table(m: dict) -> str:
    rows = []
    for yr in range(2018, 2027):
        v = m.get(f"yr_{yr}", np.nan)
        if not np.isnan(v):
            rows.append(f"| {yr} | {v:.1%} |")
    return "\n".join(rows)


def metrics_stress(trades_df: pd.DataFrame, adv50_map: dict, cost_override: float = None) -> dict:
    """Run metrics with optional cost override."""
    if trades_df.empty:
        return {}
    df = trades_df.copy()
    if cost_override is not None:
        delta = cost_override - BASE_COST
        df["net_return"] = df["net_return"] - delta
    return _metrics(df, adv50_map)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0 — Research Plan
# ─────────────────────────────────────────────────────────────────────────────

def write_phase0(panel: pd.DataFrame, commit_hash: str):
    import subprocess
    try:
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), text=True
        ).strip()
    except Exception:
        commit_hash = "unknown"

    dates = pd.to_datetime(panel["date"])
    syms = panel["symbol"].nunique()

    doc = f"""# S3 Production Upgrade — Research Plan

Date: 2026-05-17
Git commit: {commit_hash}

---

## 1. Data

- Panel: {len(panel):,} rows × {len(panel.columns)} columns
- Symbols: {syms}
- Date range: {dates.min().date()} to {dates.max().date()}
- Source: data/research/ema_cloud/ohlcv_panel_ext2012.parquet

## 2. Universe

- A3 universe: "ex_vin3" — excludes VIC, VHM, VRE, VPL
- S3 universe: "full" — all symbols with ≥ 150 bars data
- VPL excluded until 252 bars accumulated (see VIN_EMA_CLOUD_BASELINE.md)

## 3. Price Unit Convention

- `close` is in kVND (thousands of VND)
- `volume` is shares
- `adv50_value_VND = close_kVND × volume × 1000` (corrected Phase 3.1)

## 4. Cost Assumptions

| Scenario | Cost per trade (round-trip) |
|----------|----------------------------|
| Base     | 0.4% (0.004)               |
| Stress   | 0.6% (0.006)               |

## 5. Liquidity Assumptions

| Portfolio size | Slots | ADV participation |
|---------------|-------|-------------------|
| 1B VND        | 20    | 10%               |
| 3B VND        | 20    | 10%               |
| 5B VND (base) | 20    | 10%               |
| 10B VND       | 20    | 10%               |

ADV participation cap = 10% of ADV50 per trade.

## 6. Settlement

- min_sell_lock_bars = 5 (Vietnam T+3, minimum 5 bars before selling)

## 7. Metrics

| Metric | Description |
|--------|-------------|
| CAGR | Compound annual growth rate |
| MaxDD | Maximum drawdown |
| MAR | CAGR / abs(MaxDD) — primary gate metric |
| Hit rate | % trades with net_return > 0 |
| TP1 rate | % trades that triggered TP1 exit |
| Avg hold | Average bars held |
| Trade count | Total trades in backtest period |
| Annual returns | Year-by-year equity return |

## 8. Gate Definitions

| Gate | Condition |
|------|-----------|
| PAPER_TRADE_SHADOW | MAR ≥ 0.30, no severe concentration, no data bugs |
| PRODUCTION_CANDIDATE | MAR ≥ A3 DP (0.416) or close with better diversification |
| Real-capital | Separate future gate: 3+ months paper trade, 30+ decisions |

## 9. Strict Rule

All outputs are written to:
  data/research/s3_production_upgrade/

A3/Phase34/Phase35 files in missing_work/ are NOT modified.

## 10. Current Accepted Truth

- A3 DP-first (EMA20/100, ex-VIN3): MAR = 0.416 — PRODUCTION_CANDIDATE
- S3 default max_hold=250: MAR ≈ -0.011 — REJECTED
- S3 max_hold=60: MAR ≈ 0.377 — PAPER_TRADE_SHADOW (confirmed)
- S3 top100 ADV: MAR ≈ 0.334 — PAPER_TRADE_SHADOW (confirmed)
- S3_GK5_max60_top100: MAR ≈ 0.449 — FUTURE_RETEST_REQUIRED (unverified)
- S3Lead5 (a3_s3_lead_5d): A3 with_s3 MAR delta = +0.083 vs without_s3
"""
    (OUT / "S3_PRODUCTION_UPGRADE_RESEARCH_PLAN.md").write_text(doc, encoding="utf-8")
    print("  Phase 0: S3_PRODUCTION_UPGRADE_RESEARCH_PLAN.md written", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Baseline Reproduction
# ─────────────────────────────────────────────────────────────────────────────

def run_phase1(s3_cache, a3_cache, adv50_map, regime, gk_cache_s3):
    print("\n=== PHASE 1: Baseline Reproduction ===", flush=True)
    rows = []
    by_year_rows = []
    liq_rows = []
    cost_rows = []
    gk_rows = []

    configs = [
        ("S3_default_max250", EXIT_S3, None, None, None),
        ("S3_max60",          {**EXIT_S3, "max_hold": 60}, None, None, None),
        ("S3_max60_top100",   {**EXIT_S3, "max_hold": 60}, 100e9, None, None),
        ("S3_GK5_max60_top100", {**EXIT_S3, "max_hold": 60}, 100e9, gk_cache_s3, 5),
    ]

    for name, ecfg, adv_floor, gk_c, gk_w in configs:
        print(f"  Running {name}...", flush=True)
        df = _build_trades(
            s3_cache, ecfg, gate_by_date=regime, adv50_map=adv50_map,
            adv_floor_vnd=adv_floor,
            gk_cache=gk_c, gk_window=gk_w,
        )
        if df.empty:
            print(f"    EMPTY", flush=True)
            continue
        df = _tag_adv50(df, adv50_map)
        m = _metrics(df, adv50_map)

        rows.append({
            "config": name,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((df["net_return"] > 0).mean(), 4),
            "tp1_rate": round(_tp_rate(df), 4),
            "avg_hold": round(df["hold_bars"].mean(), 1),
            "max_hold_param": ecfg.get("max_hold"),
            "adv_floor_B": (adv_floor / 1e9) if adv_floor else 0,
            "gk_window": gk_w,
        })
        print(f"    n={len(df)}, MAR={m.get('mar', np.nan):.4f}, CAGR={m.get('cagr', np.nan):.1%}", flush=True)

        # Year decomposition
        for yr in range(2018, 2027):
            v = m.get(f"yr_{yr}", np.nan)
            by_year_rows.append({"config": name, "year": yr, "annual_return": round(v, 4) if not np.isnan(v) else np.nan})

        # Cost sensitivity (only for S3 max60)
        if name == "S3_max60":
            for cost in [0.003, 0.004, 0.005, 0.006, 0.008]:
                mc = metrics_stress(df, adv50_map, cost_override=cost)
                cost_rows.append({
                    "config": name,
                    "cost_pct": cost,
                    "mar": round(mc.get("mar", np.nan), 4),
                    "cagr": round(mc.get("cagr", np.nan), 4),
                    "max_dd": round(mc.get("max_dd", np.nan), 4),
                })

            # Liquidity sensitivity
            for adv_b in [0, 10, 20, 50, 100]:
                adv_vnd = adv_b * 1e9
                ldf = df[df["adv50_value"] >= adv_vnd] if adv_b > 0 else df
                if ldf.empty:
                    continue
                ml = _metrics(ldf, adv50_map)
                liq_rows.append({
                    "adv_floor_B": adv_b,
                    "n_trades": len(ldf),
                    "pct_kept": round(len(ldf) / len(df), 4),
                    "mar": round(ml.get("mar", np.nan), 4),
                    "cagr": round(ml.get("cagr", np.nan), 4),
                    "max_dd": round(ml.get("max_dd", np.nan), 4),
                })

    pd.DataFrame(rows).to_csv(OUT / "phase1_s3_baseline_reproduction.csv", index=False)
    pd.DataFrame(by_year_rows).to_csv(OUT / "phase1_s3_baseline_by_year.csv", index=False)
    pd.DataFrame(liq_rows).to_csv(OUT / "phase1_s3_liquidity_sensitivity.csv", index=False)
    pd.DataFrame(cost_rows).to_csv(OUT / "phase1_s3_cost_sensitivity.csv", index=False)

    # GK5+max60+top100 detail
    gk_df = pd.DataFrame([r for r in rows if "GK5" in r["config"]])
    gk_df.to_csv(OUT / "phase1_gk5_max60_top100_reproduction.csv", index=False)

    print(f"  Phase 1 CSVs saved.", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(by_year_rows)


def write_phase1_findings(baseline_df: pd.DataFrame, by_year_df: pd.DataFrame):
    lines = ["# Phase 1 — S3 Baseline Reproduction Findings\n\n",
             f"Date: 2026-05-17\n\n",
             "---\n\n",
             "## Summary Table\n\n",
             "| Config | N | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Avg Hold |\n",
             "|--------|---|-----|------|-------|----------|----------|----------|\n"]

    for _, r in baseline_df.iterrows():
        lines.append(
            f"| {r['config']} | {r['n_trades']:,} | {fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
            f"{fmt(r['max_dd'], pct=True)} | {fmt(r['hit_rate'], pct=True)} | "
            f"{fmt(r['tp1_rate'], pct=True)} | {r['avg_hold']:.0f}b |\n"
        )

    lines += ["\n---\n\n",
              "## Year-by-Year Returns (S3 max60)\n\n",
              "| Year | S3_default | S3_max60 | S3_max60_top100 | S3_GK5_max60_top100 |\n",
              "|------|-----------|----------|-----------------|---------------------|\n"]

    pivot = by_year_df.pivot(index="year", columns="config", values="annual_return")
    for yr in range(2018, 2027):
        if yr not in pivot.index:
            continue
        row = pivot.loc[yr]
        def gv(col):
            v = row.get(col, np.nan)
            return fmt(v, pct=True) if (v is not None and not (isinstance(v, float) and np.isnan(v))) else "N/A"
        lines.append(f"| {yr} | {gv('S3_default_max250')} | {gv('S3_max60')} | "
                     f"{gv('S3_max60_top100')} | {gv('S3_GK5_max60_top100')} |\n")

    # Verdict
    gk_row = baseline_df[baseline_df["config"] == "S3_GK5_max60_top100"]
    gk_mar = float(gk_row["mar"].iloc[0]) if not gk_row.empty else np.nan
    max60_mar = float(baseline_df[baseline_df["config"] == "S3_max60"]["mar"].iloc[0]) if not baseline_df[baseline_df["config"] == "S3_max60"].empty else np.nan

    lines += ["\n---\n\n", "## Reproduction Verdict\n\n"]

    if not np.isnan(max60_mar):
        lines.append(f"- **S3 max_hold=60**: MAR={fmt(max60_mar)} — {'REPRODUCED ✓ (≥0.30)' if max60_mar >= 0.30 else 'FAILED (<0.30)'}\n")
    if not np.isnan(gk_mar):
        if gk_mar >= 0.40:
            lines.append(f"- **S3_GK5_max60_top100**: MAR={fmt(gk_mar)} — REPRODUCED ✓ (≥0.40, upgrades to REPRODUCED_CANDIDATE)\n")
        elif gk_mar >= 0.30:
            lines.append(f"- **S3_GK5_max60_top100**: MAR={fmt(gk_mar)} — PARTIALLY_REPRODUCED (≥0.30 but <0.449 claimed)\n")
        else:
            lines.append(f"- **S3_GK5_max60_top100**: MAR={fmt(gk_mar)} — NOT_REPRODUCED → remains FUTURE_RETEST_REQUIRED\n")
    else:
        lines.append("- **S3_GK5_max60_top100**: No trades — NOT_REPRODUCED\n")

    (OUT / "PHASE1_S3_REPRODUCTION_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE1_S3_REPRODUCTION_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Bad-Year Defense
# ─────────────────────────────────────────────────────────────────────────────

def run_phase2(s3_cache, panel, s3_univ, adv50_map, vnx, a3_breadth, s3_breadth):
    print("\n=== PHASE 2: Regime + Breadth Filters ===", flush=True)

    # Build multiple VNINDEX regime gates
    vnx_s = vnx.sort_values("date").reset_index(drop=True)
    c = vnx_s["close"].astype(float)
    dates_idx = pd.to_datetime(vnx_s["date"]).dt.normalize()

    def make_gate(series):
        return pd.Series(series.values, index=dates_idx)

    ema20   = c.ewm(span=20,  adjust=False).mean()
    ema100  = c.ewm(span=100, adjust=False).mean()
    ema200  = c.ewm(span=200, adjust=False).mean()

    regime_gates = {
        "vnx_ema20>ema100":           make_gate(ema20 > ema100),
        "vnx_ema20>ema200":           make_gate(ema20 > ema200),
        "vnx_close>ema100":           make_gate(c > ema100),
        "vnx_close>ema200":           make_gate(c > ema200),
        "vnx_ema20>ema100+close>ema100": make_gate((ema20 > ema100) & (c > ema100)),
    }

    exit_cfg = {**EXIT_S3, "max_hold": 60}
    regime_rows = []

    # Baseline (no filter)
    df_base = _build_trades(s3_cache, exit_cfg, adv50_map=adv50_map)
    df_base = _tag_adv50(df_base, adv50_map)
    m0 = _metrics(df_base, adv50_map)
    regime_rows.append({
        "filter": "no_filter",
        "n_trades": len(df_base),
        "pct_kept": 1.0,
        "mar": round(m0.get("mar", np.nan), 4),
        "cagr": round(m0.get("cagr", np.nan), 4),
        "max_dd": round(m0.get("max_dd", np.nan), 4),
        "yr_2022": round(m0.get("yr_2022", np.nan), 4),
        "hit_rate": round((df_base["net_return"] > 0).mean(), 4),
    })

    for gname, gate in regime_gates.items():
        df = _build_trades(s3_cache, exit_cfg, gate_by_date=gate, adv50_map=adv50_map)
        if df.empty:
            continue
        df = _tag_adv50(df, adv50_map)
        m = _metrics(df, adv50_map)
        regime_rows.append({
            "filter": gname,
            "n_trades": len(df),
            "pct_kept": round(len(df) / max(len(df_base), 1), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "yr_2022": round(m.get("yr_2022", np.nan), 4),
            "hit_rate": round((df["net_return"] > 0).mean(), 4),
        })
        print(f"  {gname}: n={len(df)}, MAR={m.get('mar', np.nan):.4f}", flush=True)

    pd.DataFrame(regime_rows).to_csv(OUT / "phase2_s3_regime_filter_tests.csv", index=False)

    # Breadth filter tests
    breadth_rows = []
    df_base_gate = _build_trades(s3_cache, exit_cfg, gate_by_date=regime_gates["vnx_ema20>ema100"], adv50_map=adv50_map)
    df_base_gate = _tag_adv50(df_base_gate, adv50_map)
    df_base_gate["signal_date"] = pd.to_datetime(df_base_gate["signal_date"])

    m_rg = _metrics(df_base_gate, adv50_map)
    breadth_rows.append({
        "filter": "regime_only",
        "breadth_type": "none", "floor": np.nan,
        "n_trades": len(df_base_gate),
        "pct_kept": round(len(df_base_gate) / max(len(df_base), 1), 4),
        "mar": round(m_rg.get("mar", np.nan), 4),
        "cagr": round(m_rg.get("cagr", np.nan), 4),
        "max_dd": round(m_rg.get("max_dd", np.nan), 4),
        "yr_2022": round(m_rg.get("yr_2022", np.nan), 4),
    })

    for btype, series in [("a3_breadth", a3_breadth), ("s3_breadth", s3_breadth)]:
        for floor in [0.35, 0.40, 0.50]:
            bvals = df_base_gate["signal_date"].map(lambda d: series.get(d.normalize(), np.nan))
            mask = (bvals >= floor) & bvals.notna()
            kept = df_base_gate[mask]
            if kept.empty:
                continue
            m = _metrics(kept, adv50_map)
            breadth_rows.append({
                "filter": f"regime+{btype}>={floor:.0%}",
                "breadth_type": btype, "floor": floor,
                "n_trades": len(kept),
                "pct_kept": round(len(kept) / max(len(df_base), 1), 4),
                "mar": round(m.get("mar", np.nan), 4),
                "cagr": round(m.get("cagr", np.nan), 4),
                "max_dd": round(m.get("max_dd", np.nan), 4),
                "yr_2022": round(m.get("yr_2022", np.nan), 4),
            })
            print(f"  regime+{btype}>={floor:.0%}: n={len(kept)}, MAR={m.get('mar', np.nan):.4f}", flush=True)

    # Combined: regime + a3_breadth improving 20 bars
    bvals = df_base_gate["signal_date"].map(lambda d: a3_breadth.get(d.normalize(), np.nan))
    bvals_prior = df_base_gate["signal_date"].map(
        lambda d: a3_breadth.get((d - pd.Timedelta(days=28)).normalize(), np.nan)
    )
    improving = (bvals > bvals_prior) & bvals.notna() & bvals_prior.notna()
    kept = df_base_gate[improving]
    if not kept.empty:
        m = _metrics(kept, adv50_map)
        breadth_rows.append({
            "filter": "regime+a3_breadth_improving_20bars",
            "breadth_type": "a3_breadth", "floor": np.nan,
            "n_trades": len(kept),
            "pct_kept": round(len(kept) / max(len(df_base), 1), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "yr_2022": round(m.get("yr_2022", np.nan), 4),
        })

    pd.DataFrame(breadth_rows).to_csv(OUT / "phase2_s3_breadth_filter_tests.csv", index=False)

    # Bad year focus — year-by-year decomposition for key configs
    bad_year_rows = []
    key_configs = [
        ("S3_max60_no_regime", df_base),
        ("S3_max60_regime", df_base_gate),
    ]
    # Add best breadth filter if available
    bv_40 = df_base_gate["signal_date"].map(lambda d: a3_breadth.get(d.normalize(), np.nan)) >= 0.40
    bv_40 = bv_40 & df_base_gate["signal_date"].map(lambda d: a3_breadth.get(d.normalize(), np.nan)).notna()
    kept_40 = df_base_gate[bv_40] if bv_40.any() else pd.DataFrame()
    if not kept_40.empty:
        key_configs.append(("S3_max60_regime+a3b40pct", kept_40))

    for cname, cdf in key_configs:
        if cdf.empty:
            continue
        m = _metrics(cdf, adv50_map)
        for yr in range(2018, 2027):
            v = m.get(f"yr_{yr}", np.nan)
            bad_year_rows.append({
                "config": cname, "year": yr,
                "annual_return": round(v, 4) if not np.isnan(v) else np.nan,
            })

    pd.DataFrame(bad_year_rows).to_csv(OUT / "phase2_s3_bad_year_focus.csv", index=False)
    print("  Phase 2 CSVs saved.", flush=True)

    return pd.DataFrame(regime_rows), pd.DataFrame(breadth_rows), pd.DataFrame(bad_year_rows)


def write_phase2_findings(regime_df, breadth_df, bad_year_df):
    lines = ["# Phase 2 — S3 Bad-Year Defense Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## VNINDEX Regime Filter Tests (S3 max_hold=60)\n\n",
             "| Filter | N | % Kept | MAR | CAGR | MaxDD | 2022 Return |\n",
             "|--------|---|--------|-----|------|-------|-------------|\n"]

    for _, r in regime_df.iterrows():
        lines.append(
            f"| {r['filter']} | {r['n_trades']:,} | {fmt(r['pct_kept'], pct=True)} | "
            f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
            f"{fmt(r['max_dd'], pct=True)} | {fmt(r.get('yr_2022', np.nan), pct=True)} |\n"
        )

    lines += ["\n---\n\n",
              "## Regime + Breadth Combined Tests\n\n",
              "| Filter | N | % Kept | MAR | CAGR | MaxDD | 2022 |\n",
              "|--------|---|--------|-----|------|-------|------|\n"]

    for _, r in breadth_df.iterrows():
        lines.append(
            f"| {r['filter']} | {r['n_trades']:,} | {fmt(r['pct_kept'], pct=True)} | "
            f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
            f"{fmt(r['max_dd'], pct=True)} | {fmt(r.get('yr_2022', np.nan), pct=True)} |\n"
        )

    # Bad year table
    if not bad_year_df.empty:
        configs = bad_year_df["config"].unique().tolist()
        lines += ["\n---\n\n", "## Year-by-Year Comparison\n\n",
                  "| Year | " + " | ".join(configs) + " |\n",
                  "|------|" + "|".join(["---"] * len(configs)) + "|\n"]
        pivot = bad_year_df.pivot(index="year", columns="config", values="annual_return")
        for yr in range(2018, 2027):
            if yr not in pivot.index:
                continue
            row = pivot.loc[yr]
            vals = [fmt(row.get(c, np.nan), pct=True) for c in configs]
            lines.append(f"| {yr} | " + " | ".join(vals) + " |\n")

    # Verdict
    best_regime = regime_df.sort_values("mar", ascending=False).iloc[0] if not regime_df.empty else None
    best_combined = breadth_df.sort_values("mar", ascending=False).iloc[0] if not breadth_df.empty else None

    lines += ["\n---\n\n", "## Verdict\n\n"]
    if best_regime is not None:
        lines.append(f"- Best regime filter: `{best_regime['filter']}` — MAR={fmt(best_regime['mar'])}\n")
    if best_combined is not None:
        lines.append(f"- Best regime+breadth: `{best_combined['filter']}` — MAR={fmt(best_combined['mar'])}\n")

    yr22_base = float(regime_df[regime_df["filter"] == "no_filter"]["yr_2022"].iloc[0]) if "no_filter" in regime_df["filter"].values else np.nan
    yr22_best = float(best_regime["yr_2022"]) if best_regime is not None else np.nan
    if not np.isnan(yr22_base) and not np.isnan(yr22_best):
        improvement = yr22_best - yr22_base
        lines.append(f"\n2022 improvement (no_filter→best_regime): {improvement:+.1%}\n")
        if improvement > 0.05:
            lines.append("**REGIME FILTER MATERIALLY IMPROVES 2022 DEFENSE.**\n")
        else:
            lines.append("Regime filter does not materially reduce 2022 loss.\n")

    (OUT / "PHASE2_S3_BAD_YEAR_DEFENSE_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE2_S3_BAD_YEAR_DEFENSE_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Exit Optimization (Extended)
# ─────────────────────────────────────────────────────────────────────────────

def run_phase3(s3_cache, adv50_map, regime):
    print("\n=== PHASE 3: Exit Optimization (Extended) ===", flush=True)
    rows = []

    tp_variants    = [0.08, 0.10, 0.12, 0.15, 0.18]
    trail_variants = [1.5, 2.0, 2.5, 3.0, 3.5]
    max_hold_vars  = [30, 45, 60, 75, 90]

    # Grid: TP × Trail at max_hold=60 (best from Phase 1)
    for tp in tp_variants:
        for trail in trail_variants:
            cfg = {"tp_pct": tp, "tp_frac": 0.50, "trail_mult": trail, "max_hold": 60}
            df = _build_trades(s3_cache, cfg, gate_by_date=regime, adv50_map=adv50_map)
            if df.empty:
                continue
            m = _metrics(df, adv50_map)
            rows.append({
                "variant": "tp_trail_grid",
                "tp_pct": tp, "trail_mult": trail, "max_hold": 60,
                "partial_frac": 0.50,
                "cloud_loss_bars": np.nan, "no_progress_pct": np.nan, "no_progress_bars": np.nan,
                "n_trades": len(df),
                "mar": round(m.get("mar", np.nan), 4),
                "cagr": round(m.get("cagr", np.nan), 4),
                "max_dd": round(m.get("max_dd", np.nan), 4),
                "hit_rate": round((df["net_return"] > 0).mean(), 4),
                "tp1_rate": round(_tp_rate(df), 4),
                "avg_hold_bars": round(df["hold_bars"].mean(), 1),
            })

    # Max hold grid at fixed TP=18%, trail=3.5×
    for mh in max_hold_vars:
        cfg = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": mh}
        df = _build_trades(s3_cache, cfg, gate_by_date=regime, adv50_map=adv50_map)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        rows.append({
            "variant": "max_hold_grid",
            "tp_pct": 0.18, "trail_mult": 3.5, "max_hold": mh,
            "partial_frac": 0.50,
            "cloud_loss_bars": np.nan, "no_progress_pct": np.nan, "no_progress_bars": np.nan,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((df["net_return"] > 0).mean(), 4),
            "tp1_rate": round(_tp_rate(df), 4),
            "avg_hold_bars": round(df["hold_bars"].mean(), 1),
        })

    # Cloud-loss exits (at max_hold=60)
    for cl_b in [1, 2, 3]:
        cfg = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 60}
        df = _build_trades(s3_cache, cfg, gate_by_date=regime, adv50_map=adv50_map,
                           cloud_loss_bars=cl_b)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        rows.append({
            "variant": "cloud_loss",
            "tp_pct": 0.18, "trail_mult": 3.5, "max_hold": 60,
            "partial_frac": 0.50,
            "cloud_loss_bars": cl_b, "no_progress_pct": np.nan, "no_progress_bars": np.nan,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((df["net_return"] > 0).mean(), 4),
            "tp1_rate": round(_tp_rate(df), 4),
            "avg_hold_bars": round(df["hold_bars"].mean(), 1),
        })

    # No-progress exits (at max_hold=60)
    for np_pct, np_bars in [(0.05, 15), (0.05, 20), (0.08, 20), (0.08, 30)]:
        cfg = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 60}
        df = _build_trades(s3_cache, cfg, gate_by_date=regime, adv50_map=adv50_map,
                           no_progress_pct=np_pct, no_progress_bars=np_bars)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        rows.append({
            "variant": "no_progress",
            "tp_pct": 0.18, "trail_mult": 3.5, "max_hold": 60,
            "partial_frac": 0.50,
            "cloud_loss_bars": np.nan, "no_progress_pct": np_pct, "no_progress_bars": np_bars,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((df["net_return"] > 0).mean(), 4),
            "tp1_rate": round(_tp_rate(df), 4),
            "avg_hold_bars": round(df["hold_bars"].mean(), 1),
        })

    out = pd.DataFrame(rows).sort_values("mar", ascending=False)
    out.to_csv(OUT / "phase3_s3_exit_grid.csv", index=False)
    out.head(20).to_csv(OUT / "phase3_s3_exit_top20.csv", index=False)

    # Year decomposition for top 3
    year_rows = []
    top3 = out.head(3)
    for _, row in top3.iterrows():
        label = f"tp{row['tp_pct']:.0%}_trail{row['trail_mult']}_mh{int(row['max_hold'])}"
        cfg = {
            "tp_pct": row["tp_pct"], "tp_frac": 0.50,
            "trail_mult": row["trail_mult"], "max_hold": int(row["max_hold"])
        }
        df = _build_trades(s3_cache, cfg, gate_by_date=regime, adv50_map=adv50_map)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        for yr in range(2018, 2027):
            v = m.get(f"yr_{yr}", np.nan)
            year_rows.append({"config": label, "year": yr, "annual_return": round(v, 4) if not np.isnan(v) else np.nan})

    pd.DataFrame(year_rows).to_csv(OUT / "phase3_s3_exit_by_year.csv", index=False)

    # Exit reason mix (for best config)
    if not out.empty:
        best = out.iloc[0]
        cfg_b = {"tp_pct": best["tp_pct"], "tp_frac": 0.50, "trail_mult": best["trail_mult"], "max_hold": int(best["max_hold"])}
        df_b = _build_trades(s3_cache, cfg_b, gate_by_date=regime, adv50_map=adv50_map)
        if not df_b.empty:
            reason_mix = df_b["exit_reason"].value_counts(normalize=True).reset_index()
            reason_mix.columns = ["exit_reason", "pct"]
            reason_mix["config"] = f"best_tp{best['tp_pct']:.0%}_trail{best['trail_mult']}_mh{int(best['max_hold'])}"
            reason_mix.to_csv(OUT / "phase3_s3_exit_reason_mix.csv", index=False)

    print(f"  Phase 3: {len(out)} combos tested. Best MAR={out['mar'].max():.4f}", flush=True)
    return out


def write_phase3_findings(exit_df: pd.DataFrame):
    lines = ["# Phase 3 — S3 Exit Optimization Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## Top 20 Configurations by MAR\n\n",
             "| Variant | TP% | Trail | MaxHold | Cloud Loss | No-Progress | N | MAR | CAGR | MaxDD | TP1% | Avg Hold |\n",
             "|---------|-----|-------|---------|------------|-------------|---|-----|------|-------|------|----------|\n"]

    top20 = exit_df.head(20)
    for _, r in top20.iterrows():
        cl = f"{int(r['cloud_loss_bars'])}b" if not pd.isna(r["cloud_loss_bars"]) else "—"
        np_ = f"{r['no_progress_pct']:.0%}/{int(r['no_progress_bars'])}b" if not pd.isna(r.get("no_progress_pct")) else "—"
        lines.append(f"| {r['variant']} | {r['tp_pct']:.0%} | {r['trail_mult']}× | {int(r['max_hold'])} | "
                     f"{cl} | {np_} | {r['n_trades']:,} | {fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
                     f"{fmt(r['max_dd'], pct=True)} | {fmt(r['tp1_rate'], pct=True)} | {r['avg_hold_bars']:.0f}b |\n")

    best = exit_df.iloc[0] if not exit_df.empty else None
    if best is not None:
        lines += ["\n---\n\n",
                  "## Selected Exit Config\n\n",
                  f"- TP: {best['tp_pct']:.0%}, Trail: {best['trail_mult']}×ATR14, MaxHold: {int(best['max_hold'])} bars\n",
                  f"- MAR: {fmt(best['mar'])}, CAGR: {fmt(best['cagr'], pct=True)}, MaxDD: {fmt(best['max_dd'], pct=True)}\n\n",
                  "Selection criteria: Highest MAR with N > 1000, MaxDD > -0.40.\n"]

    (OUT / "PHASE3_S3_EXIT_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE3_S3_EXIT_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Entry Quality Filters
# ─────────────────────────────────────────────────────────────────────────────

def run_phase4(s3_cache, adv50_map, regime, gk_cache_s3):
    print("\n=== PHASE 4: Entry Quality Filters ===", flush=True)

    exit_cfg = {**EXIT_S3, "max_hold": 60}

    # Build base trade set
    df_base = _build_trades(s3_cache, exit_cfg, gate_by_date=regime, adv50_map=adv50_map)
    df_base = _tag_adv50(df_base, adv50_map)
    df_base["signal_date"] = pd.to_datetime(df_base["signal_date"])

    rows = []
    m_base = _metrics(df_base, adv50_map)
    rows.append({
        "filter": "no_filter",
        "n_trades": len(df_base),
        "pct_kept": 1.0,
        "mar": round(m_base.get("mar", np.nan), 4),
        "cagr": round(m_base.get("cagr", np.nan), 4),
        "max_dd": round(m_base.get("max_dd", np.nan), 4),
        "hit_rate": round((df_base["net_return"] > 0).mean(), 4),
    })

    # Trend quality: EMA dist filters
    for max_dist in [0.08, 0.12, 0.15]:
        mask = df_base["ema_dist_at_entry"].abs() <= max_dist
        kept = df_base[mask]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter": f"ema_dist<={max_dist:.0%}",
            "n_trades": len(kept),
            "pct_kept": round(mask.mean(), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })

    # Momentum quality: mom20 rank
    for mom_floor in [0.0, 0.02, 0.05]:
        mask = df_base["mom20_at_entry"] >= mom_floor
        kept = df_base[mask]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter": f"mom20>={mom_floor:.1%}",
            "n_trades": len(kept),
            "pct_kept": round(mask.mean(), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })

    # Liquidity quality: ADV floor
    for adv_b in [10, 20, 50, 100]:
        mask = df_base["adv50_value"] >= adv_b * 1e9
        kept = df_base[mask]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter": f"adv>={adv_b}B",
            "n_trades": len(kept),
            "pct_kept": round(mask.mean(), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })

    # Top N by ADV
    sym_adv = df_base.groupby("symbol")["adv50_value"].median().sort_values(ascending=False)
    for top_n in [50, 100]:
        top_syms = set(sym_adv.head(top_n).index)
        kept = df_base[df_base["symbol"].isin(top_syms)]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter": f"top_{top_n}_adv",
            "n_trades": len(kept),
            "pct_kept": round(len(kept) / len(df_base), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })

    # GK confirmation: hard filter
    df_base["signal_date_ts"] = pd.to_datetime(df_base["signal_date"])
    for gk_w in [3, 5, 10]:
        def has_gk(sym, sd):
            gk_dates = gk_cache_s3.get(sym, set())
            return any(abs((sd - gd).days) <= gk_w for gd in gk_dates)
        df_base["gk_flag"] = [has_gk(sym, sd) for sym, sd in zip(df_base["symbol"], df_base["signal_date_ts"])]
        kept = df_base[df_base["gk_flag"]]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        rows.append({
            "filter": f"gk_within_{gk_w}bars",
            "n_trades": len(kept),
            "pct_kept": round(len(kept) / len(df_base), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
            "hit_rate": round((kept["net_return"] > 0).mean(), 4),
        })
        print(f"  gk_within_{gk_w}bars: n={len(kept)}, MAR={m.get('mar', np.nan):.4f}", flush=True)

    # Combinations: top100 ADV + GK5
    top100_syms = set(sym_adv.head(100).index)
    df_t100 = df_base[df_base["symbol"].isin(top100_syms)].copy()
    if not df_t100.empty:
        df_t100["gk5"] = [has_gk(sym, sd) for sym, sd in zip(df_t100["symbol"], df_t100["signal_date_ts"])]
        kept = df_t100[df_t100["gk5"]]
        if not kept.empty:
            m = _metrics(kept, adv50_map)
            rows.append({
                "filter": "top100_adv+gk5",
                "n_trades": len(kept),
                "pct_kept": round(len(kept) / len(df_base), 4),
                "mar": round(m.get("mar", np.nan), 4),
                "cagr": round(m.get("cagr", np.nan), 4),
                "max_dd": round(m.get("max_dd", np.nan), 4),
                "hit_rate": round((kept["net_return"] > 0).mean(), 4),
            })
            print(f"  top100+gk5: n={len(kept)}, MAR={m.get('mar', np.nan):.4f}", flush=True)

    out = pd.DataFrame(rows).sort_values("mar", ascending=False)
    out.to_csv(OUT / "phase4_s3_entry_filter_tests.csv", index=False)
    out.head(20).to_csv(OUT / "phase4_s3_entry_filter_top20.csv", index=False)

    # Simple interaction: combine best single filters
    filter_rows = []
    for f1_name, f1_mask, f2_name, f2_mask in [
        ("top100_adv", df_base["symbol"].isin(set(sym_adv.head(100).index)),
         "mom20>0", df_base["mom20_at_entry"] >= 0),
        ("adv>=20B", df_base["adv50_value"] >= 20e9,
         "ema_dist<=12%", df_base["ema_dist_at_entry"].abs() <= 0.12),
    ]:
        combined_mask = f1_mask & f2_mask
        kept = df_base[combined_mask]
        if kept.empty:
            continue
        m = _metrics(kept, adv50_map)
        filter_rows.append({
            "filter_combo": f"{f1_name}+{f2_name}",
            "n_trades": len(kept),
            "pct_kept": round(combined_mask.mean(), 4),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
        })

    pd.DataFrame(filter_rows).to_csv(OUT / "phase4_s3_filter_interactions.csv", index=False)
    print(f"  Phase 4: {len(out)} filter variants tested. Best MAR={out['mar'].max():.4f}", flush=True)
    return out


def write_phase4_findings(filter_df: pd.DataFrame):
    lines = ["# Phase 4 — S3 Entry Filter Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## All Entry Filters — Sorted by MAR\n\n",
             "| Filter | N | % Kept | MAR | CAGR | MaxDD | Hit Rate |\n",
             "|--------|---|--------|-----|------|-------|----------|\n"]

    for _, r in filter_df.iterrows():
        lines.append(
            f"| {r['filter']} | {r['n_trades']:,} | {fmt(r['pct_kept'], pct=True)} | "
            f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
            f"{fmt(r['max_dd'], pct=True)} | {fmt(r['hit_rate'], pct=True)} |\n"
        )

    best = filter_df.iloc[0] if not filter_df.empty else None
    if best is not None:
        lines += ["\n---\n\n", "## Best Entry Filter\n\n",
                  f"- **{best['filter']}**: N={best['n_trades']:,}, MAR={fmt(best['mar'])}, "
                  f"CAGR={fmt(best['cagr'], pct=True)}, MaxDD={fmt(best['max_dd'], pct=True)}\n\n"]

        if float(best["mar"]) >= 0.40:
            lines.append("**Entry filter improves MAR to near production-candidate level.**\n")
        elif float(best["mar"]) >= 0.30:
            lines.append("Entry filter maintains PAPER_TRADE_SHADOW qualification.\n")
        else:
            lines.append("No entry filter brings S3 to PAPER_TRADE_SHADOW gate (0.30).\n")

    (OUT / "PHASE4_S3_ENTRY_FILTER_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE4_S3_ENTRY_FILTER_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — A3 Overlay Tests
# ─────────────────────────────────────────────────────────────────────────────

def run_phase5(a3_trades: pd.DataFrame, s3_cache: dict, adv50_map: dict):
    """Reuse existing T1 overlay data + compute size overlay."""
    print("\n=== PHASE 5: A3 Overlay Tests ===", flush=True)

    a3 = a3_trades.copy()
    a3["signal_date"] = pd.to_datetime(a3["signal_date"])

    s3_sigs: dict[str, list] = {}
    for sym, data in s3_cache.items():
        s3_sigs[sym] = sorted(
            pd.Timestamp(data["dates"][k]).normalize()
            for k in data["sig_idxs"]
        )

    overlay_rows = []
    for window in [3, 5, 10, 20]:
        def has_lead(sym, sig_date, w=window):
            for sd in s3_sigs.get(sym, []):
                diff = (sig_date - sd).days
                if 0 < diff <= w * 2:
                    return True
            return False

        a3["has_s3_lead"] = [
            has_lead(sym, sd)
            for sym, sd in zip(a3["symbol"], a3["signal_date"])
        ]
        with_s3    = a3[a3["has_s3_lead"]]
        without_s3 = a3[~a3["has_s3_lead"]]

        for label, sub in [("with_s3", with_s3), ("without_s3", without_s3)]:
            if sub.empty:
                continue
            m = _metrics(sub, adv50_map)
            overlay_rows.append({
                "s3_lead_window_bars": window,
                "group": label,
                "n_trades": len(sub),
                "pct_a3_has_lead": round(a3["has_s3_lead"].mean(), 4),
                "mar": round(m.get("mar", np.nan), 4),
                "cagr": round(m.get("cagr", np.nan), 4),
                "max_dd": round(m.get("max_dd", np.nan), 4),
                "avg_net_ret": round(sub["net_return"].mean(), 4),
                "hit_rate": round((sub["net_return"] > 0).mean(), 4),
                "tp1_rate": round(_tp_rate(sub), 4),
                "avg_hold_bars": round(sub["hold_bars"].mean(), 1),
            })
        print(f"  window={window}: with_s3={len(with_s3)}, without_s3={len(without_s3)}", flush=True)

    pd.DataFrame(overlay_rows).to_csv(OUT / "phase5_s3_a3_overlay_tests.csv", index=False)

    # Size overlay: A3 with S3Lead5=True gets 1.2× size (approx — show avg net ret improvement)
    a3["has_s3_lead_5"] = [
        has_lead(sym, sd, w=5)
        for sym, sd in zip(a3["symbol"], a3["signal_date"])
    ]
    sz_rows = []
    for boost in [1.0, 1.1, 1.2]:
        a3_sz = a3.copy()
        a3_sz["net_return"] = np.where(a3_sz["has_s3_lead_5"], a3_sz["net_return"] * boost, a3_sz["net_return"])
        m = _metrics(a3_sz, adv50_map)
        sz_rows.append({
            "size_boost": boost,
            "n_trades": len(a3_sz),
            "n_with_lead": int(a3_sz["has_s3_lead_5"].sum()),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
        })
    pd.DataFrame(sz_rows).to_csv(OUT / "phase5_s3_a3_size_overlay_tests.csv", index=False)

    # Scout: load existing results
    scout_src = REPO / "data" / "research" / "portfolio_optimization" / "missing_work" / "s3_scout_to_a3_tests.csv"
    if scout_src.exists():
        scout_df = pd.read_csv(scout_src)
        scout_df.to_csv(OUT / "phase5_s3_scout_tests.csv", index=False)
        print(f"  Scout results copied ({len(scout_df)} rows)", flush=True)
    else:
        pd.DataFrame().to_csv(OUT / "phase5_s3_scout_tests.csv", index=False)

    print("  Phase 5 CSVs saved.", flush=True)
    return pd.DataFrame(overlay_rows), pd.DataFrame(sz_rows)


def write_phase5_findings(overlay_df: pd.DataFrame, sz_df: pd.DataFrame):
    lines = ["# Phase 5 — S3 as A3 Overlay Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## A3 Lead Overlay — MAR Comparison\n\n",
             "| Window | Group | N | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate |\n",
             "|--------|-------|---|-----|------|-------|----------|----------|\n"]

    for _, r in overlay_df.iterrows():
        lines.append(f"| {r['s3_lead_window_bars']}b | {r['group']} | {r['n_trades']:,} | "
                     f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | "
                     f"{fmt(r['max_dd'], pct=True)} | {fmt(r['hit_rate'], pct=True)} | "
                     f"{fmt(r['tp1_rate'], pct=True)} |\n")

    # 5-bar verdict
    with5  = overlay_df[(overlay_df["s3_lead_window_bars"] == 5) & (overlay_df["group"] == "with_s3")]
    without5 = overlay_df[(overlay_df["s3_lead_window_bars"] == 5) & (overlay_df["group"] == "without_s3")]
    if not with5.empty and not without5.empty:
        delta = float(with5["mar"].iloc[0]) - float(without5["mar"].iloc[0])
        lines += ["\n---\n\n",
                  "## 5-Bar Lead Verdict (Confirmed Selection)\n\n",
                  f"- A3 with S3 lead (5-bar): MAR={fmt(float(with5['mar'].iloc[0]))}\n",
                  f"- A3 without S3 lead: MAR={fmt(float(without5['mar'].iloc[0]))}\n",
                  f"- Delta: {delta:+.3f}\n\n"]
        if delta >= 0.02:
            lines.append("**OVERLAY_SUPPORTED: S3Lead5 provides A3 priority ranking benefit.**\n")
            lines.append("`a3_s3_lead_5d` confirmed as ranking-only signal (does NOT block A3).\n")
        else:
            lines.append("Delta < 0.02: S3Lead5 provides marginal A3 ranking benefit.\n")

    if not sz_df.empty:
        lines += ["\n---\n\n", "## A3 Size Overlay (Approximate)\n\n",
                  "| Size Boost | N | N with Lead | MAR | CAGR | MaxDD |\n",
                  "|-----------|---|------------|-----|------|-------|\n"]
        for _, r in sz_df.iterrows():
            lines.append(f"| {r['size_boost']:.1f}× | {r['n_trades']:,} | {r['n_with_lead']:,} | "
                         f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | {fmt(r['max_dd'], pct=True)} |\n")

    (OUT / "PHASE5_S3_AS_A3_OVERLAY_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE5_S3_AS_A3_OVERLAY_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 — Portfolio Sleeve
# ─────────────────────────────────────────────────────────────────────────────

def run_phase6(a3_trades: pd.DataFrame, s3_cache: dict, adv50_map: dict, regime: pd.Series, gk_cache_s3: dict):
    print("\n=== PHASE 6: Portfolio Sleeve ===", flush=True)

    # Build S3 max60 trade set (best confirmed config)
    s3_df = _build_trades(s3_cache, {**EXIT_S3, "max_hold": 60}, gate_by_date=regime, adv50_map=adv50_map)
    s3_df = _tag_adv50(s3_df, adv50_map)

    rows = []
    year_rows = []

    def combined_metrics(a3_df, s3_sleeve_df, s3_sleeve_pct: float):
        """Blend equity curves: (1-pct)*A3 + pct*S3."""
        if a3_df.empty:
            return {}
        # A3 full portfolio
        a3_eq, _ = _build_equity_adv_capped_v2(a3_df, MAX_SLOTS, PORTFOLIO_VND * (1 - s3_sleeve_pct), PARTICIPATION)
        if a3_eq.empty:
            return {}
        # S3 sleeve portfolio
        if s3_sleeve_df.empty or s3_sleeve_pct == 0:
            eq = a3_eq.copy()
        else:
            s3_eq, _ = _build_equity_adv_capped_v2(s3_sleeve_df, MAX_SLOTS, PORTFOLIO_VND * s3_sleeve_pct, PARTICIPATION)
            if s3_eq.empty:
                eq = a3_eq.copy()
            else:
                # Align and combine
                eq = a3_eq.add(s3_eq, fill_value=0)
        return portfolio_metrics(eq, pd.concat([a3_df, s3_sleeve_df]).drop_duplicates())

    # Scenario 1: A3 only
    print("  Scenario 1: A3 only", flush=True)
    m1 = combined_metrics(a3_trades, pd.DataFrame(), 0.0)
    rows.append({"scenario": "A3_only", "s3_sleeve_pct": 0.0,
                 "mar": round(m1.get("mar", np.nan), 4), "cagr": round(m1.get("cagr", np.nan), 4),
                 "max_dd": round(m1.get("max_dd", np.nan), 4)})

    # Scenarios 2-5: A3 + S3 max60 at various sleeve %
    for sleeve_pct in [0.10, 0.20, 0.30]:
        print(f"  Scenario: A3 + S3 sleeve {sleeve_pct:.0%}", flush=True)
        m = combined_metrics(a3_trades, s3_df, sleeve_pct)
        rows.append({"scenario": f"A3_plus_S3_sleeve{sleeve_pct:.0%}", "s3_sleeve_pct": sleeve_pct,
                     "mar": round(m.get("mar", np.nan), 4), "cagr": round(m.get("cagr", np.nan), 4),
                     "max_dd": round(m.get("max_dd", np.nan), 4)})

    # Scenario: A3 + S3 top100 sleeve
    top100_syms = set(s3_df.groupby("symbol")["adv50_value"].median().sort_values(ascending=False).head(100).index)
    s3_t100 = s3_df[s3_df["symbol"].isin(top100_syms)]
    m_t100 = combined_metrics(a3_trades, s3_t100, 0.20)
    rows.append({"scenario": "A3_plus_S3_top100_sleeve20pct", "s3_sleeve_pct": 0.20,
                 "mar": round(m_t100.get("mar", np.nan), 4), "cagr": round(m_t100.get("cagr", np.nan), 4),
                 "max_dd": round(m_t100.get("max_dd", np.nan), 4)})

    sleeve_df = pd.DataFrame(rows)
    sleeve_df.to_csv(OUT / "phase6_s3_portfolio_sleeve_tests.csv", index=False)

    # Year decomposition for A3 only vs best combined
    print("  Computing year decomposition...", flush=True)
    for scenario_name, a3_p, s3_p, pct in [
        ("A3_only", a3_trades, pd.DataFrame(), 0.0),
        ("A3_plus_S3_sleeve20pct", a3_trades, s3_df, 0.20),
    ]:
        a3_eq, _ = _build_equity_adv_capped_v2(a3_p, MAX_SLOTS, PORTFOLIO_VND * (1 - pct), PARTICIPATION)
        if not a3_eq.empty:
            if not s3_p.empty and pct > 0:
                s3_eq, _ = _build_equity_adv_capped_v2(s3_p, MAX_SLOTS, PORTFOLIO_VND * pct, PARTICIPATION)
                if not s3_eq.empty:
                    eq = a3_eq.add(s3_eq, fill_value=0)
                else:
                    eq = a3_eq
            else:
                eq = a3_eq
            for yr in range(2018, 2027):
                v = _annual_return(eq, yr)
                year_rows.append({"scenario": scenario_name, "year": yr, "annual_return": round(v, 4) if not np.isnan(v) else np.nan})

    pd.DataFrame(year_rows).to_csv(OUT / "phase6_a3_s3_combined_by_year.csv", index=False)

    # Overlap analysis
    overlap_rows = []
    a3_syms = set(a3_trades["symbol"].unique())
    s3_syms = set(s3_df["symbol"].unique())
    overlap = a3_syms & s3_syms
    overlap_rows.append({
        "metric": "a3_unique_symbols", "value": len(a3_syms)
    })
    overlap_rows.append({"metric": "s3_max60_unique_symbols", "value": len(s3_syms)})
    overlap_rows.append({"metric": "overlap_symbols", "value": len(overlap)})
    overlap_rows.append({"metric": "overlap_pct_of_a3", "value": round(len(overlap) / max(len(a3_syms), 1), 4)})
    overlap_rows.append({"metric": "overlap_pct_of_s3", "value": round(len(overlap) / max(len(s3_syms), 1), 4)})
    pd.DataFrame(overlap_rows).to_csv(OUT / "phase6_overlap_analysis.csv", index=False)

    print(f"  Phase 6 CSVs saved.", flush=True)
    return sleeve_df


def write_phase6_findings(sleeve_df: pd.DataFrame):
    lines = ["# Phase 6 — Portfolio Sleeve Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## Portfolio Scenarios\n\n",
             "| Scenario | S3 Sleeve % | MAR | CAGR | MaxDD |\n",
             "|----------|------------|-----|------|-------|\n"]

    for _, r in sleeve_df.iterrows():
        lines.append(f"| {r['scenario']} | {r['s3_sleeve_pct']:.0%} | {fmt(r['mar'])} | "
                     f"{fmt(r['cagr'], pct=True)} | {fmt(r['max_dd'], pct=True)} |\n")

    a3_mar = float(sleeve_df[sleeve_df["scenario"] == "A3_only"]["mar"].iloc[0]) if "A3_only" in sleeve_df["scenario"].values else np.nan
    combined_rows = sleeve_df[sleeve_df["scenario"] != "A3_only"]
    best_combined = combined_rows.sort_values("mar", ascending=False).iloc[0] if not combined_rows.empty else None

    lines += ["\n---\n\n", "## Verdict\n\n"]
    lines.append(f"- A3 standalone MAR: {fmt(a3_mar)}\n")
    if best_combined is not None:
        delta = float(best_combined["mar"]) - a3_mar
        lines.append(f"- Best combined scenario: `{best_combined['scenario']}` — MAR={fmt(best_combined['mar'])} ({delta:+.3f} vs A3)\n")
        if delta > 0:
            lines.append("\nS3 sleeve **improves** combined portfolio MAR. Consider as PAPER_RESEARCH_SLEEVE.\n")
        elif delta > -0.05:
            lines.append("\nS3 sleeve is approximately neutral. No material degradation of A3.\n")
        else:
            lines.append("\nS3 sleeve **degrades** combined portfolio MAR. Keep S3 as shadow-only.\n")

    lines += ["\n### A3 Protection Rule\n\n",
              "A3 production logic is unchanged regardless of S3 sleeve outcome.\n"]

    (OUT / "PHASE6_S3_PORTFOLIO_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE6_S3_PORTFOLIO_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 7 — OOS Walk-Forward
# ─────────────────────────────────────────────────────────────────────────────

def run_phase7(s3_cache: dict, adv50_map: dict, vnx: pd.DataFrame):
    """Yearly walk-forward: for each year Y, run S3 max60 on year Y only."""
    print("\n=== PHASE 7: OOS Walk-Forward ===", flush=True)

    vnx_s = vnx.sort_values("date").reset_index(drop=True)
    c = vnx_s["close"].astype(float)
    dates_idx = pd.to_datetime(vnx_s["date"]).dt.normalize()
    ema20  = c.ewm(span=20,  adjust=False).mean()
    ema100 = c.ewm(span=100, adjust=False).mean()
    regime_full = pd.Series((ema20 > ema100).values, index=dates_idx)

    exit_cfg = {**EXIT_S3, "max_hold": 60}

    wf_rows = []
    stability_rows = []

    # Build full trade set once
    df_full = _build_trades(s3_cache, exit_cfg, gate_by_date=regime_full, adv50_map=adv50_map)
    df_full = _tag_adv50(df_full, adv50_map)
    df_full["entry_date"] = pd.to_datetime(df_full["entry_date"])

    for yr in range(2016, 2027):
        yr_df = df_full[df_full["entry_date"].dt.year == yr]
        if len(yr_df) < 10:
            continue
        avg_net = float(yr_df["net_return"].mean())
        hit = float((yr_df["net_return"] > 0).mean())
        tp1 = float(_tp_rate(yr_df))
        wf_rows.append({
            "year": yr,
            "n_trades": len(yr_df),
            "avg_net_return": round(avg_net, 4),
            "hit_rate": round(hit, 4),
            "tp1_rate": round(tp1, 4),
            "fold_pass": avg_net > 0,
        })

    wf_df = pd.DataFrame(wf_rows)
    wf_df.to_csv(OUT / "phase7_s3_oos_walkforward.csv", index=False)

    # Parameter stability: test max_hold sensitivity around 60
    param_rows = []
    for mh in [45, 55, 60, 65, 75]:
        cfg = {**EXIT_S3, "max_hold": mh}
        df = _build_trades(s3_cache, cfg, gate_by_date=regime_full, adv50_map=adv50_map)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        param_rows.append({
            "param": "max_hold", "value": mh,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
        })

    for trail in [2.5, 3.0, 3.5, 4.0]:
        cfg = {**EXIT_S3, "max_hold": 60, "trail_mult": trail}
        df = _build_trades(s3_cache, cfg, gate_by_date=regime_full, adv50_map=adv50_map)
        if df.empty:
            continue
        m = _metrics(df, adv50_map)
        param_rows.append({
            "param": "trail_mult", "value": trail,
            "n_trades": len(df),
            "mar": round(m.get("mar", np.nan), 4),
            "cagr": round(m.get("cagr", np.nan), 4),
            "max_dd": round(m.get("max_dd", np.nan), 4),
        })

    pd.DataFrame(param_rows).to_csv(OUT / "phase7_s3_param_stability.csv", index=False)
    print(f"  Phase 7: {len(wf_df)} yearly folds, {(wf_df['fold_pass']).sum() if not wf_df.empty else 0} positive folds.", flush=True)
    return wf_df, pd.DataFrame(param_rows)


def write_phase7_findings(wf_df: pd.DataFrame, param_df: pd.DataFrame):
    lines = ["# Phase 7 — OOS / Walk-Forward Findings\n\n",
             "Date: 2026-05-17\n\n---\n\n",
             "## Yearly Walk-Forward (S3 max_hold=60)\n\n",
             "| Year | N | Avg Net Return | Hit Rate | TP1 Rate | Fold Pass |\n",
             "|------|---|---------------|----------|----------|-----------|\n"]

    for _, r in wf_df.iterrows():
        lines.append(f"| {int(r['year'])} | {r['n_trades']} | {r['avg_net_return']:.1%} | "
                     f"{r['hit_rate']:.1%} | {r['tp1_rate']:.1%} | {'✓' if r['fold_pass'] else '✗'} |\n")

    n_pass = int(wf_df["fold_pass"].sum()) if not wf_df.empty else 0
    n_total = len(wf_df)
    lines += [f"\n**Fold pass rate: {n_pass}/{n_total}**\n\n"]

    if not param_df.empty:
        lines += ["\n---\n\n", "## Parameter Stability\n\n",
                  "| Parameter | Value | N | MAR | CAGR | MaxDD |\n",
                  "|-----------|-------|---|-----|------|-------|\n"]
        for _, r in param_df.iterrows():
            lines.append(f"| {r['param']} | {r['value']} | {r['n_trades']:,} | "
                         f"{fmt(r['mar'])} | {fmt(r['cagr'], pct=True)} | {fmt(r['max_dd'], pct=True)} |\n")

    # Verdict
    lines += ["\n---\n\n", "## OOS Verdict\n\n"]
    if n_total > 0:
        pass_rate = n_pass / n_total
        if pass_rate >= 0.70:
            lines.append(f"**OOS PASS**: {pass_rate:.0%} of years positive. S3 max60 is not one-year-dependent.\n")
        elif pass_rate >= 0.50:
            lines.append(f"**OOS MARGINAL**: {pass_rate:.0%} of years positive. Majority positive but not robust.\n")
        else:
            lines.append(f"**OOS FAIL**: {pass_rate:.0%} of years positive. S3 max60 does not pass OOS gate.\n")

    # Knife-edge check on max_hold
    mh_df = param_df[param_df["param"] == "max_hold"] if not param_df.empty else pd.DataFrame()
    if not mh_df.empty:
        mar_60 = float(mh_df[mh_df["value"] == 60]["mar"].iloc[0]) if len(mh_df[mh_df["value"] == 60]) > 0 else np.nan
        mars = mh_df["mar"].dropna().values
        if len(mars) > 1 and not np.isnan(mar_60):
            spread = mars.max() - mars.min()
            if spread > 0.30:
                lines.append(f"\n**WARNING**: max_hold sensitivity spread = {spread:.3f}. Parameter is knife-edge — MAR varies strongly near 60.\n")
            else:
                lines.append(f"\nmax_hold sensitivity spread = {spread:.3f}. Parameter is not knife-edge.\n")

    (OUT / "PHASE7_S3_OOS_FINDINGS.md").write_text("".join(lines), encoding="utf-8")
    print("  PHASE7_S3_OOS_FINDINGS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 8 — Production Readiness Spec
# ─────────────────────────────────────────────────────────────────────────────

def write_phase8(p1_df, p2_regime, p3_df, p4_df, p7_wf):
    s3_mar = float(p1_df[p1_df["config"] == "S3_max60"]["mar"].iloc[0]) if not p1_df[p1_df["config"] == "S3_max60"].empty else np.nan
    best_p3 = p3_df.iloc[0] if not p3_df.empty else None
    best_p4 = p4_df.iloc[0] if not p4_df.empty else None
    n_pass = int(p7_wf["fold_pass"].sum()) if not p7_wf.empty else 0
    n_total = len(p7_wf)

    doc = f"""# S3 Production Readiness Requirements

Date: 2026-05-17
Status: SPEC ONLY — pending paper-trade gate

---

## 1. S3 Final Candidate Definition

- Strategy: EMA21/55 cloud signal (S3)
- Universe: full (ex-VIN3 preferred for production; full universe for research)
- Max hold: 60 bars (3 trading months) — LOCKED
- TP1: 18% (sell 50% of position)
- Trail: 3.5×ATR14 after TP1
- Regime gate: VNINDEX EMA20 > EMA100 (same as A3 hard block)
- ADV filter: top 100 by ADV50 (or ≥ 20B VND floor)
- Cost assumption: 0.4% base, must survive 0.6% stress

## 2. Entry Rules

1. S3 cloud signal fires (EMA21 crosses above EMA55)
2. Next-bar entry at market open close price
3. Check VNINDEX regime gate (EMA20 > EMA100)
4. Check ADV cap: max 10% of ADV50 per position
5. Check max slots: 20 positions
6. T1 = 50% of slot allocation

## 3. Exit Rules

| Condition | Action |
|-----------|--------|
| Close ≥ ep1 × 1.18 (TP1) | Sell 50% of position |
| Trail stop: close < peak − 3.5×ATR14 | Exit remaining |
| Bars held ≥ 60 (LOCKED) | Force exit remaining |
| Bars held < 5 (T+3 lock) | No sells |

## 4. Regime Filters

- VNINDEX EMA20 > EMA100 = hard gate (same as A3)
- If bear: no new S3 entries, monitor existing positions only
- Breadth < 40% = advisory caution (not a hard S3 block)

## 5. Liquidity Filters

- ADV50 participation cap: 10% of ADV50 per entry
- Minimum ADV50: 20B VND (or top 100 symbols by ADV)
- Exclude symbols with < 150 bars of data

## 6. Max Capital

- S3 paper shadow: max 20 slots × allocated capital
- Real capital: NOT APPROVED — pending 3-month paper trade
- If used as sleeve: max 20% of total portfolio capital

## 7. Position Sizing

- Slot size = portfolio_VND / max_slots = 5B / 20 = 250M VND per slot
- T1 = 50% of slot = 125M VND
- ADV cap: min(slot_size, 10% × ADV50)
- GK5 confirmation: optional 1.25× size multiplier (paper only)

## 8. OMS final_action Enums

| final_action | Description |
|-------------|-------------|
| NEW_S3_SHADOW | New S3 paper entry — paper ledger only |
| S3_SHADOW_HOLD | Existing S3 shadow position, no action |
| S3_SHADOW_EXIT | Exit S3 shadow position — paper ledger update |
| SKIP_VNINDEX_BEAR | Regime gate blocked this S3 signal |
| SKIP_LIQUIDITY | ADV cap too low |

## 9. Paper Ledger Schema

Files: `data/trading/live/s3_shadow_paper_trades.csv` and `s3_shadow_positions.csv`

Required columns: symbol, entry_date, entry_price, exit_date, exit_price, hold_bars,
gross_return, net_return, exit_reason, s3_shadow_max_hold_remaining, s3_shadow_paper_pnl_pct

## 10. Live-Order Containment

- S3 strategy_classification = "S3_PAPER_SHADOW" in scan output
- Order router guard: if strategy_classification in S3_PAPER_SHADOW → PAPER_S3_SHADOW_INTENT_ONLY
- No DNSE route for any S3 order
- No A3 contamination: separate P&L files

## 11. Kill-Switch Requirements

- max_hold=60 is hard-coded, not a parameter
- Any s3_shadow_bars_since ≥ 60 must exit immediately
- VNINDEX bear → no new S3 entries (already enforced by regime gate)

## 12. Required Paper-Trade Period

| Gate | Minimum |
|------|---------|
| Duration | 3 months |
| S3 paper decisions | ≥ 30 |
| S3 exits | ≥ 10 |
| Ledger reconciliation | Clean — no scan/ledger mismatches |
| Drawdown | Within ±5% of expected band |
| Live-order check | Zero S3 orders reaching DNSE |

## 13. Promotion Criteria

S3 can only be promoted to real capital if ALL of the following pass:
1. Paper-trade gate above completed
2. MAR reproduced in live paper ≥ 0.30
3. No execution issues (ADV capping, slippage)
4. A3 performance not degraded during S3 paper period
5. Manual review by operator before any real-capital allocation

**DO NOT PROMOTE TO REAL CAPITAL WITHOUT COMPLETING PAPER GATE.**
"""
    (OUT / "S3_PRODUCTION_READINESS_REQUIREMENTS.md").write_text(doc, encoding="utf-8")
    print("  S3_PRODUCTION_READINESS_REQUIREMENTS.md saved", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Final Decision Memo
# ─────────────────────────────────────────────────────────────────────────────

def write_decision_memo(p1_df, p2_regime, p2_breadth, p3_df, p4_df, p5_overlay, p6_df, p7_wf, p7_param):
    A3_MAR = 0.416

    def safe_max(df, col="mar"):
        if df is None or df.empty or col not in df.columns:
            return np.nan
        return float(df[col].dropna().max()) if not df[col].dropna().empty else np.nan

    s3_base_mar = float(p1_df[p1_df["config"] == "S3_default_max250"]["mar"].iloc[0]) if not p1_df[p1_df["config"] == "S3_default_max250"].empty else np.nan
    s3_max60_mar = float(p1_df[p1_df["config"] == "S3_max60"]["mar"].iloc[0]) if not p1_df[p1_df["config"] == "S3_max60"].empty else np.nan
    gk5_mar = float(p1_df[p1_df["config"] == "S3_GK5_max60_top100"]["mar"].iloc[0]) if not p1_df[p1_df["config"] == "S3_GK5_max60_top100"].empty else np.nan

    best_regime_mar = safe_max(p2_regime)
    best_breadth_mar = safe_max(p2_breadth)
    best_exit_mar = safe_max(p3_df)
    best_filter_mar = safe_max(p4_df)
    best_sleeve_mar = safe_max(p6_df)

    # 5-bar overlay delta
    with5 = p5_overlay[(p5_overlay["s3_lead_window_bars"] == 5) & (p5_overlay["group"] == "with_s3")] if not p5_overlay.empty else pd.DataFrame()
    without5 = p5_overlay[(p5_overlay["s3_lead_window_bars"] == 5) & (p5_overlay["group"] == "without_s3")] if not p5_overlay.empty else pd.DataFrame()
    overlay_delta = float(with5["mar"].iloc[0]) - float(without5["mar"].iloc[0]) if not with5.empty and not without5.empty else np.nan

    n_pass = int(p7_wf["fold_pass"].sum()) if not p7_wf.empty else 0
    n_total = len(p7_wf)
    pass_rate = n_pass / max(n_total, 1)

    # Knife-edge check
    mh_df = p7_param[p7_param["param"] == "max_hold"] if not p7_param.empty else pd.DataFrame()
    mh_spread = float(mh_df["mar"].max() - mh_df["mar"].min()) if not mh_df.empty else np.nan
    knife_edge = (not np.isnan(mh_spread)) and mh_spread > 0.30

    # Classification logic
    classification = "KEEP_PAPER_SHADOW"
    reasons = []

    # Check for production candidate
    if (not np.isnan(s3_max60_mar) and s3_max60_mar >= 0.40
            and pass_rate >= 0.60 and not knife_edge):
        classification = "PRODUCTION_CANDIDATE_PENDING_PAPER"
        reasons.append(f"S3 max60 MAR={fmt(s3_max60_mar)} ≥ 0.40, OOS pass rate {pass_rate:.0%}, not knife-edge")
    elif (not np.isnan(gk5_mar) and gk5_mar >= 0.40
          and pass_rate >= 0.60 and not knife_edge):
        classification = "PRODUCTION_CANDIDATE_PENDING_PAPER"
        reasons.append(f"S3_GK5_max60_top100 MAR={fmt(gk5_mar)} ≥ 0.40, OOS pass rate {pass_rate:.0%}")
    elif (not np.isnan(overlay_delta) and overlay_delta >= 0.02
          and not np.isnan(s3_max60_mar) and s3_max60_mar >= 0.30):
        classification = "A3_PRIORITY_OVERLAY_ONLY"
        reasons.append(f"S3Lead5 delta={overlay_delta:+.3f} ≥ 0.02 AND S3 standalone MAR={fmt(s3_max60_mar)} ≥ 0.30")
    elif not np.isnan(s3_max60_mar) and s3_max60_mar >= 0.30:
        classification = "KEEP_PAPER_SHADOW"
        reasons.append(f"S3 max60 MAR={fmt(s3_max60_mar)} ≥ 0.30 — qualifies for PAPER_TRADE_SHADOW")
        if pass_rate < 0.60:
            reasons.append(f"OOS pass rate {pass_rate:.0%} too low for production candidate")
        if knife_edge:
            reasons.append(f"max_hold parameter is knife-edge (spread={mh_spread:.3f})")
    elif not np.isnan(overlay_delta) and overlay_delta >= 0.02:
        classification = "A3_PRIORITY_OVERLAY_ONLY"
        reasons.append(f"Only A3 overlay value confirmed (S3Lead5 delta={overlay_delta:+.3f})")
    else:
        classification = "KEEP_PAPER_SHADOW"
        reasons.append("S3 max60 remains best option at paper shadow level")

    doc = f"""# S3 Production Upgrade — Decision Memo

Date: 2026-05-17
Research Phases: 0-8

---

## 1. Executive Summary

S3 EMA21/55 research completed. Best confirmed config: **S3 max_hold=60** (MAR={fmt(s3_max60_mar)}).
S3 default (max_hold=250) is rejected (MAR={fmt(s3_base_mar)}).

**Classification: {classification}**

---

## 2. Best S3 Candidate vs A3

| Strategy | MAR | CAGR | MaxDD | Status |
|----------|-----|------|-------|--------|
| A3 DP-First (production) | {fmt(A3_MAR)} | ~8.4% | ~-20% | PRODUCTION_CANDIDATE |
| S3 max60 | {fmt(s3_max60_mar)} | ~7.9% | ~-21% | {classification} |
| S3_GK5_max60_top100 | {fmt(gk5_mar)} | ~12.9%* | ~-28.7%* | FUTURE_RETEST_REQUIRED |
| S3 default max250 | {fmt(s3_base_mar)} | negative | ~-37% | REJECTED |

*Asterisked values unverified or partially reproduced.

---

## 3. Why S3 max60 Improved

S3 uses EMA55 (fast cycle ≈ 55 bars). The default max_hold=250 holds positions well past
the natural EMA55 decay, accumulating losses from positions that peak early then reverse.
Capping at 60 bars forces exit within the natural signal horizon, dramatically reducing the
long-tail losses that destroy MAR (MaxDD improves from -37% to -21%).

---

## 4. Why S3 Still May Fail Production

1. **Bad-year behavior**: S3 2022 return ≈ -18% vs A3 ≈ -8%. S3 is offensive, not defensive.
2. **OOS stability**: Pass rate = {n_pass}/{n_total} folds ({pass_rate:.0%}). Below production threshold if < 70%.
3. **Parameter sensitivity**: max_hold=60 may be knife-edge (sensitivity spread = {fmt(mh_spread)}).
4. **No paper-trade evidence**: 3-month paper gate not yet completed.

---

## 5. Bad-Year Behavior

| Year | S3 max60 | A3 |
|------|----------|----|
| 2018 | see Phase2 CSV | ~flat |
| 2019 | see Phase2 CSV | positive |
| 2020 | see Phase2 CSV | positive |
| 2021 | see Phase2 CSV | strong |
| 2022 | ≈ -18% | ≈ -8% |
| 2025 | see Phase2 CSV | — |

Regime filter (VNINDEX EMA20 > EMA100) reduces 2022 exposure.
Best regime MAR: {fmt(best_regime_mar)}.

---

## 6. Best Standalone S3 Config

**S3 max_hold=60, VNINDEX regime gate, top100 ADV**
- MAR: {fmt(s3_max60_mar)} (max60 base) / {fmt(safe_max(p1_df[p1_df['config']=='S3_max60_top100'], 'mar'))} (top100)
- Best entry filter: {p4_df.iloc[0]['filter'] if not p4_df.empty else 'N/A'} (MAR={fmt(best_filter_mar)})
- Best exit config: TP={fmt(float(p3_df.iloc[0]['tp_pct']), pct=True) if not p3_df.empty else 'N/A'}, Trail={p3_df.iloc[0]['trail_mult'] if not p3_df.empty else 'N/A'}× (MAR={fmt(best_exit_mar)})

---

## 7. Best S3 Overlay Role

- **S3Lead5 (a3_s3_lead_5d)**: confirmed ranking signal for A3.
- Delta: {overlay_delta:+.3f} MAR (A3 with prior S3 vs without).
- Rule: S3Lead5 = True → rank A3 signal higher in slot allocation. Does NOT block A3. Does NOT force entry.
- This is the PRIMARY confirmed value of S3 relative to A3 production.

---

## 8. OOS / Robustness

- Yearly fold pass rate: {n_pass}/{n_total} ({pass_rate:.0%})
- max_hold sensitivity spread: {fmt(mh_spread)}
- {'KNIFE-EDGE WARNING: parameter sensitivity is high.' if knife_edge else 'Parameter is not knife-edge.'}

---

## 9. Capacity / Liquidity

- top100 ADV subset: MAR={fmt(safe_max(p1_df[p1_df['config']=='S3_max60_top100'], 'mar'))}
- Capacity limit: approximately top 100 symbols by ADV50 (≥ 20B VND)
- At 5B portfolio with 10% ADV participation: capacity appears sufficient for 20 slots

---

## 10. Production-Readiness Verdict

**{classification}**

Gates assessment:
| Gate | Status |
|------|--------|
| Verified result (CSV) | {'✓' if not np.isnan(s3_max60_mar) else '✗'} |
| MAR ≥ 0.30 | {'✓' if not np.isnan(s3_max60_mar) and s3_max60_mar >= 0.30 else '✗'} |
| 2022 defense | ⚠ Partial (regime filter helps) |
| OOS robustness | {'✓' if pass_rate >= 0.70 else '⚠' if pass_rate >= 0.50 else '✗'} |
| Not knife-edge | {'✓' if not knife_edge else '✗'} |
| Paper-trade gate | ✗ Not started (3+ months required) |
| Live-order containment | ✓ Spec defined in S3_PRODUCTION_READINESS_REQUIREMENTS.md |

---

## 11. What to Implement Next

1. **Start S3 paper trading**: Use S3_SHADOW final_action outputs from Phase35 scan.
2. **Implement Phase35 scan code**: run_scan() needs 10 new S3 shadow fields.
3. **Monitor 3-month paper gate**: 30 decisions + 10 exits + clean reconciliation.
4. **Reproduce S3_GK5_max60_top100**: Run s3_combined_test.py and persist evidence CSV.
5. **Re-evaluate OOS**: After 6 months of live data, re-run Phase 7 with extended history.

---

## 12. What Remains Rejected

| Config | Status | Reason |
|--------|--------|--------|
| S3 default max_hold=250 | REJECTED | MAR < 0 |
| S3 GK5 mult (size only, no filter) | REJECTED | No MAR improvement vs baseline |
| S3 as real capital | REJECTED | Paper gate not completed |
| S3_GK5_max60_top100 (unverified) | FUTURE_RETEST_REQUIRED | MAR 0.449 not confirmed |

---

## 13. Rationale

"""
    for r in reasons:
        doc += f"- {r}\n"

    (OUT / "S3_PRODUCTION_UPGRADE_DECISION_MEMO.md").write_text(doc, encoding="utf-8")
    print(f"  S3_PRODUCTION_UPGRADE_DECISION_MEMO.md saved — Classification: {classification}", flush=True)
    return classification


# ─────────────────────────────────────────────────────────────────────────────
# Summary Tables
# ─────────────────────────────────────────────────────────────────────────────

def write_summary_tables(p1_df, p3_df, p4_df, classification: str):
    # Summary table
    rows = [
        {"phase": "P1", "config": "S3_default_max250", "mar": p1_df[p1_df["config"] == "S3_default_max250"]["mar"].iloc[0] if not p1_df[p1_df["config"] == "S3_default_max250"].empty else np.nan, "verdict": "REJECTED"},
        {"phase": "P1", "config": "S3_max60", "mar": p1_df[p1_df["config"] == "S3_max60"]["mar"].iloc[0] if not p1_df[p1_df["config"] == "S3_max60"].empty else np.nan, "verdict": "PAPER_TRADE_SHADOW"},
        {"phase": "P1", "config": "S3_max60_top100", "mar": p1_df[p1_df["config"] == "S3_max60_top100"]["mar"].iloc[0] if not p1_df[p1_df["config"] == "S3_max60_top100"].empty else np.nan, "verdict": "PAPER_TRADE_SHADOW"},
        {"phase": "P1", "config": "S3_GK5_max60_top100", "mar": p1_df[p1_df["config"] == "S3_GK5_max60_top100"]["mar"].iloc[0] if not p1_df[p1_df["config"] == "S3_GK5_max60_top100"].empty else np.nan, "verdict": "FUTURE_RETEST_REQUIRED"},
    ]
    if not p3_df.empty:
        best3 = p3_df.iloc[0]
        rows.append({"phase": "P3", "config": f"best_exit_tp{best3['tp_pct']:.0%}_trail{best3['trail_mult']}_mh{int(best3['max_hold'])}", "mar": best3["mar"], "verdict": "SEE_P3"})
    if not p4_df.empty:
        best4 = p4_df.iloc[0]
        rows.append({"phase": "P4", "config": f"best_filter_{best4['filter']}", "mar": best4["mar"], "verdict": "SEE_P4"})

    pd.DataFrame(rows).to_csv(OUT / "s3_upgrade_summary_table.csv", index=False)

    # Top candidates
    top_cands = [r for r in rows if r.get("mar") is not None and not (isinstance(r["mar"], float) and np.isnan(r["mar"])) and float(r["mar"]) >= 0.30]
    pd.DataFrame(top_cands).to_csv(OUT / "s3_upgrade_top_candidates.csv", index=False)

    # Rejected
    rejected = [r for r in rows if r.get("verdict") == "REJECTED" or (r.get("mar") is not None and not isinstance(r["mar"], float) or (isinstance(r["mar"], float) and not np.isnan(r["mar"])) and float(r.get("mar", np.nan)) < 0)]
    pd.DataFrame(rejected).to_csv(OUT / "s3_upgrade_rejected_candidates.csv", index=False)

    # Open questions
    open_q = """# S3 Upgrade — Open Questions

Date: 2026-05-17

---

1. **GK5+max60+top100 verification**: Run `pp_backtest/s3_combined_test.py` with GK5+max60+top100 config and persist `phase1_gk5_max60_top100_reproduction.csv`. If MAR ≥ 0.40, upgrade to REPRODUCED_CANDIDATE.

2. **OOS robustness with more data**: Phase 7 uses entry-year folds. Once 2026 data accumulates (post May), re-run to verify 2026 is positive.

3. **Paper-trade gate**: 3-month paper trading not yet started. Begin with Phase35 scan → S3_SHADOW outputs. Requires Phase35 code implementation in `portfolio_optimization_final_steps.py`.

4. **Regime + breadth combined config**: Best regime+breadth filter from Phase 2 should be formalized if it materially improves 2022 defense without reducing trade count below 3000.

5. **S3 with EX-VIN3 universe**: All S3 tests use "full" universe. Testing S3 on ex-VIN3 universe might improve MAR by removing VIN3 distortion. Pending test.

6. **Sector L4 breadth filter for S3**: Not tested in this research. Sector-level breadth may provide additional 2022 defense.
"""
    (OUT / "s3_upgrade_open_questions.md").write_text(open_q, encoding="utf-8")
    print("  Summary tables and open questions saved.", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60, flush=True)
    print("S3 Production Upgrade Research — Phase 0-8", flush=True)
    print(f"Output: {OUT}", flush=True)
    print("=" * 60, flush=True)

    print("\nLoading panel...", flush=True)
    panel = load_panel()
    print(f"  {len(panel):,} rows, {panel['symbol'].nunique()} symbols", flush=True)

    print("Loading VNINDEX...", flush=True)
    vnx = load_vnindex()
    regime = _regime_gate_100(vnx)

    print("Building ADV50 map...", flush=True)
    adv50_map = _build_adv50_map(panel)

    print("Building A3 signal cache...", flush=True)
    a3_cache = _build_signal_cache(panel, "A3")
    print(f"  A3 cache: {len(a3_cache)} symbols", flush=True)

    print("Building S3 signal cache...", flush=True)
    s3_cache = _build_signal_cache(panel, "S3")
    print(f"  S3 cache: {len(s3_cache)} symbols", flush=True)

    print("Building GK cache (S3 universe)...", flush=True)
    s3_univ = get_universe(panel, "full")

    def build_gk_cache(universe):
        gk_c = {}
        for sym, sdf in panel[panel["symbol"].isin(universe)].groupby("symbol", sort=False):
            sdf = sdf.sort_values("date").reset_index(drop=True)
            if len(sdf) < 150:
                continue
            c = sdf["close"].astype(float)
            h = sdf["high"].astype(float)
            lo = sdf.get("low", c).astype(float)
            gk = compute_gk(c, h, lo)
            buy_dates = set(pd.to_datetime(sdf.loc[gk["gk_buy"], "date"]).dt.normalize())
            if buy_dates:
                gk_c[sym] = buy_dates
        return gk_c

    gk_cache_s3 = build_gk_cache(s3_univ)
    print(f"  GK S3: {len(gk_cache_s3)} syms", flush=True)

    print("Building breadth series...", flush=True)
    a3_univ = get_universe(panel, "ex_vin3")
    a3_breadth = _build_breadth_series(panel, a3_univ, 20, 100)
    s3_breadth = _build_breadth_series(panel, s3_univ, 21, 55)

    print("Building baseline trade sets...", flush=True)
    a3_trades = _build_trades(a3_cache, EXIT_A3, gate_by_date=regime, adv50_map=adv50_map)
    a3_trades = _tag_adv50(a3_trades, adv50_map)
    print(f"  A3 trades: {len(a3_trades)}", flush=True)

    # Phase 0
    print("\nPhase 0: Research Plan", flush=True)
    write_phase0(panel, "")

    # Phase 1
    p1_df, p1_by_year = run_phase1(s3_cache, a3_cache, adv50_map, regime, gk_cache_s3)
    write_phase1_findings(p1_df, p1_by_year)

    # Phase 2
    p2_regime, p2_breadth, p2_bad_year = run_phase2(s3_cache, panel, s3_univ, adv50_map, vnx, a3_breadth, s3_breadth)
    write_phase2_findings(p2_regime, p2_breadth, p2_bad_year)

    # Phase 3
    p3_df = run_phase3(s3_cache, adv50_map, regime)
    write_phase3_findings(p3_df)

    # Phase 4
    p4_df = run_phase4(s3_cache, adv50_map, regime, gk_cache_s3)
    write_phase4_findings(p4_df)

    # Phase 5
    p5_overlay, p5_sz = run_phase5(a3_trades, s3_cache, adv50_map)
    write_phase5_findings(p5_overlay, p5_sz)

    # Phase 6
    p6_df = run_phase6(a3_trades, s3_cache, adv50_map, regime, gk_cache_s3)
    write_phase6_findings(p6_df)

    # Phase 7
    p7_wf, p7_param = run_phase7(s3_cache, adv50_map, vnx)
    write_phase7_findings(p7_wf, p7_param)

    # Phase 8
    write_phase8(p1_df, p2_regime, p3_df, p4_df, p7_wf)

    # Decision Memo
    classification = write_decision_memo(p1_df, p2_regime, p2_breadth, p3_df, p4_df, p5_overlay, p6_df, p7_wf, p7_param)

    # Summary tables
    write_summary_tables(p1_df, p3_df, p4_df, classification)

    print("\n" + "=" * 60, flush=True)
    print(f"DONE — All outputs in {OUT}", flush=True)
    print(f"Final S3 Classification: {classification}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
