"""Market data helpers — ADV50 from OHLCV panel (formula from portfolio_optimization_phase31)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = REPO_ROOT / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"


@dataclass
class MarketDataBundle:
    asof_date: str
    panel: pd.DataFrame
    adv50_map: Dict[str, pd.Series] = field(default_factory=dict)

    def adv50_at(self, symbol: str, asof: Optional[str] = None) -> float:
        asof = asof or self.asof_date
        s = self.adv50_map.get(symbol.upper())
        if s is None or s.empty:
            return 0.0
        ed = pd.Timestamp(asof)
        valid = s[s.index <= ed].dropna()
        if valid.empty:
            return 0.0
        return float(valid.iloc[-1])

    def close_at(self, symbol: str, asof: Optional[str] = None) -> float:
        asof = asof or self.asof_date
        sym = symbol.upper()
        sub = self.panel[self.panel["symbol"] == sym]
        if sub.empty:
            return 0.0
        sub = sub.sort_values("date")
        ed = pd.Timestamp(asof)
        row = sub[sub["date"] <= ed]
        if row.empty:
            return 0.0
        return float(row.iloc[-1]["close"])


def build_adv50_map(panel: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    symbol -> Series(date -> adv50 VND).
    Source: pp_backtest/portfolio_optimization_phase31._build_adv50_map
    """
    adv50_map: Dict[str, pd.Series] = {}
    for sym, sdf in panel.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        c = sdf["close"].astype(float)
        v = sdf.get("volume", pd.Series(np.zeros(len(sdf)))).astype(float)
        if "value" in sdf.columns:
            val = sdf["value"].astype(float)
            val = val.fillna(c * v * 1000)
        else:
            val = c * v * 1000
        adv50 = val.rolling(50, min_periods=20).mean()
        adv50_map[sym] = pd.Series(adv50.values, index=pd.to_datetime(sdf["date"]))
    return adv50_map


def load_panel(
    panel_path: Optional[Path] = None,
    asof_date: Optional[str] = None,
) -> MarketDataBundle:
    path = panel_path or DEFAULT_PANEL
    if not path.exists():
        return MarketDataBundle(
            asof_date=asof_date or datetime.utcnow().strftime("%Y-%m-%d"),
            panel=pd.DataFrame(),
            adv50_map={},
        )
    panel = pd.read_parquet(path)
    panel["date"] = pd.to_datetime(panel["date"])
    if asof_date:
        ed = pd.Timestamp(asof_date)
        panel = panel[panel["date"] <= ed]
    asof = asof_date or panel["date"].max().strftime("%Y-%m-%d")
    adv50_map = build_adv50_map(panel)
    return MarketDataBundle(asof_date=asof, panel=panel, adv50_map=adv50_map)
