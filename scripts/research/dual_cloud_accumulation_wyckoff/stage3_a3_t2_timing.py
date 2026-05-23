#!/usr/bin/env python3
"""Stage 3 — A3 T2 Add-On Timing

A3 contract: T2 = 50% add-on ONLY on a ≥4% pullback within 30 bars of T1 entry.

Question: does the accumulation score at T1 entry predict whether a valid
T2 pullback (≥4% dip then recovery) will occur within 30 bars?

Simulation per A3 T1 entry:
  - T2_filled   = True if close drops ≥4% below T1 entry price within 30 bars
  - t2_fill_bar = first bar where T2 condition is met
  - t2_outcome  = net return from T2 fill bar to bar (fill_bar + 63), i.e. the
                  incremental outcome of taking T2

Compare:
  - T2 fill rate by score quintile (does high score → more frequent T2?)
  - T2 outcome (post-fill return) by score quintile
  - Whether T2 fill bars have higher tightness (confirming accumulation logic)

Outputs:
    outputs/research/dual_cloud_accumulation_wyckoff/stage3_t2_events.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage3_t2_summary.csv
    outputs/research/dual_cloud_accumulation_wyckoff/stage3_report.md

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/stage3_a3_t2_timing.py
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
    OUT_DIR, MIN_ADV_VND, MIN_HISTORY, COST_BPS, SUCCESS_TARGET,
    a3_signal, adv_mask, load_panel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

T2_PULLBACK_PCT   = 0.04    # ≥4% drawdown below T1 entry = T2 fill condition (A3 contract)
T2_WINDOW         = 30      # bars within which T2 must be filled
T2_FORWARD_BARS   = 63      # forward return horizon after T2 fill
COST_FRAC         = COST_BPS / 10_000.0


def _t2_events_for_symbol(sym: str, df: pd.DataFrame) -> pd.DataFrame | None:
    if len(df) < 150:
        return None
    try:
        df = compute_all_features(df)
        sig, _, _ = a3_signal(df)
        if sig.sum() == 0:
            return None

        # Do NOT compute score here — done cross-sectionally in run() after concat.
        # Store feature values at signal bars; score is added post-concat.
        liq = adv_mask(df)
        hist_ok = pd.Series(np.arange(len(df)), index=df.index) >= MIN_HISTORY
        valid = sig & liq & hist_ok

        n = len(df)
        close_arr = df["close"].values
        low_arr   = df["low"].values
        open_arr  = df["open"].values
        dates_arr = df["date"].values if "date" in df.columns else np.arange(n)
        year_arr  = pd.to_datetime(df["date"]).dt.year.values if "date" in df.columns else np.zeros(n)

        # Collect causal feature values at each signal bar for cross-sectional scoring
        feat_cols_snap = ["pt_20", "atr_ratio", "vol_ratio", "vol_drying",
                          "bo_vol_exp", "bo_close_str"]
        feat_snap = {fc: df[fc].values for fc in feat_cols_snap if fc in df.columns}

        rows = []
        for bar in np.where(valid.values)[0]:
            entry_bar = bar + 1
            if entry_bar >= n:
                continue
            ep = open_arr[entry_bar]
            if ep <= 0:
                continue

            t2_thresh = ep * (1.0 - T2_PULLBACK_PCT)

            t2_filled = False
            t2_fill_bar = None
            # Use low[] to detect T2 fill — intraday dip below threshold counts
            for t in range(entry_bar + 1, min(entry_bar + T2_WINDOW + 1, n)):
                if low_arr[t] <= t2_thresh:
                    t2_filled = True
                    t2_fill_bar = t
                    break

            # Forward return after T2 fill (if filled)
            t2_entry_price = np.nan
            t2_net_return  = np.nan
            if t2_filled and t2_fill_bar is not None:
                t2_entry_bar = t2_fill_bar + 1
                if t2_entry_bar < n:
                    t2_ep = open_arr[t2_entry_bar]
                    t2_entry_price = t2_ep  # set whenever T2 fills, even if return unavailable
                    t2_exit_bar = t2_entry_bar + T2_FORWARD_BARS
                    if t2_exit_bar < n:
                        t2_xp = open_arr[t2_exit_bar]
                        t2_net_return = (t2_xp / t2_ep - 1.0) - COST_FRAC

            # T1 forward return at same horizon for comparison
            t1_exit_bar = entry_bar + T2_FORWARD_BARS
            t1_net_ret = np.nan
            if t1_exit_bar < n:
                t1_xp = open_arr[t1_exit_bar]
                t1_net_ret = (t1_xp / ep - 1.0) - COST_FRAC

            row = {
                "symbol":          sym,
                "signal_bar":      bar,
                "signal_date":     dates_arr[bar],
                "entry_bar":       entry_bar,
                "entry_price":     ep,
                "t2_filled":       int(t2_filled),
                "t2_fill_bar":     t2_fill_bar,
                "t2_entry_price":  t2_entry_price,
                "t2_net_return":   t2_net_return,
                "t1_net_return":   t1_net_ret,
                "year":            year_arr[bar],
            }
            # Snapshot causal feature values at signal bar
            for fc, arr in feat_snap.items():
                row[fc] = arr[bar]
            rows.append(row)

        return pd.DataFrame(rows) if rows else None
    except Exception as exc:
        log.warning("%s failed: %s", sym, exc)
        return None


def run(ex_vin: bool = True, workers: int = 4) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panels = load_panel(ex_vin=ex_vin)

    all_events: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_t2_events_for_symbol, sym, df): sym for sym, df in panels.items()}
        for fut in as_completed(futs):
            r = fut.result()
            if r is not None:
                all_events.append(r)

    if not all_events:
        log.error("No T2 events.")
        return

    events = pd.concat(all_events, ignore_index=True)
    log.info("T2 events: %d entries across %d symbols", len(events), events["symbol"].nunique())

    # Tradable as-of-date score: each date scored against prior dates only (date-group stable)
    events["score"]             = tradable_asof_score(events)
    events["score_warmup_flag"] = tradable_asof_warmup_mask(events)
    events["score_q"] = pd.qcut(
        events["score"].rank(method="first"), 5, labels=False
    ).astype("Int64") + 1

    events.to_csv(OUT_DIR / "stage3_t2_events.csv", index=False)

    # ── Summary by score quintile ──────────────────────────────────────────────
    summary_rows = []
    for q, g in events.groupby("score_q"):
        filled = g[g["t2_filled"] == 1]
        t2_wr = (filled["t2_net_return"] >= SUCCESS_TARGET).mean() if len(filled) else np.nan
        summary_rows.append({
            "score_q":       q,
            "n_entries":     len(g),
            "t2_fill_rate":  round(g["t2_filled"].mean(), 4),
            "n_t2_filled":   len(filled),
            "t2_win_rate":   round(t2_wr, 4) if not np.isnan(t2_wr) else np.nan,
            "t2_avg_ret":    round(filled["t2_net_return"].mean(), 4) if len(filled) else np.nan,
            "t1_avg_ret":    round(g["t1_net_return"].mean(), 4),
        })

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT_DIR / "stage3_t2_summary.csv", index=False)

    # ── Year breakdown ─────────────────────────────────────────────────────────
    year_rows = []
    for yr, yg in events.groupby("year"):
        n = len(yg)
        if n < 5:
            continue
        year_rows.append({
            "year":          yr,
            "n_entries":     n,
            "t2_fill_rate":  round(yg["t2_filled"].mean(), 4),
            "t2_avg_ret":    round(yg[yg["t2_filled"] == 1]["t2_net_return"].mean(), 4)
                             if yg["t2_filled"].sum() > 0 else np.nan,
        })
    year_df = pd.DataFrame(year_rows)

    _write_report(events, summary, year_df, ex_vin)
    log.info("Stage 3 complete.")


def _write_report(events, summary, year_df, ex_vin):
    universe = "ex-VIN" if ex_vin else "full"
    overall_fill_rate = events["t2_filled"].mean()

    lines = [
        "# Stage 3 — A3 T2 Add-On Timing",
        "",
        f"**Universe:** {universe} | **Run date:** {pd.Timestamp.now().date()}",
        "",
        "## Objective",
        "Test whether accumulation score at T1 entry predicts T2 fill probability",
        "and T2 outcome. A3 T2 = 50% add-on on ≥4% pullback within 30 bars.",
        "",
        f"**Overall T2 fill rate:** {overall_fill_rate:.1%} across {len(events)} entries",
        "",
        "## T2 fill rate and outcome by score quintile",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## By-year breakdown",
        "",
        year_df.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## FACTS vs INTERPRETATION",
        "",
        "**FACTS:**",
        f"- Overall T2 fill rate = {overall_fill_rate:.1%}",
        f"- N entries = {len(events)} across {events['symbol'].nunique()} symbols",
        "",
        "**INTERPRETATION:**",
        "- If high-score (Q4/Q5) entries have meaningfully higher T2 fill rates AND",
        "  better post-fill returns → score helps identify better T2 setups.",
        "- If fill rate uniform across quintiles → score does not predict T2 timing.",
        "- T2 win_rate > T2 fill rate × all-signal wr → T2 is accretive for high scores.",
        "",
        "## Next step",
        "Proceed to Stage 4 (S3 shadow quality) regardless of Stage 3 outcome.",
    ]
    (OUT_DIR / "stage3_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ex-vin", action="store_true", default=True)
    parser.add_argument("--full-universe", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(ex_vin=not args.full_universe, workers=args.workers)


if __name__ == "__main__":
    main()
