# pp_backtest/backtest.py — Single-symbol backtest, entry/exit at next open
from __future__ import annotations
import numpy as np
import pandas as pd

try:
    from pp_backtest.config import BacktestConfig
except ImportError:
    from config import BacktestConfig


def _first_true_reason(row: pd.Series) -> str:
    """Priority: DARVAS_BOX/LIVERMORE_* > UGLY_BAR > SELL_V4 > MARKET_DD > STOCK_DD > UNKNOWN."""
    if bool(row.get("sell_darvas_box", False)):
        return "DARVAS_BOX"
    if bool(row.get("sell_livermore_pf", False)):
        return "LIVERMORE_PF"
    if bool(row.get("sell_livermore_ma20", False)):
        return "LIVERMORE_MA20"
    if bool(row.get("sell_livermore_ma50", False)):
        return "LIVERMORE_MA50"
    if bool(row.get("sell_ugly_only", False)):
        return "UGLY_BAR"
    if bool(row.get("sell_v4", False)):
        return "SELL_V4"
    if bool(row.get("sell_mkt_dd", False)):
        return "MARKET_DD"
    if bool(row.get("sell_stk_dd", False)):
        return "STOCK_DD"
    return "UNKNOWN"


# Gate: setup_quality_score >= GATE_THRESHOLD (pre-registered); None/NaN → block entry (Option A)
GATE_THRESHOLD = 50


def _score_invalid(score: object) -> bool:
    """True if score is None or NaN (warmup / no data)."""
    if score is None:
        return True
    try:
        return pd.isna(score)
    except Exception:
        return True


