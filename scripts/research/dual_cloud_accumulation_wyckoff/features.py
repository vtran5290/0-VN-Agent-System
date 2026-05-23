"""Accumulation / Wyckoff feature library.

All functions take aligned pd.Series with reset integer index, sorted by date.
All computations are strictly causal — features at bar t use data through bar t.
(Entry at bar t+1 open; no lookahead.)

Feature groups:
  price_tightness  — volatility/range compression
  volume_tightness — supply drying up
  breakout_quality — demand returning (same-bar features at signal bar)
  wyckoff_tags     — spring, SOS, LPS, UTAD, effort_vs_result
  composite        — accumulation_score (weighted rank sum)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Internal helpers ──────────────────────────────────────────────────────────

def _atr_ewm(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    tr = pd.concat(
        [high - low,
         (high - close.shift(1)).abs(),
         (low  - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _linslope_norm(s: pd.Series, window: int) -> pd.Series:
    """Normalized linear slope of s over `window` bars. Negative = declining."""
    x = np.arange(window, dtype=float)
    x -= x.mean()
    ss_x = (x ** 2).sum()

    def _slope_fn(arr: np.ndarray) -> float:
        if np.isnan(arr).any() or ss_x == 0:
            return np.nan
        slope = (x * (arr - arr.mean())).sum() / ss_x
        mu = arr.mean()
        return float(slope / mu) if mu != 0 else np.nan

    return s.rolling(window, min_periods=window).apply(_slope_fn, raw=True)


# ── Price tightness ───────────────────────────────────────────────────────────

def price_tightness_20(close: pd.Series) -> pd.Series:
    """20-bar rolling close std / mean. Lower = price more compressed."""
    mu = close.rolling(20, min_periods=10).mean()
    sd = close.rolling(20, min_periods=10).std(ddof=1)
    return (sd / mu.replace(0, np.nan)).fillna(np.nan)


def price_tightness_40(close: pd.Series) -> pd.Series:
    mu = close.rolling(40, min_periods=20).mean()
    sd = close.rolling(40, min_periods=20).std(ddof=1)
    return (sd / mu.replace(0, np.nan)).fillna(np.nan)


def atr_ratio_14_50(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """ATR14 / ATR50. < 1 signals contracting volatility (compression phase)."""
    atr14 = _atr_ewm(high, low, close, 14)
    atr50 = _atr_ewm(high, low, close, 50)
    return (atr14 / atr50.replace(0, np.nan)).fillna(np.nan)


def bar_range_pct(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """(high − low) / close. Lower = narrower daily bars."""
    return ((high - low) / close.replace(0, np.nan)).fillna(np.nan)


def range_vs_ma20(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """bar_range_pct divided by its 20-bar mean. < 1 = range compressing."""
    brp = bar_range_pct(high, low, close)
    ma20 = brp.rolling(20, min_periods=10).mean()
    return (brp / ma20.replace(0, np.nan)).fillna(np.nan)


# ── Volume tightness ──────────────────────────────────────────────────────────

def vol_ratio_20(volume: pd.Series) -> pd.Series:
    """volume / vol_ma(20). < 1 = below-average volume."""
    vol_ma = volume.rolling(20, min_periods=10).mean()
    return (volume / vol_ma.replace(0, np.nan)).fillna(np.nan)


def vol_trend_10(volume: pd.Series) -> pd.Series:
    """Normalized linear slope of volume, 10 bars. Negative = volume declining."""
    return _linslope_norm(volume, 10)


def vol_below_avg_streak(volume: pd.Series) -> pd.Series:
    """Consecutive bars of below-average (< vol_ma20) volume. Capped at 20."""
    vol_ma = volume.rolling(20, min_periods=10).mean()
    below = (volume < vol_ma).astype(float)
    result = np.zeros(len(volume), dtype=float)
    streak = 0.0
    for i in range(len(volume)):
        if below.iloc[i] == 1.0:
            streak = min(streak + 1, 20.0)
        else:
            streak = 0.0
        result[i] = streak
    return pd.Series(result, index=volume.index)


def vol_drying_score(volume: pd.Series) -> pd.Series:
    """Fraction of last 10 bars with volume < 0.8 × vol_ma20. Range [0, 1]."""
    vol_ma = volume.rolling(20, min_periods=10).mean()
    very_low = (volume < vol_ma * 0.8).astype(float)
    return very_low.rolling(10, min_periods=5).mean()


# ── Breakout quality (same-bar features at signal bar) ───────────────────────

def bo_vol_expansion(volume: pd.Series) -> pd.Series:
    """volume / vol_ma20 on this bar. > 1.5 = clear volume expansion."""
    return vol_ratio_20(volume)


def bo_close_strength(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """(close − low) / (high − low). 1.0 = closed at high; 0.0 = at low."""
    rng = (high - low).replace(0, np.nan)
    return ((close - low) / rng).fillna(0.5)


def bo_range_expansion(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """(high − low) / ATR14. > 1 = wider bar than average."""
    atr14 = _atr_ewm(high, low, close, 14)
    return ((high - low) / atr14.replace(0, np.nan)).fillna(np.nan)


# ── Mechanical Wyckoff tags ───────────────────────────────────────────────────

def spring_tag(
    close: pd.Series,
    low: pd.Series,
    support_lookback: int = 20,
    reclaim_bars: int = 3,
) -> pd.Series:
    """
    Spring: price violated rolling 20-bar support (min of lows), then reclaimed.

    Two detection modes:
    1. Same-bar spring: low < support AND close >= support on the same bar
       (shakeout and intrabar recovery).
    2. Multi-bar spring: close was below support in previous reclaim_bars bars
       and close has now returned above support.

    Causal: support level uses data shifted by 1 (previous bar's 20-bar min).
    """
    support = low.rolling(support_lookback, min_periods=support_lookback // 2).min().shift(1)
    below = close < support
    low_below = low < support

    # Same-bar: intraday dip below support with close recovery
    same_bar = low_below & (close >= support)

    # Multi-bar: was below support recently, now reclaimed
    went_below_recently = below.rolling(reclaim_bars, min_periods=1).max().shift(1).fillna(False)
    reclaimed = (~below) & (close >= support)
    multi_bar = went_below_recently.astype(bool) & reclaimed

    return (same_bar | multi_bar).fillna(False)


def sos_tag(
    close: pd.Series,
    high: pd.Series,
    volume: pd.Series,
    resistance_lookback: int = 20,
    vol_expansion_x: float = 1.5,
) -> pd.Series:
    """
    Sign of Strength: close breaks above 20-bar resistance on high volume
    (≥ 1.5 × vol_ma20).

    Causal: resistance uses shift(1) of rolling max.
    """
    resistance = high.rolling(resistance_lookback, min_periods=resistance_lookback // 2).max().shift(1)
    vol_ma = volume.rolling(20, min_periods=10).mean()
    return (
        (close > resistance)
        & (volume >= vol_ma * vol_expansion_x)
    ).fillna(False)


def lps_tag(
    close: pd.Series,
    high: pd.Series,
    volume: pd.Series,
    resistance_lookback: int = 20,
    near_pct: float = 0.03,
    vol_contraction_x: float = 0.7,
    sos_lookback: int = 30,
) -> pd.Series:
    """
    Last Point of Support: pullback to within near_pct of the ORIGINAL SOS
    breakout level on low volume (< 0.7 × vol_ma20).

    Uses the resistance level at the time the SOS fired (not the current
    rolling high, which drifts higher as price rallies away from the SOS level).
    """
    resistance = high.rolling(resistance_lookback, min_periods=resistance_lookback // 2).max().shift(1)
    sos = sos_tag(close, high, volume, resistance_lookback)

    # Carry forward the SOS breakout level (resistance value at the SOS bar)
    # for up to sos_lookback bars. This anchors LPS to the original breakout price.
    sos_level = resistance.where(sos).ffill(limit=sos_lookback)

    vol_ma = volume.rolling(20, min_periods=10).mean()
    had_sos = (
        sos
        .rolling(sos_lookback, min_periods=1).max()
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    near_level = (
        sos_level.notna()
        & (close >= sos_level * (1.0 - near_pct))
        & (close <= sos_level * (1.0 + near_pct * 0.5))
    )
    low_vol = volume < vol_ma * vol_contraction_x

    return (had_sos & near_level & low_vol).fillna(False)


def utad_tag(
    close: pd.Series,
    high: pd.Series,
    resistance_lookback: int = 20,
    fail_bars: int = 5,
) -> pd.Series:
    """
    Upthrust After Distribution: close broke above resistance in the last
    fail_bars bars, but is now back below it.

    Signal fires at the failure/return bar — caution signal.
    """
    resistance = high.rolling(resistance_lookback, min_periods=resistance_lookback // 2).max().shift(1)
    above = (close > resistance).fillna(False)
    was_above_recently = above.rolling(fail_bars, min_periods=1).max().shift(1).fillna(False)
    return (was_above_recently.astype(bool) & (~above)).fillna(False)


def effort_vs_result(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    open_: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """
    Effort vs Result score.

    Low score (high volume, small net move) = potential distribution.
    Score = move_efficiency / vol_ratio, where:
        move_efficiency = |close − open| / (high − low)   [0, 1]
        vol_ratio       = volume / vol_ma20

    Low score + high volume = supply absorbing demand without price progress.
    """
    bar_rng = (high - low).replace(0, np.nan)
    net_move = (close - open_).abs()
    move_efficiency = (net_move / bar_rng).clip(0, 1).fillna(0.5)

    vr = vol_ratio_20(volume).replace(0, np.nan)
    return (move_efficiency / vr).fillna(np.nan)


# ── Composite accumulation score ──────────────────────────────────────────────

# Score weights (shared by both score functions below)
_SCORE_COLS_DIRS = [
    ("pt_20",        False),   # lower pt_20  = tighter price  → better
    ("atr_ratio",    False),   # lower ratio  = contracting ATR → better
    ("vol_ratio",    False),   # lower vol    = drying supply   → better
    ("vol_drying",   True),    # higher       = more drying     → better
    ("bo_vol_exp",   True),    # higher       = vol expansion   → better
    ("bo_close_str", True),    # higher       = strong close    → better
]
_SCORE_WEIGHTS = [0.20, 0.20, 0.20, 0.15, 0.15, 0.10]


def tradable_asof_score(rows: pd.DataFrame) -> pd.Series:
    """
    Date-group stable, no-future-contamination accumulation score.

    For each unique signal_date D:
      - History = all rows where signal_date < D  (strictly prior dates only)
      - Every row on date D is scored against that fixed historical distribution
      - Same-date rows do NOT affect each other's scores
      - Row order within a date group has NO effect on any row's score

    Warmup (first observed date, no prior history): score = 0.5 (neutral).
    Adding future signal rows never changes scores for past dates.

    Use in selection stages (2, 3, 4). For research, use diagnostic_global_score().
    """
    if rows.empty:
        return pd.Series(dtype=float, index=rows.index)
    if "signal_date" not in rows.columns:
        return accumulation_score_cross_sectional(rows)

    dates_arr = pd.to_datetime(rows["signal_date"]).values
    unique_dates = np.unique(dates_arr)  # chronological

    # Pre-extract column arrays once to avoid repeated DataFrame access
    col_arrays: dict[str, np.ndarray] = {}
    for col, _ in _SCORE_COLS_DIRS:
        if col in rows.columns:
            col_arrays[col] = rows[col].astype(float).values

    result_arr = np.full(len(rows), 0.5)  # warmup default

    for d in unique_dates:
        date_mask = dates_arr == d
        hist_mask = dates_arr < d

        if not hist_mask.any():
            continue  # first date — no prior history — keep 0.5 (warmup)

        n_today = int(date_mask.sum())
        score_arr = np.zeros(n_today)

        for (col, ascending), w in zip(_SCORE_COLS_DIRS, _SCORE_WEIGHTS):
            if col not in col_arrays:
                score_arr += 0.5 * w
                continue

            all_vals = col_arrays[col]
            hist_vals  = all_vals[hist_mask]
            today_vals = all_vals[date_mask]

            hist_valid = hist_vals[~np.isnan(hist_vals)]
            if len(hist_valid) == 0:
                score_arr += 0.5 * w
                continue

            hist_sorted = np.sort(hist_valid)
            n_hist = len(hist_sorted)

            pct_arr = np.full(n_today, 0.5)
            nan_mask = np.isnan(today_vals)
            valid_today = today_vals[~nan_mask]

            if len(valid_today):
                if ascending:
                    # Higher feature value → better score
                    pct_arr[~nan_mask] = (
                        np.searchsorted(hist_sorted, valid_today, side="right") / n_hist
                    )
                else:
                    # Lower feature value → better score
                    pct_arr[~nan_mask] = (
                        (n_hist - np.searchsorted(hist_sorted, valid_today, side="left"))
                        / n_hist
                    )

            score_arr += pct_arr * w

        result_arr[date_mask] = score_arr

    return pd.Series(result_arr, index=rows.index)


def compute_candidate_score_dategroup(
    rows: pd.DataFrame,
    spec: list[tuple[str, bool, float]],
) -> pd.Series:
    """
    Date-group stable percentile scoring with an arbitrary feature spec.

    Same guarantee as tradable_asof_score:
      - For each unique signal_date D, rows on D are scored against the
        historical distribution of all rows where signal_date < D.
      - Warmup (first date — no prior history): score = 0.5 (neutral).
      - Missing columns: contribute 0.5 * weight (neutral, graceful skip).
      - NaN feature values: contribute 0.5 * weight for that row.

    Parameters
    ----------
    rows : pd.DataFrame
        Signal rows with a `signal_date` column and feature columns.
    spec : list of (col_name, ascending, weight) tuples
        ascending=True  → higher value = better percentile rank
        ascending=False → lower value = better percentile rank
        Weights need not sum to 1; they are applied as-is.

    Returns
    -------
    pd.Series aligned to rows.index, values in [0, 1].
    """
    if rows.empty:
        return pd.Series(dtype=float, index=rows.index)
    if "signal_date" not in rows.columns:
        # Fallback: cross-sectional ranking across all rows
        score = pd.Series(0.0, index=rows.index)
        for col, ascending, w in spec:
            if col not in rows.columns:
                score += 0.5 * w
                continue
            r = rows[col].rank(pct=True, ascending=ascending, na_option="keep")
            score += r.fillna(0.5) * w
        return score

    dates_arr = pd.to_datetime(rows["signal_date"]).values
    unique_dates = np.unique(dates_arr)

    col_arrays: dict[str, np.ndarray] = {}
    for col, _asc, _w in spec:
        if col in rows.columns:
            col_arrays[col] = rows[col].astype(float).values

    result_arr = np.full(len(rows), 0.5)

    for d in unique_dates:
        date_mask = dates_arr == d
        hist_mask = dates_arr < d

        if not hist_mask.any():
            continue  # warmup — keep 0.5

        n_today = int(date_mask.sum())
        score_arr = np.zeros(n_today)

        for col, ascending, w in spec:
            if col not in col_arrays:
                score_arr += 0.5 * w
                continue

            all_vals   = col_arrays[col]
            hist_vals  = all_vals[hist_mask]
            today_vals = all_vals[date_mask]

            hist_valid = hist_vals[~np.isnan(hist_vals)]
            if len(hist_valid) == 0:
                score_arr += 0.5 * w
                continue

            hist_sorted = np.sort(hist_valid)
            n_hist = len(hist_sorted)

            pct_arr = np.full(n_today, 0.5)
            nan_mask = np.isnan(today_vals)
            valid_today = today_vals[~nan_mask]

            if len(valid_today):
                if ascending:
                    pct_arr[~nan_mask] = (
                        np.searchsorted(hist_sorted, valid_today, side="right") / n_hist
                    )
                else:
                    pct_arr[~nan_mask] = (
                        (n_hist - np.searchsorted(hist_sorted, valid_today, side="left"))
                        / n_hist
                    )

            score_arr += pct_arr * w

        result_arr[date_mask] = score_arr

    return pd.Series(result_arr, index=rows.index)


def tradable_asof_warmup_mask(rows: pd.DataFrame) -> pd.Series:
    """
    Returns a boolean Series: True for rows that received the warmup neutral score
    (signal_date is the first observed date — no prior signal history existed).

    Store as `score_warmup_flag` in stage outputs to flag unreliable scores.
    """
    if rows.empty or "signal_date" not in rows.columns:
        return pd.Series(False, index=rows.index)
    dates_arr = pd.to_datetime(rows["signal_date"]).values
    if len(dates_arr) == 0:
        return pd.Series(False, index=rows.index)
    first_date = np.min(dates_arr)
    return pd.Series(dates_arr == first_date, index=rows.index)


def diagnostic_global_score(rows: pd.DataFrame) -> pd.Series:
    """Cross-sectional score across ALL rows — alias for accumulation_score_cross_sectional.

    Ranks every row against every other row regardless of date. Appropriate for
    Stage 1 feature validation (full cross-section maximises statistical power).
    NOT appropriate for selection stages — use tradable_asof_score() instead.
    """
    return accumulation_score_cross_sectional(rows)


def accumulation_score_cross_sectional(rows: pd.DataFrame) -> pd.Series:
    """
    Cross-sectional accumulation score for a DataFrame of signal-bar trade rows.

    Each row represents one A3/S3 signal event; feature columns (pt_20,
    atr_ratio, …) were extracted AT bar t (causal — no lookahead).

    Ranking is cross-sectional across ALL rows in `rows` (all symbols, all
    dates). This is the correct framing for selection/ranking research: "how
    does this signal's tightness compare to every other signal in the study?"

    Call this AFTER concatenating trades from all symbols in run().

    Returns a Series aligned to rows.index with values in [0, 1].
    Higher = more accumulation evidence.
    """
    score = pd.Series(0.0, index=rows.index)
    for (col, ascending), w in zip(_SCORE_COLS_DIRS, _SCORE_WEIGHTS):
        if col not in rows.columns:
            continue
        r = rows[col].rank(pct=True, ascending=ascending, na_option="keep")
        score = score + r.fillna(0.5) * w
    return score


def accumulation_score(df_features: pd.DataFrame) -> pd.Series:
    """
    Per-bar accumulation score on a single symbol's full time series.

    NOTE: this function ranks each bar relative to ALL bars in the series,
    including future bars. It is useful for internal feature development /
    plotting but introduces a mild time-series look-ahead. For research
    output, use accumulation_score_cross_sectional() instead.

    Tightness features inverted (lower = better). Breakout/drying direct.
    """
    def _rank_pct(s: pd.Series, ascending: bool) -> pd.Series:
        return s.rank(pct=True, ascending=ascending, na_option="keep")

    score = pd.Series(0.0, index=df_features.index)
    for (col, ascending), w in zip(_SCORE_COLS_DIRS, _SCORE_WEIGHTS):
        if col not in df_features.columns:
            continue
        r = _rank_pct(df_features[col], ascending=ascending)
        score = score + r.fillna(0.5) * w
    return score


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all accumulation/Wyckoff features for one symbol's OHLCV frame.

    Expected input columns: open, high, low, close, volume, date
    close/open/high/low in kVND (units do not affect ratios).
    volume in shares.

    Returns df with all feature columns appended (in-place copy).
    All features at bar t are computed from data through bar t — strictly causal.
    """
    df = df.copy()
    c, h, l, o, v = df["close"], df["high"], df["low"], df["open"], df["volume"]

    # Price tightness
    df["pt_20"]         = price_tightness_20(c)
    df["pt_40"]         = price_tightness_40(c)
    df["atr_ratio"]     = atr_ratio_14_50(h, l, c)
    df["bar_range_pct"] = bar_range_pct(h, l, c)
    df["range_vs_ma20"] = range_vs_ma20(h, l, c)

    # Volume tightness
    df["vol_ratio"]       = vol_ratio_20(v)
    df["vol_trend_10"]    = vol_trend_10(v)
    df["vol_below_streak"]= vol_below_avg_streak(v)
    df["vol_drying"]      = vol_drying_score(v)

    # Breakout quality (same-bar features)
    df["bo_vol_exp"]   = bo_vol_expansion(v)
    df["bo_close_str"] = bo_close_strength(h, l, c)
    df["bo_range_exp"] = bo_range_expansion(h, l, c)

    # Mechanical Wyckoff tags
    df["spring"] = spring_tag(c, l).astype(int)
    df["sos"]    = sos_tag(c, h, v).astype(int)
    df["lps"]    = lps_tag(c, h, v).astype(int)
    df["utad"]   = utad_tag(c, h).astype(int)
    df["efvr"]   = effort_vs_result(h, l, c, o, v)

    # ATR14 for downstream stop/trail use
    df["atr14"] = _atr_ewm(h, l, c, 14)

    return df
