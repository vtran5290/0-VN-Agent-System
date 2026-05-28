from __future__ import annotations

import pandas as pd

from src.scans.institutional_accumulation.filters import detect_price_value_units, passes_liquidity


def test_liquidity_gate_and_unit_detection() -> None:
    df = pd.DataFrame({"close": [20.0] * 60, "volume": [200000] * 60})
    mode, scale, warn = detect_price_value_units(df)
    assert mode in {"thousand_vnd", "full_vnd", "unknown"}
    liq = {"n_bars": 200, "adv20_value": 3_000_000_000.0, "adv50_value": 2_000_000_000.0}
    ok, _ = passes_liquidity(liq, min_history=120, min_adv20=2_000_000_000.0, min_adv50=1_500_000_000.0)
    assert ok is True