def run_single_symbol_with_ledger(
    df: pd.DataFrame,
    cfg: BacktestConfig,
    use_gate: bool = False,
    use_regime_ma200: bool = False,
    use_regime_liquidity: bool = False,
    use_meta_v1: bool = False,
    use_dist_entry_filter: bool = False,
    dist_entry_max: int = 4,
    use_regime_ftd: bool = False,
    use_no_new_positions: bool = False,
    use_above_ma50: bool = False,
    use_demand_thrust: bool = False,
    use_tightness: bool = False,
    use_right_side_of_base: bool = False,
    use_avoid_extended: bool = False,
    use_exit_fixed_bars: bool = False,
    fixed_exit_bars: int = 10,
    use_exit_armed_after: bool = False,
    exit_armed_after_bars: int = 10,
    use_darvas_trailing: bool = False,
    use_livermore_pf_k_bars: bool = False,
    livermore_pf_k: int = 3,
    use_pyramid_darvas: bool = False,
    max_adds_darvas: int = 1,
    use_pyramid_livermore: bool = False,
    max_adds_livermore: int = 1,
    pyramid_livermore_pct: float = 0.08,
    engine: str | None = None,
) -> tuple[dict, pd.DataFrame]:
    """
    Requires: date, open, high, low, close, volume, pp, sell_final.
    Darvas trailing: use_darvas_trailing + box_low, darvas_stop_buffer → exit when close < max(box_low[entry:i]) - buffer.
    Livermore K-bar: use_livermore_pf_k_bars + livermore_pf_k + trigger_level at entry → exit if bars_held <= K and close < trigger_at_entry.
    Pyramiding: add at next open when conditions; entry_px = avg of entries.
    """
    d = df.copy().reset_index(drop=True)
    pp = d["pp"].fillna(False)
    if use_gate and "setup_quality_score" in d.columns:
        score = d["setup_quality_score"]
        valid = score.apply(lambda x: not _score_invalid(x))
        e0 = pp & valid & (score >= GATE_THRESHOLD)
    else:
        e0 = pp
    # Intermediate signals for gate-hit logging (red-flag 2: verify each gate filters)
    e1 = e0 & (d["liquidity_on"].fillna(False) if use_regime_liquidity and "liquidity_on" in d.columns else True)
    e2 = e1 & (d["above_ma50"].fillna(False) if use_above_ma50 and "above_ma50" in d.columns else True)
    e3 = e2 & (d["demand_thrust"].fillna(False) if use_demand_thrust and "demand_thrust" in d.columns else True)
    e4 = e3 & (d["tightness_ok"].fillna(False) if use_tightness and "tightness_ok" in d.columns else True)
    e5 = e4 & (d["right_side_of_base"].fillna(False) if use_right_side_of_base and "right_side_of_base" in d.columns else True)
    e6 = e5 & (d["avoid_extended"].fillna(False) if use_avoid_extended and "avoid_extended" in d.columns else True)
    filtered_by_liquidity = int((e0 & ~e1).sum()) if use_regime_liquidity else 0
    filtered_by_ma50 = int((e1 & ~e2).sum()) if use_above_ma50 else 0
    filtered_by_demand_thrust = int((e2 & ~e3).sum()) if use_demand_thrust else 0
    filtered_by_tightness = int((e3 & ~e4).sum()) if use_tightness else 0
    filtered_by_right_side = int((e4 & ~e5).sum()) if use_right_side_of_base else 0
    filtered_by_avoid_extended = int((e5 & ~e6).sum()) if use_avoid_extended else 0

    d["entry_signal"] = e6
    if use_regime_ma200 and "regime_on" in d.columns:
        d["entry_signal"] = d["entry_signal"] & d["regime_on"].fillna(False)
    if use_meta_v1 and "meta_trending" in d.columns:
        # Entry at open of bar i+1 must use regime known before that open → use bar i-1 (shift 1)
        d["_meta_trending_entry"] = d["meta_trending"].shift(1).fillna(False)
        d["entry_signal"] = d["entry_signal"] & d["_meta_trending_entry"]
    if use_regime_ftd and "regime_ftd" in d.columns:
        d["entry_signal"] = d["entry_signal"] & d["regime_ftd"].fillna(False)
    if use_no_new_positions and "no_new_positions" in d.columns:
        d["entry_signal"] = d["entry_signal"] & (~d["no_new_positions"].fillna(False))
    if use_dist_entry_filter and dist_entry_max > 0 and "mkt_dd_count" in d.columns:
        # Entry at open bar i+1: use mkt_dd_count at bar i-1 (shift 1)
        d["_dist_ok_entry"] = (d["mkt_dd_count"].shift(1) < dist_entry_max).fillna(True)
        d["entry_signal"] = d["entry_signal"] & d["_dist_ok_entry"]
    d["exit_signal"] = d["sell_final"].fillna(False)

    fee = cfg.fee_bps / 10000.0
    slip = cfg.slippage_bps / 10000.0

    in_pos = False
    entry_i = None
    entry_px = None
    entry_date = None
    entry_box_high = None
    entry_trigger = None
    first_entry_px = None  # for avg_entry_1 / audit
    stop_at_entry_val = np.nan  # Darvas/Livermore stop at entry
    add_date_val = None  # pyramid add date (first add only)
    add_px_val = None    # pyramid add price (first add only)
    n_units = 1
    n_adds = 0
    ledger = []
    skipped_due_to_warmup = 0
    skipped_due_to_gate = 0
    skipped_due_to_regime = 0
    skipped_due_to_dist = 0

    for i in range(len(d) - 1):
        # Count skips when gate is on: PP True but we did not enter
        if use_gate and (not in_pos) and pp.loc[i]:
            if not d.loc[i, "entry_signal"]:
                sc = d.loc[i, "setup_quality_score"] if "setup_quality_score" in d.columns else None
                if _score_invalid(sc):
                    skipped_due_to_warmup += 1
                else:
                    skipped_due_to_gate += 1
        if use_regime_ma200 and (not in_pos) and pp.loc[i] and "regime_on" in d.columns and not d.loc[i, "regime_on"]:
            skipped_due_to_regime += 1
        if use_regime_liquidity and (not in_pos) and pp.loc[i] and "liquidity_on" in d.columns and not d.loc[i, "liquidity_on"]:
            skipped_due_to_regime += 1
        if use_meta_v1 and (not in_pos) and pp.loc[i] and "_meta_trending_entry" in d.columns and not d.loc[i, "_meta_trending_entry"]:
            skipped_due_to_regime += 1
        if use_dist_entry_filter and (not in_pos) and pp.loc[i] and "_dist_ok_entry" in d.columns and not d.loc[i, "_dist_ok_entry"]:
            skipped_due_to_dist += 1
        if (not in_pos) and d.loc[i, "entry_signal"]:
            entry_i = i + 1
            entry_px = float(d.loc[entry_i, "open"]) * (1 + fee + slip)
            entry_date = d.loc[entry_i, "date"]
            first_entry_px = entry_px
            entry_box_high = float(d.loc[i, "box_high"]) if use_pyramid_darvas and "box_high" in d.columns and pd.notna(d.loc[i, "box_high"]) else None
            entry_trigger = float(d.loc[i, "trigger_level"]) if use_livermore_pf_k_bars and "trigger_level" in d.columns and pd.notna(d.loc[i, "trigger_level"]) else None
            # Stop at entry for audit (Darvas: box_low - buffer at fill bar; Livermore: trigger_level)
            if use_darvas_trailing and "box_low" in d.columns and "darvas_stop_buffer" in d.columns:
                bl = d.loc[entry_i, "box_low"]
                bf = d.loc[entry_i, "darvas_stop_buffer"]
                if pd.notna(bl) and pd.notna(bf):
                    stop_at_entry_val = float(bl) - float(bf)
                else:
                    stop_at_entry_val = np.nan
            elif use_livermore_pf_k_bars and entry_trigger is not None:
                stop_at_entry_val = float(entry_trigger)
            else:
                stop_at_entry_val = np.nan
            add_date_val = None
            add_px_val = None
            n_units = 1
            n_adds = 0
            in_pos = True
            continue

        if not in_pos:
            continue
        min_hold = getattr(cfg, "min_hold_bars", 0)
        bars_held = i - entry_i + 1
        exit_now = False

        # --- Pyramiding: add at next open when conditions met ---
        if use_pyramid_darvas and n_adds < max_adds_darvas and "box_high" in d.columns and entry_box_high is not None:
            bh = d.loc[i, "box_high"]
            if pd.notna(bh) and float(bh) > entry_box_high and float(d.loc[i, "close"]) > entry_px:
                next_open = float(d.loc[i + 1, "open"]) * (1 + fee + slip)
                if add_date_val is None:
                    add_date_val = d.loc[i + 1, "date"]
                    add_px_val = next_open
                entry_px = (entry_px * n_units + next_open) / (n_units + 1)
                n_units += 1
                n_adds += 1
                entry_box_high = float(bh)
        if use_pyramid_livermore and n_adds < max_adds_livermore:
            ret_from_entry = (float(d.loc[i, "close"]) - entry_px) / entry_px if entry_px else 0
            h = d["high"].astype(float)
            prior_high = h.shift(1).rolling(20, min_periods=20).max().shift(1)
            ph_i = prior_high.iloc[i] if i < len(prior_high) else np.nan
            new_pivot = pd.notna(ph_i) and float(d.loc[i, "close"]) > float(ph_i)
            if ret_from_entry >= pyramid_livermore_pct and new_pivot:
                next_open = float(d.loc[i + 1, "open"]) * (1 + fee + slip)
                if add_date_val is None:
                    add_date_val = d.loc[i + 1, "date"]
                    add_px_val = next_open
                entry_px = (entry_px * n_units + next_open) / (n_units + 1)
                n_units += 1
                n_adds += 1

        exit_reason_override = None
        # --- Exit: Darvas trailing (stateful) ---
        if use_darvas_trailing and "box_low" in d.columns and "darvas_stop_buffer" in d.columns:
            trailing_low = d.loc[entry_i : i, "box_low"].astype(float).max()
            buf = float(d.loc[i, "darvas_stop_buffer"]) if pd.notna(d.loc[i, "darvas_stop_buffer"]) else 0
            if float(d.loc[i, "close"]) < (trailing_low - buf):
                exit_now = True
                exit_reason_override = "DARVAS_BOX"
        # --- Exit: Livermore pivot failure within K bars ---
        if not exit_now and use_livermore_pf_k_bars and entry_trigger is not None and bars_held <= livermore_pf_k:
            if float(d.loc[i, "close"]) < entry_trigger:
                exit_now = True
                exit_reason_override = "LIVERMORE_PF"
        if not exit_now:
            if use_exit_fixed_bars:
                exit_now = bars_held >= fixed_exit_bars and (min_hold <= 0 or bars_held >= min_hold)
            elif use_exit_armed_after:
                if bars_held < exit_armed_after_bars:
                    if "sell_ugly_only" not in d.columns:
                        phase1_exit = False
                    else:
                        v = d.loc[i, "sell_ugly_only"]
                        phase1_exit = bool(v) if pd.notna(v) else False
                    exit_now = phase1_exit and (min_hold <= 0 or bars_held >= min_hold)
                else:
                    exit_now = d.loc[i, "exit_signal"] and (min_hold <= 0 or bars_held >= min_hold)
            else:
                exit_now = d.loc[i, "exit_signal"] and (min_hold <= 0 or bars_held >= min_hold)
        if exit_now:
            exit_i = i + 1
            exit_px = float(d.loc[exit_i, "open"]) * (1 - fee - slip)
            exit_date = d.loc[exit_i, "date"]
            r = (exit_px / entry_px) - 1.0  # per-trade return net of fee/slip (audit E: tail5 from this)
            signal_row = d.loc[i]
            if exit_reason_override:
                reason = exit_reason_override
            elif use_exit_fixed_bars:
                reason = "FIXED_BARS"
            elif use_exit_armed_after and bars_held < exit_armed_after_bars:
                reason = "UGLY_BAR"  # Phase 1
            else:
                reason = _first_true_reason(signal_row)

            # Stop at exit for audit (Darvas: trailing_low - buffer at exit bar; Livermore: trigger)
            if use_darvas_trailing and "box_low" in d.columns and "darvas_stop_buffer" in d.columns:
                trailing_low_ex = d.loc[entry_i : i, "box_low"].astype(float).max()
                buf_ex = float(d.loc[i, "darvas_stop_buffer"]) if pd.notna(d.loc[i, "darvas_stop_buffer"]) else 0
                stop_at_exit_val = trailing_low_ex - buf_ex
            elif use_livermore_pf_k_bars and entry_trigger is not None:
                stop_at_exit_val = float(entry_trigger)
            else:
                stop_at_exit_val = np.nan

            ledger.append({
                "entry_date": entry_date,
                "exit_signal_date": signal_row["date"],
                "exit_date": exit_date,
                "entry_px": entry_px,
                "exit_px": exit_px,
                "ret": r,
                "hold_cal_days": (exit_date - entry_date).days if pd.notna(exit_date) and pd.notna(entry_date) else np.nan,
                "hold_trading_bars": bars_held,
                "n_units": n_units,
                "engine": engine or "",
                "entry_bar_index": entry_i,
                "exit_reason": reason,
                "stop_at_entry": stop_at_entry_val,
                "stop_at_exit": stop_at_exit_val,
                "add_date": add_date_val,
                "add_px": add_px_val if add_px_val is not None else np.nan,
                "avg_entry_1": first_entry_px,
                "avg_entry_final": entry_px,
                "sell_tier": signal_row.get("sell_tier", ""),
                "mkt_dd_count": float(signal_row.get("mkt_dd_count", np.nan)) if pd.notna(signal_row.get("mkt_dd_count")) else np.nan,
                "stk_dd_count": float(signal_row.get("stk_dd_count", np.nan)) if pd.notna(signal_row.get("stk_dd_count")) else np.nan,
                "sell_v4": bool(signal_row.get("sell_v4", False)),
                "sell_mkt_dd": bool(signal_row.get("sell_mkt_dd", False)),
                "sell_stk_dd": bool(signal_row.get("sell_stk_dd", False)),
            })
            in_pos = False
            entry_i = entry_px = entry_date = entry_box_high = entry_trigger = first_entry_px = None
            stop_at_entry_val = np.nan
            add_date_val = add_px_val = None
            n_units = 1
            n_adds = 0

    if in_pos and entry_i is not None:
        last_i = len(d) - 1
        exit_px = float(d.loc[last_i, "close"]) * (1 - fee - slip)
        exit_date = d.loc[last_i, "date"]
        r = (exit_px / entry_px) - 1.0
        bars_held = last_i - entry_i + 1
        if use_darvas_trailing and "box_low" in d.columns and "darvas_stop_buffer" in d.columns:
            trailing_low_eod = d.loc[entry_i : last_i, "box_low"].astype(float).max()
            buf_eod = float(d.loc[last_i, "darvas_stop_buffer"]) if pd.notna(d.loc[last_i, "darvas_stop_buffer"]) else 0
            stop_at_exit_eod = trailing_low_eod - buf_eod
        elif use_livermore_pf_k_bars and entry_trigger is not None:
            stop_at_exit_eod = float(entry_trigger)
        else:
            stop_at_exit_eod = np.nan
        ledger.append({
            "entry_date": entry_date,
            "exit_signal_date": pd.NaT,
            "exit_date": exit_date,
            "entry_px": entry_px,
            "exit_px": exit_px,
            "ret": r,
            "hold_cal_days": (exit_date - entry_date).days if pd.notna(exit_date) and pd.notna(entry_date) else np.nan,
            "hold_trading_bars": bars_held,
            "n_units": n_units,
            "engine": engine or "",
            "entry_bar_index": entry_i,
            "exit_reason": "EOD_FORCE",
            "stop_at_entry": stop_at_entry_val,
            "stop_at_exit": stop_at_exit_eod,
            "add_date": add_date_val,
            "add_px": add_px_val if add_px_val is not None else np.nan,
            "avg_entry_1": first_entry_px,
            "avg_entry_final": entry_px,
            "sell_tier": "",
            "mkt_dd_count": np.nan,
            "stk_dd_count": np.nan,
            "sell_v4": False,
            "sell_mkt_dd": False,
            "sell_stk_dd": False,
        })

    ledger_df = pd.DataFrame(ledger)

    base_stats = {
        "trades": 0, "win_rate": np.nan, "avg_ret": np.nan, "expectancy": np.nan,
        "median_ret": np.nan, "avg_win": np.nan, "avg_loss": np.nan,
        "profit_factor": np.nan, "max_drawdown": np.nan, "avg_hold_days": np.nan,
        "tail5": np.nan, "median_hold_bars": np.nan,
    }
    if use_gate:
        base_stats["skipped_due_to_warmup"] = skipped_due_to_warmup
        base_stats["skipped_due_to_gate"] = skipped_due_to_gate
    if use_regime_ma200 or use_regime_liquidity or use_meta_v1:
        base_stats["skipped_due_to_regime"] = skipped_due_to_regime
    if use_dist_entry_filter:
        base_stats["skipped_due_to_dist"] = skipped_due_to_dist
    # Gate filter counts (red-flag 2: demand_thrust must filter something)
    if use_regime_liquidity:
        base_stats["filtered_by_liquidity"] = filtered_by_liquidity
    if use_above_ma50:
        base_stats["filtered_by_ma50"] = filtered_by_ma50
    if use_demand_thrust:
        base_stats["filtered_by_demand_thrust"] = filtered_by_demand_thrust
    if use_tightness:
        base_stats["filtered_by_tightness"] = filtered_by_tightness
    if ledger_df.empty:
        stats = dict(base_stats)
    else:
        rets = ledger_df["ret"].astype(float).values
        wins = rets[rets > 0]
        losses = rets[rets <= 0]
        pf = (wins.sum() / (-losses.sum())) if len(losses) and losses.sum() < 0 and len(wins) else np.nan
        cum = np.cumprod(1.0 + rets) - 1.0
        peak = np.maximum.accumulate(1.0 + cum)
        max_dd = float((((1.0 + cum) / peak) - 1.0).min()) if len(cum) else np.nan
        tail5 = float(np.nanpercentile(rets, 5))
        median_hold_bars = float(ledger_df["hold_trading_bars"].median()) if "hold_trading_bars" in ledger_df.columns else (
            float(ledger_df["hold_bars"].median()) if "hold_bars" in ledger_df.columns else np.nan
        )
        stats = {
            **base_stats,
            "trades": int(len(rets)),
            "win_rate": float((rets > 0).mean()),
            "avg_ret": float(rets.mean()),
            "expectancy": float(rets.mean()),
            "median_ret": float(np.median(rets)),
            "avg_win": float(wins.mean()) if len(wins) else np.nan,
            "avg_loss": float(losses.mean()) if len(losses) else np.nan,
            "profit_factor": float(pf) if pf == pf and np.isfinite(pf) else np.nan,
            "max_drawdown": max_dd,
            "avg_hold_days": float(ledger_df["hold_cal_days"].mean()) if "hold_cal_days" in ledger_df.columns else (
                float(ledger_df["hold_days"].mean()) if "hold_days" in ledger_df.columns else np.nan
            ),
            "tail5": tail5,
            "median_hold_bars": median_hold_bars,
        }
        if use_gate:
            stats["skipped_due_to_warmup"] = skipped_due_to_warmup
            stats["skipped_due_to_gate"] = skipped_due_to_gate
        if use_regime_liquidity:
            stats["filtered_by_liquidity"] = filtered_by_liquidity
        if use_above_ma50:
            stats["filtered_by_ma50"] = filtered_by_ma50
        if use_demand_thrust:
            stats["filtered_by_demand_thrust"] = filtered_by_demand_thrust
        if use_tightness:
            stats["filtered_by_tightness"] = filtered_by_tightness

    return stats, ledger_df


