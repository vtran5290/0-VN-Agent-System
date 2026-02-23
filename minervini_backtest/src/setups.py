# minervini_backtest/src/setups.py — VCP proxy (Contraction Stack + Volume Dry-up), 3-week tight
from __future__ import annotations
import numpy as np
import pandas as pd


def contraction_stack(
    df: pd.DataFrame,
    short: int = 5,
    mid: int = 10,
    long: int = 20,
) -> pd.Series:
    """
    ATR%_short < ATR%_mid < ATR%_long (volatility contracting).
    Uses atr_pct_5, atr_pct_10, atr_pct_20 if present; else computes.
    """
    if f"atr_pct_{short}" not in df.columns:
        from indicators import add_atr_pct
        df = add_atr_pct(df.copy(), [short, mid, long])
    s = df[f"atr_pct_{short}"]
    m = df[f"atr_pct_{mid}"]
    l = df[f"atr_pct_{long}"]
    return (s < m) & (m < l)


def volume_dry_up(
    df: pd.DataFrame,
    vol5_lt_vol20: bool = True,
    vol5_max_ratio: float | None = None,
) -> pd.Series:
    """
    SMA(Vol,5) < SMA(Vol,20).
    If vol5_max_ratio set (e.g. 0.85), also require Vol5 < vol5_max_ratio * Vol20 (stronger).
    """
    if "vol_sma5" not in df.columns or "vol_sma20" not in df.columns:
        from indicators import add_vol_sma
        df = add_vol_sma(df.copy(), [5, 20])
    ok = df["vol_sma5"] < df["vol_sma20"]
    if vol5_max_ratio is not None:
        ok = ok & (df["vol_sma5"] < (vol5_max_ratio * df["vol_sma20"]))
    return ok.fillna(False)


def vcp_proxy(
    df: pd.DataFrame,
    cs_short: int = 5,
    cs_mid: int = 10,
    cs_long: int = 20,
    vdu_strong: float | None = None,
) -> pd.Series:
    """CS (contraction stack) + VDU (volume dry-up). vdu_strong e.g. 0.85 for Vol5 < 0.85*Vol20."""
    cs = contraction_stack(df, cs_short, cs_mid, cs_long)
    vdu = volume_dry_up(df, vol5_max_ratio=vdu_strong)
    return (cs & vdu).fillna(False)


def three_week_tight(
    df: pd.DataFrame,
    window: int = 15,
    max_range_pct: float = 0.06,
    vol5_lt_vol20: bool = True,
) -> pd.Series:
    """
    3-week tight proxy: (max(Close)-min(Close))/avg(Close) < max_range_pct in last `window` bars.
    Plus Vol5 < Vol20.
    """
    c = df["close"]
    roll_max = c.rolling(window, min_periods=window).max()
    roll_min = c.rolling(window, min_periods=window).min()
    roll_avg = c.rolling(window, min_periods=window).mean()
    range_pct = (roll_max - roll_min) / roll_avg.replace(0, np.nan)
    tight = (range_pct <= max_range_pct).fillna(False)
    if vol5_lt_vol20:
        if "vol_sma5" not in df.columns:
            from indicators import add_vol_sma
            df = add_vol_sma(df.copy(), [5, 20])
        tight = tight & (df["vol_sma5"] < df["vol_sma20"]).fillna(False)
    return tight


def add_setup(
    df: pd.DataFrame,
    setup_type: str,
    **kwargs,
) -> pd.DataFrame:
    """
    setup_type: 'vcp' | 'vcp_strong' | '3wt'
    Adds setup_ok column.
    """
    out = df.copy()
    if setup_type.lower() == "vcp":
        out["setup_ok"] = vcp_proxy(out, **kwargs)
    elif setup_type.lower() == "vcp_strong":
        out["setup_ok"] = vcp_proxy(out, vdu_strong=0.85, **kwargs)
    elif setup_type.lower() in ("3wt", "3_week_tight"):
        out["setup_ok"] = three_week_tight(out, **kwargs)
    else:
        raise ValueError(f"Unknown setup_type: {setup_type}")
    return out
