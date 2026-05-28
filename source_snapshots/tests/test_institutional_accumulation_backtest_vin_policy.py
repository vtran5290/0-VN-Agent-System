from __future__ import annotations

from src.research.institutional_accumulation_backtest.schema import VinPolicy


def test_ex_vin_symbols_defined() -> None:
    pol = VinPolicy()
    assert set(pol.exclude_symbols) == {"VIC", "VHM", "VRE"}
    assert pol.vpl_min_bars_required == 252
