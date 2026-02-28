from __future__ import annotations

from typing import Optional

import pandas as pd

from .regime_types import MarketStatus, RegimeConfig, RegimeState, defensive_state


def _init_state() -> RegimeState:
    return RegimeState()


def compute_regime(df: pd.DataFrame, cfg: Optional[RegimeConfig] = None) -> pd.DataFrame:
    """
    Compute daily O'Neil-style market regime for a VN index time series.

    df must be sorted ascending by date and contain at least:
      - 'date', 'open', 'high', 'low', 'close', 'volume'
    """
    if cfg is None:
        cfg = RegimeConfig()

    # Ensure date sorting
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Derived columns
    df["ma50"] = df["close"].rolling(50, min_periods=1).mean()
    df["prev_close"] = df["close"].shift(1)
    df["prev_low"] = df["low"].shift(1)
    df["prev_volume"] = df["volume"].shift(1)
    df["pct_change_close"] = df["close"] / df["prev_close"] - 1

    # Distribution day flag
    df["dd_flag_today"] = (
        (df["pct_change_close"] <= cfg.dd_drop_thresh)
        & (df["volume"] > df["prev_volume"])
    )
    # Rolling DD count
    df["distribution_count_20d"] = (
        df["dd_flag_today"].rolling(cfg.dd_window, min_periods=1).sum().astype(int)
    )

    state = _init_state()
    rolling_peak: Optional[float] = None

    out_rows = []

    # Track consecutive days below MA50 for structural downtrend
    below_ma50_streak = 0
    last_downtrend_low_idx: Optional[int] = None
    downtrend_low_price: Optional[float] = None

    for i, row in df.iterrows():
        date = row["date"].date().isoformat()
        close = float(row["close"])
        low = float(row["low"])
        volume = float(row["volume"])
        ma50 = float(row["ma50"])
        prev_close = float(row["prev_close"]) if pd.notna(row["prev_close"]) else None
        prev_low = float(row["prev_low"]) if pd.notna(row["prev_low"]) else None
        prev_volume = float(row["prev_volume"]) if pd.notna(row["prev_volume"]) else None
        pct_change = float(row["pct_change_close"]) if pd.notna(row["pct_change_close"]) else None
        dd_flag = bool(row["dd_flag_today"])
        dd_count = int(row["distribution_count_20d"])

        # Snapshot structural low anchor at start of day
        prev_downtrend_low_price = downtrend_low_price

        # Update structural below-MA50 streak
        if close < ma50:
            below_ma50_streak += 1
        else:
            below_ma50_streak = 0

        # Rally reset only if undercut PREVIOUS structural downtrend low
        ma50_break_flag = False
        ftd_flag_today = False

        if (
            state.rally_attempt_active
            and prev_downtrend_low_price is not None
            and low < prev_downtrend_low_price
        ):
            # Reset rally attempt and invalidate FTD from this attempt
            state.rally_attempt_active = False
            state.rally_day_count = 0
            state.rally_start_date = None
            state.day1_low = None
            if state.ftd_attempt_id == state.attempt_id:
                state.ftd_valid = False
            # In a structural undercut, we are in downtrend/correction
            state.market_status = MarketStatus.DOWNTREND

        # Structural downtrend low detection (after possible reset)
        downtrend_low_day = False
        if close < ma50:
            # min low over last n_low days (including today)
            start_idx = max(0, i - cfg.n_low + 1)
            window_lows = df.loc[start_idx:i, "low"]
            min_low = float(window_lows.min())
            if low == min_low:
                downtrend_low_day = True
                last_downtrend_low_idx = i
                downtrend_low_price = low

        # Day-1 detection (only when no active rally attempt)
        day1_triggered_today = False
        is_day1 = False
        if not state.rally_attempt_active:
            if (
                prev_low is not None
                and prev_close is not None
                and low >= prev_low
                and (close > prev_close if cfg.day1_requires_upday else close >= prev_close)
                and last_downtrend_low_idx is not None
                and i > last_downtrend_low_idx
            ):
                is_day1 = True

        if is_day1:
            state.rally_attempt_active = True
            state.rally_day_count = 1
            state.rally_start_date = date
            state.day1_low = low
            state.attempt_id += 1
            day1_triggered_today = True
        elif state.rally_attempt_active:
            # Within an active attempt, just count days; do not re-anchor
            state.rally_day_count += 1

        # MA50_BREAK event
        if (
            prev_close is not None
            and row.name > 0
            and close < ma50
            and prev_close >= df.at[i - 1, "ma50"]
        ):
            if not cfg.ma50_break_volume_confirm or (
                prev_volume is not None and volume > prev_volume
            ):
                ma50_break_flag = True
            else:
                ma50_break_flag = False
        else:
            ma50_break_flag = False

        # FTD detection (scope restricted + bounded in rally days)
        if state.market_status in {
            MarketStatus.DOWNTREND,
            MarketStatus.CORRECTION,
            MarketStatus.RALLY_ATTEMPT,
        }:
            if (
                state.rally_attempt_active
                and prev_close is not None
                and pct_change is not None
                and pct_change >= cfg.ftd_min_pct
                and prev_volume is not None
                and volume > prev_volume
                and state.rally_day_count >= cfg.ftd_day_min
                and state.rally_day_count <= cfg.ftd_max_day
            ):
                # Only one FTD per attempt
                if not state.ftd_detected or state.ftd_attempt_id != state.attempt_id:
                    ftd_flag_today = True
                    state.ftd_detected = True
                    state.ftd_date = date
                    state.ftd_low = low
                    state.ftd_close = close
                    state.ftd_valid = True
                    state.ftd_attempt_id = state.attempt_id
                    state.ftd_late = state.rally_day_count > cfg.ftd_day_max
                    # Once FTD is in place, end the rally attempt; uptrend takes over
                    state.rally_attempt_active = False
                    state.rally_day_count = 0
                    state.rally_start_date = None
                    state.day1_low = None

        # FTD invalidation (low breach or FTD close break)
        if state.ftd_valid and state.ftd_date and state.ftd_close is not None:
            ftd_idx = df.index[df["date"].dt.date == pd.to_datetime(state.ftd_date).date()]
            if len(ftd_idx) > 0:
                days_since_ftd = i - int(ftd_idx[0])
            else:
                days_since_ftd = 0

            # Low breach within N days
            if days_since_ftd > 0 and days_since_ftd <= cfg.ftd_invalidation_days:
                if state.ftd_low is not None and low < state.ftd_low:
                    state.ftd_valid = False
                    state.market_status = MarketStatus.CORRECTION
                    state.rally_attempt_active = False

            # FTD close break (drop below FTD close by configured %
            if state.ftd_valid and state.ftd_close is not None:
                if close <= state.ftd_close * (1.0 + cfg.ftd_close_break):
                    state.ftd_valid = False
                    state.market_status = MarketStatus.CORRECTION
                    state.rally_attempt_active = False

        # Apply precedence for regime transitions
        # 1) Rally reset already applied above (undercut Day-1 low)
        # 2) FTD invalidation handled above

        # 3) DD threshold & MA50_BREAK
        if ma50_break_flag or dd_count >= cfg.dd_correction_min:
            state.market_status = MarketStatus.CORRECTION
        else:
            # 4) DD 4–5 => under_pressure if currently in uptrend
            if dd_count >= cfg.dd_under_pressure_min and dd_count <= cfg.dd_under_pressure_max:
                if state.market_status in {
                    MarketStatus.CONFIRMED_UPTREND,
                    MarketStatus.UPTREND_UNDER_PRESSURE,
                }:
                    state.market_status = MarketStatus.UPTREND_UNDER_PRESSURE

        # 5) FTD detection => confirmed_uptrend
        if ftd_flag_today and state.ftd_valid:
            state.market_status = MarketStatus.CONFIRMED_UPTREND

        # 6) If rally attempt active but no FTD, ensure state at least rally_attempt
        if state.rally_attempt_active and state.market_status in {
            MarketStatus.DOWNTREND,
            MarketStatus.CORRECTION,
        }:
            state.market_status = MarketStatus.RALLY_ATTEMPT

        # 7) Invariant: a valid FTD implies an uptrend-type market_status
        if state.ftd_valid:
            if cfg.dd_under_pressure_min <= dd_count <= cfg.dd_under_pressure_max:
                state.market_status = MarketStatus.UPTREND_UNDER_PRESSURE
            elif state.market_status not in {
                MarketStatus.CONFIRMED_UPTREND,
                MarketStatus.UPTREND_UNDER_PRESSURE,
            }:
                state.market_status = MarketStatus.CONFIRMED_UPTREND

        # Close vs MA metrics
        close_vs_ma50_pct = (close / ma50 - 1.0) if ma50 != 0 else None
        if state.ftd_close is not None and state.ftd_valid:
            close_vs_ftd_close_pct = close / state.ftd_close - 1.0
        else:
            close_vs_ftd_close_pct = None

        state.close_vs_ma50_pct = close_vs_ma50_pct
        state.close_vs_ftd_close_pct = close_vs_ftd_close_pct
        state.dd_flag_today = dd_flag
        state.distribution_count_20d = dd_count
        state.ma50_break_flag = ma50_break_flag
        state.ftd_flag_today = ftd_flag_today

        allow_new_buys = state.market_status in {
            MarketStatus.CONFIRMED_UPTREND,
            MarketStatus.UPTREND_UNDER_PRESSURE,
        }

        out_rows.append(
            {
                "date": date,
                "market_status": state.market_status.value,
                "rally_attempt_active": state.rally_attempt_active,
                "rally_day_count": state.rally_day_count,
                "rally_start_date": state.rally_start_date,
                "attempt_id": state.attempt_id,
                "downtrend_low_day": downtrend_low_day,
                "day1_triggered_today": day1_triggered_today,
                "day1_low": state.day1_low,
                "ftd_detected": state.ftd_detected,
                "ftd_valid": state.ftd_valid,
                "ftd_date": state.ftd_date,
                "ftd_late": state.ftd_late,
                "ftd_low": state.ftd_low,
                "ftd_close": state.ftd_close,
                "distribution_count_20d": state.distribution_count_20d,
                "dd_flag_today": state.dd_flag_today,
                "ftd_flag_today": state.ftd_flag_today,
                "ma50_break_flag": state.ma50_break_flag,
                "ma50": ma50,
                "close": close,
                "close_vs_ma50_pct": state.close_vs_ma50_pct,
                "close_vs_ftd_close_pct": state.close_vs_ftd_close_pct,
                "allow_new_buys": allow_new_buys,
            }
        )

    return pd.DataFrame(out_rows)

