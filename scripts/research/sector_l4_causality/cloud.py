"""
Thin wrapper around pp_backtest/ema_levels/indicators.py -> ema_cloud().
Uses EMA20/100 only (A3 definition). Do not introduce a third cloud.
"""
import sys
from pathlib import Path
import pandas as pd

_PP = Path(__file__).resolve().parents[3] / "pp_backtest" / "ema_levels"
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP.parent.parent))

from pp_backtest.ema_levels.indicators import ema_cloud as _ema_cloud
from .config import EMA_FAST, EMA_SLOW


def compute_cloud_series(close: pd.Series) -> pd.DataFrame:
    """Return DataFrame with ema_fast, ema_slow, cloud_bull_20_100 for one symbol."""
    result = _ema_cloud(close, EMA_FAST, EMA_SLOW)
    return pd.DataFrame({
        "ema_fast":           result["ema_fast"],
        "ema_slow":           result["ema_slow"],
        "cloud_bull_20_100":  result["cloud_bull"].astype(int),
    }, index=close.index)


def add_cloud_to_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Add ema_fast, ema_slow, cloud_bull_20_100 to a symbol×date panel.
    Panel must have columns: symbol, date, close (sorted by symbol, date).
    """
    panel = panel.sort_values(["symbol", "date"]).copy()
    cloud_parts = []
    for sym, grp in panel.groupby("symbol", sort=False):
        cloud_df = compute_cloud_series(grp.set_index("date")["close"])
        cloud_df = cloud_df.reset_index()
        cloud_df["symbol"] = sym
        cloud_parts.append(cloud_df)
    cloud_panel = pd.concat(cloud_parts, ignore_index=True)
    panel = panel.merge(cloud_panel, on=["symbol", "date"], how="left")
    return panel
