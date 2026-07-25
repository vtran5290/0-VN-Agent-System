"""B0_CLEAN signal layer (frozen primary + reporting ablations)."""

from __future__ import annotations

import pandas as pd

from .indicators import add_symbol_indicators, add_vnindex_indicators


def prepare_panel_with_signals(
    panel: pd.DataFrame,
    vnindex: pd.DataFrame,
    *,
    ablation: str = "primary",
) -> pd.DataFrame:
    """
    ablation:
      primary | no_rsi | no_low_vol | no_vnindex
    """
    vni = add_vnindex_indicators(vnindex)
    vni_max = pd.to_datetime(vni["date"]).max()

    parts: list[pd.DataFrame] = []
    for sym, g in panel.groupby("symbol", sort=False):
        ind = add_symbol_indicators(g)
        ind["symbol"] = sym
        parts.append(ind)
    df = pd.concat(parts, ignore_index=True)
    df = df.merge(vni, on="date", how="left")

    # Regime gate requires VNINDEX; no signal after VNINDEX ends
    df["vni_ok"] = df["vnindex_close"] > df["vni_sma20"]
    if ablation == "no_vnindex":
        df["vni_ok"] = True

    rsi_ok = df["rsi14"] < 45.0
    if ablation == "no_rsi":
        rsi_ok = True

    low_vol_ok = df["volume"] < df["vol_sma20"]
    if ablation == "no_low_vol":
        low_vol_ok = True

    pull_ok = (df["pullback3"] >= -0.07) & (df["pullback3"] <= -0.02)
    trend_ok = df["close"] > df["sma20"]

    # Universe must already be on frame as universe_eligible
    uni = df["universe_eligible"] if "universe_eligible" in df.columns else True

    df["signal"] = (
        rsi_ok & trend_ok & pull_ok & low_vol_ok & df["vni_ok"] & uni & df["date"].le(vni_max)
    ).fillna(False)

    df["ablation"] = ablation
    return df


def apply_signal_gates(df: pd.DataFrame, *, ablation: str = "primary") -> pd.DataFrame:
    """Recompute `signal` from existing indicator columns (no re-indicator)."""
    out = df.copy()
    vni_ok = out["vnindex_close"] > out["vni_sma20"]
    if ablation == "no_vnindex":
        vni_ok = pd.Series(True, index=out.index)
    rsi_ok = out["rsi14"] < 45.0
    if ablation == "no_rsi":
        rsi_ok = pd.Series(True, index=out.index)
    low_vol_ok = out["volume"] < out["vol_sma20"]
    if ablation == "no_low_vol":
        low_vol_ok = pd.Series(True, index=out.index)
    pull_ok = (out["pullback3"] >= -0.07) & (out["pullback3"] <= -0.02)
    trend_ok = out["close"] > out["sma20"]
    uni = out["universe_eligible"] if "universe_eligible" in out.columns else True
    vni_dated = out.loc[out["vnindex_close"].notna(), "date"]
    vni_max = pd.to_datetime(vni_dated).max() if len(vni_dated) else out["date"].max()
    out["vni_ok"] = vni_ok
    out["signal"] = (
        rsi_ok & trend_ok & pull_ok & low_vol_ok & vni_ok & uni & out["date"].le(vni_max)
    ).fillna(False)
    out["ablation"] = ablation
    return out
