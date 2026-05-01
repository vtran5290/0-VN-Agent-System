from __future__ import annotations

import argparse
import logging
from typing import Optional

from .config import RSEngineConfig
from .data_loader import load_stock_universe
from .exporter import export_outputs
from .rs_engine import run_rs_engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VN Relative Strength engine (O'Neil/Minervini-style).",
    )
    parser.add_argument(
        "--mode",
        choices=["tactical_vn", "position_vn"],
        help="RS scoring mode (tactical_vn or position_vn).",
    )
    parser.add_argument(
        "--benchmark",
        help="Benchmark ticker symbol (default: VNINDEX).",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        help="Minimum last close price to pass universe filter.",
    )
    parser.add_argument(
        "--min-median-value-20d",
        type=float,
        help="Minimum 20d median traded value (VND).",
    )
    parser.add_argument(
        "--min-avg-value-50d",
        type=float,
        help="Minimum 50d average traded value (VND).",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        help="Minimum history length in trading days.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def build_config_from_args(args: argparse.Namespace) -> RSEngineConfig:
    cfg = RSEngineConfig()

    if args.mode:
        cfg.scoring_mode = args.mode
    if args.benchmark:
        cfg.benchmark_ticker = args.benchmark
    if args.min_price is not None:
        cfg.min_price = args.min_price
    if args.min_median_value_20d is not None:
        cfg.min_median_value_20d = args.min_median_value_20d
    if args.min_avg_value_50d is not None:
        cfg.min_avg_value_50d = args.min_avg_value_50d
    if args.min_history_days is not None:
        cfg.min_history_days = args.min_history_days

    return cfg


def main() -> None:
    configure_logging()
    args = parse_args()
    cfg = build_config_from_args(args)

    logging.info(
        "Starting VN RS engine with mode=%s, benchmark=%s",
        cfg.scoring_mode,
        cfg.benchmark_ticker,
    )

    universe = load_stock_universe(cfg.data_stocks_dir)

    if not universe.stocks:
        logging.error("No stock CSV files found in %s", cfg.data_stocks_dir)
        return

    if universe.broken_files:
        logging.warning("Broken files skipped: %d", len(universe.broken_files))

    result = run_rs_engine(universe, cfg)

    export_outputs(result.full_timeseries, result.latest_snapshot, cfg)

    summary = result.summary
    logging.info("=== VN RS Engine Summary ===")
    logging.info("Total files found:          %d", summary["total_files_found"])
    logging.info("Successfully processed:     %d", summary["successfully_processed"])
    logging.info("Skipped (errors/broken):    %d", summary["skipped"])
    logging.info("Passing liquidity filters:  %d", summary["liquidity_pass_count"])
    logging.info("Passing trend template:     %d", summary["trend_template_count"])
    logging.info("In top RS decile (latest):  %d", summary["top_decile_count"])


if __name__ == "__main__":
    main()

