#!/usr/bin/env python3
"""Stage 4 — S3 Shadow Quality Filter

S3 max60 contract (PAPER_TRADE_SHADOW only, no real capital):
- EMA21/55 cloud signal
- VNINDEX regime gate required
- max_hold = 60 bars
- TP1 = +18%; trail = 3.5× ATR14
- ADV50 ≥ 2B VND

Question: does filtering S3 signals by accumulation score improve quality?
Test "all S3 signals" vs "top-quintile S3 signals" under the max60 sim.

S3 max60 simulation: fixed 60-bar hold, no trail/TP modelling here (kept to
forward-return analysis to match Stage 1 methodology; production S3 logic
is handled separately in the paper ledger).

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage4_s3_trades.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage4_s3_summary.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage4_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage4_s3_quality.py
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
    OUT_DIR, SUCCESS_TARGET, SUCCESS_STOP, COST_BPS,
    forward_returns, load_panel, load_vnindex_regime, s3_signal,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

S3_MAX_HOLD     = 60        # S3 max hold bars (contract)
S3_TP1          = 0.18      # +18% take-profit
S3_TRAIL_MULT   = 3.5       # trail = 3.5× ATR14
COST_FRAC       = COST_BPS / 10_000.0


def _simulate_s3_trade(
    open_arr: np.ndarray,
    close_arr: np.ndarray,
    atr_arr: np.ndarray,
    entry_bar: int,
    n: int,
) -> dict:
    """
    Simulate a single S3 max60 trade with TP1 + ATR14 trail.
    Returns dict with exit_bar, exit_reason, net_return.
    """
    ep = open_arr[entry_bar]
    if ep <= 0:
        return {"net_return": np.nan, "exit_reason": "BAD_ENTRY", "hold_bars": 0}

    atr_entry = atr_arr[entry_bar]
    tp1_price = ep * (1.0 + S3_TP1)
    tp1_taken = False
    high_water = ep
    exit_bar = None
    exit_reason = "MAX_HOLD"

    for t in range(entry_bar, min(entry_bar + S3_MAX_HOLD, n)):
        c = close_arr[t]
        if c > high_water:
            high_water = c

        # Simplified TP1: full exit at +18% (contract is 50/50 split; this is a quality proxy)
        if not tp1_taken and c >= tp1_price:
            exit_bar = min(t + 1, n - 1)
            exit_reason = "TP1"
            break

        # ATR trail (from high water)
        if not np.isnan(atr_entry) and atr_entry > 0:
            trail_stop = high_water - S3_TRAIL_MULT * atr_entry
            if c < trail_stop:
                exit_bar = min(t + 1, n - 1)
                exit_reason = "TRAIL"
                break

    if exit_bar is None:
        exit_bar = min(entry_bar + S3_MAX_HOLD, n - 1)

    xp = open_arr[exit_bar]
    gr = xp / ep - 1.0 if ep > 0 else np.nan
    nr = gr - COST_FRAC if not np.isnan(gr) else np.nan

    return {
        "exit_bar":    exit_bar,
        "exit_reason": exit_reason,
        "hold_bars":   exit_bar - entry_bar,
        "gross_return":gr,
        "net_return":  nr,
    }


def _process_symbol(sym: str, df: pd.DataFrame, regime_map: pd.Series) -> pd.DataFrame | None:
    if len(df) < 150:
        return None
    try:
        df = compute_all_features(df)
        sig, _, _ = s3_signal(df, regime_map=regime_map)
        if sig.sum() == 0:
            return None

        from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import (
            adv_mask, MIN_HISTORY,
        )
        liq     = adv_mask(df)
        hist_ok = pd.Series(np.arange(len(df)), index=df.index) >= MIN_HISTORY
        valid   = sig & liq & hist_ok

        n = len(df)
        open_arr  = df["open"].values
        close_arr = df["close"].values
        atr_arr   = df["atr14"].values
        dates_arr = df["date"].values if "date" in df.columns else np.arange(n)

        # Causal feature snapshot at signal bars (score computed cross-sectionally in run())
        feat_cols_snap = ["pt_20", "atr_ratio", "vol_ratio", "vol_drying",
                          "bo_vol_exp", "bo_close_str"]
        feat_snap = {fc: df[fc].values for fc in feat_cols_snap if fc in df.columns}

        rows = []
        for bar in np.where(valid.values)[0]:
            entry_bar = bar + 1
            if entry_bar >= n:
                continue

            result = _simulate_s3_trade(open_arr, close_arr, atr_arr, entry_bar, n)
            result["symbol"]      = sym
            result["signal_bar"]  = bar
            result["signal_date"] = dates_arr[bar]
            result["entry_bar"]   = entry_bar
            result["entry_price"] = open_arr[entry_bar]
            result["year"]        = pd.to_datetime(dates_arr[bar]).year
            for fc, arr in feat_snap.items():
                result[fc] = arr[bar]

            rows.append(result)

        return pd.DataFrame(rows) if rows else None
    except Exception as exc:
        log.warning("%s failed: %s", sym, exc)
        return None


def run(ex_vin: bool = True, workers: int = 4) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panels = load_panel(ex_vin=ex_vin)

    log.info("Loading VNINDEX regime for S3 gate")
    regime_map = load_vnindex_regime()

    all_trades: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(_process_symbol, sym, df, regime_map): sym
            for sym, df in panels.items()
        }
        for fut in as_completed(futs):
            r = fut.result()
            if r is not None:
                all_trades.append(r)

    if not all_trades:
        log.error("No S3 trades generated.")
        return

    trades = pd.concat(all_trades, ignore_index=True)
    log.info("S3 trades: %d across %d symbols", len(trades), trades["symbol"].nunique())

    # Tradable as-of-date score: each date scored against prior dates only (date-group stable)
    trades["score"]             = tradable_asof_score(trades)
    trades["score_warmup_flag"] = tradable_asof_warmup_mask(trades)
    trades["score_q"] = pd.qcut(
        trades["score"].rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    trades.to_csv(OUT_DIR / "stage4_s3_trades.csv", index=False)

    # ── Summary by bucket ─────────────────────────────────────────────────────
    summary_rows = []
    for bucket_label, mask in [
        ("all_s3",       trades["score_q"].notna()),
        ("top_q45",      trades["score_q"] >= 4),
        ("top_q5_only",  trades["score_q"] == 5),
    ]:
        g = trades[mask]["net_return"].dropna()
        if len(g) == 0:
            continue
        exits = trades[mask]["exit_reason"].value_counts(normalize=True)
        summary_rows.append({
            "bucket":       bucket_label,
            "n_trades":     len(g),
            "win_rate":     round((g >= SUCCESS_TARGET).mean(), 4),
            "loss_rate":    round((g <= -SUCCESS_STOP).mean(), 4),
            "avg_net_ret":  round(g.mean(), 4),
            "med_net_ret":  round(g.median(), 4),
            "tp1_rate":     round(exits.get("TP1", 0.0), 4),
            "trail_rate":   round(exits.get("TRAIL", 0.0), 4),
            "maxhold_rate": round(exits.get("MAX_HOLD", 0.0), 4),
        })

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT_DIR / "stage4_s3_summary.csv", index=False)

    # ── Year breakdown ─────────────────────────────────────────────────────────
    year_rows = []
    for yr, yg in trades.groupby("year"):
        for bucket, mask in [("all", yg["score_q"].notna()), ("topq", yg["score_q"] >= 4)]:
            g = yg[mask]["net_return"].dropna()
            if len(g) < 5:
                continue
            year_rows.append({
                "year":     yr,
                "bucket":   bucket,
                "n_trades": len(g),
                "win_rate": round((g >= SUCCESS_TARGET).mean(), 4),
                "avg_ret":  round(g.mean(), 4),
            })
    year_df = pd.DataFrame(year_rows)

    _write_report(trades, summary, year_df, ex_vin)
    log.info("Stage 4 complete.")


def _write_report(trades, summary, year_df, ex_vin):
    universe = "ex-VIN" if ex_vin else "full"
    all_row = summary[summary["bucket"] == "all_s3"]
    top_row = summary[summary["bucket"] == "top_q45"]
    all_wr  = all_row["win_rate"].values[0]  if len(all_row) else float("nan")
    top_wr  = top_row["win_rate"].values[0]  if len(top_row) else float("nan")

    lines = [
        "# Stage 4 — S3 Shadow Quality Filter",
        "",
        f"**Universe:** {universe} | **Run date:** {pd.Timestamp.now().date()}",
        "",
        "## Objective",
        "Test whether filtering S3 max60 signals by accumulation score improves quality.",
        "S3 is PAPER_TRADE_SHADOW only — no real capital, no DNSE orders.",
        "",
        "## S3 max60 simulation parameters",
        f"- TP1 = +{S3_TP1:.0%} (simplified: full exit at TP1; contract is 50/50 split — quality proxy only)",
        f"- Trail = {S3_TRAIL_MULT}× ATR14 from high-water",
        f"- Max hold = {S3_MAX_HOLD} bars",
        "- VNINDEX regime gate applied",
        "- ADV50 ≥ 2B VND (corrected formula)",
        "",
        "## Bucket comparison",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        f"**Delta top_q45 vs all_s3:** {top_wr - all_wr:+.1%}",
        "",
        "## By-year breakdown",
        "",
        year_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- All S3 signals: win_rate={all_wr:.1%}, n={len(trades)}",
        f"- Top Q4/Q5: win_rate={top_wr:.1%}",
        "",
        "**INTERPRETATION:**",
        "- If top_q45 win_rate > all_s3 by > 5 pp and n > 30: score adds value to S3 filtering.",
        "- Check TP1 rate: higher TP1 rate in top_q45 confirms breakout quality.",
        "- Year consistency required before drawing conclusions.",
        "",
        "**Constraints reminder:**",
        "- S3 is PAPER_SHADOW only. Do NOT promote S3 to production based on these results.",
        "- Do NOT use S3 to gate A3.",
        "",
        "## Next step",
        "Proceed to Stage 5 (Wyckoff tag marginal value).",
    ]
    (OUT_DIR / "stage4_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ex-vin", action="store_true", default=True)
    parser.add_argument("--full-universe", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(ex_vin=not args.full_universe, workers=args.workers)


if __name__ == "__main__":
    main()
