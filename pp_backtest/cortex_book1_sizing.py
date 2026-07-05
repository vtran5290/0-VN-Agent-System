#!/usr/bin/env python3
"""
Cortex Book #1 — fixed-fractional risk-per-trade sizing backtest (2012-present).

Baseline: A3 P1 honest + D4 cash yield + D3 sector slot sizing (1.25/0.75).
Candidates: same entry stream, sizing by risk_pct / initial-stop distance at
1.25%, 1.75%, 2.5% (three separate sub-tests).

RESEARCH_ONLY_NOT_PRODUCTION — does not touch sizing_policy.py or live paths.

Usage:
  python pp_backtest/cortex_book1_sizing.py
"""
from __future__ import annotations

import sys
import warnings
from datetime import date
from typing import Any

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_book1_common import (
    G1A_MARGIN,
    G1B_FLOOR,
    IS_WINDOW,
    OOS_WINDOW,
    OUT_DIR,
    PANEL_END,
    PANEL_START,
    RESEARCH_LABEL,
    RISK_PCT_CANDIDATES,
    build_entry_price_atr_map,
    evaluate_gates,
    prepare_risk_pct_trades,
    write_report,
)
from pp_backtest.d1_capital_based_validation import _metrics_from_equity
from pp_backtest.d3_sector_rs_validation import D4_CASH_YIELD, assert_frozen_a3, run_capital_sim, signal_stream
from pp_backtest.sprint2b_common import build_baseline_stack, slice_equity_last_months, slice_equity_years


def run_cortex_book1() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Cortex Book #1 — fixed-fractional risk-per-trade sizing", flush=True)
    print(f"  Window: {PANEL_START} -> {PANEL_END}", flush=True)
    print(f"  Gates: G1a +{G1A_MARGIN:.3f} MAR vs baseline OOS; G1b floor {G1B_FLOOR:.3f}", flush=True)
    print(f"  OOS primary: {OOS_WINDOW[0]}-{OOS_WINDOW[1]}", flush=True)

    stack = build_baseline_stack()
    ctx = stack["ctx"]
    base_trades = stack["base_trades"]
    eq_base = stack["eq"]
    prep_base = stack["prep"]

    price_atr_map = build_entry_price_atr_map(ctx.panel)

    m_base_full = _metrics_from_equity(eq_base)
    eq_base_oos = slice_equity_years(eq_base, OOS_WINDOW[0], OOS_WINDOW[1])
    eq_base_oos12 = slice_equity_last_months(eq_base)
    eq_base_is = slice_equity_years(eq_base, IS_WINDOW[0], IS_WINDOW[1])
    m_base_oos = _metrics_from_equity(eq_base_oos)
    m_base_oos12 = _metrics_from_equity(eq_base_oos12)
    m_base_is = _metrics_from_equity(eq_base_is)

    print(
        f"  Baseline full MAR={m_base_full['mar']:.4f} OOS={m_base_oos['mar']:.4f} "
        f"OOS12m={m_base_oos12['mar']:.4f}",
        flush=True,
    )

    candidate_rows: list[dict[str, Any]] = []
    for risk_pct in RISK_PCT_CANDIDATES:
        label = f"{risk_pct * 100:.2f}%"
        print(f"  Candidate risk_pct={label}...", flush=True)

        cand_trades = base_trades.copy()
        assert_frozen_a3(base_trades, cand_trades, "identity", f"risk_{label}")
        frozen_ok = signal_stream(base_trades) == signal_stream(cand_trades)

        prep_cand = prepare_risk_pct_trades(cand_trades, price_atr_map, risk_pct)
        eq_cand, fills, ann_rt = run_capital_sim(prep_cand, ctx.gate, D4_CASH_YIELD)

        m_full = _metrics_from_equity(eq_cand)
        m_oos = _metrics_from_equity(slice_equity_years(eq_cand, OOS_WINDOW[0], OOS_WINDOW[1]))
        m_oos12 = _metrics_from_equity(slice_equity_last_months(eq_cand))
        m_is = _metrics_from_equity(slice_equity_years(eq_cand, IS_WINDOW[0], IS_WINDOW[1]))
        gates, verdict = evaluate_gates(m_base_oos, m_oos, frozen_ok)

        candidate_rows.append(
            {
                "risk_pct": risk_pct,
                "risk_pct_label": label,
                "verdict": verdict,
                "full": m_full,
                "oos": m_oos,
                "oos_12m": m_oos12,
                "is": m_is,
                "gates": gates,
                "frozen_a3_ok": frozen_ok,
                "n_trades_prepared": len(prep_cand),
                "n_trades_baseline": len(prep_base),
                "annual_turnover_rts": ann_rt,
            }
        )
        print(f"    OOS MAR={m_oos['mar']:.4f} verdict={verdict}", flush=True)

    meta: dict[str, Any] = {
        "generated": str(date.today()),
        "research_label": RESEARCH_LABEL,
        "panel_start": PANEL_START,
        "panel_end": PANEL_END,
        "oos_window": list(OOS_WINDOW),
        "is_window": list(IS_WINDOW),
        "g1a_margin": G1A_MARGIN,
        "g1b_floor": G1B_FLOOR,
        "initial_stop_atr": 2.0,
        "baseline_full": m_base_full,
        "baseline_oos": m_base_oos,
        "baseline_oos_12m": m_base_oos12,
        "baseline_is": m_base_is,
        "candidates": candidate_rows,
    }
    write_report(meta)
    print(f"\nReport: {OUT_DIR / 'cortex_book1_sizing_report.md'}", flush=True)
    return meta


def main() -> None:
    run_cortex_book1()


if __name__ == "__main__":
    main()
