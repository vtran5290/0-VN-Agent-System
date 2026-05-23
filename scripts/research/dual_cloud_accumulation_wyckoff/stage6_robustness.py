#!/usr/bin/env python3
"""Stage 6 — Robustness Checks

Tests whether accumulation feature improvements survive slicing by:
  - Year (2020–2026 individually)
  - VNINDEX regime (bull / sideways / bear)
  - Liquidity bucket (2B–5B, 5B–20B, 20B+)

Source of truth: stage1_trades.csv (Stage 1 output). Run Stage 1 first.

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage6_by_year.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage6_by_regime.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage6_by_liquidity.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage6_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage6_robustness.py
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
    OUT_DIR, SUCCESS_TARGET, SUCCESS_STOP, load_vnindex_regime,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

STAGE1_TRADES = OUT_DIR / "stage1_trades.csv"
HORIZON = 63

LIQ_BINS   = [0, 5e9, 20e9, np.inf]
LIQ_LABELS = ["2B–5B", "5B–20B", "20B+"]


def _win_rate_summary(g: pd.Series, label_col: str = "") -> dict:
    valid = g.dropna()
    if len(valid) == 0:
        return {}
    return {
        "n_trades":     len(valid),
        "win_rate":     round((valid >= SUCCESS_TARGET).mean(), 4),
        "loss_rate":    round((valid <= -SUCCESS_STOP).mean(), 4),
        "avg_net_ret":  round(valid.mean(), 4),
        "pct_positive": round((valid > 0).mean(), 4),
    }


def run(horizon: int = HORIZON) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not STAGE1_TRADES.exists():
        log.error(
            "stage1_trades.csv not found at %s. "
            "Run stage1_feature_value.py first.",
            STAGE1_TRADES,
        )
        return

    trades_all = pd.read_csv(STAGE1_TRADES, parse_dates=["signal_date"])
    sub = trades_all[trades_all["horizon"] == horizon].copy()

    if sub.empty:
        log.error("No rows at horizon=%d in stage1_trades.csv", horizon)
        return

    log.info("Stage 6 robustness: %d trades at %d-bar horizon", len(sub), horizon)

    # Assign score quintile if not already present
    if "score_q" not in sub.columns and "score" in sub.columns:
        sub["score_q"] = pd.qcut(
            sub["score"].rank(method="first"), 5, labels=False
        ).astype("Int64") + 1

    # ── Attach VNINDEX regime ─────────────────────────────────────────────────
    try:
        regime_map = load_vnindex_regime()
        # reindex+ffill handles date gaps between VNINDEX and equity panels
        sub["regime_bull"] = (
            regime_map.reindex(sub["signal_date"]).ffill().fillna(False).values
        )
        sub["regime_label"] = sub["regime_bull"].map({True: "bull", False: "bear_sideways"})
    except Exception as exc:
        log.warning("Could not load VNINDEX regime: %s — regime column skipped", exc)
        sub["regime_label"] = "unknown"

    # ── Liquidity bucket ──────────────────────────────────────────────────────
    if "adv50" in sub.columns:
        sub["liq_bucket"] = pd.cut(
            sub["adv50"], bins=LIQ_BINS, labels=LIQ_LABELS, right=False
        )
    else:
        sub["liq_bucket"] = "unknown"

    # ── By year ───────────────────────────────────────────────────────────────
    year_rows = []
    for yr, yg in sub.groupby("year"):
        all_wr = _win_rate_summary(yg["net_return"])
        if not all_wr:
            continue
        all_wr["year"] = yr
        all_wr["bucket"] = "all"
        year_rows.append(all_wr)

        if "score_q" in sub.columns:
            q5g = yg[yg["score_q"] == 5]
            q5_wr = _win_rate_summary(q5g["net_return"])
            if q5_wr:
                q5_wr["year"] = yr
                q5_wr["bucket"] = "Q5"
                year_rows.append(q5_wr)

    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(OUT_DIR / "stage6_by_year.csv", index=False)

    # ── By regime ─────────────────────────────────────────────────────────────
    regime_rows = []
    for rg, rg_g in sub.groupby("regime_label"):
        all_wr = _win_rate_summary(rg_g["net_return"])
        if not all_wr:
            continue
        all_wr["regime"] = rg
        all_wr["bucket"] = "all"
        regime_rows.append(all_wr)

        if "score_q" in sub.columns:
            q5g = rg_g[rg_g["score_q"] == 5]
            q5_wr = _win_rate_summary(q5g["net_return"])
            if q5_wr:
                q5_wr["regime"] = rg
                q5_wr["bucket"] = "Q5"
                regime_rows.append(q5_wr)

    regime_df = pd.DataFrame(regime_rows)
    regime_df.to_csv(OUT_DIR / "stage6_by_regime.csv", index=False)

    # ── By liquidity bucket ───────────────────────────────────────────────────
    liq_rows = []
    if "adv50" in sub.columns:
        for lb, lb_g in sub.groupby("liq_bucket", observed=True):
            all_wr = _win_rate_summary(lb_g["net_return"])
            if not all_wr:
                continue
            all_wr["liq_bucket"] = lb
            all_wr["bucket"] = "all"
            liq_rows.append(all_wr)

            if "score_q" in sub.columns:
                q5g = lb_g[lb_g["score_q"] == 5]
                q5_wr = _win_rate_summary(q5g["net_return"])
                if q5_wr:
                    q5_wr["liq_bucket"] = lb
                    q5_wr["bucket"] = "Q5"
                    liq_rows.append(q5_wr)

    liq_df = pd.DataFrame(liq_rows)
    liq_df.to_csv(OUT_DIR / "stage6_by_liquidity.csv", index=False)

    _write_report(sub, year_df, regime_df, liq_df, horizon)
    log.info("Stage 6 complete. Outputs in %s", OUT_DIR)


def _flag_consistency(year_df: pd.DataFrame) -> str:
    """Check if Q5 outperforms 'all' in most years."""
    if "bucket" not in year_df.columns or "win_rate" not in year_df.columns:
        return "Cannot assess — missing columns."
    wide = year_df.pivot_table(index="year", columns="bucket", values="win_rate")
    if "Q5" not in wide.columns or "all" not in wide.columns:
        return "Q5 or all bucket missing from year table."
    delta = wide["Q5"] - wide["all"]
    pos_years = (delta > 0.03).sum()
    neg_years = (delta < -0.03).sum()
    total = delta.notna().sum()
    return (
        f"Q5 outperformed 'all' by >3pp in {pos_years}/{total} years; "
        f"underperformed in {neg_years}/{total} years."
    )


def _write_report(sub, year_df, regime_df, liq_df, horizon: int = HORIZON):
    n_total = len(sub["net_return"].dropna())
    overall_wr = (sub["net_return"].dropna() >= SUCCESS_TARGET).mean()
    consistency = _flag_consistency(year_df)

    lines = [
        "# Stage 6 — Robustness Checks",
        "",
        f"**Run date:** {pd.Timestamp.now().date()}",
        f"**Source:** stage1_trades.csv | **Horizon:** {horizon} bars",
        "",
        "## Objective",
        "Verify that accumulation score improvements are not period-specific.",
        "Check by-year, by-regime, and by-liquidity-bucket consistency.",
        "",
        f"**Total trades:** {n_total} | **Overall baseline win_rate:** {overall_wr:.1%}",
        "",
        "## By year (all vs Q5)",
        "",
        year_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"**Year consistency:** {consistency}",
        "",
        "## By VNINDEX regime (bull vs bear/sideways)",
        "",
        regime_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## By liquidity bucket",
        "",
        liq_df.to_markdown(index=False, floatfmt=".4f") if not liq_df.empty else "(adv50 not in trades — skip)",
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- {n_total} trades analysed at {horizon}-bar horizon",
        f"- Overall win_rate = {overall_wr:.1%}",
        "",
        "**INTERPRETATION:**",
        "- Year consistency: if Q5 outperforms 'all' in < 50% of years → not robust.",
        "- Regime: features expected to help more in bull regime (cloud already bullish).",
        "  If features only work in bear/sideways regime → likely overfitting to reversal phase.",
        "- Liquidity: if Q5 only wins in illiquid bucket → execution at scale is impossible.",
        "",
        "## Decision framework",
        "| Condition | Action |",
        "|-----------|--------|",
        "| Q5 > baseline by > 5pp in ≥ 3 of 4 most recent years | Recommend Stage 2 overlay for A3 |",
        "| Liquidity: improvement holds in 5B+ bucket | Safe to use in liquid universe |",
        "| Regime: improvement holds in bull only | Only apply score in bull VNINDEX regime |",
        "| No consistent year/regime pattern | Do NOT promote — revisit features |",
        "",
        "## Next steps",
        "- If robust: document findings in a decision memo and propose A3 ranking overlay.",
        "- If not robust: report which feature subsets (if any) are consistent and narrow scope.",
    ]
    (OUT_DIR / "stage6_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=HORIZON,
                        help="Forward return horizon in bars (default 63)")
    args = parser.parse_args()
    run(horizon=args.horizon)


if __name__ == "__main__":
    main()
