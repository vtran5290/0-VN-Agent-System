"""Liquid ADV50 universe from FireAnt OHLCV panel (research only, no lookahead)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
OHLCV_PANEL = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
ADV50_THRESHOLD_VND = 2_000_000_000
MIN_BARS_ADV50 = 50


@dataclass(frozen=True)
class PanelAudit:
    source_path: str
    columns: list[str]
    date_min: str
    date_max: str
    n_tickers: int
    n_rows: int
    price_unit: str
    value_unit_note: str
    latest_liquid_n: int
    assumptions: list[str]
    warnings: list[str]


def _normalize_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, str, str, list[str]]:
    warnings: list[str] = []
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    if "symbol" in df.columns:
        df = df.rename(columns={"symbol": "ticker"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    med = float(df["close"].median())
    if 1 <= med <= 500:
        price_unit = "thousand_VND"
        for col in ("open", "high", "low", "close"):
            df[f"{col}_v"] = df[col].astype(float) * 1000.0
    else:
        price_unit = "VND_native"
        for col in ("open", "high", "low", "close"):
            df[f"{col}_v"] = df[col].astype(float)

    if "value" in df.columns and df["value"].notna().mean() > 0.5:
        samp = df[(df["volume"] > 0) & (df["close_v"] > 0)].copy()
        samp["comp"] = samp["close_v"] * samp["volume"]
        ratio = float((samp["value"] / samp["comp"].replace(0, np.nan)).median())
        if 0.5 < ratio < 2.0:
            df["tv"] = df["value"].astype(float)
            vol_note = f"value column VND (median ratio={ratio:.2f})"
        elif 0.005 < ratio < 0.05:
            df["tv"] = df["value"].astype(float) * 1000.0
            vol_note = f"value kVND scaled ×1000 (ratio={ratio:.3f})"
        else:
            df["tv"] = df["close_v"] * df["volume"]
            vol_note = f"computed close×volume (ratio={ratio:.3f})"
            warnings.append(f"value/close×volume ratio unusual: {ratio:.3f}")
    else:
        df["tv"] = df["close_v"] * df["volume"]
        vol_note = "computed close×volume (no reliable value col)"

    g = df.groupby("ticker", sort=False)
    df["adv50_value"] = g["tv"].transform(
        lambda s: s.rolling(MIN_BARS_ADV50, min_periods=MIN_BARS_ADV50).mean()
    )
    df["is_liquid"] = df["adv50_value"] >= ADV50_THRESHOLD_VND
    df["prev_close_v"] = g["close_v"].shift(1)
    return df, price_unit, vol_note, warnings


@lru_cache(maxsize=1)
def load_normalized_panel() -> pd.DataFrame:
    if not OHLCV_PANEL.is_file():
        raise FileNotFoundError(f"OHLCV panel missing: {OHLCV_PANEL}")
    raw = pd.read_parquet(OHLCV_PANEL)
    panel, _, _, _ = _normalize_panel(raw)
    return panel


def audit_panel(*, as_of: Optional[str] = None) -> PanelAudit:
    panel = load_normalized_panel()
    as_of_ts = pd.Timestamp(as_of) if as_of else panel["date"].max()
    sub = panel[panel["date"] == as_of_ts]
    latest_liquid = int(sub["is_liquid"].sum()) if not sub.empty else 0
    _, price_unit, vol_note, warns = _normalize_panel(pd.read_parquet(OHLCV_PANEL))
    assumptions = [
        f"ADV50 = rolling {MIN_BARS_ADV50}-day mean of daily value traded (tv), no lookahead",
        f"Liquid if adv50_value >= {ADV50_THRESHOLD_VND:,.0f} VND on that date",
        "Universe size varies by date; not a fixed ticker list",
        "Panel history starts 2017-05-18 (not full 2012 index history)",
    ]
    return PanelAudit(
        source_path=str(OHLCV_PANEL),
        columns=list(panel.columns),
        date_min=panel["date"].min().strftime("%Y-%m-%d"),
        date_max=panel["date"].max().strftime("%Y-%m-%d"),
        n_tickers=int(panel["ticker"].nunique()),
        n_rows=len(panel),
        price_unit=price_unit,
        value_unit_note=vol_note,
        latest_liquid_n=latest_liquid,
        assumptions=assumptions,
        warnings=warns,
    )


def liquid_slice(
    panel: pd.DataFrame,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    out = panel[panel["is_liquid"]].copy()
    if start:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end:
        out = out[out["date"] <= pd.Timestamp(end)]
    return out


def per_ticker_ma_flags(panel: pd.DataFrame) -> pd.DataFrame:
    """Add above-MA and new high/low flags per row (liquid rows used downstream)."""
    df = panel.copy()
    g = df.groupby("ticker", sort=False)
    c = df["close_v"]
    for w, col in ((20, "ma20"), (50, "ma50"), (100, "ma100"), (150, "ma150"), (200, "ma200")):
        ma = g["close_v"].transform(lambda s, win=w: s.rolling(win, min_periods=win).mean())
        df[col] = ma
        df[f"above_{col}"] = c > ma
    for w in (20, 50):
        roll_hi = g["close_v"].transform(lambda s, win=w: s.rolling(win, min_periods=win).max())
        roll_lo = g["close_v"].transform(lambda s, win=w: s.rolling(win, min_periods=win).min())
        df[f"new_{w}d_high"] = c >= roll_hi
        df[f"new_{w}d_low"] = c <= roll_lo
    pc = df["prev_close_v"]
    df["is_advancer"] = c > pc
    df["is_decliner"] = c < pc
    df["is_unchanged"] = ~(df["is_advancer"] | df["is_decliner"])
    return df
