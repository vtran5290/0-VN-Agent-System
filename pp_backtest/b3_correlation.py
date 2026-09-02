#!/usr/bin/env python3
"""
B3 — Preliminary Sleeve Correlation Analysis.

Computes pairwise correlation between A3_RS, W2, IA annual return streams.
Also builds daily equity curves from honest trade ledgers for granular correlation.

Caveats (must report):
  - W2 and IA have ~78% mean cash → sparse equity, correlation may be noisy
  - Different regime gates across sleeves (A3=EMA20>100, W2=TT_Lite, IA=normal_regime)
  - Annual returns give direction; daily equity gives precision
  - Low correlation + low MAR still ≠ useful diversifier

Usage:
  python pp_backtest/b3_correlation.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION, DATA_END, DATA_START, GK_MULT,
    MAX_POSITIONS, PORTFOLIO_VND, binary_gate_ema20_100,
)
from pp_backtest.portfolio_optimization_phase1 import load_panel, load_vnindex
from pp_backtest.portfolio_optimization_phase31 import _build_adv50_map, _tag_adv50
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.p3_rs_cashyield import _compute_rs_scores, _build_equity_with_cash_yield
from pp_backtest.p0_realism_p1_winner import _build_honest_cache, _simulate_honest_trades

OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "b3_correlation"
SLEEVE_W2 = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_w2"
SLEEVE_IA = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_ia"
SLEEVE_A3 = REPO / "data" / "research" / "portfolio_optimization" / "p3_rs_cashyield"


def _build_equity_from_trades(trades: pd.DataFrame, rank_col: str | None = None) -> pd.Series:
    """Build daily equity curve from a trade ledger using the shared equity builder."""
    if trades.empty:
        return pd.Series(dtype=float)

    trades = trades.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["exit_date"] = pd.to_datetime(trades["exit_date"])

    if "adv50_value" not in trades.columns:
        trades["adv50_value"] = 0.0
    if "has_gk" not in trades.columns:
        trades["has_gk"] = False
    if "total_frac" not in trades.columns:
        trades["total_frac"] = 1.0
    if "t1_frac" not in trades.columns:
        trades["t1_frac"] = 0.5

    eq, _ = _build_equity_with_cash_yield(
        trades, MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
        rank_col=rank_col, cash_yield_annual=0.0,
    )
    return eq


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("B3 Correlation Analysis", flush=True)

    # --- Load annual returns ---
    a3_ann = pd.read_csv(SLEEVE_A3 / "p3_annual_returns.csv")
    w2_ann = pd.read_csv(SLEEVE_W2 / "w2_annual_returns.csv")
    ia_ann = pd.read_csv(SLEEVE_IA / "ia_annual_returns.csv")

    ann_df = pd.DataFrame({
        "year": a3_ann["year"],
        "A3_RS": a3_ann["rs_ranked"],
        "W2": w2_ann["annual_return"],
        "IA": ia_ann["annual_return"],
    }).dropna()

    ann_corr = ann_df[["A3_RS", "W2", "IA"]].corr()
    print("\n=== Annual Return Correlation ===")
    print(ann_corr.to_string(float_format="%.4f"))

    ann_corr.to_csv(OUT_DIR / "b3_annual_correlation.csv", float_format="%.4f")
    ann_df.to_csv(OUT_DIR / "b3_annual_returns_combined.csv", index=False, float_format="%.6f")

    # --- Build daily equity curves from honest trade ledgers ---
    print("\nBuilding daily equity curves from trade ledgers...", flush=True)

    a3_trades = pd.read_csv(SLEEVE_A3.parent / "p3_rs_cashyield" / "../../.." / ".." / "pp_backtest" / "dummy.csv",
                             on_bad_lines="skip") if False else None

    # A3: rebuild from honest trades (same as Phase A)
    print("  A3_RS: rebuilding equity from P0 honest trades...", flush=True)
    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)]
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)

    honest_cache = _build_honest_cache(panel)
    a3_honest = _simulate_honest_trades(honest_cache, gate, adv)
    rs_scores = _compute_rs_scores(panel, a3_honest)
    a3_honest["rs_score"] = rs_scores
    a3_tagged = _tag_adv50(a3_honest.copy(), adv)

    eq_a3 = _build_equity_from_trades(
        a3_tagged.drop(columns=["ema_dist_at_entry"], errors="ignore"),
        rank_col="rs_score",
    )

    # W2: from honest trade ledger
    print("  W2: building equity from honest trade ledger...", flush=True)
    w2_trades = pd.read_csv(SLEEVE_W2 / "w2_honest_p0_trades.csv")
    eq_w2 = _build_equity_from_trades(w2_trades)

    # IA: from honest trade ledger
    print("  IA: building equity from honest trade ledger...", flush=True)
    ia_trades = pd.read_csv(SLEEVE_IA / "ia_honest_p0_trades.csv")
    eq_ia = _build_equity_from_trades(ia_trades)

    # --- Align equity curves on common dates ---
    print("  Aligning equity curves...", flush=True)
    eq_combined = pd.DataFrame({
        "A3_RS": eq_a3,
        "W2": eq_w2,
        "IA": eq_ia,
    }).dropna()

    if eq_combined.empty or len(eq_combined) < 20:
        print(f"WARNING: Only {len(eq_combined)} overlapping daily observations — correlation will be noisy.")

    # Daily returns
    daily_ret = eq_combined.pct_change().dropna()
    daily_corr = daily_ret.corr()

    print(f"\n=== Daily Return Correlation ({len(daily_ret)} obs) ===")
    print(daily_corr.to_string(float_format="%.4f"))

    # Weekly returns (less noisy)
    weekly_eq = eq_combined.resample("W-FRI").last().dropna()
    weekly_ret = weekly_eq.pct_change().dropna()
    weekly_corr = weekly_ret.corr() if len(weekly_ret) > 10 else pd.DataFrame()

    if not weekly_corr.empty:
        print(f"\n=== Weekly Return Correlation ({len(weekly_ret)} obs) ===")
        print(weekly_corr.to_string(float_format="%.4f"))

    # Monthly returns
    monthly_eq = eq_combined.resample("ME").last().dropna()
    monthly_ret = monthly_eq.pct_change().dropna()
    monthly_corr = monthly_ret.corr() if len(monthly_ret) > 10 else pd.DataFrame()

    if not monthly_corr.empty:
        print(f"\n=== Monthly Return Correlation ({len(monthly_ret)} obs) ===")
        print(monthly_corr.to_string(float_format="%.4f"))

    # --- Save outputs ---
    daily_corr.to_csv(OUT_DIR / "b3_daily_correlation.csv", float_format="%.4f")
    daily_ret.to_csv(OUT_DIR / "b3_daily_returns.csv", float_format="%.6f")
    eq_combined.to_csv(OUT_DIR / "b3_equity_curves.csv", float_format="%.6f")

    if not weekly_corr.empty:
        weekly_corr.to_csv(OUT_DIR / "b3_weekly_correlation.csv", float_format="%.4f")
    if not monthly_corr.empty:
        monthly_corr.to_csv(OUT_DIR / "b3_monthly_correlation.csv", float_format="%.4f")

    # --- Interpretation ---
    a3_w2_daily = float(daily_corr.loc["A3_RS", "W2"]) if "W2" in daily_corr.columns else np.nan
    a3_ia_daily = float(daily_corr.loc["A3_RS", "IA"]) if "IA" in daily_corr.columns else np.nan
    w2_ia_daily = float(daily_corr.loc["W2", "IA"]) if "IA" in daily_corr.columns else np.nan

    a3_w2_ann = float(ann_corr.loc["A3_RS", "W2"])
    a3_ia_ann = float(ann_corr.loc["A3_RS", "IA"])
    w2_ia_ann = float(ann_corr.loc["W2", "IA"])

    diversifying_threshold = 0.50

    report = f"""# B3 — Preliminary Sleeve Correlation Analysis

