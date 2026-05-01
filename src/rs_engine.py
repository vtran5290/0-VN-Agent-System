from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .config import RSEngineConfig
from .data_loader import CLOSE_COL, DATE_COL, VALUE_COL, LoadedUniverse
from .filters import add_trend_flags, apply_universe_filters
from .indicators import add_52w_stats, add_liquidity_stats, add_moving_averages


logger = logging.getLogger(__name__)


SCORING_WEIGHTS = {
    "tactical_vn": {
        21: 0.35,
        63: 0.35,
        126: 0.20,
        189: 0.10,
    },
    "position_vn": {
        63: 0.40,
        126: 0.25,
        189: 0.20,
        252: 0.15,
    },
}


def compute_rs_line(stock: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    """
    Align stock with benchmark on dates and compute RS line (stock / benchmark).
    """
    s = stock[[DATE_COL, CLOSE_COL]].rename(columns={CLOSE_COL: "stock_close"})
    b = benchmark[[DATE_COL, CLOSE_COL]].rename(columns={CLOSE_COL: "benchmark_close"})

    merged = pd.merge(s, b, on=DATE_COL, how="inner")
    if merged.empty:
        raise ValueError("No overlapping dates between stock and benchmark.")

    merged["rs_line"] = merged["stock_close"] / merged["benchmark_close"]
    return merged


def compute_rs_score(
    rs_line: pd.Series,
    scoring_mode: str,
) -> pd.Series:
    """
    Compute weighted RS score from RS line based on configured mode.

    RS ROC is computed on rs_line, not on raw price.
    """
    if scoring_mode not in SCORING_WEIGHTS:
        raise ValueError(f"Unsupported scoring_mode: {scoring_mode}")

    weights = SCORING_WEIGHTS[scoring_mode]
    rs_score = pd.Series(0.0, index=rs_line.index, dtype=float)

    for period, weight in weights.items():
        roc = (rs_line / rs_line.shift(period) - 1.0) * 100.0
        rs_score = rs_score + weight * roc

    return rs_score


@dataclass
class RSEngineResult:
    """Container for full RS computation outputs."""

    full_timeseries: pd.DataFrame
    latest_snapshot: pd.DataFrame
    summary: Dict[str, int]


def run_rs_engine(
    universe: LoadedUniverse,
    cfg: RSEngineConfig,
) -> RSEngineResult:
    """
    Run RS computation for entire universe and return long panel + latest snapshot.
    """
    benchmark = universe.benchmark
    stock_dfs = universe.stocks

    timeseries_list: List[pd.DataFrame] = []
    skipped_tickers: List[str] = []

    for ticker, df in stock_dfs.items():
        try:
            # Align with benchmark and compute rs_line
            aligned = compute_rs_line(df, benchmark)

            # Bring over original OHLCV/value for aligned dates
            aligned = aligned.merge(
                df[
                    [
                        DATE_COL,
                        CLOSE_COL,
                        VALUE_COL,
                        "volume",
                    ]
                ],
                on=DATE_COL,
                how="left",
            )

            # Indicators
            aligned = add_moving_averages(aligned)
            aligned = add_52w_stats(aligned)
            aligned = add_liquidity_stats(aligned)

            # RS score
            aligned["rs_score"] = compute_rs_score(
                aligned["rs_line"], scoring_mode=cfg.scoring_mode
            )

            # RS leadership flags (time-series)
            aligned["rs_new_high_252"] = aligned["rs_line"] >= aligned["rs_line"].rolling(
                window=252, min_periods=126
            ).max()

            # Universe filters / trend flags
            aligned = apply_universe_filters(aligned, cfg, ticker)
            aligned = add_trend_flags(aligned, cfg)

            aligned["ticker"] = ticker

            timeseries_list.append(aligned)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping ticker %s due to error: %s", ticker, exc)
            skipped_tickers.append(ticker)

    if not timeseries_list:
        raise RuntimeError("No tickers successfully processed.")

    full_ts = pd.concat(timeseries_list, ignore_index=True)

    # Cross-sectional RS percentile rank by date
    full_ts["rs_percentile"] = (
        full_ts.groupby(DATE_COL)["rs_score"]
        .rank(pct=True, method="average")
        .mul(100.0)
    )

    # RS top-decile flag
    full_ts["rs_top_decile"] = full_ts["rs_percentile"] >= 90.0

    # Leader flag on each row
    full_ts["leader_flag"] = (
        full_ts["quality_universe_pass"]
        & full_ts["trend_template"]
        & full_ts["rs_top_decile"]
    )

    # Latest snapshot per ticker (last available date)
    full_ts = full_ts.sort_values([DATE_COL, "ticker"])
    latest_idx = full_ts.groupby("ticker")[DATE_COL].idxmax()
    latest_snapshot = full_ts.loc[latest_idx].copy()

    # Summary statistics
    summary = {
        "total_files_found": len(stock_dfs),
        "successfully_processed": len(timeseries_list),
        "skipped": len(skipped_tickers) + len(universe.broken_files),
        "liquidity_pass_count": int(latest_snapshot["liquidity_pass"].sum()),
        "trend_template_count": int(latest_snapshot["trend_template"].sum()),
        "top_decile_count": int((latest_snapshot["rs_percentile"] >= 90.0).sum()),
    }

    logger.info("RS engine summary: %s", summary)

    return RSEngineResult(
        full_timeseries=full_ts,
        latest_snapshot=latest_snapshot,
        summary=summary,
    )

