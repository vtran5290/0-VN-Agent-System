#!/usr/bin/env python3
"""
P0 Realism re-run — P1 winner (tp1=none, trail=3.5, stop=2.0×ATR).

Canonical idealized engine: phase_exit_sweep_core + EMA20>EMA100 + FIFO.
Honest layer: next-open fills, floor/ceiling locks, T+2 settlement, 0.40% costs,
+0.5% slippage when ADV cap binds or floor-lock delays exit.

Outputs: data/research/portfolio_optimization/p0_realism/

Usage:
  .venv\\Scripts\\python.exe pp_backtest/p0_realism_p1_winner.py
"""
from __future__ import annotations

import json
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.ema_levels.indicators import ema_cloud, compute_atr
from pp_backtest.ema_levels.entry import cloud_only_entry
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.phase_exit_sweep_core import (
    DATA_END,
    DATA_START,
    MAX_HOLD,
    MAX_POSITIONS,
    MIN_SELL_LOCK,
    PB_DEPTH,
    PB_QUALITY,
    PB_WINDOW,
    PORTFOLIO_VND,
    ADV_PARTICIPATION,
    GK_MULT,
    STRATEGY,
    T1_FRAC,
    T2_FRAC,
    binary_gate_ema20_100,
    build_a3_dp_cache,
    build_all_trades,
    eval_config_row,
)
from pp_backtest.portfolio_optimization_phase1 import (
    STRATEGY_CONFIGS,
    _quality_ok,
    get_universe,
    load_panel,
    load_vnindex,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _annual_return,
    _build_adv50_map,
    _build_equity_adv_capped_v2,
    _tag_adv50,
)

OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "p0_realism"

TRAIL_MULT = 3.5
INITIAL_STOP = 2.0

BUY_COMM = 0.0015
SELL_COMM = 0.0015
SELL_TAX = 0.0010
SLIPPAGE_PENALTY = 0.005
FLOOR_MULT = 0.93
CEILING_MULT = 1.07
LOCK_TOL = 0.002
SETTLEMENT_BDAY = 2

BH_MAR_REF = 0.152


def _limit_prices(prior_close: float) -> tuple[float, float]:
    return prior_close * FLOOR_MULT, prior_close * CEILING_MULT


def _is_ceiling_locked(close: float, prior_close: float) -> bool:
    if prior_close <= 0 or np.isnan(close) or np.isnan(prior_close):
        return False
    return close >= prior_close * CEILING_MULT * (1.0 - LOCK_TOL)


def _is_floor_locked(close: float, prior_close: float) -> bool:
    if prior_close <= 0 or np.isnan(close) or np.isnan(prior_close):
        return False
    return close <= prior_close * FLOOR_MULT * (1.0 + LOCK_TOL)


def _net_return_from_gross(gross: float) -> float:
    return gross - BUY_COMM - SELL_COMM - SELL_TAX


def _earliest_exit_bar(dates: np.ndarray, entry_i: int) -> int:
    entry_dt = pd.Timestamp(dates[entry_i])
    settle_dt = entry_dt + pd.tseries.offsets.BDay(SETTLEMENT_BDAY)
    for k in range(entry_i + 1, len(dates)):
        if pd.Timestamp(dates[k]) > settle_dt:
            return k
    return len(dates)


