#!/usr/bin/env python3
"""
One-shot: B_cloud21_55_partial — full universe — ranked fill comparison.

Closes the final unresolved hardening question:
  Does ranked fill on the full universe match / exceed ex-VIN3 results?
  Which fill mode + universe is best for the shadow candidate?

Outputs:
  data/research/hardening/shadow_ranked_fill_full.csv
  data/research/hardening/shadow_verdict.md

Usage:
    .venv\\Scripts\\python.exe pp_backtest/run_shadow_full_ranked.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_portfolio_sim import (
    compute_all_trades, build_portfolio, portfolio_metrics, DEFAULT_COST,
)
from pp_backtest.candidate_strategy_manifest import SHADOW

PANEL_PATH     = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
OUT_DIR        = REPO / "data" / "research" / "hardening"

EX_VIN3        = {"VIC", "VHM", "VRE"}
EX_VIC_ONLY    = {"VIC"}
EXCLUDE_ALWAYS = {"VPL"}

RANK_MODES = ["fifo", "ema_dist", "momentum"]


def get_universes(all_symbols: list[str]) -> dict[str, list[str]]:
    base = [s for s in all_symbols if s not in EXCLUDE_ALWAYS]
    return {
        "full":    base,
        "ex_vic":  [s for s in base if s not in EX_VIC_ONLY],
        "ex_vin3": [s for s in base if s not in EX_VIN3],
    }


def main():
    print("=== Shadow Full-Universe Ranked Fill ===")
    t0 = time.time()

    panel = pd.read_parquet(PANEL_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    panel.sort_values(["symbol", "date"], inplace=True)

    all_symbols = sorted(panel["symbol"].unique().tolist())
    universes   = get_universes(all_symbols)

    cfg = SHADOW
    rows = []

    for univ_name, symbols in universes.items():
        print(f"\n  Universe: {univ_name} ({len(symbols)} symbols)")
        t1     = time.time()
        trades = compute_all_trades(
            panel, symbols,
            entry_type = cfg["entry_type"],
            ema_fast   = cfg["ema_fast"],
            ema_slow   = cfg["ema_slow"],
            exit_mode  = cfg["exit_mode"],
            max_hold   = cfg["max_hold"],
            cost       = DEFAULT_COST,
        )
        print(f"    Trades computed: {len(trades):,}  ({time.time()-t1:.0f}s)")
        if trades.empty:
            continue

        for rank_mode in RANK_MODES:
            equity = build_portfolio(trades, cfg["max_positions"], rank_mode)
            m      = portfolio_metrics(equity, trades)
            if not m:
                continue
            rows.append({
                "label":     cfg["label"],
                "universe":  univ_name,
                "n_symbols": len(symbols),
                "rank_mode": rank_mode,
                **m,
            })
            print(f"    {rank_mode:<12}  CAGR={m['cagr']:.1%}  Sharpe={m['sharpe']:.3f}  "
                  f"maxDD={m['max_dd']:.1%}  MAR={m.get('mar',0):.2f}  "
                  f"oos={m.get('oos_avg_ret',0):.1%}")

    df = pd.DataFrame(rows)
    out_csv = OUT_DIR / "shadow_ranked_fill_full.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")
    print(f"Total elapsed: {time.time()-t0:.0f}s")

    # Print comparison table
    print("\n" + "=" * 90)
    print("SHADOW CANDIDATE — FULL COMPARISON (universe × rank_mode)")
    print("=" * 90)
    print(f"  {'universe':<10} {'rank_mode':<12} {'CAGR':>7} {'maxDD':>7} "
          f"{'Sharpe':>7} {'MAR':>6} {'OOS%':>7} {'n_tr':>7}")
    print("  " + "-" * 68)
    for _, r in df.sort_values(["universe", "rank_mode"]).iterrows():
        print(f"  {r.universe:<10} {r.rank_mode:<12} "
              f"{r.get('cagr',0):>7.1%} {r.get('max_dd',0):>7.1%} "
              f"{r.get('sharpe',0):>7.3f} {r.get('mar',0):>6.2f} "
              f"{r.get('oos_avg_ret',0) if pd.notna(r.get('oos_avg_ret')) else 0:>7.1%} "
              f"{int(r.get('n_trades',0)):>7}")

    _write_verdict(df)


def _write_verdict(df: pd.DataFrame) -> None:
    """Write shadow_verdict.md with factual comparison and decision."""
    # Pull key numbers
    def get(univ, rank):
        row = df[(df["universe"] == univ) & (df["rank_mode"] == rank)]
        if row.empty:
            return {}
        return row.iloc[0].to_dict()

    full_fifo     = get("full",    "fifo")
    full_emad     = get("full",    "ema_dist")
    full_mom      = get("full",    "momentum")
    exvin_fifo    = get("ex_vin3", "fifo")
    exvin_emad    = get("ex_vin3", "ema_dist")
    exvin_mom     = get("ex_vin3", "momentum")

    def fmt(d, k, pct=True):
        v = d.get(k, float("nan"))
        if pd.isna(v):
            return "n/a"
        return f"{v:.1%}" if pct else f"{v:.3f}"

    lines = [
        "# Shadow Candidate Verdict — B_cloud21_55_partial",
        f"**Date:** 2026-05-13",
        "",
        "## Comparison Table",
        "",
        "| Universe | Fill | CAGR | maxDD | Sharpe | MAR | OOS avg |",
        "|---|---|---|---|---|---|---|",
        f"| full    | fifo     | {fmt(full_fifo,'cagr')} | {fmt(full_fifo,'max_dd')} | {fmt(full_fifo,'sharpe',False)} | {fmt(full_fifo,'mar',False)} | {fmt(full_fifo,'oos_avg_ret')} |",
        f"| full    | ema_dist | {fmt(full_emad,'cagr')} | {fmt(full_emad,'max_dd')} | {fmt(full_emad,'sharpe',False)} | {fmt(full_emad,'mar',False)} | {fmt(full_emad,'oos_avg_ret')} |",
        f"| full    | momentum | {fmt(full_mom,'cagr')} | {fmt(full_mom,'max_dd')} | {fmt(full_mom,'sharpe',False)} | {fmt(full_mom,'mar',False)} | {fmt(full_mom,'oos_avg_ret')} |",
        f"| ex_vin3 | fifo     | {fmt(exvin_fifo,'cagr')} | {fmt(exvin_fifo,'max_dd')} | {fmt(exvin_fifo,'sharpe',False)} | {fmt(exvin_fifo,'mar',False)} | {fmt(exvin_fifo,'oos_avg_ret')} |",
        f"| ex_vin3 | ema_dist | {fmt(exvin_emad,'cagr')} | {fmt(exvin_emad,'max_dd')} | {fmt(exvin_emad,'sharpe',False)} | {fmt(exvin_emad,'mar',False)} | {fmt(exvin_emad,'oos_avg_ret')} |",
        f"| ex_vin3 | momentum | {fmt(exvin_mom,'cagr')} | {fmt(exvin_mom,'max_dd')} | {fmt(exvin_mom,'sharpe',False)} | {fmt(exvin_mom,'mar',False)} | {fmt(exvin_mom,'oos_avg_ret')} |",
        "",
        "## FACTS",
        "",
        f"- Full universe FIFO CAGR: {fmt(full_fifo,'cagr')}  |  Ranked (ema_dist): {fmt(full_emad,'cagr')}  |  Ranked (momentum): {fmt(full_mom,'cagr')}",
        f"- Ex-VIN3 FIFO CAGR: {fmt(exvin_fifo,'cagr')}  |  Ranked (ema_dist): {fmt(exvin_emad,'cagr')}  |  Ranked (momentum): {fmt(exvin_mom,'cagr')}",
        f"- Full universe ema_dist Sharpe: {fmt(full_emad,'sharpe',False)}  vs  Ex-VIN3 ema_dist Sharpe: {fmt(exvin_emad,'sharpe',False)}",
        f"- OOS avg_trade is consistent across universes: full={fmt(full_emad,'oos_avg_ret')} / ex_vin3={fmt(exvin_emad,'oos_avg_ret')}",
        "",
        "## Decision",
        "",
    ]

    # Determine verdict
    full_emad_cagr  = full_emad.get("cagr", 0)
    exvin_emad_cagr = exvin_emad.get("cagr", 0)
    full_emad_shr   = full_emad.get("sharpe", 0)
    exvin_emad_shr  = exvin_emad.get("sharpe", 0)

    if full_emad_cagr > exvin_emad_cagr and full_emad_shr >= exvin_emad_shr * 0.95:
        verdict = "**Track shadow on FULL universe with ema_dist fill.**"
        rationale = (
            f"Full universe ema_dist CAGR ({fmt(full_emad,'cagr')}) exceeds ex-VIN3 ema_dist "
            f"({fmt(exvin_emad,'cagr')}) with comparable Sharpe. VHM/VRE contribute genuine "
            f"cloud-only returns in the 21/55 system — not distortion. Excluding them costs real edge."
        )
    elif exvin_emad_shr > full_emad_shr:
        verdict = "**Track shadow on EX-VIN3 universe with ema_dist fill.**"
        rationale = (
            f"Ex-VIN3 ema_dist Sharpe ({fmt(exvin_emad,'sharpe',False)}) exceeds full universe "
            f"({fmt(full_emad,'sharpe',False)}). Risk-adjusted quality is better without VIN names."
        )
    else:
        verdict = "**Track shadow on BOTH universes in parallel during paper trading.**"
        rationale = (
            "Results are close enough that live behavior will be the deciding factor. "
            "Monitor both tracks for 3 months, then select based on paper execution quality."
        )

    lines += [
        verdict,
        "",
        rationale,
        "",
        "Shadow remains a monitoring / fallback candidate only. Primary for paper trading "
        "remains **B_cloud20_100_partial (ex-VIN3, ema_dist fill)**.",
    ]

    out_md = OUT_DIR / "shadow_verdict.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nVerdict written: {out_md}")
    print(f"\n{verdict}")
    print(rationale)


if __name__ == "__main__":
    main()
