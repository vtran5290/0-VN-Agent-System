# minervini_backtest/src/wyckoff.py — Wyckoff state machine (SC → AR → ST → Spring → JAC → LPS)
# VN: entry on LPS (Test of Spring), not on JAC or Spring bar.
from __future__ import annotations
import numpy as np
import pandas as pd


def _long_lower_wick(row: pd.Series, min_wick_ratio: float = 0.4) -> bool:
    """Close in upper 60% of range (long lower wick)."""
    rng = row["high"] - row["low"]
    if rng <= 0:
        return False
    return (row["close"] - row["low"]) >= min_wick_ratio * rng


def add_wyckoff_state(
    df: pd.DataFrame,
    sc_vol_mult: float = 3.0,
    sc_spread_atr_mult: float = 2.0,
    ar_rally_pct: float = 0.05,
    ar_max_bars: int = 20,
    st_vol_max_ratio: float = 1.0,
    spring_vol_max_ratio: float = 0.7,
    recovery_bars: int = 5,
    min_tr_bars: int = 15,
    max_tr_range_pct: float = 0.25,
    jac_vol_mult: float = 1.2,
    jac_spread_atr_mult: float = 1.5,
    lps_vol_max_ratio: float = 0.5,
    lps_near_ar_pct: float = 0.025,
    vol_lookback: int = 50,
    tight_close_window: int = 10,
    base_max_close_range_pct: float = 0.04,
    base_max_close_stdev_pct: float = 0.015,
    ultra_dry_vol_ratio: float = 0.5,
    ultra_dry_min_days: int = 1,
    jac_breakout_pct: float = 0.0,
    jac_close_pos_min: float = 0.7,
    sos_lookback: int = 10,
    sos_vol_mult: float = 1.2,
    sos_spread_atr_mult: float = 1.2,
    min_sos_bars: int = 1,
) -> pd.DataFrame:
    """
    Single forward pass: SC → AR (TR), then ST, Spring, JAC, LPS.
    Adds: wyckoff_tr_low, wyckoff_tr_high, wyckoff_phase, wyckoff_spring_ok,
          wyckoff_jac_done, wyckoff_lps_signal, wyckoff_setup_ok, wyckoff_trigger.
    """
    out = df.copy()
    n = len(out)
    if n < vol_lookback + ar_max_bars + recovery_bars:
        out["wyckoff_tr_low"] = np.nan
        out["wyckoff_tr_high"] = np.nan
        out["wyckoff_phase"] = 0
        out["wyckoff_spring_ok"] = False
        out["wyckoff_jac_done"] = False
        out["wyckoff_lps_signal"] = False
        out["wyckoff_setup_ok"] = False
        out["wyckoff_trigger"] = False
        return out

    vol = out["volume"].values
    high = out["high"].values
    low = out["low"].values
    close = out["close"].values
    atr_arr = out["atr"].values
    vol_sma20 = out["vol_sma20"].values
    spread = high - low

    vol_max_50 = np.full(n, np.nan)
    for i in range(vol_lookback, n):
        vol_max_50[i] = np.max(vol[i - vol_lookback : i + 1])

    tr_low_arr = np.full(n, np.nan)
    tr_high_arr = np.full(n, np.nan)
    phase_arr = np.zeros(n, dtype=int)
    st_done_arr = np.zeros(n, dtype=bool)  # True when we've seen ST in this TR (supply drying)
    tight_base_arr = np.zeros(n, dtype=bool)
    ultra_dry_days_arr = np.zeros(n, dtype=int)
    sos_ready_arr = np.zeros(n, dtype=bool)
    spring_ok_arr = np.zeros(n, dtype=bool)
    jac_done_arr = np.zeros(n, dtype=bool)
    jac_bar_arr = np.zeros(n, dtype=bool)  # True only on first JAC bar
    lps_signal_arr = np.zeros(n, dtype=bool)

    last_sc_idx = None
    last_sc_low = np.nan
    last_sc_vol = np.nan
    last_ar_high = np.nan
    tr_start_idx = None
    saw_st = False
    spring_ok = False
    jac_bar_idx = None
    lps_emitted = False

    for i in range(vol_lookback, n):
        if atr_arr[i] <= 0 or vol_sma20[i] <= 0:
            continue

        is_sc = (
            vol[i] >= vol_max_50[i]
            and spread[i] >= sc_spread_atr_mult * atr_arr[i]
            and _long_lower_wick(out.iloc[i], 0.4)
        )

        if is_sc:
            last_sc_idx = i
            last_sc_low = low[i]
            last_sc_vol = vol[i]
            last_ar_high = np.nan
            tr_start_idx = None
            saw_st = False
            spring_ok = False
            jac_bar_idx = None
            lps_emitted = False
            continue

        if last_sc_idx is None:
            continue

        # Look for AR in [last_sc_idx+1, i]
        if np.isnan(last_ar_high):
            window_high = np.max(high[last_sc_idx + 1 : i + 1])
            if window_high >= last_sc_low * (1 + ar_rally_pct):
                last_ar_high = window_high
                tr_start_idx = last_sc_idx

        if not np.isfinite(last_ar_high) or tr_start_idx is None:
            continue

        tr_range_pct = (last_ar_high - last_sc_low) / last_sc_low
        if tr_range_pct > max_tr_range_pct:
            continue

        tr_low_arr[i] = last_sc_low
        tr_high_arr[i] = last_ar_high
        tr_bars = i - tr_start_idx

        # Tight base = closes compress and stop moving much inside the TR.
        base_start = max(tr_start_idx, i - tight_close_window + 1)
        base_closes = close[base_start : i + 1]
        if len(base_closes) >= min(5, tight_close_window):
            base_mean = float(np.mean(base_closes))
            if base_mean > 0:
                close_range_pct = (float(np.max(base_closes)) - float(np.min(base_closes))) / base_mean
                close_stdev_pct = float(np.std(base_closes)) / base_mean
                tight_base_arr[i] = (
                    close_range_pct <= base_max_close_range_pct
                    and close_stdev_pct <= base_max_close_stdev_pct
                )

        base_vol = vol[base_start : i + 1]
        base_vol_sma = vol_sma20[base_start : i + 1]
        ultra_dry_mask = (base_vol_sma > 0) & (base_vol <= ultra_dry_vol_ratio * base_vol_sma)
        ultra_dry_days_arr[i] = int(np.sum(ultra_dry_mask))

        # SOS bars = wide spread up-bars on strong volume. We want at least one/few recent attacks.
        sos_start = max(tr_start_idx, i - sos_lookback + 1)
        sos_bars = 0
        for j in range(sos_start, i + 1):
            prev_close = close[j - 1] if j > 0 else close[j]
            is_up_bar = close[j] > prev_close
            if (
                is_up_bar
                and vol_sma20[j] > 0
                and vol[j] >= sos_vol_mult * vol_sma20[j]
                and spread[j] >= sos_spread_atr_mult * atr_arr[j]
            ):
                sos_bars += 1
        sos_ready_arr[i] = sos_bars >= min_sos_bars

        # ST (Secondary Test: return to SC zone on LOWER volume = supply drying)
        if low[i] <= last_sc_low * 1.02 and high[i] >= last_sc_low * 0.98 and vol[i] < last_sc_vol * st_vol_max_ratio:
            saw_st = True
        st_done_arr[i] = saw_st

        # Spring
        if not spring_ok and low[i] < last_sc_low and vol[i] < last_sc_vol * spring_vol_max_ratio:
            for r in range(1, min(recovery_bars + 1, n - i)):
                if close[i + r] > last_sc_low:
                    spring_ok = True
                    break
                if low[i + r] < last_sc_low and vol[i + r] >= last_sc_vol * spring_vol_max_ratio:
                    break
        if spring_ok:
            spring_ok_arr[i] = True

        # JAC (first bar that qualifies)
        close_pos = (close[i] - low[i]) / spread[i] if spread[i] > 0 else 0.0
        jac_this_bar = (
            close[i] > last_ar_high * (1 + jac_breakout_pct)
            and vol[i] >= jac_vol_mult * vol_sma20[i]
            and spread[i] >= jac_spread_atr_mult * atr_arr[i]
            and close_pos >= jac_close_pos_min
        )
        if jac_this_bar and jac_bar_idx is None:
            jac_bar_idx = i
            jac_bar_arr[i] = True
        if jac_bar_idx is not None:
            jac_done_arr[i] = True
            phase_arr[i] = 4
        else:
            phase_arr[i] = 2 if saw_st else 1

        # LPS
        if jac_bar_idx is not None and not lps_emitted:
            ar_zone_lo = last_ar_high * (1 - lps_near_ar_pct)
            ar_zone_hi = last_ar_high * (1 + lps_near_ar_pct)
            in_zone = (low[i] <= ar_zone_hi and high[i] >= ar_zone_lo)
            if in_zone and vol[i] <= lps_vol_max_ratio * vol_sma20[i]:
                lps_signal_arr[i] = True
                lps_emitted = True

    out["wyckoff_tr_low"] = tr_low_arr
    out["wyckoff_tr_high"] = tr_high_arr
    out["wyckoff_phase"] = phase_arr
    out["wyckoff_st_done"] = st_done_arr
    out["wyckoff_base_tight"] = tight_base_arr
    out["wyckoff_ultra_dry_days"] = ultra_dry_days_arr
    out["wyckoff_sos_ready"] = sos_ready_arr
    out["wyckoff_spring_ok"] = spring_ok_arr
    out["wyckoff_jac_done"] = jac_done_arr
    out["wyckoff_jac_bar"] = jac_bar_arr
    out["wyckoff_lps_signal"] = lps_signal_arr

    tr_dur = np.zeros(n)
    for i in range(1, n):
        tr_dur[i] = (tr_dur[i - 1] + 1) if np.isfinite(tr_low_arr[i]) else 0
    out["wyckoff_setup_ok"] = (
        (phase_arr >= 2) & (tr_dur >= min_tr_bars) & np.isfinite(tr_low_arr)
    )
    # trigger: LPS only (VN default) or JAC or LPS
    out["wyckoff_trigger"] = out["wyckoff_lps_signal"].astype(bool)
    out["wyckoff_trigger_jac_or_lps"] = (out["wyckoff_lps_signal"] | out["wyckoff_jac_bar"]).astype(bool)
    return out