def run_single_symbol(df: pd.DataFrame, cfg: BacktestConfig) -> dict:
    """
    df must contain: date, open, high, low, close, volume, pp (bool), sell (bool)
    Entry at next open after PP; exit at next open after sell (or at last close if still in position).
    Returns stats including win_rate, expectancy (avg_ret), profit_factor, max_drawdown.
    """
    d = df.copy().reset_index(drop=True)

    d["entry_signal"] = d["pp"].fillna(False)
    d["exit_signal"] = d["sell"].fillna(False)

    in_pos = False
    entry_idx = None
    trades = []

    for i in range(len(d) - 1):
        if (not in_pos) and d.loc[i, "entry_signal"]:
            entry_idx = i + 1
            in_pos = True
            continue
        if in_pos and d.loc[i, "exit_signal"]:
            exit_idx = i + 1
            trades.append((entry_idx, exit_idx))
            in_pos = False
            entry_idx = None

    if in_pos and entry_idx is not None:
        trades.append((entry_idx, len(d) - 1))

    fee = cfg.fee_bps / 10000.0
    slip = cfg.slippage_bps / 10000.0

    rets = []
    hold_days = []

    for en, ex in trades:
        buy_px = d.loc[en, "open"] * (1 + slip + fee)
        if ex == len(d) - 1:
            sell_px = d.loc[ex, "close"] * (1 - slip - fee)
        else:
            sell_px = d.loc[ex, "open"] * (1 - slip - fee)
        r = (sell_px / buy_px) - 1.0
        rets.append(r)
        hold_days.append((d.loc[ex, "date"] - d.loc[en, "date"]).days)

    rets = np.array(rets, dtype=float)
    if rets.size == 0:
        return {
            "trades": 0,
            "win_rate": np.nan,
            "avg_ret": np.nan,
            "expectancy": np.nan,
            "median_ret": np.nan,
            "avg_win": np.nan,
            "avg_loss": np.nan,
            "profit_factor": np.nan,
            "max_drawdown": np.nan,
            "avg_hold_days": np.nan,
        }

    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    profit_factor = (wins.sum() / (-losses.sum())) if losses.size and losses.sum() < 0 else (np.nan if not wins.size else np.inf)

    # Max drawdown on cumulative returns (equity curve of trades)
    cum = np.cumprod(1.0 + rets) - 1.0
    peak = np.maximum.accumulate(1.0 + cum)
    dd = (1.0 + cum) / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else np.nan

    return {
        "trades": int(rets.size),
        "win_rate": float((rets > 0).mean()),
        "avg_ret": float(rets.mean()),
        "expectancy": float(rets.mean()),
        "median_ret": float(np.median(rets)),
        "avg_win": float(wins.mean()) if wins.size else np.nan,
        "avg_loss": float(losses.mean()) if losses.size else np.nan,
        "profit_factor": float(profit_factor) if np.isfinite(profit_factor) and profit_factor == profit_factor else np.nan,
        "max_drawdown": max_dd,
        "avg_hold_days": float(np.mean(hold_days)) if hold_days else np.nan,
    }
