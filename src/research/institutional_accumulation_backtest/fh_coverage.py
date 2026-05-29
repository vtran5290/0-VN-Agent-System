"""Phase 0: Full-history data coverage audit.

Produces:
  data/research/institutional_accumulation_full_history/data_coverage_audit.csv
  data/research/institutional_accumulation_full_history/data_coverage_summary.csv

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .fh_data_loader import ParquetSymbolLoader, load_fh_benchmark

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"
EX_VIN = {"VIC", "VHM", "VRE"}


def _adv50_first_valid(df: pd.DataFrame) -> str | None:
    """Return the earliest date at which the symbol has ≥50 bars of history."""
    if df is None or len(df) < 50:
        return None
    return str(df["date"].iloc[49].date())


def _has_year_data(df: pd.DataFrame, year: int) -> bool:
    if df is None or df.empty:
        return False
    return bool((pd.to_datetime(df["date"]).dt.year == year).any())


def _count_missing_blocks(df: pd.DataFrame, max_gap_days: int = 10) -> int:
    """Count calendar gaps > max_gap_days in the date series."""
    if df is None or len(df) < 2:
        return 0
    dates = pd.to_datetime(df["date"]).sort_values()
    diffs = dates.diff().dropna()
    return int((diffs > pd.Timedelta(days=max_gap_days)).sum())


def run_coverage_audit(
    loader: ParquetSymbolLoader,
    out_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Phase 0 data coverage audit.

    Returns (audit_df, summary_df) and writes CSVs to out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Per-symbol audit
    rows: list[dict[str, Any]] = []
    for sym in loader.symbols:
        df = loader(sym)
        if df is None or df.empty:
            continue
        first = str(df["date"].min().date())
        last = str(df["date"].max().date())
        bar_count = len(df)
        source = df["_source"].iloc[0] if "_source" in df.columns else "unknown"
        rows.append(
            {
                "ticker": sym,
                "first_date": first,
                "last_date": last,
                "bar_count": bar_count,
                "has_2012_data": _has_year_data(df, 2012),
                "has_2017_data": _has_year_data(df, 2017),
                "has_2022_data": _has_year_data(df, 2022),
                "has_2024_data": _has_year_data(df, 2024),
                "missing_date_blocks": _count_missing_blocks(df),
                "adv50_first_valid_date": _adv50_first_valid(df),
                "source_file": source,
                "coverage_label": (
                    "BLOCKED_BY_DATA_COVERAGE"
                    if bar_count < 50
                    else ("FULL_HISTORY" if _has_year_data(df, 2012) else "PARTIAL_2017_PLUS")
                ),
                "research_only_flag": RESEARCH_ONLY_FLAG,
            }
        )

    audit_df = pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)

    # VNINDEX benchmark
    try:
        bench = load_fh_benchmark()
        vn_min = str(bench["date"].min().date())
        vn_max = str(bench["date"].max().date())
    except FileNotFoundError:
        vn_min = vn_max = "NOT_FOUND"

    # Determine usable starts
    if not audit_df.empty:
        tickers_2017 = int(audit_df["has_2017_data"].sum())
        tickers_2022 = int(audit_df["has_2022_data"].sum())
        tickers_2024 = int(audit_df["has_2024_data"].sum())
        tickers_2012 = int(audit_df["has_2012_data"].sum())
        total = len(audit_df)
        # Usable event backtest start: need >= 30 tickers with 120+ bars
        event_start_candidates = audit_df[audit_df["bar_count"] >= 120].sort_values("first_date")
        usable_event_start = (
            str(event_start_candidates.iloc[29]["first_date"])
            if len(event_start_candidates) >= 30
            else "BLOCKED_INSUFFICIENT_UNIVERSE"
        )
        # Usable portfolio start: need >= 100 tickers with adv50 valid
        adv50_valid = audit_df[audit_df["adv50_first_valid_date"].notna()].sort_values("adv50_first_valid_date")
        usable_portfolio_start = (
            str(adv50_valid.iloc[99]["adv50_first_valid_date"])
            if len(adv50_valid) >= 100
            else "BLOCKED_INSUFFICIENT_UNIVERSE"
        )
    else:
        total = tickers_2012 = tickers_2017 = tickers_2022 = tickers_2024 = 0
        usable_event_start = usable_portfolio_start = "BLOCKED_NO_DATA"

    summary_rows = [
        {"metric": "research_only_flag", "value": RESEARCH_ONLY_FLAG, "status": "INFO", "note": "Not production"},
        {"metric": "panel_min_date", "value": str(audit_df["first_date"].min()) if total > 0 else "N/A",
         "status": "INFO", "note": "Earliest any ticker data exists"},
        {"metric": "panel_max_date", "value": str(audit_df["last_date"].max()) if total > 0 else "N/A",
         "status": "INFO", "note": "Latest data available"},
        {"metric": "ticker_count_total", "value": str(total), "status": "INFO", "note": "Total tickers audited"},
        {"metric": "ticker_count_with_2012_data", "value": str(tickers_2012),
         "status": "WARN" if tickers_2012 < 50 else "OK",
         "note": "Tickers with 2012 data (minervini raw supplement)"},
        {"metric": "ticker_count_with_2017_data", "value": str(tickers_2017),
         "status": "OK" if tickers_2017 > 50 else "WARN",
         "note": "Tickers with 2017 data"},
        {"metric": "ticker_count_with_2022_data", "value": str(tickers_2022),
         "status": "OK" if tickers_2022 > 200 else "WARN",
         "note": "Tickers with 2022 data"},
        {"metric": "ticker_count_with_2024_data", "value": str(tickers_2024),
         "status": "OK" if tickers_2024 > 500 else "WARN",
         "note": "Tickers with 2024 data"},
        {"metric": "vnindex_min_date", "value": vn_min, "status": "INFO", "note": "VNINDEX benchmark start"},
        {"metric": "vnindex_max_date", "value": vn_max, "status": "INFO", "note": "VNINDEX benchmark end"},
        {"metric": "data_gap_2019_2021", "value": "PARQUET_SPARSE",
         "status": "WARN",
         "note": "230-251 tickers in parquet 2019-2021; minervini raw adds 100-150 more"},
        {"metric": "usable_full_history_start", "value": "2017-05-18",
         "status": "PARTIAL",
         "note": "Parquet starts 2017-05-18; 2012-2016 BLOCKED_BY_DATA_COVERAGE for stock universe"},
        {"metric": "usable_event_backtest_start", "value": usable_event_start,
         "status": "OK" if "BLOCKED" not in usable_event_start else "BLOCKED",
         "note": "First date with >=30 tickers having 120+ bar history"},
        {"metric": "usable_portfolio_backtest_start", "value": usable_portfolio_start,
         "status": "OK" if "BLOCKED" not in usable_portfolio_start else "BLOCKED",
         "note": "First date with >=100 tickers having valid ADV50"},
        {"metric": "pre_2017_coverage", "value": "BLOCKED_BY_DATA_COVERAGE",
         "status": "BLOCKED",
         "note": "Individual stock OHLCV not available before 2017 in parquet; minervini raw adds 165 tickers back to 2012"},
        {"metric": "pre_2019_portfolio", "value": "BLOCKED_BY_SPARSE_UNIVERSE",
         "status": "BLOCKED",
         "note": "Fewer than 200 tickers in 2017-2018; top-200 universe not viable"},
    ]
    summary_df = pd.DataFrame(summary_rows)

    audit_df.to_csv(out_dir / "data_coverage_audit.csv", index=False)
    summary_df.to_csv(out_dir / "data_coverage_summary.csv", index=False)
    print(f"[Phase 0] Coverage audit: {total} tickers  2012:{tickers_2012}  2017:{tickers_2017}  2022:{tickers_2022}  2024:{tickers_2024}")
    print(f"[Phase 0] Usable event start: {usable_event_start}")
    print(f"[Phase 0] Usable portfolio start: {usable_portfolio_start}")
    return audit_df, summary_df
