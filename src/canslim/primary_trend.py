from __future__ import annotations

"""
Primary trend engine (Tier 1) for VN CANSLIM.

This module implements a coarse, slow-moving primary regime:
    - UP
    - DOWN
    - NEUTRAL

It is deliberately separate from the tactical FTD-based engine.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


MA_SHORT = 50
MA_LONG = 200
MA_SLOPE_WINDOW = 20
BREADTH_THRESHOLD = 0.45


@dataclass(frozen=True)
class PrimaryTrendConfig:
    ma_short: int = MA_SHORT
    ma_long: int = MA_LONG
    ma_slope_window: int = MA_SLOPE_WINDOW
    breadth_threshold: float = BREADTH_THRESHOLD


def _compute_ma(series: pd.Series, window: int) -> pd.Series:
    """Rolling simple moving average with min_periods=1."""
    return series.rolling(window, min_periods=1).mean()


def _compute_breadth_series(
    constituent_prices: Dict[str, pd.DataFrame],
    dates: pd.Series,
    ma_window: int,
) -> pd.Series:
    """
    Compute daily breadth: % of constituents with close > MA(ma_window).

    Only counts symbols that have a valid MA value on that date.
    If no symbols have valid MA on a date, breadth_pct is NaN.
    """
    if not constituent_prices:
        return pd.Series(np.nan, index=dates)

    # Precompute per-symbol MA50, aligned by date
    ma_dict: Dict[str, pd.DataFrame] = {}
    for sym, df in constituent_prices.items():
        if "date" not in df.columns or "close" not in df.columns:
            continue
        s = df.copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.sort_values("date").reset_index(drop=True)
        s["ma"] = _compute_ma(s["close"], ma_window)
        ma_dict[sym] = s[["date", "close", "ma"]]

    # Align to the union of index dates; we will fill breadth only on requested dates
    date_index = pd.to_datetime(dates).sort_values().reset_index(drop=True)
    breadth_values = []

    for d in date_index:
        n_valid = 0
        n_above = 0
        for s in ma_dict.values():
            row = s.loc[s["date"] == d]
            if row.empty:
                continue
            ma_val = row["ma"].iloc[0]
            close_val = row["close"].iloc[0]
            if pd.isna(ma_val):
                continue
            n_valid += 1
            if close_val > ma_val:
                n_above += 1
        if n_valid == 0:
            breadth_values.append(np.nan)
        else:
            breadth_values.append(n_above / n_valid)

    breadth_series = pd.Series(breadth_values, index=date_index)
    # Reindex back to supplied dates
    breadth_series = breadth_series.reindex(date_index).reset_index(drop=True)
    breadth_series.index = dates.index
    return breadth_series


def compute_primary_trend(
    index_df: pd.DataFrame,
    constituent_prices: Dict[str, pd.DataFrame],
    breadth_threshold: float = BREADTH_THRESHOLD,
    cfg: Optional[PrimaryTrendConfig] = None,
) -> pd.DataFrame:
    """
    Compute primary trend time series for a VN index.

    Parameters
    ----------
    index_df : pd.DataFrame
        DataFrame with at least columns ['date', 'close', 'volume'] for the index.
    constituent_prices : dict[str, pd.DataFrame]
        Mapping symbol -> DataFrame with at least ['date', 'close'] for each constituent.
        Used to compute breadth (% of stocks above their own MA50).
    breadth_threshold : float, default 0.45
        Minimum fraction of constituents above their MA50 required for Primary = "UP".
    cfg : PrimaryTrendConfig, optional
        Optional configuration object. If None, uses default constants.

    Returns
    -------
    pd.DataFrame
        Columns:
            - date
            - primary_state       ("UP", "DOWN", "NEUTRAL")
            - close
            - ma50
            - ma200
            - ma200_slope         (ma200[t] - ma200[t-20]) / ma200[t-20]
            - ma50_above_ma200    (bool)
            - breadth_pct         (float, 0.0-1.0, may be NaN)
            - breadth_pass        (bool, breadth_pct >= breadth_threshold)
    """
    if cfg is None:
        cfg = PrimaryTrendConfig(breadth_threshold=breadth_threshold)
    else:
        # Ensure we respect the explicit breadth_threshold argument if provided
        if breadth_threshold is not None:
            cfg = PrimaryTrendConfig(
                ma_short=cfg.ma_short,
                ma_long=cfg.ma_long,
                ma_slope_window=cfg.ma_slope_window,
                breadth_threshold=breadth_threshold,
            )

    df = index_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["ma50"] = _compute_ma(df["close"], cfg.ma_short)
    df["ma200"] = _compute_ma(df["close"], cfg.ma_long)

    ma200_prev = df["ma200"].shift(cfg.ma_slope_window)
    with np.errstate(divide="ignore", invalid="ignore"):
        ma200_slope = (df["ma200"] - ma200_prev) / ma200_prev
    # Guard divide-by-zero / NaN
    ma200_slope = ma200_slope.where(ma200_prev > 0)
    df["ma200_slope"] = ma200_slope

    df["ma50_above_ma200"] = (df["ma50"] > df["ma200"]) & df["ma50"].notna() & df["ma200"].notna()

    breadth_series = _compute_breadth_series(
        constituent_prices=constituent_prices,
        dates=df["date"],
        ma_window=cfg.ma_short,
    )
    df["breadth_pct"] = breadth_series
    df["breadth_pass"] = df["breadth_pct"] >= cfg.breadth_threshold

    # Primary regime rules
    cond_price_up = df["close"] > df["ma200"]
    # Deterministic slope check: ma200[t] >= ma200[t - window]
    cond_slope_up = df["ma200"] >= df["ma200"].shift(cfg.ma_slope_window)
    cond_slope_up = cond_slope_up.fillna(False)
    cond_ma_order_up = df["ma50_above_ma200"]
    cond_breadth_up = df["breadth_pass"].fillna(False)

    primary_state = np.full(len(df), "NEUTRAL", dtype=object)

    up_mask = cond_price_up & cond_slope_up & cond_ma_order_up & cond_breadth_up
    down_mask = (df["close"] < df["ma200"]) & (df["ma50"] < df["ma200"])

    primary_state[up_mask] = "UP"
    primary_state[down_mask] = "DOWN"

    out = pd.DataFrame(
        {
            "date": df["date"],
            "primary_state": primary_state,
            "close": df["close"],
            "ma50": df["ma50"],
            "ma200": df["ma200"],
            "ma200_slope": df["ma200_slope"],
            "ma50_above_ma200": df["ma50_above_ma200"],
            "breadth_pct": df["breadth_pct"],
            "breadth_pass": df["breadth_pass"],
        }
    )

    return out


def get_primary_state(primary_df: pd.DataFrame, date: pd.Timestamp | str) -> str:
    """
    Lookup primary_state for a given date, with fallback to nearest prior date.

    Parameters
    ----------
    primary_df : pd.DataFrame
        Output of compute_primary_trend (must contain 'date' and 'primary_state').
    date : str or pd.Timestamp
        Target date (YYYY-MM-DD or Timestamp).

    Returns
    -------
    str
        One of "UP", "DOWN", "NEUTRAL".
        Returns "NEUTRAL" if no prior data is available.
    """
    if primary_df.empty:
        return "NEUTRAL"

    target = pd.to_datetime(date)
    df = primary_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    exact = df[df["date"] == target]
    if not exact.empty:
        return str(exact["primary_state"].iloc[-1])

    prior = df[df["date"] < target]
    if prior.empty:
        return "NEUTRAL"

    row = prior.iloc[-1]
    return str(row["primary_state"])


# Integration note:
# In adapter.py, detect_market_status() will be updated to:
#   1. Call get_primary_state() first
#   2. If primary = "DOWN" -> return "downtrend" immediately (skip FTD check)
#   3. If primary = "NEUTRAL" -> return "correction" (allow FTD to run but no new buys)
#   4. If primary = "UP" -> run existing FTD tactical engine
#   Final market_status = combined output


def _make_synthetic_index(
    n_days: int,
    start: float,
    end: float,
    start_date: str = "2020-01-01",
) -> pd.DataFrame:
    dates = pd.date_range(start=start_date, periods=n_days, freq="D")
    closes = np.linspace(start, end, n_days)
    volumes = np.full(n_days, 1_000_000.0)
    return pd.DataFrame({"date": dates, "close": closes, "volume": volumes})


def _make_constituents_from_index(
    index_df: pd.DataFrame,
    symbols: Iterable[str],
    noise_scale: float = 0.0,
    scale: float = 1.0,
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(symbols):
        df = index_df.copy()
        noise = np.random.normal(loc=0.0, scale=noise_scale, size=len(df))
        df["close"] = df["close"] * scale + noise + i * 0.01
        out[sym] = df[["date", "close"]].copy()
    return out


def _run_tests() -> None:
    print("Running primary_trend tests...")

    # Test 1: primary = DOWN when close < MA200 and MA50 < MA200
    idx_down = _make_synthetic_index(120, start=100, end=80)
    const_down = _make_constituents_from_index(idx_down, ["AAA"])
    pt_down = compute_primary_trend(idx_down, const_down)
    last = pt_down.iloc[-1]
    cond1 = last["primary_state"] == "DOWN"
    print("Test 1 (DOWN conditions) :", "PASS" if cond1 else "FAIL", f"-> {last['primary_state']}")

    # Test 2: primary = UP when all 4 conditions met
    idx_up = _make_synthetic_index(250, start=80, end=120)
    # Many constituents strongly trending up -> breadth ~1.0
    const_up = _make_constituents_from_index(idx_up, [f"S{i}" for i in range(10)])
    pt_up = compute_primary_trend(idx_up, const_up)
    last_up = pt_up.iloc[-1]
    cond2 = last_up["primary_state"] == "UP"
    print("Test 2 (UP conditions)   :", "PASS" if cond2 else "FAIL", f"-> {last_up['primary_state']}")

    # Test 3: primary = NEUTRAL when close > MA200 but breadth < 0.45
    idx_neu = _make_synthetic_index(250, start=80, end=120)
    # 2 symbols strong up, 8 flat -> breadth ~0.2
    strong = _make_constituents_from_index(idx_neu, ["L1", "L2"])
    flat_idx = _make_synthetic_index(250, start=90, end=90)
    flat = _make_constituents_from_index(flat_idx, [f"F{i}" for i in range(8)])
    const_neu = {**strong, **flat}
    pt_neu = compute_primary_trend(idx_neu, const_neu)
    last_neu = pt_neu.iloc[-1]
    cond3 = last_neu["primary_state"] == "NEUTRAL"
    print("Test 3 (NEUTRAL breadth) :", "PASS" if cond3 else "FAIL", f"-> {last_neu['primary_state']}")

    # Build simple primary_df for get_primary_state tests
    dates = pd.to_datetime(["2020-01-01", "2020-01-05", "2020-01-10"])
    states = ["DOWN", "UP", "NEUTRAL"]
    primary_df = pd.DataFrame({"date": dates, "primary_state": states})

    # Test 4: get_primary_state returns correct state for known date
    s4 = get_primary_state(primary_df, "2020-01-05")
    cond4 = s4 == "UP"
    print("Test 4 (exact date)      :", "PASS" if cond4 else "FAIL", f"-> {s4}")

    # Test 5: get_primary_state falls back to nearest prior date
    s5a = get_primary_state(primary_df, "2020-01-07")  # between 5 and 10 -> use 5 (UP)
    s5b = get_primary_state(primary_df, "2020-01-20")  # after last -> use 10 (NEUTRAL)
    cond5 = (s5a == "UP") and (s5b == "NEUTRAL")
    print("Test 5 (fallback)        :", "PASS" if cond5 else "FAIL", f"-> {s5a}, {s5b}")


if __name__ == "__main__":
    _run_tests()

