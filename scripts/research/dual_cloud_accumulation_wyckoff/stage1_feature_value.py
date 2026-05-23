#!/usr/bin/env python3
"""Stage 1 — Feature Predictive Value

Tests whether accumulation/tightness features correlate with forward returns
on A3 cloud signals. Compares top-quintile vs all-signal baseline.

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage1_trades.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage1_quintile_summary.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage1_feature_correlations.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage1_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage1_feature_value.py
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage1_feature_value.py --ex-vin
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage1_feature_value.py --workers 8
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy import stats as scipy_stats
    _SCIPY_OK = True
except ImportError:
    scipy_stats = None  # type: ignore[assignment]
    _SCIPY_OK = False

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    accumulation_score_cross_sectional, compute_all_features,
)
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, HORIZONS, SUCCESS_TARGET, SUCCESS_STOP,
    a3_signal, adv_mask, forward_returns, load_panel,
    quintile_summary, score_quintile, trade_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

FEATURE_COLS = [
    "pt_20", "pt_40", "atr_ratio", "bar_range_pct", "range_vs_ma20",
    "vol_ratio", "vol_trend_10", "vol_below_streak", "vol_drying",
    "bo_vol_exp", "bo_close_str", "bo_range_exp",
]


def _process_symbol(sym: str, df: pd.DataFrame) -> pd.DataFrame | None:
    if len(df) < 150:
        return None
    try:
        df = compute_all_features(df)
        sig, _ef, _es = a3_signal(df)
        if sig.sum() == 0:
            return None

        # Do NOT add score to df here — score is computed cross-sectionally
        # across all symbols in run() after concat to avoid time-series lookahead.
        trades = forward_returns(df, sig, horizons=HORIZONS)
        if trades.empty:
            return None

        trades["symbol"] = sym
        trades["year"] = pd.to_datetime(trades["signal_date"]).dt.year
        return trades
    except Exception as exc:
        log.warning("Symbol %s failed: %s", sym, exc)
        return None


def run(ex_vin: bool = True, workers: int = 4) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panels = load_panel(ex_vin=ex_vin)
    log.info("Processing %d symbols with %d workers", len(panels), workers)

    all_trades: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_process_symbol, sym, df): sym for sym, df in panels.items()}
        for fut in as_completed(futs):
            result = fut.result()
            if result is not None:
                all_trades.append(result)

    if not all_trades:
        log.error("No trades generated — check panel path and universe.")
        return

    trades = pd.concat(all_trades, ignore_index=True)
    log.info("Total signal trades: %d (across %d symbols)", len(trades), trades["symbol"].nunique())

    # ── Cross-sectional score (P0 fix: computed AFTER concat, no time-series lookahead)
    # Each row has causal feature values pulled from bar t. Ranking cross-sectionally
    # across all A3 signal events gives a valid relative comparison.
    trades["score"] = accumulation_score_cross_sectional(trades)
    trades["score_q"] = pd.qcut(
        trades["score"].rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    # ── Save raw trades ───────────────────────────────────────────────────────
    trades.to_csv(OUT_DIR / "stage1_trades.csv", index=False)
    log.info("Saved stage1_trades.csv (%d rows)", len(trades))

    # ── Quintile summary at 63-bar horizon ────────────────────────────────────
    q_summary = quintile_summary(trades, quintile_col="score_q", horizon=63)
    q_summary.to_csv(OUT_DIR / "stage1_quintile_summary.csv", index=False)

    # ── Feature-return correlations ───────────────────────────────────────────
    sub63 = trades[trades["horizon"] == 63].copy()
    sub63["success"] = (sub63["net_return"] >= SUCCESS_TARGET).astype(int)

    corr_rows = []
    if not _SCIPY_OK:
        log.warning("scipy not installed — skipping Spearman/PB correlations")
    for feat in FEATURE_COLS:
        if feat not in sub63.columns:
            continue
        valid = sub63[[feat, "net_return", "success"]].dropna()
        if len(valid) < 30:
            continue
        if _SCIPY_OK:
            rho, p_rho = scipy_stats.spearmanr(valid[feat], valid["net_return"])
            pb, p_pb   = scipy_stats.pointbiserialr(valid["success"], valid[feat])
        else:
            rho = p_rho = pb = p_pb = float("nan")
        corr_rows.append({
            "feature":         feat,
            "spearman_rho":    round(rho, 4),
            "spearman_p":      round(p_rho, 4),
            "pb_corr_success": round(pb, 4),
            "pb_p":            round(p_pb, 4),
            "n":               len(valid),
        })

    corr_df = pd.DataFrame(corr_rows).sort_values("spearman_rho", ascending=False)
    corr_df.to_csv(OUT_DIR / "stage1_feature_correlations.csv", index=False)

    # ── Overall summary by horizon ────────────────────────────────────────────
    overall = trade_summary(trades)

    # ── Year breakdown at 63d ─────────────────────────────────────────────────
    year_rows = []
    for yr, g in sub63.groupby("year"):
        valid = g["net_return"].dropna()
        n = len(valid)
        if n < 5:
            continue
        year_rows.append({
            "year":        yr,
            "n_trades":    n,
            "win_rate":    round((valid >= SUCCESS_TARGET).mean(), 4),
            "avg_net_ret": round(valid.mean(), 4),
        })
    year_df = pd.DataFrame(year_rows)

    # ── Write markdown report ─────────────────────────────────────────────────
    _write_report(trades, q_summary, corr_df, overall, year_df, ex_vin)
    log.info("Stage 1 complete. Outputs in %s", OUT_DIR)


def _write_report(
    trades: pd.DataFrame,
    q_summary: pd.DataFrame,
    corr_df: pd.DataFrame,
    overall: pd.DataFrame,
    year_df: pd.DataFrame,
    ex_vin: bool,
) -> None:
    sub63 = trades[trades["horizon"] == 63]
    n_total = len(sub63["net_return"].dropna())
    baseline_wr = (sub63["net_return"] >= SUCCESS_TARGET).mean()
    baseline_avg = sub63["net_return"].mean()

    q5 = q_summary[q_summary["score_q"] == 5]
    q1 = q_summary[q_summary["score_q"] == 1]
    q5_wr  = q5["win_rate"].values[0]  if len(q5) else float("nan")
    q1_wr  = q1["win_rate"].values[0]  if len(q1) else float("nan")
    q5_avg = q5["avg_net_ret"].values[0] if len(q5) else float("nan")
    q5_n   = q5["n_trades"].values[0]   if len(q5) else 0

    universe = "ex-VIN" if ex_vin else "full"
    lines = [
        "# Stage 1 — Feature Predictive Value",
        "",
        f"**Universe:** {universe} | **Run date:** {pd.Timestamp.now().date()}",
        "",
        "## Objective",
        "Test whether accumulation/tightness features have predictive value over A3",
        "cloud signals. Primary horizon: 63 bars (~quarter). Success = net_return ≥ +15%.",
        "",
        "## Overall baseline (all A3 signals, 63-bar horizon)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| N trades | {n_total} |",
        f"| Win rate (≥+15%) | {baseline_wr:.1%} |",
        f"| Avg net return | {baseline_avg:.2%} |",
        "",
        "## Quintile breakdown (score_q=5 = highest accumulation evidence)",
        "",
        q_summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"**Q5 vs baseline win rate:** {q5_wr:.1%} vs {baseline_wr:.1%} "
        f"(delta = {q5_wr - baseline_wr:+.1%}, n={q5_n})",
        f"**Q5 avg net return:** {q5_avg:.2%}",
        f"**Q1 win rate:** {q1_wr:.1%}",
        "",
        "## Feature-return correlations (Spearman ρ, 63-bar horizon)",
        "",
        corr_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Overall horizon summary",
        "",
        overall.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## By-year breakdown (63-bar horizon)",
        "",
        year_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- {n_total} A3 cloud signals analysed across {trades['symbol'].nunique()} symbols",
        f"- Q5 win rate = {q5_wr:.1%} vs baseline {baseline_wr:.1%}",
        "",
        "**INTERPRETATION:**",
        "- If Q5 win rate > baseline by > 5 pp with n > 40 → features warrant Stage 2 ranking test.",
        "- If strongest Spearman |ρ| < 0.05 across all features → features have no predictive signal.",
        "- Year-by-year consistency required: a result only in one year is not actionable.",
        "",
        "## Next step",
        "If Q5 outperforms baseline by > 5 pp: proceed to Stage 2 (A3 candidate ranking).",
        "If not: revisit feature definitions before proceeding.",
    ]
    report_path = OUT_DIR / "stage1_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report written to %s", report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1: Feature predictive value")
    parser.add_argument("--ex-vin", action="store_true", default=True,
                        help="Exclude VIC, VHM, VRE (default: True)")
    parser.add_argument("--full-universe", action="store_true",
                        help="Include full universe (overrides --ex-vin)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    ex_vin = not args.full_universe
    run(ex_vin=ex_vin, workers=args.workers)


if __name__ == "__main__":
    main()
