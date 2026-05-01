from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import RSEngineConfig


logger = logging.getLogger(__name__)


def _ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def export_outputs(
    full_ts: pd.DataFrame,
    latest: pd.DataFrame,
    cfg: RSEngineConfig,
) -> None:
    """
    Export required CSV/Parquet outputs.
    """
    _ensure_output_dir(cfg.output_dir)

    # 1. rs_full_latest.csv
    full_latest_cols = [
        "ticker",
        "date",
        "close",
        "volume",
        "value",
        "avg_value_20",
        "avg_value_50",
        "median_value_20",
        "rs_line",
        "rs_score",
        "rs_percentile",
        "above_sma50",
        "above_sma150",
        "above_sma200",
        "sma50_gt_sma150",
        "sma150_gt_sma200",
        "sma200_rising_20d",
        "near_52w_high",
        "off_52w_low",
        "trend_template",
        "liquidity_pass",
        "price_pass",
        "history_pass",
        "quality_universe_pass",
        "rs_new_high_252",
        "rs_top_decile",
        "leader_flag",
    ]

    rs_full_latest_path = cfg.output_dir / "rs_full_latest.csv"
    latest[full_latest_cols].sort_values(
        ["rs_percentile", "rs_score", "ticker"], ascending=[False, False, True]
    ).to_csv(rs_full_latest_path, index=False)

    # 2. rs_leaders_latest.csv (universe-pass & rs_percentile >= 80)
    leaders = latest[
        (latest["quality_universe_pass"]) & (latest["rs_percentile"] >= 80.0)
    ].copy()

    rs_leaders_latest_path = cfg.output_dir / "rs_leaders_latest.csv"
    leaders.sort_values(
        ["rs_percentile", "rs_score", "ticker"], ascending=[False, False, True]
    ).to_csv(rs_leaders_latest_path, index=False)

    # 3. rs_top_decile_trend_template.csv
    top_decile_tt = latest[
        (latest["quality_universe_pass"])
        & (latest["trend_template"])
        & (latest["rs_percentile"] >= 90.0)
    ].copy()

    rs_top_decile_tt_path = cfg.output_dir / "rs_top_decile_trend_template.csv"
    top_decile_tt.sort_values(
        ["rs_percentile", "rs_score", "ticker"], ascending=[False, False, True]
    ).to_csv(rs_top_decile_tt_path, index=False)

    # 4. rs_timeseries.parquet (preferred) or CSV fallback
    ts_cols = [
        "date",
        "ticker",
        "close",
        "value",
        "rs_line",
        "rs_score",
        "rs_percentile",
    ]
    ts = full_ts[ts_cols].copy().sort_values(["date", "ticker"])

    ts_parquet_path = cfg.output_dir / "rs_timeseries.parquet"
    ts_csv_fallback_path = cfg.output_dir / "rs_timeseries.csv"

    try:
        ts.to_parquet(ts_parquet_path, index=False)
        logger.info("Wrote time-series Parquet to %s", ts_parquet_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to write Parquet (%s). Falling back to CSV: %s", exc, ts_csv_fallback_path
        )
        ts.to_csv(ts_csv_fallback_path, index=False)

