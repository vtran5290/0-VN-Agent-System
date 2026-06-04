#!/usr/bin/env python3
"""Run Trend Speed × 2-cloud research (v2 — exact T2, Pine speed). OBSERVATION ONLY."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import load_panel, load_vnindex_regime
from scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation import (
    _simulate_a3_trade_blended,
)
from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import _atr14
from scripts.research.trend_speed_2cloud.engine import (
    OUT_DIR,
    ENTRY_FILTERS,
    HAS_EXISTING_A3_RANK,
    T2_GATES,
    apply_entry_filter,
    classify_variant,
    collect_trades,
    compare_to_baseline,
    load_breadth,
    rank_decile_analysis,
    resimulate_a3_with_t2_gates,
    select_daily_slots,
    trade_metrics,
    attach_tsa_ranks,
)
from src.research.indicators.trend_speed_analyzer import compute_tsa_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

RANK_COLS = ["tsa_rank_composite", "tsa_rank_1", "tsa_rank_2", "tsa_rank_3"]
BASELINE_MAR_TOLERANCE = 0.015


def _prepare_panels(ex_vin: bool) -> dict:
    panels = load_panel(ex_vin=ex_vin)
    for sym, df in panels.items():
        tsa = attach_tsa_ranks(compute_tsa_features(df))
        for c in tsa.columns:
            df[c] = tsa[c].values
    return panels


def _run_entry_matrix(trades: pd.DataFrame, baseline_metrics: dict) -> pd.DataFrame:
    rows = []
    base_trades = trades.copy()
    for name in ENTRY_FILTERS:
        filt = apply_entry_filter(trades, name)
        m = trade_metrics(filt)
        cmp = compare_to_baseline(baseline_metrics, m, base_trades, filt)
        rows.append(
            {
                "variant": name,
                "group": "entry",
                **m,
                **cmp,
                "classification": classify_variant(baseline_metrics, m, cmp),
            }
        )
    return pd.DataFrame(rows)


def _run_ranking(a3_trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    modes = [
        ("fifo", "fifo"),
        ("tsa_composite_only", "tsa_composite_only"),
    ]
    if HAS_EXISTING_A3_RANK:
        modes.extend(
            [
                ("existing_rank_only", "existing_rank_only"),
                ("existing_rank_then_tsa_tiebreak", "existing_rank_then_tsa_tiebreak"),
            ]
        )

    perf_rows = []
    decile_parts = []
    for label, mode in modes:
        sel = select_daily_slots(a3_trades, mode, tiebreak_col="tsa_rank_composite")
        m = trade_metrics(sel)
        perf_rows.append(
            {
                "rank_mode": label,
                "implemented": len(sel) > 0 or mode == "fifo",
                "has_existing_a3_rank": HAS_EXISTING_A3_RANK,
                **m,
            }
        )
        for rc in RANK_COLS:
            dec = rank_decile_analysis(a3_trades, rc)
            if not dec.empty:
                dec["rank_mode"] = label
                decile_parts.append(dec)

    return pd.DataFrame(perf_rows), pd.concat(decile_parts, ignore_index=True) if decile_parts else pd.DataFrame()


def _run_t2_matrix(a3_trades: pd.DataFrame, panels: dict, breadth: pd.Series, baseline_metrics: dict) -> pd.DataFrame:
    log.info("Exact T2 re-simulation for %d variants...", len(T2_GATES))
    by_var = resimulate_a3_with_t2_gates(a3_trades, panels, breadth)
    rows = []
    for variant, tdf in by_var.items():
        m = trade_metrics(tdf)
        cmp = compare_to_baseline(baseline_metrics, m, a3_trades, tdf)
        blocked = int(tdf.get("t2_blocked_by_tsa", pd.Series(dtype=bool)).sum()) if "t2_blocked_by_tsa" in tdf else 0
        rows.append(
            {
                "variant": variant,
                "simulation": "exact_t1_t2_resim",
                **m,
                **cmp,
                "t2_filled_rate": float(tdf["t2_filled"].mean()) if len(tdf) else np.nan,
                "t2_blocked_by_tsa_count": blocked,
                "classification": classify_variant(baseline_metrics, m, cmp),
            }
        )
        tdf.to_csv(OUT_DIR / "review_pack" / f"a3_trades_{variant}.csv", index=False)
    return pd.DataFrame(rows)


def _validate_baseline_vs_stage13(a3_trades: pd.DataFrame, panels: dict, breadth: pd.Series) -> dict:
    """Spot-check C0 vs stage13 on rows where breadth does not block T2."""
    diffs = []
    sample = a3_trades.head(200)
    for _, row in sample.iterrows():
        sym = row["symbol"]
        bar = int(row["signal_bar"])
        df = panels.get(sym)
        if df is None:
            continue
        if row.get("t2_blocked_by_breadth"):
            continue
        ref = _simulate_a3_trade_blended(bar, df, _atr14(df).values)
        if ref is None:
            continue
        v = row.get("blended_net_return", np.nan)
        r = ref.get("blended_net_return", np.nan)
        if pd.notna(v) and pd.notna(r):
            diffs.append(abs(v - r))
    return {
        "n_compared": len(diffs),
        "max_abs_diff": float(max(diffs)) if diffs else np.nan,
        "mean_abs_diff": float(np.mean(diffs)) if diffs else np.nan,
        "within_1e6": bool(max(diffs) < 1e-6) if diffs else False,
    }


def _charts(a3_base: pd.DataFrame, a3_best: pd.DataFrame, entry_df: pd.DataFrame, deciles: pd.DataFrame, out: Path) -> None:
    charts = out / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    def _equity_curve(tr):
        sub = tr[tr["matured"] == True].sort_values("signal_date")  # noqa: E712
        if sub.empty:
            return None, None
        daily = sub.groupby("signal_date")["blended_net_return"].mean()
        eq = (1 + daily).cumprod()
        return eq.index, eq.values

    x0, y0 = _equity_curve(a3_base)
    x1, y1 = _equity_curve(a3_best)
    if x0 is not None:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x0, y0, label="A3 baseline")
        if x1 is not None:
            ax.plot(x1, y1, label="A3 best entry", alpha=0.8)
        ax.legend()
        ax.set_title("Equity curve (daily mean return)")
        fig.tight_layout()
        fig.savefig(charts / "equity_baseline_vs_best.png", dpi=120)
        plt.close(fig)

    dec = deciles[deciles["rank_col"] == "tsa_rank_composite"] if "rank_col" in deciles.columns else deciles
    if not dec.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(dec["decile"], dec["avg_return"])
        ax.set_title("TSA composite rank decile vs avg return")
        fig.tight_layout()
        fig.savefig(charts / "rank_decile_returns.png", dpi=120)
        plt.close(fig)

    ent = entry_df[entry_df.get("group", "") == "entry"] if "group" in entry_df.columns else entry_df
    if not ent.empty and "delta_mar" in ent.columns:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.scatter(ent["trade_count_retained_pct"], ent["delta_mar"])
        for _, r in ent.iterrows():
            ax.annotate(r["variant"], (r["trade_count_retained_pct"], r["delta_mar"]), fontsize=7)
        ax.axhline(0, color="gray", lw=0.5)
        fig.tight_layout()
        fig.savefig(charts / "retained_vs_mar.png", dpi=120)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-universe", action="store_true")
    args = parser.parse_args()
    ex_vin = not args.full_universe

    pack_dir = OUT_DIR / "review_pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    panels = _prepare_panels(ex_vin=ex_vin)
    breadth = load_breadth()
    a3_regime = load_vnindex_regime(20, 100)
    s3_regime = load_vnindex_regime(21, 55)

    log.info("Collecting A3/S3 baseline trades (exact T2 for A3)...")
    a3_trades = collect_trades("A3", panels, a3_regime, breadth, ex_vin=ex_vin)
    s3_trades = collect_trades("S3", panels, s3_regime, breadth, ex_vin=ex_vin)

    a3_trades.to_csv(pack_dir / "a3_trades_baseline.csv", index=False)
    s3_trades.to_csv(pack_dir / "s3_trades_baseline.csv", index=False)
    a3_trades.head(500).to_csv(pack_dir / "tsa_feature_sample.csv", index=False)

    baseline_check = _validate_baseline_vs_stage13(a3_trades, panels, breadth)
    (pack_dir / "baseline_validation.json").write_text(json.dumps(baseline_check, indent=2), encoding="utf-8")
    log.info("Baseline vs stage13: %s", baseline_check)

    a3_base_m = trade_metrics(a3_trades)
    s3_base_m = trade_metrics(s3_trades)

    a3_entry = _run_entry_matrix(a3_trades, a3_base_m)
    s3_entry = _run_entry_matrix(s3_trades, s3_base_m)
    a3_entry["sleeve"] = "A3"
    s3_entry["sleeve"] = "S3"
    a3_entry.to_csv(pack_dir / "a3_baseline_vs_tsa_variants.csv", index=False)
    s3_entry.to_csv(pack_dir / "s3_baseline_vs_tsa_variants.csv", index=False)

    rank_perf, rank_dec = _run_ranking(a3_trades)
    rank_perf.to_csv(pack_dir / "ranking_mode_summary_a3.csv", index=False)
    rank_dec.to_csv(pack_dir / "tsa_rank_deciles_a3.csv", index=False)
    for rc in RANK_COLS:
        rank_decile_analysis(a3_trades, rc).to_csv(pack_dir / f"tsa_rank_deciles_a3_{rc}.csv", index=False)

    a3_t2 = _run_t2_matrix(a3_trades, panels, breadth, a3_base_m)
    a3_t2.to_csv(pack_dir / "t2_gate_results_a3.csv", index=False)

    pd.DataFrame(
        [
            {
                "note": "Exit overlay REMOVED in v2 — prior D2–D5 used single-leg S3 simulator, not comparable to A3 blended T1/T2.",
                "status": "NOT_RUN_INCONCLUSIVE",
            }
        ]
    ).to_csv(pack_dir / "exit_overlay_results_a3.csv", index=False)

    yearly, regime = _robustness(pd.concat([a3_trades, s3_trades], ignore_index=True))
    yearly.to_csv(pack_dir / "yearly_robustness.csv", index=False)
    regime.to_csv(pack_dir / "regime_robustness.csv", index=False)

    best_entry = a3_entry.sort_values("mar", ascending=False).iloc[0]["variant"] if len(a3_entry) else "A0_baseline"
    best_t2 = a3_t2.sort_values("mar", ascending=False).iloc[0] if len(a3_t2) else None
    best_rank = rank_perf.sort_values("mar", ascending=False).iloc[0] if len(rank_perf) else None

    summary = {
        "version": "v2",
        "pine_speed_reset": "fixed_double_add_on_cross",
        "t2_simulation": "exact_resim_per_gate",
        "has_existing_a3_rank": HAS_EXISTING_A3_RANK,
        "a3_baseline": a3_base_m,
        "s3_baseline": s3_base_m,
        "best_a3_entry": best_entry,
        "best_a3_t2": best_t2.to_dict() if best_t2 is not None else {},
        "best_rank_mode": best_rank.to_dict() if best_rank is not None else {},
        "baseline_validation": baseline_check,
        "exit_overlay": "removed_v2",
    }
    (pack_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    _charts(a3_trades, apply_entry_filter(a3_trades, best_entry), a3_entry, rank_dec, pack_dir)
    log.info("Done — %s", OUT_DIR)


def _robustness(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sub = trades[trades["matured"] == True]  # noqa: E712
    yearly = (
        sub.groupby(["sleeve", sub["signal_date"].dt.year])["blended_net_return"]
        .agg(n="count", avg_return="mean", win_rate=lambda x: (x > 0).mean())
        .reset_index()
    )
    yearly.columns = ["sleeve", "year", "n", "avg_return", "win_rate"]
    if "tp1_hit" in sub.columns:
        tp1 = (
            sub.assign(year=sub["signal_date"].dt.year)
            .groupby(["sleeve", "year"])["tp1_hit"]
            .mean()
            .reset_index(name="tp1_rate")
        )
        yearly = yearly.merge(tp1, on=["sleeve", "year"], how="left")

    regime_rows = []
    for sleeve, g in sub.groupby("sleeve"):
        for regime, rg in g.groupby("regime_bull"):
            regime_rows.append(
                {
                    "sleeve": sleeve,
                    "regime": "bull" if regime else "bear_sideways",
                    "n": len(rg),
                    "avg_return": float(rg["blended_net_return"].mean()),
                    "win_rate": float((rg["blended_net_return"] > 0).mean()),
                }
            )
    return yearly, pd.DataFrame(regime_rows)


if __name__ == "__main__":
    main()
