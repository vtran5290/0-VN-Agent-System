"""
Stock DNA Feature Engineering
==============================
Computes the 4 council-approved candidate lines (EMA20, EMA50, SMA100, SMA150),
ATR14, ADV20/50, stock phase labels, regime features, and forward return labels.

Lookahead rules (enforced):
  - All backward-looking features use .shift(1) on the rolling result.
  - Forward return columns use negative shifts (future data) — labels only, never features.
  - Phase labels derived from shifted MA/EMA values → no lookahead.

VIN / VPL handling (per VIN_EMA_CLOUD_BASELINE.md):
  - VPL excluded if bar count < VPL_MIN_BARS (252).
  - VIN tagged with vin_return_distortion_flag = 1 throughout.
  - Dual universe output: full + ex_vin flags.
"""
from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

from src.trading.research.stock_dna.schema import (
    CANDIDATE_LINES,
    DATA_DIR,
    DISTORTION_FLAG_SYMBOLS,
    MIN_ADV20_VND,
    MIN_BARS_REQUIRED,
    SSOT_DIR,
    VPL_MIN_BARS,
    StockPhase,
    BreadthRegime,
)

logger = logging.getLogger(__name__)

FEATURE_START_DATE = "2016-01-01"


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_ohlcv(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = data_dir / "fireant_ssot" / "ta_ohlcv_panel.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def load_vnindex(data_dir: Path = DATA_DIR) -> Optional[pd.DataFrame]:
    path = data_dir / "fireant_ssot" / "ta_vnindex.parquet"
    if not path.exists():
        logger.warning("VNINDEX parquet not found at %s — regime features will be limited", path)
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_regime_log(data_dir: Path = DATA_DIR) -> Optional[pd.DataFrame]:
    path = data_dir / "combined_regime_log_2012_now.csv"
    if not path.exists():
        logger.warning("Regime log not found at %s — breadth regime will be panel-derived", path)
        return None
    df = pd.read_csv(path, low_memory=False)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


# ── Per-symbol rolling helpers ────────────────────────────────────────────────

def _sym_roll_mean(panel: pd.DataFrame, col: str, w: int) -> pd.Series:
    min_p = max(1, w // 2)
    return panel.groupby("symbol")[col].transform(
        lambda s: s.rolling(w, min_periods=min_p).mean().shift(1)
    )


def _sym_ema(panel: pd.DataFrame, col: str, span: int) -> pd.Series:
    return panel.groupby("symbol")[col].transform(
        lambda s: s.ewm(span=span, adjust=False).mean().shift(1)
    )


def _sym_roll_max(panel: pd.DataFrame, col: str, w: int) -> pd.Series:
    min_p = max(1, w // 2)
    return panel.groupby("symbol")[col].transform(
        lambda s: s.rolling(w, min_periods=min_p).max().shift(1)
    )


# ── Indicator computation ─────────────────────────────────────────────────────

def compute_indicators(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Compute EMA20, EMA50, SMA100, SMA150, ATR14, ADV20, ADV50.
    All values at row t reflect data available at or before t-1 (shift(1) applied).
    """
    # EMA lines
    panel["ema20"]  = _sym_ema(panel, "close", 20)
    panel["ema50"]  = _sym_ema(panel, "close", 50)

    # SMA lines (sma50 added 2026-06-06 — council v2 candidate lines)
    panel["sma50"]  = _sym_roll_mean(panel, "close", 50)
    panel["sma100"] = _sym_roll_mean(panel, "close", 100)
    panel["sma150"] = _sym_roll_mean(panel, "close", 150)

    # ATR14 (true range, 14-bar average, shifted)
    prev_c = panel.groupby("symbol")["close"].transform(lambda s: s.shift(1))
    tr = pd.concat([
        panel["high"] - panel["low"],
        (panel["high"] - prev_c).abs(),
        (panel["low"]  - prev_c).abs(),
    ], axis=1).max(axis=1)
    tr_df = panel[["symbol"]].copy()
    tr_df["tr"] = tr
    panel["atr14"] = tr_df.groupby("symbol")["tr"].transform(
        lambda s: s.rolling(14, min_periods=7).mean().shift(1)
    )

    # ADV20, ADV50
    # The parquet `value` column changed units in Feb 2024 (from raw VND to close×volume).
    # close is consistently in thousands-VND throughout all history, so
    # close × volume × 1000 always yields correct raw VND regardless of parquet version.
    panel["_value_raw_vnd"] = panel["close"] * panel["volume"] * 1000
    panel["adv20_vnd"] = _sym_roll_mean(panel, "_value_raw_vnd", 20)
    panel["adv50_vnd"] = _sym_roll_mean(panel, "_value_raw_vnd", 50)

    # Distance from each line (pct and ATR-normalized)
    for line_name in CANDIDATE_LINES:
        col = line_name
        if col not in panel.columns:
            continue
        panel[f"dist_pct_{col}"]  = (panel["close"] - panel[col]) / panel[col].replace(0, np.nan)
        panel[f"dist_atr_{col}"]  = (panel["close"] - panel[col]).abs() / panel["atr14"].replace(0, np.nan)

    return panel


# ── Stock phase labels ────────────────────────────────────────────────────────

def assign_stock_phase(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Assign phase label per (symbol, date) using shifted EMA/SMA values.
    Phase at t uses EMA/SMA values from t-1 (already shifted in compute_indicators).

    MARKUP              : close > ema50 AND ema20 > ema50
    PULLBACK_IN_UPTREND : close < ema20 AND close > ema50 AND ema20 > ema50
    DECLINE             : close < ema50 AND ema20 < ema50
    BASE_OR_CHOP        : everything else
    """
    close   = panel["close"]
    ema20   = panel["ema20"]
    ema50   = panel["ema50"]

    markup    = (close > ema50) & (ema20 > ema50)
    pullback  = (close < ema20) & (close > ema50) & (ema20 > ema50)
    decline   = (close < ema50) & (ema20 < ema50)

    phase = pd.Series(StockPhase.BASE_OR_CHOP.value, index=panel.index)
    phase[markup]   = StockPhase.MARKUP.value
    phase[pullback] = StockPhase.PULLBACK_IN_UPTREND.value
    phase[decline]  = StockPhase.DECLINE.value

    panel["stock_phase"] = phase
    return panel


# ── Regime features ───────────────────────────────────────────────────────────

def _bucket_breadth(bp: float) -> str:
    try:
        bp = float(bp)
    except (TypeError, ValueError):
        bp = 50.0
    if bp >= 60:
        return BreadthRegime.BULL_BROAD.value
    elif bp >= 50:
        return BreadthRegime.BULL_NARROW.value
    elif bp >= 40:
        return BreadthRegime.NEUTRAL.value
    elif bp >= 30:
        return BreadthRegime.BEAR.value
    return BreadthRegime.STRESS.value


def _compute_panel_breadth(panel: pd.DataFrame) -> pd.Series:
    """Compute % stocks above SMA50 per date from the panel itself."""
    sma50 = panel.groupby("symbol")["close"].transform(
        lambda s: s.rolling(50, min_periods=25).mean().shift(1)
    )
    above = (panel["close"] > sma50).astype(float)
    return above.groupby(panel["date"]).transform("mean") * 100.0


def add_regime_features(
    panel: pd.DataFrame,
    regime_log: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Join breadth regime to panel. Falls back to panel-derived breadth if no regime log."""
    if regime_log is not None:
        r = regime_log.copy()
        keep = [c for c in ["date", "breadth_pct", "market_status_combined", "allow_new_buys"] if c in r.columns]
        panel = panel.merge(r[keep], on="date", how="left")
        if "breadth_pct" in panel.columns:
            pct_col = pd.to_numeric(panel["breadth_pct"], errors="coerce")
        else:
            pct_col = pd.Series(np.nan, index=panel.index)
    else:
        pct_col = pd.Series(np.nan, index=panel.index)

    # Fill gaps with panel-derived breadth
    nan_mask = pct_col.isna()
    if nan_mask.any():
        panel_breadth = _compute_panel_breadth(panel)
        pct_col = pct_col.where(~nan_mask, panel_breadth)

    panel["market_pct_above_sma50"] = pct_col
    panel["breadth_regime"] = [_bucket_breadth(v) for v in pct_col]

    # Convenience flag for regime-split analysis
    panel["regime_is_bull"] = panel["breadth_regime"].isin(
        [BreadthRegime.BULL_BROAD.value, BreadthRegime.BULL_NARROW.value]
    ).astype(int)
    panel["regime_is_bear"] = panel["breadth_regime"].isin(
        [BreadthRegime.BEAR.value, BreadthRegime.STRESS.value]
    ).astype(int)

    return panel


# ── Forward return labels ─────────────────────────────────────────────────────

def add_forward_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Forward return labels. MUST NOT be used as predictor features.
    Computed with negative shifts (future data).
    """
    for d in [5, 10, 20]:
        panel[f"fwd_ret_{d}d"] = panel.groupby("symbol")["close"].transform(
            lambda s, d=d: s.shift(-d) / s - 1
        )

    # MFE / MAE: max / min of high / low over bars t+1 to t+d (inclusive).
    # Formula: shift(-1) so position t holds bar t+1, then reverse-rolling max/min
    # of d bars, then reverse back. Last d bars per symbol are masked to NaN because
    # those rows lack a full forward window and must not appear in OOS metrics.
    for d in [20]:
        def _fwd_max(s: pd.Series, d: int = d) -> pd.Series:
            shifted = s.shift(-1)
            result = shifted[::-1].rolling(d, min_periods=1).max()[::-1]
            # Mask tail: last d bars have incomplete forward windows
            result.iloc[-d:] = np.nan
            return result

        def _fwd_min(s: pd.Series, d: int = d) -> pd.Series:
            shifted = s.shift(-1)
            result = shifted[::-1].rolling(d, min_periods=1).min()[::-1]
            result.iloc[-d:] = np.nan
            return result

        fwd_h = panel.groupby("symbol")["high"].transform(_fwd_max)
        fwd_l = panel.groupby("symbol")["low"].transform(_fwd_min)
        panel[f"mfe_{d}d"] = ((fwd_h / panel["close"]) - 1).clip(lower=0)
        panel[f"mae_{d}d"] = ((fwd_l / panel["close"]) - 1).clip(upper=0)

    return panel


# ── VIN / VPL handling ────────────────────────────────────────────────────────

def apply_vin_vpl_handling(panel: pd.DataFrame) -> pd.DataFrame:
    """
    Per VIN_EMA_CLOUD_BASELINE.md:
      - VPL: exclude if bar count < VPL_MIN_BARS (252)
      - VIN: keep but tag vin_return_distortion_flag = 1
      - Add ex_vin flag for dual-universe analysis
    """
    panel["vin_return_distortion_flag"] = panel["symbol"].isin(DISTORTION_FLAG_SYMBOLS).astype(int)
    panel["ex_vin"] = (~panel["symbol"].isin(DISTORTION_FLAG_SYMBOLS)).astype(int)

    # Exclude VPL if fewer than VPL_MIN_BARS bars are available
    vpl_counts = panel[panel["symbol"] == "VPL"]["symbol"].count() if "VPL" in panel["symbol"].values else 0
    if vpl_counts > 0 and vpl_counts < VPL_MIN_BARS:
        before = len(panel)
        panel = panel[panel["symbol"] != "VPL"].copy()
        logger.info("VPL excluded: only %d bars (< %d required)", vpl_counts, VPL_MIN_BARS)
        logger.info("Panel after VPL exclusion: %d -> %d rows", before, len(panel))

    return panel


# ── Liquidity filter ──────────────────────────────────────────────────────────

def filter_liquid_universe(
    panel: pd.DataFrame,
    min_adv20_vnd: float = MIN_ADV20_VND,
    min_bars: int = MIN_BARS_REQUIRED,
) -> pd.DataFrame:
    """
    Apply council-required liquidity floor:
      - ADV20 >= min_adv20_vnd (default 5bn VND)
      - Symbol must have >= min_bars bars total

    Symbols failing both criteria are dropped entirely.
    Symbols failing ADV20 on some dates are filtered to qualifying rows only.
    """
    # Bar count filter (per symbol, total available history)
    bar_counts = panel.groupby("symbol")["date"].count()
    qualified = bar_counts[bar_counts >= min_bars].index
    before = len(panel)
    panel = panel[panel["symbol"].isin(qualified)].copy()
    logger.info(
        "Bar count filter (>= %d bars): %d -> %d rows, %d -> %d symbols",
        min_bars, before, len(panel),
        len(bar_counts), len(qualified),
    )

    # ADV20 filter (per row)
    before = len(panel)
    panel = panel[panel["adv20_vnd"].fillna(0) >= min_adv20_vnd].copy()
    logger.info(
        "ADV20 filter (>= %.0fbn VND): %d -> %d rows",
        min_adv20_vnd / 1e9, before, len(panel),
    )

    return panel


# ── Main panel builder ────────────────────────────────────────────────────────

def build_dna_panel(
    data_dir: Path = DATA_DIR,
    start_date: str = FEATURE_START_DATE,
    end_date: Optional[str] = None,
    min_adv20_vnd: float = MIN_ADV20_VND,
    apply_liquidity_filter: bool = True,
) -> pd.DataFrame:
    """
    Build the full Stock DNA feature panel.

    Args:
        data_dir: Root data directory.
        start_date: Earliest date to include in output (warmup excluded).
        end_date: Latest date to include. None = all available data.
        min_adv20_vnd: Minimum ADV20 filter. Applied per row after warmup.
        apply_liquidity_filter: Whether to apply ADV20 + bar-count filter.

    Returns:
        DataFrame with all indicators, phase labels, regime features, and
        forward return labels. Forward return columns are LABELS ONLY — never
        use as predictor features.
    """
    logger.info("Stock DNA panel build — loading data sources...")
    ohlcv       = load_ohlcv(data_dir)
    regime_log  = load_regime_log(data_dir)

    logger.info("  OHLCV: %d rows, %d symbols", len(ohlcv), ohlcv["symbol"].nunique())

    panel = ohlcv.copy()

    logger.info("Computing indicators (EMA20, EMA50, SMA50, SMA100, SMA150, ATR14, ADV) [v2 candidate lines]...")
    panel = compute_indicators(panel)

    logger.info("Assigning stock phase labels...")
    panel = assign_stock_phase(panel)

    logger.info("Adding regime features...")
    panel = add_regime_features(panel, regime_log)

    logger.info("Applying VIN/VPL handling...")
    panel = apply_vin_vpl_handling(panel)

    logger.info("Adding forward return labels...")
    panel = add_forward_returns(panel)

    # Drop warmup period
    panel = panel[panel["date"] >= pd.Timestamp(start_date)].copy()

    if end_date:
        panel = panel[panel["date"] <= pd.Timestamp(end_date)].copy()

    if apply_liquidity_filter:
        panel = filter_liquid_universe(panel, min_adv20_vnd=min_adv20_vnd)

    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    logger.info(
        "DNA panel ready: %d rows, %d cols, %d symbols, %s to %s",
        len(panel), len(panel.columns), panel["symbol"].nunique(),
        panel["date"].min().date(), panel["date"].max().date(),
    )

    return panel
