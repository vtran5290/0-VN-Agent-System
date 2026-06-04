#!/usr/bin/env python
"""
VN IBD-Style RS Rating Research Pipeline — 2026
================================================
RESEARCH ONLY. No production changes. No final_action changes. No OMS.

Tests 12 RS Rating variants (families A/B/C/D) as context overlays on
top of the A3 EMA Cloud entry signals, across IS/OOS time splits.

Outputs → data/research/rs_rating/
  rs_rating_daily.parquet              daily RS ratings (1-99) all variants
  overlay_backtest.csv                 entry-filter backtest (variant × threshold × split)
  variant_summary.csv                  IS/OOS classification per variant
  RS_RATING_RESEARCH_DECISION_MEMO.md  decision memo
"""
from __future__ import annotations

import datetime
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(REPO))

from src.market.rs_rating.compute import (
    compute_rs_ratings,
    load_panel_and_vni,
    load_universe,
    VARIANT_DEFS,
)

OUT_DIR = REPO / "data" / "research" / "rs_rating"

# Time splits for IS / OOS evaluation
SPLITS: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {
    "IS_2012_2016":   (pd.Timestamp("2012-01-01"), pd.Timestamp("2016-12-31")),
    "OOS1_2017_2020": (pd.Timestamp("2017-01-01"), pd.Timestamp("2020-12-31")),
    "OOS2_2021_2023": (pd.Timestamp("2021-01-01"), pd.Timestamp("2023-12-31")),
    "OOS3_2024_now":  (pd.Timestamp("2024-01-01"), pd.Timestamp("2099-12-31")),
}

# RS rating thresholds to test as entry filters
THRESHOLDS = [40, 50, 60, 70, 80]

# Forward return horizons (trading days)
FWD_HORIZONS = [21, 63]


# ---------------------------------------------------------------------------
# Signal and return computation
# ---------------------------------------------------------------------------

def compute_a3_signals(close_px: pd.DataFrame) -> pd.DataFrame:
    """
    Simplified A3 cloud entry signal: close > EMA100 AND EMA20 > EMA100.
    new_entry = first bar entering cloud after being out.
    Returns boolean DataFrame (date × symbol).
    """
    ema20  = close_px.ewm(span=20,  adjust=False).mean()
    ema100 = close_px.ewm(span=100, adjust=False).mean()
    cloud_bull = (close_px > ema100) & (ema20 > ema100)
    prev_cloud = cloud_bull.shift(1).fillna(False)
    return (cloud_bull & ~prev_cloud).astype(bool)


