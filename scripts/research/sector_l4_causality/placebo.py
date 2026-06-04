"""
D03 — Placebo shuffle: shuffle symbols across L4 labels preserving sector-size distribution.
Measures whether real L4 result is above the 95th percentile of shuffled-label results.
Output: placebo_sector_shuffle_summary.csv
"""
from __future__ import annotations
import logging

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR, PLACEBO_ITERS_P0, VIN_GROUP_SYMBOLS, FORWARD_HORIZONS

log = logging.getLogger(__name__)


def _shuffle_sector_map(sector_map: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Shuffle symbols across L4 labels while preserving the count distribution per L4.
    """
    shuffled = sector_map.copy()
    symbols = shuffled["symbol"].values.copy()
    rng.shuffle(symbols)
    shuffled["sector_l4"] = shuffled["sector_l4"].values  # keep sizes
    shuffled["symbol"] = symbols
    return shuffled


def _compute_headline_metric(
    stock_events: pd.DataFrame,
    shuffled_map: pd.DataFrame,
    sector_panel_template: pd.DataFrame,
    panel: pd.DataFrame,
    threshold: float = 0.40,
    horizon: int = 60,
) -> float:
    """
    Quick headline metric for one iteration: delta hit_rate at horizon using equal-weight gate.
    Returns delta vs no-gate baseline. Uses pre-built sector panel with re-labeled symbols.
    """
    # Re-label stock events with shuffled sector assignments
    sym_sec = shuffled_map[["symbol", "sector_l4"]].drop_duplicates("symbol")
    ev = stock_events.merge(
        sym_sec.rename(columns={"sector_l4": "sector_l4_shuffle"}),
        on="symbol", how="left"
    )
    ev["sector_l4_shuffle"] = ev["sector_l4_shuffle"].fillna("Unknown")

    # Rebuild breadth from panel using shuffled map
    enriched_shuf = panel.merge(sym_sec, on="symbol", how="left")
    enriched_shuf["sector_l4"] = enriched_shuf["sector_l4"].fillna("Unknown")

    breadth_shuf = (
        enriched_shuf[enriched_shuf["sector_l4"] != "Unknown"]
        .groupby(["date", "sector_l4"])["cloud_bull_20_100"]
        .mean()
        .reset_index()
        .rename(columns={"cloud_bull_20_100": "shuf_breadth"})
    )

    ev = ev.merge(
        breadth_shuf.rename(columns={"sector_l4": "sector_l4_shuffle"}),
        on=["date", "sector_l4_shuffle"], how="left"
    )

    col = f"fwd_ret_{horizon}d"
    if col not in ev.columns:
        return np.nan

    base_hit = float((ev[col].dropna() > 0).mean()) if not ev[col].dropna().empty else np.nan
    gated = ev[ev["shuf_breadth"].fillna(0) >= threshold]
    gate_hit = float((gated[col].dropna() > 0).mean()) if not gated[col].dropna().empty else np.nan

    return gate_hit - base_hit if not np.isnan(gate_hit) and not np.isnan(base_hit) else np.nan


def run_placebo(
    stock_events: pd.DataFrame,
    sector_map: pd.DataFrame,
    panel: pd.DataFrame,
    real_delta_hit_rate_60d: float,
    n_iters: int = PLACEBO_ITERS_P0,
    threshold: float = 0.40,
) -> pd.DataFrame:
    """
    Run N placebo iterations. Report real result percentile vs placebo distribution.
    """
    rng = np.random.default_rng(42)
    shuf_deltas = []

    log.info("Running %d placebo iterations …", n_iters)
    for i in range(n_iters):
        if i % 50 == 0:
            log.info("  Placebo iter %d/%d", i, n_iters)
        shuf_map = _shuffle_sector_map(sector_map, rng)
        delta = _compute_headline_metric(
            stock_events, shuf_map, None, panel,
            threshold=threshold, horizon=60
        )
        shuf_deltas.append(delta)

    clean = [d for d in shuf_deltas if not np.isnan(d)]
    percentile = float(np.mean([d < real_delta_hit_rate_60d for d in clean]) * 100) if clean else np.nan
    passes_gate = percentile >= 95.0

    summary = pd.DataFrame({
        "metric":                   ["delta_hit_rate_60d"],
        "real_value":               [real_delta_hit_rate_60d],
        "placebo_mean":             [float(np.nanmean(shuf_deltas))],
        "placebo_p50":              [float(np.nanpercentile(clean, 50)) if clean else np.nan],
        "placebo_p95":              [float(np.nanpercentile(clean, 95)) if clean else np.nan],
        "placebo_p99":              [float(np.nanpercentile(clean, 99)) if clean else np.nan],
        "real_percentile":          [percentile],
        "passes_95th_gate":         [int(passes_gate)],
        "n_valid_iters":            [len(clean)],
        "n_total_iters":            [n_iters],
        "conclusion":               ["REAL_ABOVE_PLACEBO" if passes_gate else "PLACEBO_SIMILAR_TO_REAL"],
    })

    out_path = OUTPUT_DIR / "placebo_sector_shuffle_summary.csv"
    summary.to_csv(out_path, index=False)
    log.info("Placebo summary: real=%.4f, percentile=%.1f%% -> %s",
             real_delta_hit_rate_60d, percentile,
             "PASS" if passes_gate else "FAIL")
    return summary