def _simulate_exit_honest_p1(
    open_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    close_arr: np.ndarray,
    atr_arr: np.ndarray,
    dates: np.ndarray,
    entry_i: int,
    entry_price: float,
) -> dict:
    n = len(close_arr)
    stop_price = entry_price - INITIAL_STOP * float(atr_arr[entry_i])
    high_water = entry_price
    floor_exit_delay = 0
    exit_delayed = False
    min_exit_i = _earliest_exit_bar(dates, entry_i)
    end_i = min(entry_i + MAX_HOLD, n - 1)
    exit_i = None
    exit_price = None
    exit_reason = "max_hold"

    k = entry_i + 1
    while k <= end_i:
        if k >= n:
            break
        prior_c = close_arr[k - 1] if k > 0 else close_arr[k]
        floor_locked = _is_floor_locked(close_arr[k], prior_c)
        atr = atr_arr[k]
        if np.isnan(atr) or atr <= 0:
            atr = entry_price * 0.02
        bars_held = k - entry_i

        if bars_held >= min_exit_i and close_arr[k] <= stop_price:
            if floor_locked:
                floor_exit_delay += 1
                exit_delayed = True
                k += 1
                continue
            fill_i = k + 1
            if fill_i >= n:
                break
            exit_i = fill_i
            exit_price = float(open_arr[fill_i])
            exit_reason = "initial_stop"
            break

        if bars_held >= min_exit_i:
            high_water = max(high_water, close_arr[k])
            trail_stop = high_water - TRAIL_MULT * atr
            if low_arr[k] <= trail_stop:
                if floor_locked:
                    floor_exit_delay += 1
                    exit_delayed = True
                    k += 1
                    continue
                fill_i = k + 1
                if fill_i >= n:
                    break
                exit_i = fill_i
                exit_price = min(float(open_arr[fill_i]), float(trail_stop))
                exit_reason = "trail_only"
                break

        if k >= end_i and bars_held >= min_exit_i:
            if floor_locked:
                floor_exit_delay += 1
                exit_delayed = True
                k += 1
                continue
            fill_i = k + 1
            if fill_i >= n:
                break
            exit_i = fill_i
            exit_price = float(open_arr[fill_i])
            exit_reason = "max_hold"
            break

        k += 1

    if exit_i is None:
        exit_i = min(end_i + 1, n - 1)
        exit_price = float(open_arr[exit_i]) if exit_i < n else float(close_arr[end_i])
        exit_reason = "max_hold"

    gross = exit_price / entry_price - 1.0
    hold = exit_i - entry_i
    obs_end = min(exit_i, n - 1)
    mfe = (np.max(high_arr[entry_i: obs_end + 1]) / entry_price - 1.0) if obs_end >= entry_i else 0.0

    return {
        "exit_i": exit_i,
        "gross_return": gross,
        "net_return": _net_return_from_gross(gross),
        "exit_reason": exit_reason,
        "hold_bars": hold,
        "mfe": mfe,
        "floor_exit_delay": floor_exit_delay,
        "exit_delayed": exit_delayed,
        "fill_mode": "next_open",
    }


def _build_honest_cache(panel: pd.DataFrame) -> dict:
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
        opn = sdf["open"].astype(float)
        dates = pd.to_datetime(sdf["date"])
        cloud_d = ema_cloud(close, ema_f, ema_s)
        sig = cloud_only_entry(
            close, cloud_d["ema_fast"], cloud_d["cloud_bull"],
            min_bars_bear=3, warmup=warmup,
        )
        sig_idxs = np.where(sig.values)[0]
        if len(sig_idxs) == 0:
            continue
        cache[sym] = {
            "open": opn.values.astype(float),
            "high": high.values.astype(float),
            "low": low.values.astype(float),
            "close": close.values.astype(float),
            "atr": compute_atr(high, low, close, 14).values.astype(float),
            "slow": cloud_d["ema_slow"].values.astype(float),
            "dates": dates.values,
            "sig_idxs": sig_idxs,
        }
    return cache


def _adv_cap_binds(adv50: float, t1_target_vnd: float) -> tuple[bool, float]:
    if adv50 <= 0:
        return False, t1_target_vnd
    cap = adv50 * ADV_PARTICIPATION
    eff = min(t1_target_vnd, cap)
    return eff < t1_target_vnd * 0.95, eff