Generated: {date.today()}

## FACTS — Honest P0 MAR by Sleeve

| Sleeve | Honest P0 MAR | CAGR | Status |
|--------|---------------|------|--------|
| A3_RS | 0.273 | ~5.0% | TREND_OVERLAY (accepted) |
| W2 | 0.074 | 0.56% | RESEARCH_ONLY (weak) |
| IA | -0.006 | -0.03% | RESEARCH_ONLY (negative) |

## Annual Return Correlation (n={len(ann_df)} years)

| Pair | Correlation |
|------|------------|
| A3_RS vs W2 | {a3_w2_ann:.4f} |
| A3_RS vs IA | {a3_ia_ann:.4f} |
| W2 vs IA | {w2_ia_ann:.4f} |

## Daily Return Correlation (n={len(daily_ret)} trading days)

| Pair | Correlation |
|------|------------|
| A3_RS vs W2 | {a3_w2_daily:.4f} |
| A3_RS vs IA | {a3_ia_daily:.4f} |
| W2 vs IA | {w2_ia_daily:.4f} |

{"## Weekly Return Correlation (n=" + str(len(weekly_ret)) + " weeks)" + chr(10) + chr(10) + "| Pair | Correlation |" + chr(10) + "|------|------------|" + chr(10) + f"| A3_RS vs W2 | {float(weekly_corr.loc['A3_RS', 'W2']):.4f} |" + chr(10) + f"| A3_RS vs IA | {float(weekly_corr.loc['A3_RS', 'IA']):.4f} |" + chr(10) + f"| W2 vs IA | {float(weekly_corr.loc['W2', 'IA']):.4f} |" if not weekly_corr.empty else "Weekly correlation: insufficient data"}

