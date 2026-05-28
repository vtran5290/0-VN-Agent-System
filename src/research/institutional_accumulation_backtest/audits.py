from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def run_coverage_audit(
    *,
    panel: pd.DataFrame,
    outcomes: pd.DataFrame | None,
    requested_start: str,
    requested_end: str,
    cadence: str,
    context_mode: str,
    max_symbols_used: int | None,
    source_ticker_count: int,
    vnindex_available: bool,
    vnindex_non_null_rows: int,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    actual_first = ""
    actual_last = ""
    ticker_count_panel = 0
    if not panel.empty:
        dt = pd.to_datetime(panel["scan_date"])
        actual_first = str(dt.min().date())
        actual_last = str(dt.max().date())
        ticker_count_panel = int(panel["ticker"].nunique())

    outcome_rows = int(len(outcomes)) if outcomes is not None else 0
    ticker_with_outcomes = int(outcomes["ticker"].nunique()) if outcomes is not None and not outcomes.empty else 0
    full_rows = int(panel["universe_full"].fillna(False).sum()) if "universe_full" in panel.columns else 0
    ex_vin_rows = int(panel["universe_ex_vin"].fillna(False).sum()) if "universe_ex_vin" in panel.columns else 0
    vin_only_rows = int(panel["is_vin"].fillna(False).sum()) if "is_vin" in panel.columns else 0
    weekly_scan_count = int(pd.to_datetime(panel["scan_date"]).dt.to_period("W-FRI").nunique()) if not panel.empty else 0
    monthly_scan_count = int(pd.to_datetime(panel["scan_date"]).dt.to_period("M").nunique()) if not panel.empty else 0

    status = "RUN_COMPLETE"
    note = "runtime complete: full weekly run appears complete"
    if max_symbols_used is not None:
        status = "INCOMPLETE_RUNTIME_FALLBACK"
        note = "runtime fallback restriction (max_symbols) was used"
    elif cadence.lower() != "weekly":
        status = "INCOMPLETE_RUNTIME_FALLBACK"
        note = "final run cadence is not weekly"
    elif panel.empty:
        status = "BLOCKED_BY_DATA"
        note = "panel is empty"
    elif source_ticker_count > 0 and ticker_count_panel < int(source_ticker_count * 0.9):
        status = "INCOMPLETE_RUNTIME_FALLBACK"
        note = "panel ticker coverage below full universe threshold"
    elif outcome_rows > 0 and outcome_rows < 5000 and cadence.lower() == "weekly":
        status = "INCOMPLETE_RUNTIME_FALLBACK"
        note = "outcome row count below weekly full-universe expectation"

    tier1_rows = int(panel["is_tier1"].fillna(False).sum()) if "is_tier1" in panel.columns else 0
    tier2_rows = int(panel["is_tier2"].fillna(False).sum()) if "is_tier2" in panel.columns else 0
    tier3_rows = int(panel["is_tier3"].fillna(False).sum()) if "is_tier3" in panel.columns else 0
    reject_rows = int(panel["is_reject"].fillna(False).sum()) if "is_reject" in panel.columns else 0

    rows = [
        ("requested_start_date", requested_start, "INFO", ""),
        ("actual_first_scan_date", actual_first, "INFO", ""),
        ("requested_end_date", requested_end, "INFO", ""),
        ("actual_last_scan_date", actual_last, "INFO", ""),
        ("rebalance_cadence", cadence, "INFO", ""),
        ("context_mode", context_mode, "INFO", ""),
        ("ticker_count_total", source_ticker_count, "INFO", ""),
        ("ticker_count_with_outcomes", ticker_with_outcomes, "INFO", ""),
        ("outcome_rows", outcome_rows, "INFO", ""),
        ("weekly_scan_count", weekly_scan_count, "INFO", ""),
        ("monthly_scan_count", monthly_scan_count, "INFO", ""),
        ("full_universe_used", bool(full_rows > 0 and max_symbols_used is None), "INFO", ""),
        ("max_symbols_used", max_symbols_used if max_symbols_used is not None else "", "INFO", ""),
        ("vnindex_available", vnindex_available, "INFO", ""),
        ("vnindex_non_null_rows", vnindex_non_null_rows, "INFO", ""),
        ("full_universe_rows", full_rows, "INFO", ""),
        ("ex_vin_rows", ex_vin_rows, "INFO", ""),
        ("vin_only_rows", vin_only_rows, "INFO", ""),
        ("tier1_rows", tier1_rows, "INFO", ""),
        ("tier2_rows", tier2_rows, "INFO", ""),
        ("tier3_rows", tier3_rows, "INFO", ""),
        ("reject_rows", reject_rows, "INFO", ""),
        ("run_status", status, status, note),
    ]
    df = pd.DataFrame(rows, columns=["metric", "value", "status", "note"])
    summary = {r[0]: r[1] for r in rows}
    summary["run_status"] = status
    summary["run_status_note"] = note
    summary["ticker_count_panel"] = ticker_count_panel
    return df, summary, status


def benchmark_validation_csv(
    bench: pd.DataFrame,
    outcomes: pd.DataFrame,
    path: Path,
) -> pd.DataFrame:
    b = bench.copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce")
    b = b.dropna(subset=["date"])
    ret_cols = [c for c in outcomes.columns if c.startswith("vnindex_ret_")]
    non_null = int(outcomes[ret_cols].notna().any(axis=1).sum()) if ret_cols else 0
    status = "OK" if len(b) > 0 and non_null > 0 else "BLOCKED_NO_BENCHMARK_DATA"
    note = "benchmark returns present in outcomes" if status == "OK" else "no benchmark returns found"
    out = pd.DataFrame(
        [
            {
                "benchmark": "VNINDEX",
                "date_start": str(b["date"].min().date()) if not b.empty else "",
                "date_end": str(b["date"].max().date()) if not b.empty else "",
                "rows": int(len(b)),
                "missing_rows": int(b["date"].isna().sum()),
                "non_null_return_rows": non_null,
                "status": status,
                "note": note,
            }
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out