def compute_forward_returns(close_px: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """21-day and 63-day forward returns (no lookahead — measured after signal date)."""
    return {h: close_px.shift(-h) / close_px - 1 for h in FWD_HORIZONS}


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def _assign_split(dates: pd.Series) -> pd.Series:
    result = pd.Series(None, index=dates.index, dtype=object)
    for name, (t0, t1) in SPLITS.items():
        result[(dates >= t0) & (dates <= t1)] = name
    return result


def run_overlay_backtest(
    signals: pd.DataFrame,
    fwd_rets: dict[int, pd.DataFrame],
    ratings_long: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each variant × threshold × split: compute entry-filter backtest stats.

    Parameters
    ----------
    signals      : bool (date × symbol) — True = A3 cloud new_entry signal
    fwd_rets     : {horizon: DataFrame (date × symbol)}
    ratings_long : [date, symbol, rs_A1, ..., rs_D3]

    Returns
    -------
    DataFrame: [variant, threshold, split, n_signals,
                mean_fwd21, win_rate21, mean_fwd63, win_rate63,
                vs_raw_mean_fwd21, vs_raw_mean_fwd63]
    """
    # --- build base: one row per (date, symbol) where signal=True ---
    sig_long = (
        signals.stack()
        .rename("signal")
        .reset_index()
    )
    sig_long.columns = ["date", "symbol", "signal"]
    sig_long = sig_long[sig_long["signal"]].drop(columns="signal")

    # attach forward returns
    for h in FWD_HORIZONS:
        fr = fwd_rets[h].stack().rename(f"fwd{h}").reset_index()
        fr.columns = ["date", "symbol", f"fwd{h}"]
        sig_long = sig_long.merge(fr, on=["date", "symbol"], how="left")

    # attach RS ratings (wide: one col per variant)
    sig_long = sig_long.merge(ratings_long, on=["date", "symbol"], how="left")

    # assign split
    sig_long["split"] = _assign_split(sig_long["date"])
    sig_long = sig_long.dropna(subset=["split"])

    variant_cols = [c for c in sig_long.columns if c.startswith("rs_")]
    results: list[dict] = []

    for varcol in variant_cols:
        var_name = varcol[3:]  # strip "rs_"

        for split_name in SPLITS:
            sub = sig_long[sig_long["split"] == split_name].dropna(
                subset=["fwd21", "fwd63"]
            )
            if len(sub) < 5:
                continue

            raw_m21 = sub["fwd21"].mean()
            raw_m63 = sub["fwd63"].mean()
            raw_w21 = (sub["fwd21"] > 0).mean()
            raw_w63 = (sub["fwd63"] > 0).mean()

            # threshold=0 = raw (no RS filter)
            results.append(dict(
                variant=var_name, threshold=0, split=split_name,
                n_signals=len(sub),
                mean_fwd21=round(raw_m21 * 100, 2),
                mean_fwd63=round(raw_m63 * 100, 2),
                win_rate21=round(raw_w21 * 100, 1),
                win_rate63=round(raw_w63 * 100, 1),
                vs_raw_mean_fwd21=0.0, vs_raw_mean_fwd63=0.0,
            ))

            for thr in THRESHOLDS:
                filt = sub[sub[varcol] >= thr]
                if len(filt) < 5:
                    continue
                m21 = filt["fwd21"].mean()
                m63 = filt["fwd63"].mean()
                results.append(dict(
                    variant=var_name, threshold=thr, split=split_name,
                    n_signals=len(filt),
                    mean_fwd21=round(m21 * 100, 2),
                    mean_fwd63=round(m63 * 100, 2),
                    win_rate21=round((filt["fwd21"] > 0).mean() * 100, 1),
                    win_rate63=round((filt["fwd63"] > 0).mean() * 100, 1),
                    vs_raw_mean_fwd21=round((m21 - raw_m21) * 100, 2),
                    vs_raw_mean_fwd63=round((m63 - raw_m63) * 100, 2),
                ))

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Variant summary + classification
# ---------------------------------------------------------------------------

def compute_variant_summary(backtest_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each variant: find best IS threshold → evaluate at that threshold in OOS splits.
    Classify each variant.

    Classification rules (applied to mean_fwd21 lift vs raw):
      CANDIDATE_FOR_OPERATOR_REVIEW : all 3 OOS splits show lift > +1 pp
      PAPER_SHADOW_ONLY             : >= 2 OOS splits show lift > +0.5 pp
      REVIEW_RANKING_ONLY           : >= 2 OOS splits show any positive lift
      WATCHLIST_ONLY                : >= 1 OOS split shows positive lift
      REJECT                        : no OOS split shows positive lift
    """
    oos_splits = [s for s in SPLITS if s != "IS_2012_2016"]
    rows: list[dict] = []

    for var in sorted(backtest_df["variant"].unique()):
        vdf = backtest_df[backtest_df["variant"] == var]
        is_df = vdf[vdf["split"] == "IS_2012_2016"]
        if is_df.empty:
            continue

        # Best threshold in IS by mean_fwd21 (threshold > 0 only)
        is_filt = is_df[is_df["threshold"] > 0]
        if is_filt.empty:
            continue
        best_thr = int(is_filt.sort_values("mean_fwd21", ascending=False).iloc[0]["threshold"])

        row: dict = {"variant": var, "best_is_threshold": best_thr}

        # Pull raw and filtered metrics for each split
        for split_name in SPLITS:
            raw_row = vdf[(vdf["split"] == split_name) & (vdf["threshold"] == 0)]
            filt_row = vdf[(vdf["split"] == split_name) & (vdf["threshold"] == best_thr)]
            if not raw_row.empty:
                d = raw_row.iloc[0]
                row[f"{split_name}_n_raw"] = int(d["n_signals"])
                row[f"{split_name}_mean_fwd21_raw"] = d["mean_fwd21"]
                row[f"{split_name}_win_rate21_raw"] = d["win_rate21"]
            if not filt_row.empty:
                d = filt_row.iloc[0]
                row[f"{split_name}_n_filt"] = int(d["n_signals"])
                row[f"{split_name}_mean_fwd21_filt"] = d["mean_fwd21"]
                row[f"{split_name}_win_rate21_filt"] = d["win_rate21"]
                row[f"{split_name}_vs_raw21"] = d["vs_raw_mean_fwd21"]

        # Classification
        oos_lifts = [row.get(f"{s}_vs_raw21") for s in oos_splits]
        oos_lifts = [x for x in oos_lifts if x is not None]

        if not oos_lifts:
            row["classification"] = "INSUFFICIENT_DATA"
        elif all(x > 1.0 for x in oos_lifts):
            row["classification"] = "CANDIDATE_FOR_OPERATOR_REVIEW"
        elif sum(x > 0.5 for x in oos_lifts) >= 2:
            row["classification"] = "PAPER_SHADOW_ONLY"
        elif sum(x > 0 for x in oos_lifts) >= 2:
            row["classification"] = "REVIEW_RANKING_ONLY"
        elif sum(x > 0 for x in oos_lifts) >= 1:
            row["classification"] = "WATCHLIST_ONLY"
        else:
            row["classification"] = "REJECT"

        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Decision memo
# ---------------------------------------------------------------------------

VARIANT_DESC = {
    "A1":  "IBD standard (40% 12m / 20% each 9/6/3m)",
    "A2":  "Equal weight 12/9/6/3m",
    "A3v": "Recent-heavy 12/9/6/3m (20/20/30/30%)",
    "B1":  "VN4M: 10% 6m / 40% 3m / 30% 2m / 20% 1m",
    "B2":  "Short-heavy: 20% 3m / 50% 2m / 30% 1m",
    "B3":  "Equal weight 6/3/2/1m",
    "C1":  "RS line 3m momentum",
    "C2":  "RS line 1m momentum",
    "C3":  "RS line acceleration (3m minus 6m RS momentum)",
    "D1":  "Sharpe proxy: 3m return / 3m volatility",
    "D2":  "Sortino proxy: 3m return / 3m downside vol",
    "D3":  "Calmar proxy: 3m return / 3m max drawdown",
}


def write_decision_memo(
    variant_summary: pd.DataFrame,
    run_date: str,
    out_dir: Path,
) -> None:
    classification_order = [
        "CANDIDATE_FOR_OPERATOR_REVIEW",
        "PAPER_SHADOW_ONLY",
        "REVIEW_RANKING_ONLY",
        "WATCHLIST_ONLY",
        "REJECT",
        "INSUFFICIENT_DATA",
    ]

    def _cls_block(cls: str) -> list[str]:
        sub = variant_summary[variant_summary["classification"] == cls]
        if sub.empty:
            return []
        lines = [f"### {cls} ({len(sub)} variant(s))"]
        lines.append(
            "| Variant | Best Thr | IS mean_fwd21 | OOS1 vs raw | OOS2 vs raw | OOS3 vs raw |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for _, r in sub.iterrows():
            is_m21 = r.get("IS_2012_2016_mean_fwd21_filt", "–")
            oos1   = r.get("OOS1_2017_2020_vs_raw21", "–")
            oos2   = r.get("OOS2_2021_2023_vs_raw21", "–")
            oos3   = r.get("OOS3_2024_now_vs_raw21", "–")
            lines.append(
                f"| {r['variant']} | {int(r['best_is_threshold'])} "
                f"| {is_m21} pp | {oos1} pp | {oos2} pp | {oos3} pp |"
            )
        return lines + [""]

    candidates = variant_summary[
        variant_summary["classification"] == "CANDIDATE_FOR_OPERATOR_REVIEW"
    ]
    paper_only = variant_summary[
        variant_summary["classification"] == "PAPER_SHADOW_ONLY"
    ]

    if candidates.empty and paper_only.empty:
        decision = (
            "**REJECT / WATCHLIST ONLY — No production integration this sprint.**\n\n"
            "No variant showed consistent positive lift across all 3 OOS splits.\n"
            "RS Rating does not reliably improve A3 EMA Cloud entry quality at this time.\n\n"
            "Possible causes:\n"
            "- VN market structure and liquidity differ from US (IBD origin).\n"
            "- A3 EMA cloud already captures cross-sectional momentum implicitly.\n"
            "- 272-symbol universe too small for stable cross-sectional rank.\n"
            "- Mean-reversion dominates at VN short horizons, penalising high-RS entries.\n\n"
            "**Recommended next step for operator:** Re-run quarterly with updated data.\n"
            "Consider testing RS Rating as an exit-warning lens (low RS = earlier exit)\n"
            "rather than an entry filter."
        )
    else:
        best_vars = list(candidates["variant"]) + list(paper_only["variant"])
        decision = (
            f"**PAPER SHADOW — Candidate variants identified: {', '.join(best_vars)}.**\n\n"
            "At least one variant showed positive OOS lift in >= 2 of 3 OOS splits.\n"
            "Recommended: run paper shadow for 30 trading days before operator review.\n\n"
            "**Operator decision required** before any integration into daily scan.\n"
            "Do not add to final_action logic without explicit written approval."
        )

    lines = [
        "# RS Rating Research — Decision Memo",
        f"_Date: {run_date}_",
        "",
        "> **SAFETY:** This is a research context lens only. It does **not** set or override",
        "> `final_action`. No production changes. No OMS. No live trading.",
        "",
        "---",
        "",
        "## Research Question",
        "Does an IBD-style cross-sectional Relative Strength Rating (1–99) applied as an",
        "entry filter improve A3 EMA Cloud entry signals from 2012 to latest available data?",
        "",
        "## Data",
        "| Item | Value |",
        "| --- | --- |",
        f"| OHLCV panel | `ohlcv_panel_ext2012.parquet` (2012-{run_date[:4]}) |",
        "| Benchmark | `ta_vnindex.parquet` |",
        "| Universe | `universe_liquid_adv50_2b.txt` (272 symbols) |",
        "| EX_VIN (excluded from ranking) | VIC, VHM, VRE |",
        "| Min bars before ranking | 252 trading days |",
        "| A3 signal | close > EMA100 AND EMA20 > EMA100 (first bar entering cloud) |",
        "| Forward returns | 21-day and 63-day |",
        "",
        "## Variants Tested",
        "| Variant | Family | Description |",
        "| --- | --- | --- |",
    ]
    for v, desc in VARIANT_DESC.items():
        fam = VARIANT_DEFS[v][0]
        lines.append(f"| {v} | {fam} | {desc} |")

    lines += [
        "",
        "## Time Splits",
        "| Split | Period | Role |",
        "| --- | --- | --- |",
        "| IS_2012_2016 | 2012-01-01 – 2016-12-31 | In-sample (threshold selection) |",
        "| OOS1_2017_2020 | 2017-01-01 – 2020-12-31 | Out-of-sample 1 |",
        "| OOS2_2021_2023 | 2021-01-01 – 2023-12-31 | Out-of-sample 2 |",
        "| OOS3_2024_now | 2024-01-01 – latest | Out-of-sample 3 (most recent) |",
        "",
        "## Overlay Types Tested",
        "- **Display only** (threshold = 0): no filter, baseline comparison",
        "- **Entry filter** at RS ≥ 40 / 50 / 60 / 70 / 80: only take A3 signals where RS rating meets threshold",
        "",
        "## Overfitting Guards",
        "- Threshold selected on IS only; never on OOS data.",
        "- Classification requires positive lift in ALL 3 OOS splits for CANDIDATE status.",
        "- PAPER_SHADOW_ONLY requires positive lift in >= 2 of 3 OOS splits.",
        "- Universe is fixed (adv50_2b), not hand-optimised.",
        "",
        "## Results",
        "",
        "### Classification Summary",
        "| Variant | Family | Best IS Threshold | Classification |",
        "| --- | --- | --- | --- |",
    ]
    for _, r in variant_summary.sort_values(
        "classification",
        key=lambda s: s.map({c: i for i, c in enumerate(classification_order)}).fillna(99),
    ).iterrows():
        fam = VARIANT_DEFS.get(r["variant"], ("?",))[0]
        lines.append(
            f"| {r['variant']} | {fam} | {int(r['best_is_threshold'])} | {r['classification']} |"
        )

    lines += [""]
    for cls in classification_order:
        lines += _cls_block(cls)

    lines += [
        "## Decision",
        "",
        decision,
        "",
        "---",
        "",
        "## SSOT Confirmation",
        "- `final_action` is unchanged by this research.",
        "- RS Rating is a research/context lens only.",
        "- No OMS, DNSE, or live trading exposure.",
        "- Real capital: NO-GO.",
        "",
        "## Output Files",
        "| File | Contents |",
        "| --- | --- |",
        "| `rs_rating_daily.parquet` | Daily RS ratings (1–99) per symbol × 12 variants |",
        "| `overlay_backtest.csv` | Entry-filter backtest: variant × threshold × split |",
        "| `variant_summary.csv` | IS/OOS metrics + classification per variant |",
        "| `RS_RATING_RESEARCH_DECISION_MEMO.md` | This memo |",
    ]

    memo_path = out_dir / "RS_RATING_RESEARCH_DECISION_MEMO.md"
    memo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Decision memo: {memo_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_date = datetime.date.today().isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("VN IBD-Style RS Rating Research")
    print(f"Run date : {run_date}")
    print("RESEARCH ONLY - no production changes")
    print("=" * 60)
    print()

    # 1. Load data
    print("[1/6] Loading universe and OHLCV panel...")
    universe = load_universe()
    print(f"      Universe: {len(universe)} symbols")
    close_px, vni_close = load_panel_and_vni(universe)
    print(f"      Panel   : {close_px.shape} (dates x symbols)")
    print(f"      Dates   : {close_px.index[0].date()} to {close_px.index[-1].date()}")
    print()

    # 2. Compute RS ratings
    print("[2/6] Computing RS ratings (12 variants, cross-sectional 1-99)...")
    ratings_long = compute_rs_ratings(close_px, vni_close, universe)
    out_parquet = OUT_DIR / "rs_rating_daily.parquet"
    ratings_long.to_parquet(out_parquet, index=False)
    print(f"      Saved : {out_parquet.relative_to(REPO)}")
    print(f"      Rows  : {len(ratings_long):,}  Columns: {list(ratings_long.columns)}")
    print()

    # 3. A3 entry signals
    print("[3/6] Computing A3 cloud entry signals (EMA20 > EMA100, close > EMA100)...")
    signals = compute_a3_signals(close_px)
    n_signals = int(signals.sum().sum())
    print(f"      Total entry signals across all symbols/dates: {n_signals:,}")
    print()

    # 4. Forward returns
    print("[4/6] Computing 21-day and 63-day forward returns...")
    fwd_rets = compute_forward_returns(close_px)
    print()

    # 5. Backtest
    print("[5/6] Running overlay backtest (12 variants x 6 thresholds x 4 splits)...")
    backtest_df = run_overlay_backtest(signals, fwd_rets, ratings_long)
    backtest_path = OUT_DIR / "overlay_backtest.csv"
    backtest_df.to_csv(backtest_path, index=False)
    print(f"      Saved : {backtest_path.relative_to(REPO)}")
    print(f"      Rows  : {len(backtest_df):,}")
    print()

    # 6. Variant summary + decision memo
    print("[6/6] Classifying variants and writing decision memo...")
    variant_summary = compute_variant_summary(backtest_df)
    summary_path = OUT_DIR / "variant_summary.csv"
    variant_summary.to_csv(summary_path, index=False)
    print(f"      Saved : {summary_path.relative_to(REPO)}")
    print()

    # Print classification table
    print("  Variant  BestThr  Classification")
    print("  " + "-" * 50)
    cls_order = [
        "CANDIDATE_FOR_OPERATOR_REVIEW", "PAPER_SHADOW_ONLY",
        "REVIEW_RANKING_ONLY", "WATCHLIST_ONLY", "REJECT", "INSUFFICIENT_DATA",
    ]
    for _, r in variant_summary.sort_values(
        "classification",
        key=lambda s: s.map({c: i for i, c in enumerate(cls_order)}).fillna(99),
    ).iterrows():
        print(f"  {r['variant']:6s}   {int(r['best_is_threshold']):2d}     {r['classification']}")
    print()

    write_decision_memo(variant_summary, run_date, OUT_DIR)
    print()

    print("=" * 60)
    print("Research complete.")
    print(f"All outputs: {OUT_DIR.relative_to(REPO)}")
    print("RS Rating is context only - no production changes.")
    print("=" * 60)


if __name__ == "__main__":
    main()