def _simulate_honest_trades(cache: dict, gate: pd.Series, adv50_map: dict) -> pd.DataFrame:
    rows: list[dict] = []
    slot_vnd = PORTFOLIO_VND / MAX_POSITIONS
    t1_target_vnd = slot_vnd * T1_FRAC

    for sym, data in cache.items():
        close_arr = data["close"]
        open_arr = data["open"]
        high_arr = data["high"]
        low_arr = data["low"]
        atr_arr = data["atr"]
        dates = data["dates"]
        n = len(close_arr)

        for si in data["sig_idxs"]:
            entry_i = si + 1
            if entry_i >= n:
                continue
            sig_date = pd.Timestamp(dates[si]).normalize()
            if not bool(gate.get(sig_date, True)):
                continue

            prior_for_entry = close_arr[si] if si > 0 else close_arr[entry_i]
            if _is_ceiling_locked(close_arr[entry_i], prior_for_entry):
                continue
            ep1 = float(open_arr[entry_i])
            if ep1 <= 0 or np.isnan(ep1):
                continue

            pb_bar = None
            ep2 = None
            for k in range(entry_i + 1, min(entry_i + PB_WINDOW + 1, n)):
                if close_arr[k] <= ep1 * (1.0 - PB_DEPTH) and _quality_ok(data, k, PB_QUALITY):
                    fill_i = k + 1
                    if fill_i >= n:
                        break
                    if _is_ceiling_locked(close_arr[fill_i], close_arr[k]):
                        continue
                    ep2 = float(open_arr[fill_i])
                    pb_bar = k
                    break

            if ep2 is not None:
                blended_ep = (T1_FRAC * ep1 + T2_FRAC * ep2) / (T1_FRAC + T2_FRAC)
                total_frac = T1_FRAC + T2_FRAC
            else:
                blended_ep = ep1
                total_frac = T1_FRAC

            entry_dt = pd.Timestamp(dates[entry_i])
            adv_s = adv50_map.get(sym)
            adv50 = 0.0
            if adv_s is not None:
                valid = adv_s[adv_s.index <= entry_dt].dropna()
                if not valid.empty:
                    adv50 = float(valid.iloc[-1])
            adv_binds, _ = _adv_cap_binds(adv50, t1_target_vnd)

            ex = _simulate_exit_honest_p1(
                open_arr, high_arr, low_arr, close_arr, atr_arr, dates, entry_i, blended_ep,
            )
            slip = SLIPPAGE_PENALTY if (adv_binds or ex["exit_delayed"]) else 0.0
            net = ex["net_return"] - slip

            rows.append({
                "symbol": sym,
                "signal_date": sig_date.date(),
                "entry_date": entry_dt.date(),
                "exit_date": pd.Timestamp(dates[min(ex["exit_i"], n - 1)]).date(),
                "ep1": ep1,
                "ep2": ep2,
                "blended_ep": blended_ep,
                "t1_frac": T1_FRAC,
                "total_frac": total_frac,
                "has_pullback": pb_bar is not None,
                "gross_return": ex["gross_return"],
                "net_return": net,
                "hold_bars": ex["hold_bars"],
                "exit_reason": ex["exit_reason"],
                "adv50_value": adv50,
                "adv_cap_binds": adv_binds,
                "slippage_penalty": slip,
                "floor_exit_delay_bars": ex["floor_exit_delay"],
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df


def _metrics(trades: pd.DataFrame, adv50_map: dict) -> dict:
    tagged = _tag_adv50(trades, adv50_map)
    eq_in = tagged.drop(columns=["ema_dist_at_entry"], errors="ignore")
    eq, _ = _build_equity_adv_capped_v2(
        eq_in, MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT,
    )
    m = portfolio_metrics(eq, eq_in) if not eq.empty else {}
    m["equity"] = eq
    return m


def _kill_decision(mar: float) -> str:
    if mar <= BH_MAR_REF:
        return "KILL"
    if mar < 0.30:
        return "RE-SCOPE"
    return "PROCEED"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)]
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)
    cache = build_a3_dp_cache(panel)

    ideal_trades = build_all_trades(cache, gate, None, TRAIL_MULT, None, INITIAL_STOP)
    ideal_row = eval_config_row(ideal_trades, adv, "none", TRAIL_MULT, None, INITIAL_STOP)
    ideal_m = _metrics(ideal_trades, adv)

    honest_cache = _build_honest_cache(panel)
    honest_trades = _simulate_honest_trades(honest_cache, gate, adv)
    honest_m = _metrics(honest_trades, adv)

    decision = _kill_decision(float(honest_m.get("mar", np.nan)))
    ratio_bh = float(honest_m.get("mar", np.nan)) / BH_MAR_REF if BH_MAR_REF else np.nan

    results = pd.DataFrame([
        {
            "mode": "idealized_canonical",
            "mar": ideal_m.get("mar", ideal_row["mar_full"]),
            "cagr": ideal_m.get("cagr", ideal_row["cagr"]),
            "max_dd": ideal_m.get("max_dd", ideal_row["max_dd"]),
            "sharpe": ideal_m.get("sharpe", ideal_row["sharpe"]),
            "n_trades": ideal_m.get("n_trades", ideal_row["n_trades"]),
            "win_rate": ideal_m.get("hit_rate", ideal_row["win_rate"]),
            "avg_trade": ideal_m.get("avg_trade_ret", ideal_row["avg_trade"]),
        },
        {
            "mode": "honest_p0",
            "mar": honest_m.get("mar", np.nan),
            "cagr": honest_m.get("cagr", np.nan),
            "max_dd": honest_m.get("max_dd", np.nan),
            "sharpe": honest_m.get("sharpe", np.nan),
            "n_trades": honest_m.get("n_trades", len(honest_trades)),
            "win_rate": honest_m.get("hit_rate", np.nan),
            "avg_trade": honest_m.get("avg_trade_ret", np.nan),
        },
    ])
    results.to_csv(OUT_DIR / "p0_realism_results.csv", index=False, float_format="%.6f")

    delta_md = f"""# P0 Realism vs Idealized — P1 Winner

Generated: {date.today()}

## Config
- tp1=none, trail=3.5×ATR, vol=none, stop=2.0×ATR
- Canonical idealized: phase_exit_sweep_core, EMA20>EMA100, FIFO, 35 bps cost

## Realism corrections (honest path)
1. Next-bar open fills (entry/exit)
2. No entry on ceiling-locked bars; floor-lock delays exit
3. +0.5% slippage when ADV cap binds or floor-lock delay
4. T+2 settlement (VSDC 2026)
5. Transaction costs: 0.40% RT (0.15% buy + 0.15% sell + 0.10% tax)

## Results

| Mode | MAR | CAGR | MaxDD | n_trades |
|------|-----|------|-------|----------|
| Idealized (canonical) | {ideal_row['mar_full']:.4f} | {ideal_row['cagr']:.4f} | {ideal_row['max_dd']:.4f} | {int(ideal_row['n_trades'])} |
| Honest P0 | {honest_m.get('mar', np.nan):.4f} | {honest_m.get('cagr', np.nan):.4f} | {honest_m.get('max_dd', np.nan):.4f} | {int(honest_m.get('n_trades', len(honest_trades)))} |

- MAR delta (honest − ideal): {(honest_m.get('mar', np.nan) - ideal_row['mar_full']):+.4f}
- vs buy-and-hold MAR ({BH_MAR_REF}): **{ratio_bh:.2f}×**
- **Decision: {decision}**

## Kill criteria
- MAR ≤ 0.152: KILL
- MAR 0.152–0.30: RE-SCOPE to overlay
- MAR ≥ 0.30: PROCEED to P2.1
"""
    (OUT_DIR / "p0_realism_vs_idealized.md").write_text(delta_md, encoding="utf-8")

    meta = {
        "generated": str(date.today()),
        "config": {"tp1": None, "trail": TRAIL_MULT, "stop": INITIAL_STOP},
        "decision": decision,
        "bh_mar_ref": BH_MAR_REF,
        "mar_ratio_vs_bh": ratio_bh,
    }
    (OUT_DIR / "p0_realism_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(delta_md.encode("ascii", errors="replace").decode("ascii"))
    print(f"Wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
