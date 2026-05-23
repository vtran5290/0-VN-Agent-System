#!/usr/bin/env python3
"""Stage 5 — Wyckoff Tags Incremental Value

Question: after controlling for tightness features, do mechanical Wyckoff tags
(spring, SOS, LPS, UTAD, effort_vs_result) add marginal predictive value?

Method: compare three feature sets on A3 signals at 63-bar horizon:
  1. tightness_only   — pt_20, atr_ratio, vol_ratio, vol_drying
  2. tightness+bo     — tightness + breakout quality (bo_vol_exp, bo_close_str)
  3. tightness+bo+wyckoff — full set including tags

For each set, compute a quintile score and compare Q5 vs all-signal baseline.
Also: tag presence rates by return bucket (did spring/SOS occur more in winners?).

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage5_wyckoff_trades.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage5_tag_rates.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage5_feature_set_comparison.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage5_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage5_wyckoff_tags.py
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

from scripts.research.dual_cloud_accumulation_wyckoff.features import compute_all_features
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, HORIZONS, SUCCESS_TARGET, SUCCESS_STOP,
    a3_signal, forward_returns, load_panel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

WYCKOFF_TAGS = ["spring", "sos", "lps", "utad", "efvr"]

# Feature set definitions for incremental test
FEATURE_SETS = {
    "tightness_only": {
        "cols": ["pt_20", "atr_ratio", "vol_ratio", "vol_drying"],
        "dirs": [False, False, False, True],   # True = higher is better
    },
    "tightness_bo": {
        "cols": ["pt_20", "atr_ratio", "vol_ratio", "vol_drying", "bo_vol_exp", "bo_close_str"],
        "dirs": [False, False, False, True, True, True],
    },
    "tightness_bo_wyckoff": {
        "cols": ["pt_20", "atr_ratio", "vol_ratio", "vol_drying",
                 "bo_vol_exp", "bo_close_str", "spring", "sos", "lps"],
        "dirs": [False, False, False, True, True, True, True, True, True],
    },
}


def _score_from_set(df_sub: pd.DataFrame, cols: list[str], dirs: list[bool]) -> pd.Series:
    """Compute unweighted rank-sum score from specified columns."""
    ranks = []
    for col, ascending in zip(cols, dirs):
        if col not in df_sub.columns:
            continue
        r = df_sub[col].rank(pct=True, ascending=ascending, na_option="keep")
        ranks.append(r)
    if not ranks:
        return pd.Series(np.nan, index=df_sub.index)
    return pd.concat(ranks, axis=1).mean(axis=1)


def _process_symbol(sym: str, df: pd.DataFrame) -> pd.DataFrame | None:
    if len(df) < 150:
        return None
    try:
        df = compute_all_features(df)
        sig, _, _ = a3_signal(df)
        if sig.sum() == 0:
            return None

        trades = forward_returns(df, sig, horizons=[63])
        if trades.empty:
            return None

        trades["symbol"] = sym
        trades["year"]   = pd.to_datetime(trades["signal_date"]).dt.year

        # Attach feature values at signal bar
        sig_bars = trades["signal_bar"].values
        feat_cols = (
            ["pt_20", "atr_ratio", "vol_ratio", "vol_drying",
             "bo_vol_exp", "bo_close_str"]
            + WYCKOFF_TAGS
        )
        for fc in feat_cols:
            if fc in df.columns:
                trades[fc] = df[fc].iloc[sig_bars].values

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
        log.error("No trades.")
        return

    trades = pd.concat(all_trades, ignore_index=True)
    log.info("Trades: %d across %d symbols", len(trades), trades["symbol"].nunique())

    # ── Score each feature set and compute Q5 win rate ────────────────────────
    comparison_rows = []
    baseline_wr = (trades["net_return"].dropna() >= SUCCESS_TARGET).mean()
    baseline_n  = len(trades["net_return"].dropna())

    for set_name, cfg in FEATURE_SETS.items():
        trades[f"score_{set_name}"] = _score_from_set(trades, cfg["cols"], cfg["dirs"])
        q5_mask = trades[f"score_{set_name}"].rank(method="first") > (
            trades[f"score_{set_name}"].rank(method="first").max() * 0.8
        )
        q5_rets = trades[q5_mask]["net_return"].dropna()
        comparison_rows.append({
            "feature_set":    set_name,
            "n_all":          baseline_n,
            "n_q5":           len(q5_rets),
            "baseline_wr":    round(baseline_wr, 4),
            "q5_win_rate":    round((q5_rets >= SUCCESS_TARGET).mean(), 4) if len(q5_rets) else np.nan,
            "q5_avg_ret":     round(q5_rets.mean(), 4) if len(q5_rets) else np.nan,
            "delta_vs_baseline": round(
                (q5_rets >= SUCCESS_TARGET).mean() - baseline_wr, 4
            ) if len(q5_rets) else np.nan,
        })

    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(OUT_DIR / "stage5_feature_set_comparison.csv", index=False)

    # ── Tag presence rates by return bucket ───────────────────────────────────
    trades["return_bucket"] = pd.cut(
        trades["net_return"],
        bins=[-np.inf, -0.08, 0, 0.10, 0.18, np.inf],
        labels=["loss_gt8pct", "loss_0_8pct", "gain_0_10pct", "gain_10_18pct", "winner_gt18pct"],
    )

    tag_rows = []
    for tag in WYCKOFF_TAGS:
        if tag not in trades.columns:
            continue
        for bucket, g in trades.groupby("return_bucket", observed=True):
            tag_col = g[tag].dropna()
            if len(tag_col) == 0:
                continue
            tag_rows.append({
                "tag":          tag,
                "return_bucket":bucket,
                "n":            len(tag_col),
                "tag_rate":     round(tag_col.mean(), 4),
            })
    tag_df = pd.DataFrame(tag_rows)
    tag_df.to_csv(OUT_DIR / "stage5_tag_rates.csv", index=False)

    # Pivot for readability
    try:
        tag_pivot = tag_df.pivot(index="tag", columns="return_bucket", values="tag_rate")
    except Exception:
        tag_pivot = tag_df

    trades.to_csv(OUT_DIR / "stage5_wyckoff_trades.csv", index=False)
    _write_report(comparison_df, tag_df, tag_pivot, trades, ex_vin)
    log.info("Stage 5 complete.")


def _write_report(comparison_df, tag_df, tag_pivot, trades, ex_vin):
    universe = "ex-VIN" if ex_vin else "full"
    lines = [
        "# Stage 5 — Wyckoff Tags Incremental Value",
        "",
        f"**Universe:** {universe} | **Run date:** {pd.Timestamp.now().date()}",
        "",
        "## Objective",
        "Test whether mechanical Wyckoff tags add value beyond price/volume tightness.",
        "Three feature sets compared: tightness_only → tightness+breakout → +wyckoff.",
        "",
        "## Feature set comparison (Q5 = top 20% of signals by score, 63-bar horizon)",
        "",
        comparison_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Wyckoff tag presence by return bucket",
        "(Higher rate in winner bucket = tag is positively predictive)",
        "",
        tag_pivot.to_markdown(floatfmt=".3f") if hasattr(tag_pivot, "to_markdown") else str(tag_pivot),
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- N total trades: {len(trades)}",
        f"- Feature sets tested: {', '.join(FEATURE_SETS.keys())}",
        "",
        "**INTERPRETATION:**",
        "- Wyckoff adds value if tightness_bo_wyckoff Q5 win_rate > tightness_bo Q5 by > 3 pp.",
        "- Tag presence in winner_gt18pct bucket > loss_gt8pct bucket = directionally correct.",
        "- UTAD should appear more in loss buckets (it is a warning tag, not bullish).",
        "- efvr: low score (high vol / low net move) should appear more in loss buckets.",
        "",
        "## Next step",
        "Proceed to Stage 6 (robustness across years, regimes, sectors, liquidity).",
    ]
    (OUT_DIR / "stage5_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ex-vin", action="store_true", default=True)
    parser.add_argument("--full-universe", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(ex_vin=not args.full_universe, workers=args.workers)


if __name__ == "__main__":
    main()
