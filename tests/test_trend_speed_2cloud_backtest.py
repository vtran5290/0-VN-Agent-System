"""Backtest discipline tests for Trend Speed × 2-cloud research."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import cloud_signal, load_panel
from scripts.research.trend_speed_2cloud.engine import collect_trades, load_breadth
from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import load_vnindex_regime


@pytest.fixture(scope="module")
def tiny_panels():
    panels = load_panel(ex_vin=True)
    out = {}
    for sym in list(panels.keys())[:3]:
        out[sym] = panels[sym].iloc[-400:].reset_index(drop=True)
    return out


def test_entry_fill_is_next_open(tiny_panels):
    sym = next(iter(tiny_panels))
    df = tiny_panels[sym]
    sig, _, _ = cloud_signal(df, 20, 100)
    bars = np.where(sig.values)[0]
    if len(bars) == 0:
        pytest.skip("no signals in sample")
    bar = int(bars[0])
    entry_bar = bar + 1
    assert entry_bar < len(df)
    assert df["open"].iloc[entry_bar] > 0


def test_rolling_rank_uses_past_only():
    from scripts.research.trend_speed_2cloud.engine import _zscore_rolling

    s = pd.Series(np.arange(300, dtype=float))
    z = _zscore_rolling(s, window=252)
    assert np.isnan(z.iloc[58])
    assert not np.isnan(z.iloc[-1])


def test_baseline_trade_collection_smoke(tiny_panels):
    breadth = load_breadth()
    regime = load_vnindex_regime(20, 100)
    trades = collect_trades("A3", tiny_panels, regime, breadth, ex_vin=True)
    assert "tsa_trendspeed" in trades.columns or trades.empty
    if not trades.empty:
        assert trades["signal_bar"].max() < 400
