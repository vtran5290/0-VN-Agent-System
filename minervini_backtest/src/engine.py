# minervini_backtest/src/engine.py — Bar-by-bar event-driven engine, gates style (TT → Setup → Trigger → Risk → Exit)
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Any

from indicators import add_all_indicators, ensure_columns, atr
from filters import add_tt
from setups import vcp_proxy, three_week_tight, contraction_stack, volume_dry_up
from triggers import (
    breakout,
    breakout_tight,
    undercut_rally,
    pivot_level,
    pivot_tight_level,
    pivot_low_level,
    retest_ok,
    add_breakout,
)
from risk import stop_price, position_size_r
from exits import (
    exit_fail_fast,
    exit_hard_stop,
    exit_time_stop,
    exit_trend_break,
    exit_climax_proxy,
    exit_trailing_ma,
)
from metrics import trade_metrics, trades_per_year, minervini_r_metrics


def _get_cfg(cfg: dict, key: str, default: Any = None) -> Any:
    return cfg.get(key, default)


def prepare_bars(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add all indicators, TT, setup, trigger columns per config."""
    df = df.copy()
    df = ensure_columns(df)
    df = add_all_indicators(
        df,
        ma_windows=[20, 50, 150, 200],
        atr_n=14,
        atr_pct_windows=[5, 10, 20],
        vol_sma_windows=[5, 20],
    )
    tt_mode = _get_cfg(cfg, "tt", "lite").strip().lower()
    df = add_tt(df, mode=tt_mode, ma200_slope_bars=_get_cfg(cfg, "ma200_slope_bars", 20))
    # Setup (gate attribution: none=all True, vdu_only, cs_only, vcp, vcp_strong, 3wt)
    setup_type = _get_cfg(cfg, "setup", "vcp").strip().lower()
    if setup_type == "none" or setup_type == "skip":
        df["setup_ok"] = True
    elif setup_type == "vdu_only":
        df["setup_ok"] = volume_dry_up(df, vol5_max_ratio=_get_cfg(cfg, "vdu_strong"))
    elif setup_type == "cs_only":
        df["setup_ok"] = contraction_stack(df)
    elif setup_type == "vcp":
        df["setup_ok"] = vcp_proxy(df, vdu_strong=_get_cfg(cfg, "vdu_strong"))
    elif setup_type == "vcp_strong":
        df["setup_ok"] = vcp_proxy(df, vdu_strong=0.85)
    elif setup_type in ("3wt", "3_week_tight"):
        df["setup_ok"] = three_week_tight(
            df,
            window=_get_cfg(cfg, "3wt_window", 15),
            max_range_pct=_get_cfg(cfg, "3wt_max_range_pct", 0.06),
        )
    else:
        df["setup_ok"] = vcp_proxy(df)
    # Trigger (HH lookback vs M9 tight-range pivot); optional breakout_mode, vol_mode
    lb = int(_get_cfg(cfg, "lookback_base", 40))
    vol_mult = float(_get_cfg(cfg, "vol_mult", 1.5))
    trigger_type = _get_cfg(cfg, "trigger_type", "hh").strip().lower()
    trigger_kw = {
        "breakout_mode": _get_cfg(cfg, "breakout_mode", "close"),
        "vol_mode": _get_cfg(cfg, "vol_mode", "thrust"),
    }
    if trigger_type == "tight_range":
        tw = int(_get_cfg(cfg, "pivot_tight_window", 15))
        df["trigger_breakout"] = breakout_tight(df, tw, vol_mult=vol_mult, close_strength=_get_cfg(cfg, "close_strength", True), **trigger_kw)
    elif trigger_type in ("undercut_rally", "uandr"):
        uandr_lookback = int(_get_cfg(cfg, "undercut_rally_lookback", 10))
        undercut_pct = float(_get_cfg(cfg, "undercut_pct", 0.0))
        df["trigger_breakout"] = undercut_rally(
            df, lookback_low=uandr_lookback, undercut_pct=undercut_pct, close_strength=_get_cfg(cfg, "close_strength", True)
        )
    else:
        df["trigger_breakout"] = breakout(df, lb, vol_mult=vol_mult, close_strength=_get_cfg(cfg, "close_strength", True), **trigger_kw)
    return df


def run_single_symbol(
    df: pd.DataFrame,
    cfg: dict,
    symbol: str = "",
    initial_equity: float = 1.0,
    collect_funnel: bool = False,
) -> tuple[dict, pd.DataFrame] | tuple[dict, pd.DataFrame, dict]:
    """
    Bar-by-bar: Gate1 TT → Gate2 Setup → Gate3 Trigger (→ M4 retest if configured).
    Entry at next open after signal; exit at next open (or EOD force).
    cfg keys: tt, setup, lookback_base, vol_mult, close_strength, stop_pct, atr_k,
              risk_pct, exits: { ... }, use_retest, chase_cap, stop_vol_only,
              fee_bps, slippage_bps, min_hold_bars, warmup_bars (default 252+lookback_base).
    If collect_funnel=True, returns (stats, ledger, funnel_counts) with
    tt_pass, setup_pass, trigger_pass, retest_pass, entries, exits.
    """
    funnel = (
        {"tt_pass": 0, "setup_pass": 0, "trigger_pass": 0, "retest_pass": 0, "entries": 0, "exits": 0}
        if collect_funnel
        else None
    )
    d = prepare_bars(df, cfg).reset_index(drop=True)
    # Warmup: require 252 + lookback_base bars so 52w high/low and pivot are valid (no early-period bias)
    lb = int(_get_cfg(cfg, "lookback_base", 40))
    warmup = int(_get_cfg(cfg, "warmup_bars", 252 + lb))
    if len(d) > warmup:
        d = d.iloc[warmup:].reset_index(drop=True)
    fee = _get_cfg(cfg, "fee_bps", 20) / 10000.0
    slip = _get_cfg(cfg, "slippage_bps", 5) / 10000.0
    min_hold = int(_get_cfg(cfg, "min_hold_bars", 0))
    exits_cfg = _get_cfg(cfg, "exits", {}) or {}
    use_retest = _get_cfg(cfg, "use_retest", False)
    lookback_base = int(_get_cfg(cfg, "lookback_base", 40))
    trigger_type = _get_cfg(cfg, "trigger_type", "hh").strip().lower()
    pivot_tight_window = int(_get_cfg(cfg, "pivot_tight_window", 15))

    uandr_lookback = int(_get_cfg(cfg, "undercut_rally_lookback", 10))

    def _pivot_at(idx: int):
        if trigger_type == "tight_range":
            return pivot_tight_level(d, pivot_tight_window, idx)
        if trigger_type in ("undercut_rally", "uandr"):
            return pivot_low_level(d, uandr_lookback, idx)
        return pivot_level(d, lookback_base, idx)

    in_pos = False
    entry_i = None
    entry_px = None
    entry_date = None
    stop_px = None
    bars_held = 0
    partial_taken = False
    pivot_at_entry = None
    ledger = []
    equity = initial_equity
    pending_breakout_i = None
    pending_pivot = None
    pending_gap_i = None
    pending_gap_pivot = None
    gap_filter = _get_cfg(cfg, "gap_filter", False)
    gap_atr_mult = float(_get_cfg(cfg, "gap_atr_mult", 2.5))
    retest_max_bars = int(_get_cfg(cfg, "retest_max_bars", 5))
    max_undercut_pct = float(_get_cfg(cfg, "max_undercut_pct", 0.02))
    confirm_days = int(_get_cfg(cfg, "confirm_days", 0))
    pending_confirm_until = None
    pending_confirm_pivot = None

    for i in range(len(d) - 1):
        row = d.iloc[i]
        next_open = float(d.iloc[i + 1]["open"])
        next_date = d.iloc[i + 1]["date"]

        # --- M10: gap day → wait for next bar to hold above pivot (retest) ---
        if not in_pos and gap_filter and pending_gap_i is not None:
            if i == pending_gap_i + 1:
                if float(row["close"]) > pending_gap_pivot:
                    if funnel is not None:
                        funnel["entries"] += 1
                    entry_i = i + 1
                    entry_px = next_open * (1 + fee + slip)
                    entry_date = next_date
                    atr_val = float(row.get("atr") or 0.0)
                    if atr_val <= 0:
                        atr_series = atr(d, 14)
                        atr_val = float(atr_series.iloc[i]) if i < len(atr_series) else 0.0
                    stop_pct = None if _get_cfg(cfg, "stop_vol_only", False) else _get_cfg(cfg, "stop_pct")
                    stop_px = stop_price(entry_px, stop_pct=stop_pct, atr=atr_val, atr_k=_get_cfg(cfg, "atr_k"))
                    if stop_px <= 0:
                        stop_px = entry_px * 0.95
                    bars_held = 0
                    partial_taken = False
                    pending_gap_i = pending_gap_pivot = None
                    in_pos = True
            else:
                pending_gap_i = pending_gap_pivot = None
            continue

        # --- Confirm window (confirm_days >= 2): hold above pivot then allow retest/entry ---
        if not in_pos and confirm_days >= 2 and pending_confirm_until is not None:
            pivot_c = pending_confirm_pivot
            if i > pending_confirm_until:
                pending_confirm_until = pending_confirm_pivot = None
            else:
                close_below = float(row["close"]) < pivot_c
                undercut = float(row["low"]) < pivot_c * (1 - max_undercut_pct)
                if close_below or undercut:
                    pending_confirm_until = pending_confirm_pivot = None
                elif i == pending_confirm_until:
                    if use_retest:
                        pending_breakout_i = i
                        pending_pivot = pivot_c
                    else:
                        if funnel is not None:
                            funnel["entries"] += 1
                        entry_i = i + 1
                        entry_px = next_open * (1 + fee + slip)
                        entry_date = next_date
                        atr_val = float(row.get("atr") or 0.0)
                        if atr_val <= 0:
                            atr_series = atr(d, 14)
                            atr_val = float(atr_series.iloc[i]) if i < len(atr_series) else 0.0
                        stop_pct = None if _get_cfg(cfg, "stop_vol_only", False) else _get_cfg(cfg, "stop_pct")
                        stop_px = stop_price(entry_px, stop_pct=stop_pct, atr=atr_val, atr_k=_get_cfg(cfg, "atr_k"))
                        if stop_px <= 0:
                            stop_px = entry_px * 0.95
                        bars_held = 0
                        partial_taken = False
                        in_pos = True
                    pending_confirm_until = pending_confirm_pivot = None
            continue

        # --- M4: waiting for retest after breakout ---
        if not in_pos and use_retest and pending_breakout_i is not None:
            bars_since = i - pending_breakout_i
            if bars_since > retest_max_bars:
                pending_breakout_i = pending_pivot = None
            else:
                low_ok = float(row["low"]) >= pending_pivot * (1 - max_undercut_pct)
                close_above = float(row["close"]) > pending_pivot
                if close_above and low_ok:
                    if funnel is not None:
                        funnel["retest_pass"] += 1
                        funnel["entries"] += 1
                    entry_i = i + 1
                    entry_px = next_open * (1 + fee + slip)
                    entry_date = next_date
                    atr_val = float(row.get("atr") or 0.0)
                    if atr_val <= 0:
                        atr_series = atr(d, 14)
                        atr_val = float(atr_series.iloc[i]) if i < len(atr_series) else 0.0
                    sp = None if _get_cfg(cfg, "stop_vol_only", False) else _get_cfg(cfg, "stop_pct")
                    stop_px = stop_price(entry_px, stop_pct=sp, atr=atr_val, atr_k=_get_cfg(cfg, "atr_k"))
                    if stop_px <= 0:
                        stop_px = entry_px * 0.95
                    bars_held = 0
                    partial_taken = False
                    pending_breakout_i = pending_pivot = None
                    in_pos = True
                continue

        # --- Entry logic ---
        if not in_pos:
            g1 = row.get("tt_ok", False)
            g2 = row.get("setup_ok", False)
            g3 = row.get("trigger_breakout", False)
            if funnel is not None:
                if g1:
                    funnel["tt_pass"] += 1
                if g1 and g2:
                    funnel["setup_pass"] += 1
                if g1 and g2 and g3:
                    funnel["trigger_pass"] += 1
            if not (g1 and g2 and g3):
                continue
            # Regime gate (M11): require regime_on if column present
            if row.get("regime_on") is not None and not row.get("regime_on", True):
                continue
            # M10 gap filter: if TR > gap_atr_mult*ATR, defer entry until next bar holds above pivot
            tr_val = float(row.get("true_range", row["high"] - row["low"]))
            atr_val_bar = float(row.get("atr") or 0.0)
            if gap_filter and atr_val_bar > 0 and tr_val > gap_atr_mult * atr_val_bar:
                pending_gap_i = i
                pending_gap_pivot = _pivot_at(i)
                continue
            # M6 No-Chase: entry only if Close <= pivot * (1 + chase_cap)
            chase_cap = _get_cfg(cfg, "chase_cap")
            if chase_cap is not None and chase_cap is not False:
                pivot = _pivot_at(i)
                cap = float(chase_cap) if chase_cap is not True else 0.015
                if float(row["close"]) > pivot * (1 + cap):
                    continue
            # 2-day (or n-day) confirm: defer entry until confirm bar
            if confirm_days >= 2:
                pending_confirm_until = i + confirm_days - 1
                pending_confirm_pivot = _pivot_at(i)
                continue
            if use_retest:
                pivot = _pivot_at(i)
                pending_breakout_i = i
                pending_pivot = pivot
                continue
            if funnel is not None:
                funnel["entries"] += 1
            entry_i = i + 1
            entry_px = next_open * (1 + fee + slip)
            entry_date = next_date
            atr_val = float(row.get("atr") or 0.0)
            if atr_val <= 0 and "atr" not in d.columns:
                atr_series = atr(d, 14)
                atr_val = float(atr_series.iloc[i]) if i < len(atr_series) else 0.0
            stop_pct = None if _get_cfg(cfg, "stop_vol_only", False) else _get_cfg(cfg, "stop_pct")
            atr_k = _get_cfg(cfg, "atr_k")
            stop_px = stop_price(entry_px, stop_pct=stop_pct, atr=atr_val, atr_k=atr_k)
            if stop_px <= 0:
                stop_px = entry_px * 0.95
            bars_held = 0
            partial_taken = False
            pivot_at_entry = _pivot_at(i) if use_retest else None
            in_pos = True
            continue

        # --- In position: exit checks ---
        bars_held = i - entry_i + 1
        close = float(row["close"])
        low = float(row["low"])
        high = float(row["high"])
        vol = float(row.get("volume", 0))
        vol_sma20 = float(row.get("vol_sma20", 0))
        atr14 = float(row.get("atr", 0))
        tr = float(row.get("true_range", high - low))
        ma50 = row.get("ma50")
        ma20 = row.get("ma20")
        r_multiple = (close - entry_px) / (entry_px - stop_px) if (entry_px - stop_px) > 0 else 0.0

        exit_now = False
        reason = ""

        if min_hold > 0 and bars_held < min_hold:
            # Only hard stop before min_hold
            if exit_hard_stop(close, low, stop_px):
                exit_now = True
                reason = "HARD_STOP"
        else:
            if exit_hard_stop(close, low, stop_px):
                exit_now = True
                reason = "HARD_STOP"
            if not exit_now and exits_cfg.get("fail_fast_days"):
                if exit_fail_fast(bars_held, close, entry_px, int(exits_cfg["fail_fast_days"])):
                    exit_now = True
                    reason = "FAIL_FAST"
            if not exit_now and exits_cfg.get("time_stop_days"):
                min_r = float(exits_cfg.get("min_r", 1.0))
                if exit_time_stop(bars_held, int(exits_cfg["time_stop_days"]), r_multiple, min_r):
                    exit_now = True
                    reason = "TIME_STOP"
            if not exit_now and exits_cfg.get("trend_break_ma"):
                ma_val = row.get(f"ma{exits_cfg['trend_break_ma']}")
                if ma_val is not None and pd.notna(ma_val) and exit_trend_break(close, float(ma_val)):
                    exit_now = True
                    reason = "TREND_BREAK"
            if not exit_now and exits_cfg.get("trail_ma"):
                trail_ma_val = row.get(f"ma{exits_cfg['trail_ma']}")
                if trail_ma_val is not None and pd.notna(trail_ma_val) and exit_trailing_ma(close, float(trail_ma_val)):
                    exit_now = True
                    reason = "TRAIL_MA"
            if not exit_now and exits_cfg.get("climax_proxy") and atr14 > 0:
                if exit_climax_proxy(tr, atr14, 2.0, 0.25, high, low, close, vol, vol_sma20, 1.5):
                    exit_now = True
                    reason = "CLIMAX"
            if not exit_now and not partial_taken and exits_cfg.get("take_partial_r"):
                if r_multiple >= float(exits_cfg["take_partial_r"]):
                    partial_taken = True
                    # Don't exit full position; just mark. (Simplified: we don't scale out; just note for stats.)

        if exit_now:
            exit_px = next_open * (1 - fee - slip)
            ret = (exit_px / entry_px) - 1.0
            exit_date = next_date
            try:
                hold_days = (pd.Timestamp(exit_date) - pd.Timestamp(entry_date)).days
            except Exception:
                hold_days = np.nan
            if funnel is not None:
                funnel["exits"] += 1
            ledger.append({
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_px": entry_px,
                "exit_px": exit_px,
                "stop_px": stop_px,
                "ret": ret,
                "hold_bars": bars_held,
                "hold_days": hold_days,
                "exit_reason": reason,
            })
            in_pos = False
            entry_i = entry_px = entry_date = stop_px = pivot_at_entry = None

    if in_pos and entry_i is not None:
        if funnel is not None:
            funnel["exits"] += 1
        last = d.iloc[-1]
        exit_px = float(last["close"]) * (1 - fee - slip)
        ret = (exit_px / entry_px) - 1.0
        bars_held = len(d) - entry_i
        ledger.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": last["date"],
            "entry_px": entry_px,
            "exit_px": exit_px,
            "stop_px": stop_px,
            "ret": ret,
            "hold_bars": bars_held,
            "hold_days": np.nan,
            "exit_reason": "EOD_FORCE",
        })

    ledger_df = pd.DataFrame(ledger)
    stats = trade_metrics(ledger_df)
    stats["symbol"] = symbol
    stats["trades_per_year"] = trades_per_year(ledger_df)
    for k, v in minervini_r_metrics(ledger_df).items():
        stats[k] = v
    if collect_funnel and funnel is not None:
        return stats, ledger_df, funnel
    return stats, ledger_df


def run_backtest(
    data_by_symbol: dict[str, pd.DataFrame],
    cfg: dict,
    initial_equity: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    data_by_symbol: { symbol: df with date, open, high, low, close, volume }.
    Returns (stats_df, ledger_df) where ledger is concatenated across symbols.
    """
    all_stats = []
    all_ledgers = []
    for sym, df in data_by_symbol.items():
        stats, ledger = run_single_symbol(df, cfg, symbol=sym, initial_equity=initial_equity)
        all_stats.append(stats)
        if not ledger.empty:
            all_ledgers.append(ledger)
    stats_df = pd.DataFrame(all_stats)
    ledger_df = pd.concat(all_ledgers, ignore_index=True) if all_ledgers else pd.DataFrame()
    return stats_df, ledger_df
