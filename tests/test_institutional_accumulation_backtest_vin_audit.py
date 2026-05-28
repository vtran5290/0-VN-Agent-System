from __future__ import annotations

import pandas as pd

from scripts.research.institutional_accumulation_backtest.run_outcomes import _write_vin_ticker_audit


def test_vin_audit_includes_required_tickers(tmp_path) -> None:
    panel = pd.DataFrame({"ticker": ["VIC", "AAA"]})
    outcomes = pd.DataFrame({"ticker": ["VIC"]})
    prices = {
        "VIC": pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "open": [1.0], "close": [1.0]}),
        "VHM": pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "open": [1.0], "close": [1.0]}),
    }
    path = tmp_path / "vin_ticker_audit.csv"
    _write_vin_ticker_audit(panel=panel, outcomes=outcomes, prices_by_ticker=prices, path=path)
    df = pd.read_csv(path)
    assert set(["VIC", "VHM", "VRE", "VPL"]).issubset(set(df["ticker"]))