{"## Monthly Return Correlation (n=" + str(len(monthly_ret)) + " months)" + chr(10) + chr(10) + "| Pair | Correlation |" + chr(10) + "|------|------------|" + chr(10) + f"| A3_RS vs W2 | {float(monthly_corr.loc['A3_RS', 'W2']):.4f} |" + chr(10) + f"| A3_RS vs IA | {float(monthly_corr.loc['A3_RS', 'IA']):.4f} |" + chr(10) + f"| W2 vs IA | {float(monthly_corr.loc['W2', 'IA']):.4f} |" if not monthly_corr.empty else "Monthly correlation: insufficient data"}

## Caveats

1. **W2 and IA have ~78% mean cash** — equity curves are mostly flat with sparse active periods. Daily correlation on flat-vs-flat segments may show artificially low correlation that does not reflect true signal relationship.
2. **Different regime gates** — A3 uses EMA20>EMA100, W2 uses TT Lite (MA50/200), IA uses normal_regime. These gate differences are a confound: low correlation may reflect gate timing, not signal independence.
3. **Low correlation + low MAR does not equal useful diversifier.** A sleeve with near-zero returns adds noise, not diversification benefit. The portfolio-level question is whether combining sleeves improves risk-adjusted return, not just whether they are uncorrelated.
4. **Annual correlation is directionally useful but statistically weak** (n={len(ann_df)}). Daily and weekly correlations are more reliable.

## INTERPRETATION

- Diversifying threshold: correlation < {diversifying_threshold} suggests potential diversification benefit.
- A3_RS vs W2 daily correlation: {a3_w2_daily:.4f} — {"below" if a3_w2_daily < diversifying_threshold else "above"} threshold
- A3_RS vs IA daily correlation: {a3_ia_daily:.4f} — {"below" if a3_ia_daily < diversifying_threshold else "above"} threshold
- W2 vs IA daily correlation: {w2_ia_daily:.4f} — {"below" if w2_ia_daily < diversifying_threshold else "above"} threshold

**However:** even if correlations are low, W2 (MAR 0.074) and IA (MAR -0.006) add negligible or negative return. Diversification benefit is only real if the combined portfolio MAR improves meaningfully over A3 alone.

## Source
- A3_RS: pp_backtest/p3_rs_cashyield.py (Phase A, honest P0)
- W2: pp_backtest/sleeve_w2.py (Phase B, honest P0, TT Lite gate)
- IA: pp_backtest/sleeve_ia.py (Phase B, honest P0, normal_regime gate)
- All use canonical P0 realism: next-bar open, floor/ceiling, T+2, 0.40% RT
"""
    (OUT_DIR / "b3_correlation_report.md").write_text(report, encoding="utf-8")

    meta = {
        "generated": str(date.today()),
        "n_daily_obs": len(daily_ret),
        "n_weekly_obs": len(weekly_ret) if not weekly_corr.empty else 0,
        "n_monthly_obs": len(monthly_ret) if not monthly_corr.empty else 0,
        "n_annual_obs": len(ann_df),
        "daily_correlation": {
            "A3_RS_vs_W2": a3_w2_daily,
            "A3_RS_vs_IA": a3_ia_daily,
            "W2_vs_IA": w2_ia_daily,
        },
        "annual_correlation": {
            "A3_RS_vs_W2": a3_w2_ann,
            "A3_RS_vs_IA": a3_ia_ann,
            "W2_vs_IA": w2_ia_ann,
        },
    }
    (OUT_DIR / "b3_correlation_meta.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )

    print(f"\nWrote B3 outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
