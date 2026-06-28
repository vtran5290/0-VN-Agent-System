"""Shared A3 DP exit-sweep engine (Phase 1 / P1.5 / P2)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.portfolio_optimization_phase1 import (
    STRATEGY_CONFIGS,
    _exit_tp_trail,
    _quality_ok,
    get_universe,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _annual_return,
    _build_equity_adv_capped_v2,
    _tag_adv50,
)

STRATEGY = "A3"
PB_DEPTH = 0.04
PB_WINDOW = 30
PB_QUALITY = "slow_097"
T1_FRAC = 0.50
T2_FRAC = 0.50
MAX_HOLD = 250
MIN_SELL_LOCK = 5
MAX_POSITIONS = 20
PORTFOLIO_VND = 5e9
ADV_PARTICIPATION = 0.10
GK_MULT = 1.0
COST_RT = 0.0025 + 0.001

IS_A = (2012, 2019)
OOS_A = (2020, 2026)
IS_B = (2012, 2020)
OOS_B = (2021, 2026)
YEAR_COLS = list(range(2012, 2027))
DATA_START = "2012-01-01"
DATA_END = "2026-12-31"

# P1 winner exit (research)
P1_WINNER = {"tp1": None, "trail_mult": 3.5, "vol_filter": None, "initial_stop": 2.0}


def binary_gate_ema20_100(vnx: pd.DataFrame) -> pd.Series:
    """Production memo gate: VNINDEX EMA20 > EMA100."""
    w = vnx.sort_values("date").reset_index(drop=True)
    c = w["close"].astype(float)
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema100 = c.ewm(span=100, adjust=False).mean()
    gate = ema20 > ema100
    idx = pd.to_datetime(w["date"]).dt.normalize()
    return pd.Series(gate.values, index=idx)


def phase1_regime_gate(vnx: pd.DataFrame) -> pd.Series:
    """Legacy Phase-1 gate: close > EMA50 AND EMA20 > EMA50 (more permissive)."""
    from pp_backtest.portfolio_optimization_phase1 import vnindex_regime_gate

    gate, _ = vnindex_regime_gate(vnx)
    return gate


def _vol_adjusted_tp_pct(
    entry_price: float,
    atr_at_entry: float,
    realized_vol_60d: float,
) -> float:
    """max(6×ATR14/price, 1.5×realized_vol_60d)."""
    atr_frac = (6.0 * atr_at_entry / entry_price) if entry_price > 0 else 0.0
    vol_frac = 1.5 * realized_vol_60d if not np.isnan(realized_vol_60d) else 0.0
    return max(atr_frac, vol_frac, 0.01)


def _exit_flexible(
    close_arr: np.ndarray,
    high_arr: np.ndarray,
    atr_arr: np.ndarray,
    start: int,
    entry_price: float,
    *,
    tp_pct: float | None,
    tp_frac: float = 0.50,
    trail_mult: float = 2.5,
    max_hold: int = 250,
    initial_stop_mult: float | None = None,
    min_lock: int = 5,
    vol_60d_arr: np.ndarray | None = None,
) -> tuple[int, float, str]:
    n = len(close_arr)
    effective_tp = tp_pct
    effective_tp_frac = tp_frac

    if tp_pct == "vol_adjusted":
        atr_e = float(atr_arr[start])
        if np.isnan(atr_e) or atr_e <= 0:
            atr_e = entry_price * 0.02
        vol60 = (
            float(vol_60d_arr[start])
            if vol_60d_arr is not None and start < len(vol_60d_arr)
            else np.nan
        )
        effective_tp = _vol_adjusted_tp_pct(entry_price, atr_e, vol60)
        effective_tp_frac = 0.25

    stop_price = (
        entry_price - initial_stop_mult * atr_arr[start]
        if initial_stop_mult is not None and initial_stop_mult > 0
        else None
    )

    tp_hit = False
    high_water = entry_price

    for k in range(start + 1, min(start + max_hold + 1, n)):
        c = close_arr[k]
        h = high_arr[k]
        atr = atr_arr[k]
        if np.isnan(atr) or atr <= 0:
            atr = entry_price * 0.02
        bars_held = k - start

        if stop_price is not None and c <= stop_price:
            if bars_held < min_lock:
                continue
            return bars_held, (c / entry_price) - 1.0, "initial_stop"

        if bars_held < min_lock:
            high_water = max(high_water, c)
            continue

        if effective_tp is not None and not tp_hit:
            if h >= entry_price * (1.0 + float(effective_tp)):
                tp_hit = True
                high_water = max(c, entry_price * (1.0 + float(effective_tp)))

        trail_active = effective_tp is None or tp_hit
        if trail_active:
            high_water = max(high_water, c)
            trail_stop = high_water - trail_mult * atr
            if c <= trail_stop:
                if tp_hit and effective_tp is not None:
                    gross = (effective_tp_frac * float(effective_tp)) + (
                        (1.0 - effective_tp_frac) * (c / entry_price - 1.0)
                    )
                    reason = "tp_trail"
                else:
                    gross = (c / entry_price) - 1.0
                    reason = "trail_only"
                return bars_held, gross, reason

    end_i = min(start + max_hold, n - 1)
    c_end = close_arr[end_i]
    gross = (c_end / entry_price) - 1.0
    reason = "max_hold" if tp_hit or effective_tp is None else "tp_not_hit_max_hold"
    return end_i - start, gross, reason


def build_a3_dp_cache(panel: pd.DataFrame) -> dict:
    cfg = STRATEGY_CONFIGS[STRATEGY]
    ema_f, ema_s = cfg["ema_fast"], cfg["ema_slow"]
    universe = get_universe(panel, cfg["universe"])
    warmup = max(ema_s + 5, 60)
    cache: dict = {}

    for sym, sdf in panel[panel["symbol"].isin(universe)].groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < warmup + 10:
            continue
        close = sdf["close"].astype(float)
        high = sdf["high"].astype(float)
        low = sdf.get("low", close).astype(float)
        volume = sdf.get("volume", pd.Series(np.ones(len(sdf)))).astype(float)
        dates = pd.to_datetime(sdf["date"])

        cloud_d = ema_cloud(close, ema_f, ema_s)
        atr = compute_atr(high, low, close, period=14)
        vol_ma20 = volume.rolling(20, min_periods=10).mean()
        ret = close.pct_change()
        realized_vol_60d = ret.rolling(60, min_periods=30).std(ddof=1) * np.sqrt(252)

        sig = cloud_only_entry(
            close, cloud_d["ema_fast"], cloud_d["cloud_bull"],
            min_bars_bear=3, warmup=warmup,
        )
        sig_idxs = np.where(sig.values)[0]
        if len(sig_idxs) == 0:
            continue

        cache[sym] = {
            "close": close.values.astype(float),
            "high": high.values.astype(float),
            "volume": volume.values.astype(float),
            "vol_ma20": vol_ma20.values.astype(float),
            "atr": atr.values.astype(float),
            "vol_60d": realized_vol_60d.values.astype(float),
            "fast": cloud_d["ema_fast"].values.astype(float),
            "slow": cloud_d["ema_slow"].values.astype(float),
            "cloud": cloud_d["cloud_bull"].values.astype(bool),
            "dates": dates.values,
            "sig_idxs": sig_idxs,
        }
    return cache


def _vol_ok(data: dict, sig_i: int, vol_min: float | None) -> bool:
    if vol_min is None:
        return True
    vol = float(data["volume"][sig_i])
    vma = float(data["vol_ma20"][sig_i])
    if vma <= 0 or np.isnan(vma):
        return False
    return (vol / vma) >= vol_min


def sim_dp_symbol(
    sym: str,
    data: dict,
    gate_by_date: pd.Series,
    *,
    tp_pct: float | str | None,
    trail_mult: float,
    vol_filter: float | None,
    initial_stop: float | None,
    cost: float,
) -> list[dict]:
    close_arr = data["close"]
    high_arr = data["high"]
    atr_arr = data["atr"]
    vol_60d = data.get("vol_60d")
    dates = data["dates"]
    n = len(close_arr)
    trades: list[dict] = []

    for si in data["sig_idxs"]:
        if not _vol_ok(data, si, vol_filter):
            continue
        entry_i = si + 1
        if entry_i >= n:
            continue
        sig_date = pd.Timestamp(dates[si]).normalize()
        if not bool(gate_by_date.get(sig_date, True)):
            continue

        ep1 = float(close_arr[entry_i])
        if ep1 <= 0 or np.isnan(ep1):
            continue

        pb_bar = None
        ep2 = None
        for k in range(entry_i + 1, min(entry_i + PB_WINDOW + 1, n)):
            c = float(close_arr[k])
            if c <= ep1 * (1.0 - PB_DEPTH) and _quality_ok(data, k, PB_QUALITY):
                pb_bar = k
                ep2 = c
                break

        if pb_bar is not None:
            blended_ep = (T1_FRAC * ep1 + T2_FRAC * ep2) / (T1_FRAC + T2_FRAC)
            total_frac = T1_FRAC + T2_FRAC
        else:
            blended_ep = ep1
            total_frac = T1_FRAC

        hold, gross, reason = _exit_flexible(
            close_arr, high_arr, atr_arr, entry_i, blended_ep,
            tp_pct=tp_pct,
            tp_frac=0.50 if tp_pct != "vol_adjusted" else 0.25,
            trail_mult=trail_mult,
            max_hold=MAX_HOLD,
            initial_stop_mult=initial_stop,
            min_lock=MIN_SELL_LOCK,
            vol_60d_arr=vol_60d,
        )
        exit_i = min(entry_i + hold, n - 1)
        net = gross - cost

        tp_trigger = np.nan
        if tp_pct == "vol_adjusted":
            tp_trigger = _vol_adjusted_tp_pct(
                blended_ep, float(atr_arr[entry_i]), float(vol_60d[entry_i]) if vol_60d is not None else np.nan,
            )

        trades.append({
            "symbol": sym,
            "strategy": STRATEGY,
            "signal_date": sig_date.date(),
            "entry_date": pd.Timestamp(dates[entry_i]).date(),
            "exit_date": pd.Timestamp(dates[exit_i]).date(),
            "ep1": ep1,
            "ep2": ep2,
            "blended_ep": blended_ep,
            "t1_frac": T1_FRAC,
            "total_frac": total_frac,
            "has_pullback": pb_bar is not None,
            "hold_bars": hold,
            "gross_return": gross,
            "net_return": net,
            "exit_reason": reason,
            "tp1_trigger_pct": tp_trigger,
        })
    return trades


def build_all_trades(
    cache: dict,
    gate_by_date: pd.Series,
    tp_pct: float | str | None,
    trail_mult: float,
    vol_filter: float | None,
    initial_stop: float | None,
    cost: float = COST_RT,
) -> pd.DataFrame:
    rows: list[dict] = []
    for sym, data in cache.items():
        rows.extend(
            sim_dp_symbol(
                sym, data, gate_by_date,
                tp_pct=tp_pct, trail_mult=trail_mult,
                vol_filter=vol_filter, initial_stop=initial_stop, cost=cost,
            )
        )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df


def mar_for_entry_years(trades: pd.DataFrame, adv50_map: dict, y0: int, y1: int) -> float:
    if trades.empty:
        return np.nan
    sub = trades[(trades["entry_date"].dt.year >= y0) & (trades["entry_date"].dt.year <= y1)].copy()
    if sub.empty or len(sub) < 5:
        return np.nan
    sub = _tag_adv50(sub, adv50_map)
    eq, _ = _build_equity_adv_capped_v2(
        sub.drop(columns=["ema_dist_at_entry"], errors="ignore"),
        MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
    )
    if eq.empty or len(eq) < 5:
        return np.nan
    return float(portfolio_metrics(eq, sub).get("mar", np.nan))


def eval_config_row(
    trades: pd.DataFrame,
    adv50_map: dict,
    tp_label,
    trail_mult: float,
    vol_filter,
    initial_stop,
    max_positions: int = MAX_POSITIONS,
) -> dict:
    tagged = _tag_adv50(trades, adv50_map)
    eq_input = tagged.drop(columns=["ema_dist_at_entry"], errors="ignore")
    eq, liq_stats = _build_equity_adv_capped_v2(
        eq_input, max_positions, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
    )
    m = portfolio_metrics(eq, eq_input) if not eq.empty else {}

    row = {
        "tp1": tp_label,
        "trail_mult": trail_mult,
        "vol_filter": vol_filter if vol_filter is not None else "none",
        "initial_stop": initial_stop if initial_stop is not None else "none",
        "mar_full": m.get("mar", np.nan),
        "cagr": m.get("cagr", np.nan),
        "max_dd": m.get("max_dd", np.nan),
        "sharpe": m.get("sharpe", np.nan),
        "win_rate": m.get("hit_rate", np.nan),
        "avg_trade": m.get("avg_trade_ret", np.nan),
        "avg_trade_gross": float(tagged["gross_return"].mean()) if not tagged.empty else np.nan,
        "cost_rt_assumed": COST_RT,
        "n_trades": m.get("n_trades", len(tagged)),
        "pct_adv_capped_t1": liq_stats.get("pct_partial_T1", np.nan),
        "mar_is_a": mar_for_entry_years(tagged, adv50_map, *IS_A),
        "mar_oos_a": mar_for_entry_years(tagged, adv50_map, *OOS_A),
        "mar_is_b": mar_for_entry_years(tagged, adv50_map, *IS_B),
        "mar_oos_b": mar_for_entry_years(tagged, adv50_map, *OOS_B),
    }
    for yr in YEAR_COLS:
        row[f"y{yr}"] = _annual_return(eq, yr) if not eq.empty else np.nan
    return row


def max_consecutive_loss_streak(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    t = trades.sort_values("exit_date")
    streak = max_streak = 0
    for r in t["net_return"]:
        if r < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def buyhold_equal_weight_mar(panel: pd.DataFrame, start: str, end: str) -> dict:
    """Equal-weight ex-VIN3, monthly rebalance."""
    cfg = STRATEGY_CONFIGS[STRATEGY]
    universe = get_universe(panel, cfg["universe"])
    sub = panel[(panel["symbol"].isin(universe)) & (panel["date"] >= start) & (panel["date"] <= end)].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    px = sub.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index().ffill()
    if px.empty:
        return {}
    px = sub.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index().ffill()
    if px.empty:
        return {}
    daily_ret = px.pct_change().fillna(0.0)
    ew_ret = daily_ret.mean(axis=1)
    eq = (1.0 + ew_ret).cumprod()
    eq.iloc[0] = 1.0
    m = portfolio_metrics(eq, pd.DataFrame())
    return {
        "benchmark": "ex_vin3_equal_weight_monthly_rebal",
        "mar": m.get("mar", np.nan),
        "cagr": m.get("cagr", np.nan),
        "max_dd": m.get("max_dd", np.nan),
        "sharpe": m.get("sharpe", np.nan),
        "n_symbols": int(px.shape[1]),
        "start": str(eq.index[0].date()),
        "end": str(eq.index[-1].date()),
    }
