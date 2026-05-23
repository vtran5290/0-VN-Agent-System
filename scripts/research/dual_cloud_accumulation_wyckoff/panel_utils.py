"""Shared panel loading, signal generation, and ADV filtering utilities.

Used by all stage scripts. Keeps panel IO and signal logic in one place.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
PANEL_PARQUET  = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
VNINDEX_PARQUET= REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
UNIVERSE_FILE  = REPO / "config" / "universe_liquid_adv50_2b.txt"
OUT_DIR        = REPO / "outputs" / "research" / "dual_cloud_accumulation_wyckoff"

# ── Universe / exclusion policy (SSOT: docs/research/VIN_EMA_CLOUD_BASELINE.md)
EX_VIN_SYMBOLS    = frozenset({"VIC", "VHM", "VRE"})
VPL_SYMBOL        = "VPL"
MIN_BARS_VPL      = 252

# ── Liquidity ─────────────────────────────────────────────────────────────────
MIN_ADV_VND    = 2_000_000_000   # 2 B VND/day
COST_BPS       = 40              # 15 fee + 5 slip each side = 40 bps round-trip
MIN_HISTORY    = 100             # warmup bars before signals allowed

# ── Strategy parameters ───────────────────────────────────────────────────────
A3_FAST, A3_SLOW = 20, 100
S3_FAST, S3_SLOW = 21, 55
SUCCESS_TARGET   = 0.15          # +15% for win classification
SUCCESS_STOP     = 0.08          # −8% for loss classification
HORIZONS         = [25, 50, 63, 100]  # forward return horizons (bars)


# ── Panel loading ─────────────────────────────────────────────────────────────

def load_panel(ex_vin: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Load ohlcv_panel_ext2012.parquet and split into per-symbol DataFrames.

    Returns dict {symbol: df} where each df has columns:
        date, open, high, low, close, volume, adv50
    close/open/high/low are in kVND. adv50 is in VND.
    Sorted by date, integer-indexed.

    Applies:
    - ex-VIN exclusion if ex_vin=True (excludes VIC, VHM, VRE)
    - VPL excluded if bar count < MIN_BARS_VPL
    - ADV50 computed as close_kVND * volume * 1000 (corrected formula)
    """
    log.info("Loading panel from %s", PANEL_PARQUET)
    raw = pd.read_parquet(PANEL_PARQUET)

    # Normalize column names
    raw.columns = raw.columns.str.lower().str.strip()
    if "ticker" in raw.columns and "symbol" not in raw.columns:
        raw = raw.rename(columns={"ticker": "symbol"})
    if "symbol" not in raw.columns:
        raise ValueError("Panel missing 'symbol' column")

    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Detect price units — close should be kVND (typical range 1–500)
    med_close = raw["close"].median()
    if med_close > 500:
        log.warning(
            "Median close = %.1f — looks like VND not kVND. "
            "ADV formula will assume raw VND and divide by 1000.",
            med_close,
        )
        price_scale = 1 / 1000
    else:
        price_scale = 1.0   # already in kVND

    # Corrected ADV: close_kVND * volume * 1000 = VND turnover
    raw["adv50"] = (
        (raw["close"] * price_scale * raw["volume"] * 1000)
        .groupby(raw["symbol"])
        .transform(lambda s: s.rolling(50, min_periods=20).mean())
    )

    # Apply exclusions
    symbols_all = raw["symbol"].unique().tolist()
    excluded: set[str] = set()

    if ex_vin:
        excluded |= EX_VIN_SYMBOLS

    # VPL: exclude if fewer than MIN_BARS_VPL rows
    vpl_bars = (raw["symbol"] == VPL_SYMBOL).sum()
    if vpl_bars < MIN_BARS_VPL:
        excluded.add(VPL_SYMBOL)
        log.info("VPL excluded: only %d bars (< %d)", vpl_bars, MIN_BARS_VPL)

    raw = raw[~raw["symbol"].isin(excluded)]
    log.info(
        "Panel: %d symbols after exclusions (%s), %d rows total",
        raw["symbol"].nunique(),
        ", ".join(sorted(excluded)) or "none",
        len(raw),
    )

    # Split to per-symbol dicts
    panels: Dict[str, pd.DataFrame] = {}
    for sym, grp in raw.groupby("symbol", sort=False):
        g = grp.reset_index(drop=True)
        panels[str(sym)] = g

    return panels


