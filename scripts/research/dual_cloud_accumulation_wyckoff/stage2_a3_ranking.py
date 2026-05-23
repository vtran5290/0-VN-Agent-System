#!/usr/bin/env python3
"""Stage 2 — A3 Candidate Ranking Overlay

On days when multiple A3 cloud signals fire simultaneously, does ranking
candidates by accumulation score (taking only the top N) improve outcomes
vs taking all signals?

Simulation: each calendar day, collect all A3 signals. For each day:
  - Baseline bucket: all signals that day
  - Top-N bucket: top 3 signals by score that day
  - Top-quintile bucket: only Q4/Q5 signals

Compare 63-bar win rates across the three buckets.

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage2_ranked_trades.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage2_ranking_summary.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage2_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage2_a3_ranking.py
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

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.features import (
    tradable_asof_score, tradable_asof_warmup_mask, compute_all_features,
)
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, HORIZONS, SUCCESS_TARGET, SUCCESS_STOP,
    a3_signal, forward_returns, load_panel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

TOP_N = 3   # keep top N signals per day in the filtered bucket


def _process_symbol(sym: str, df: pd.DataFrame) -> pd.DataFrame | None:
    if len(df) < 150:
        return None
    try:
        df = compute_all_features(df)
        sig, _, _ = a3_signal(df)
        if sig.sum() == 0:
            return None

        trades = forward_returns(df, sig, horizons=HORIZONS)
        if trades.empty:
            return None

        trades["symbol"] = sym
        trades["year"]   = pd.to_datetime(trades["signal_date"]).dt.year
        return trades
    except Exception as exc:
        log.warning("%s failed: %s", sym, exc)
        return None


def run(ex_vin: bool = True, workers: int = 4) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panels = load_panel(ex_vin=ex_vin)

    all_trades: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_process_symbol, sym, df): sym for sym, df in panels.items()}
        for fut in as_completed(futs):
            r = fut.result()
            if r is not None:
                all_trades.append(r)

    if not all_trades:
        log.error("No trades — check panel.")
        return

    trades = pd.concat(all_trades, ignore_index=True)
    log.info("Total trades: %d across %d symbols", len(trades), trades["symbol"].nunique())

    # Tradable as-of-date score: each date scored against prior dates only (date-group stable)
    trades["score"]             = tradable_asof_score(trades)
    trades["score_warmup_flag"] = tradable_asof_warmup_mask(trades)
    trades.to_csv(OUT_DIR / "stage2_ranked_trades.csv", index=False)

    # ── Assign ranking buckets at 63d horizon ─────────────────────────────────
    sub63 = trades[trades["horizon"] == 63].copy()

    # Global score quintile across all trades at this horizon
    sub63["score_q"] = pd.qcut(
        sub63["score"].rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    # Per-date rank within each signal date (uses cross-sectional score → correct)
    sub63["date_rank"] = sub63.groupby("signal_date")["score"].rank(
        ascending=False, method="first"
    ).astype(int)

    sub63["bucket_all"]    = True
    sub63["bucket_top3"]   = sub63["date_rank"] <= TOP_N
    sub63["bucket_topq"]   = sub63["score_q"] >= 4   # Q4 + Q5

    summary_rows = []
    for bucket_label, col in [
        ("all_signals",     "bucket_all"),
        (f"top_{TOP_N}_by_score", "bucket_top3"),
        ("top_quintile_q4q5", "bucket_topq"),
    ]:
        g = sub63[sub63[col]]["net_return"].dropna()
        if len(g) == 0:
            continue
        summary_rows.append({
            "bucket":      bucket_label,
            "n_trades":    len(g),
            "win_rate":    round((g >= SUCCESS_TARGET).mean(), 4),
            "loss_rate":   round((g <= -SUCCESS_STOP).mean(), 4),
            "avg_net_ret": round(g.mean(), 4),
            "med_net_ret": round(g.median(), 4),
            "pct_positive":round((g > 0).mean(), 4),
        })

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT_DIR / "stage2_ranking_summary.csv", index=False)

    # ── Year × bucket ─────────────────────────────────────────────────────────
    year_rows = []
    for yr, yg in sub63.groupby("year"):
        for bucket_label, col in [
            ("all",    "bucket_all"),
            ("top3",   "bucket_top3"),
            ("topq",   "bucket_topq"),
        ]:
            g = yg[yg[col]]["net_return"].dropna()
            if len(g) == 0:
                continue
            year_rows.append({
                "year":      yr,
                "bucket":    bucket_label,
                "n_trades":  len(g),
                "win_rate":  round((g >= SUCCESS_TARGET).mean(), 4),
                "avg_ret":   round(g.mean(), 4),
            })
    year_df = pd.DataFrame(year_rows)

    _write_report(summary, year_df, sub63, ex_vin)
    log.info("Stage 2 complete.")


def _write_report(summary, year_df, sub63, ex_vin):
    universe = "ex-VIN" if ex_vin else "full"
    all_wr   = summary[summary["bucket"] == "all_signals"]["win_rate"].values
    top3_wr  = summary[summary["bucket"] == f"top_{TOP_N}_by_score"]["win_rate"].values
    topq_wr  = summary[summary["bucket"] == "top_quintile_q4q5"]["win_rate"].values

    all_wr   = all_wr[0]   if len(all_wr)  else float("nan")
    top3_wr  = top3_wr[0]  if len(top3_wr) else float("nan")
    topq_wr  = topq_wr[0]  if len(topq_wr) else float("nan")

    lines = [
        "# Stage 2 — A3 Candidate Ranking Overlay",
        "",
        f"**Universe:** {universe} | **Run date:** {pd.Timestamp.now().date()}",
        "",
        "## Objective",
        "Test whether ranking A3 candidates by accumulation score improves outcomes.",
        f"Top-{TOP_N}-per-day bucket vs all-signal baseline. Primary horizon: 63 bars.",
        "",
        "## Bucket comparison (63-bar horizon)",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"**Delta top3 vs all:** {top3_wr - all_wr:+.1%}",
        f"**Delta topQ vs all:** {topq_wr - all_wr:+.1%}",
        "",
        "## By-year breakdown",
        "",
        year_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- All signals: win_rate={all_wr:.1%}",
        f"- Top-{TOP_N} by score: win_rate={top3_wr:.1%}",
        f"- Top quintile (Q4/Q5): win_rate={topq_wr:.1%}",
        "",
        "**INTERPRETATION:**",
        f"- Ranking adds value if top3 win_rate > all by > 5 pp with n > 40.",
        f"- If delta < 3 pp: score is not selective enough for ranking use.",
        "- Year consistency required: check year_df above.",
        "",
        "## Next step",
        "- If ranking adds value: proceed to Stage 3 (T2 timing).",
        "- If not: revisit score weights in features.py.",
    ]
    (OUT_DIR / "stage2_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ex-vin", action="store_true", default=True)
    parser.add_argument("--full-universe", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(ex_vin=not args.full_universe, workers=args.workers)


if __name__ == "__main__":
    main()
