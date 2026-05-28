from __future__ import annotations

import pandas as pd

from src.research.institutional_accumulation_backtest.audits import run_coverage_audit


def test_runtime_fallback_status_when_max_symbols_used() -> None:
    panel = pd.DataFrame(
        [
            {"scan_date": "2024-01-05", "ticker": "AAA", "universe_full": True, "universe_ex_vin": True, "is_vin": False},
            {"scan_date": "2024-01-12", "ticker": "BBB", "universe_full": True, "universe_ex_vin": True, "is_vin": False},
        ]
    )
    audit, summary, status = run_coverage_audit(
        panel=panel,
        outcomes=None,
        requested_start="2012-01-01",
        requested_end="2024-12-31",
        cadence="weekly",
        context_mode="OHLCV_ONLY",
        max_symbols_used=80,
        source_ticker_count=2,
        vnindex_available=True,
        vnindex_non_null_rows=2,
    )
    assert status == "INCOMPLETE_RUNTIME_FALLBACK"
    assert summary["run_status"] == "INCOMPLETE_RUNTIME_FALLBACK"
    assert (audit["metric"] == "run_status").any()