# ── VNINDEX regime ────────────────────────────────────────────────────────────

def load_vnindex_regime(fast: int = 21, slow: int = 55) -> pd.Series:
    """
    Returns a boolean Series indexed by date: True = VNINDEX cloud bullish
    (EMA_fast > EMA_slow). Used as S3 regime gate.
    """
    raw = pd.read_parquet(VNINDEX_PARQUET)
    raw.columns = raw.columns.str.lower()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values("date").reset_index(drop=True)

    # Dedup BEFORE EMA — duplicate rows would skew the EMA calculation
    raw = raw.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    col = "close"
    ef = raw[col].ewm(span=fast, adjust=False).mean()
    es = raw[col].ewm(span=slow, adjust=False).mean()
    return pd.Series((ef > es).fillna(False).values, index=raw["date"], name="regime_bull")


# ── Cloud signal generation ───────────────────────────────────────────────────

def cloud_signal(
    df: pd.DataFrame,
    fast: int,
    slow: int,
    min_bars_bear: int = 5,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute EMA cloud signal for one symbol's OHLCV frame.

    A signal fires at bar t when:
    1. ema_fast[t] > ema_slow[t]  (cloud bullish)
    2. close[t] > ema_fast[t]     (price above fast EMA)
    3. cloud was bearish for at least min_bars_bear consecutive bars before t
       (ensures we're capturing cloud transitions, not just trending cloud)

    Returns (signal, ema_fast, ema_slow) — all pd.Series with df.index.
    """
    c   = df["close"]
    ef  = c.ewm(span=fast, adjust=False).mean()
    es  = c.ewm(span=slow, adjust=False).mean()

    cloud_bull = ef > es

    # Require at least min_bars_bear consecutive bearish bars just before current bar
    was_consistently_bear = (
        (~cloud_bull)
        .astype(float)
        .rolling(min_bars_bear, min_periods=min_bars_bear)
        .min()
        .shift(1)
        .fillna(0)
        .astype(bool)
    )

    sig = cloud_bull & (c > ef) & was_consistently_bear

    # Suppress warmup
    sig.iloc[: max(slow + min_bars_bear, MIN_HISTORY)] = False
    return sig.fillna(False), ef, es


def a3_signal(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """A3 cloud signal: EMA20/100."""
    return cloud_signal(df, A3_FAST, A3_SLOW)


def s3_signal(
    df: pd.DataFrame,
    regime_map: pd.Series | None = None,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    S3 cloud signal: EMA21/55 + optional VNINDEX regime gate.
    regime_map: date-indexed bool Series (True = bull). If None, no gate.
    """
    sig, ef, es = cloud_signal(df, S3_FAST, S3_SLOW)

    if regime_map is not None and "date" in df.columns:
        # reindex + ffill handles date gaps between VNINDEX and equity panels
        aligned = regime_map.reindex(df["date"]).ffill().fillna(False).values
        in_bull = pd.Series(aligned, index=sig.index, dtype=bool)
        sig = sig & in_bull

    return sig, ef, es


# ── ADV / liquidity gate ──────────────────────────────────────────────────────

def adv_mask(df: pd.DataFrame, min_adv: float = MIN_ADV_VND) -> pd.Series:
    """True where ADV50 ≥ min_adv. Missing ADV is treated as failing the gate."""
    if "adv50" not in df.columns:
        log.warning("adv50 column missing — all bars marked illiquid")
        return pd.Series(False, index=df.index)
    return df["adv50"].fillna(0) >= min_adv


# ── Forward return computation ────────────────────────────────────────────────

def forward_returns(
    df: pd.DataFrame,
    signals: pd.Series,
    horizons: list[int] = HORIZONS,
    cost_bps: int = COST_BPS,
    require_adv: bool = True,
    min_adv: float = MIN_ADV_VND,
) -> pd.DataFrame:
    """
    For each signal bar t, compute net forward returns at each horizon.

    Entry: open of bar t+1.
    Exit : open of bar (t + 1 + horizon).
    Cost : cost_bps / 10_000 deducted from gross return.

    Returns DataFrame with columns:
        signal_bar, signal_date, entry_bar, entry_date, entry_price,
        horizon, gross_return, net_return
    plus all feature columns from df (if present).
    """
    n = len(df)
    open_arr  = df["open"].values
    dates_arr = df["date"].values if "date" in df.columns else np.arange(n)

    liq = adv_mask(df, min_adv) if require_adv else pd.Series(True, index=df.index)
    history_ok = pd.Series(np.arange(n), index=df.index) >= MIN_HISTORY

    valid = signals & liq & history_ok
    sig_bars = np.where(valid.values)[0]

    cost_frac = cost_bps / 10_000.0

    # Causal feature columns present in df.
    # Exclude OHLCV price/volume cols and "score" (recomputed cross-sectionally).
    # adv50 is retained for Stage 6 liquidity bucketing.
    _EXCLUDE = {"date", "open", "high", "low", "close", "volume", "value",
                "symbol", "ticker", "score"}
    feat_cols = [c for c in df.columns if c not in _EXCLUDE]

    _adv50_missing = "adv50" not in df.columns

    rows: list[dict] = []
    for bar in sig_bars:
        entry_bar = bar + 1
        if entry_bar >= n:
            continue
        ep = open_arr[entry_bar]
        if ep <= 0:
            continue

        feat_vals = {fc: df[fc].iloc[bar] for fc in feat_cols}
        _liq_pass = bool(liq.iloc[bar])
        _adv50_nan = (not _adv50_missing) and bool(pd.isna(df["adv50"].iloc[bar]))

        for h in horizons:
            exit_bar = entry_bar + h
            if exit_bar < n:
                xp   = open_arr[exit_bar]
                gr   = xp / ep - 1.0
                nr   = gr - cost_frac
            else:
                xp = gr = nr = np.nan

            rows.append({
                "signal_bar":        bar,
                "signal_date":       dates_arr[bar],
                "entry_bar":         entry_bar,
                "entry_date":        dates_arr[entry_bar],
                "entry_price":       ep,
                "horizon":           h,
                "gross_return":      gr,
                "net_return":        nr,
                "liquidity_pass":    _liq_pass,
                "adv50_missing_flag": _adv50_missing or _adv50_nan,
                **feat_vals,
            })

    return pd.DataFrame(rows)


# ── Analysis helpers ──────────────────────────────────────────────────────────

def score_quintile(score: pd.Series, n_bins: int = 5) -> pd.Series:
    """Assign [1..n_bins] quintile labels to a score Series."""
    return pd.qcut(score.rank(method="first"), n_bins, labels=False).astype("Int64") + 1


def trade_summary(trades: pd.DataFrame, success_target: float = SUCCESS_TARGET) -> pd.DataFrame:
    """
    Group trade DataFrame by 'horizon' and compute summary stats.
    Expects columns: net_return, gross_return, horizon.
    """
    def _agg(g):
        valid = g["net_return"].dropna()
        n = len(valid)
        if n == 0:
            return pd.Series(dtype=float)
        return pd.Series({
            "n_trades":      n,
            "win_rate":      (valid >= success_target).mean(),
            "loss_rate":     (valid <= -SUCCESS_STOP).mean(),
            "avg_net_ret":   valid.mean(),
            "med_net_ret":   valid.median(),
            "pct_positive":  (valid > 0).mean(),
            "avg_gross_ret": g["gross_return"].dropna().mean(),
        })
    return trades.groupby("horizon").apply(_agg).reset_index()


def quintile_summary(
    trades: pd.DataFrame,
    quintile_col: str = "score_q",
    horizon: int = 63,
    success_target: float = SUCCESS_TARGET,
) -> pd.DataFrame:
    """
    Break trades by quintile at a given horizon and compute summary stats.
    """
    sub = trades[trades["horizon"] == horizon].copy()
    if quintile_col not in sub.columns:
        raise KeyError(f"Column '{quintile_col}' not found in trades")

    def _agg(g):
        valid = g["net_return"].dropna()
        n = len(valid)
        if n == 0:
            return pd.Series(dtype=float)
        return pd.Series({
            "n_trades":     n,
            "win_rate":     (valid >= success_target).mean(),
            "loss_rate":    (valid <= -SUCCESS_STOP).mean(),
            "avg_net_ret":  valid.mean(),
            "med_net_ret":  valid.median(),
            "pct_positive": (valid > 0).mean(),
        })
    return sub.groupby(quintile_col).apply(_agg).reset_index()
