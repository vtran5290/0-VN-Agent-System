#!/usr/bin/env python3
"""
D1 — Capitulation / floor-lock mean reversion sleeve (Phase D1).

RESEARCH_ONLY_NOT_PRODUCTION — no production promotion.

Signal: buy after N consecutive floor-lock days; entry on first unlock-day open.
P0 realism: next-open fills, floor/ceiling on exit, T+2 settlement, RT costs,
separate swept entry slippage.

Usage:
  python pp_backtest/sleeve_d1_capitulation.py --probe          # N=3 event count
  python pp_backtest/sleeve_d1_capitulation.py --sweep          # full 72-config grid
  python pp_backtest/sleeve_d1_capitulation.py                  # same as --sweep
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.b3_correlation import _build_equity_from_trades
from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.p0_realism_p1_winner import _build_honest_cache, _simulate_honest_trades
from pp_backtest.p3_rs_cashyield import _compute_rs_scores
from pp_backtest.phase_exit_sweep_core import (
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    YEAR_COLS,
    binary_gate_ema20_100,
)
from pp_backtest.portfolio_optimization_phase1 import (
    STRATEGY_CONFIGS,
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
from pp_backtest.sleeve_harness import (
    BUY_COMM,
    COST_RT_P0,
    SELL_COMM,
    SELL_TAX,
    SETTLEMENT_BDAY,
    SLIPPAGE_PENALTY,
    SleeveAdapter,
    adv_cap_binds,
    build_ohlcv_cache,
    earliest_exit_bar,
    is_floor_locked,
    net_return_from_gross,
    normalize_trades,
)

RESEARCH_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"
OUT_DIR = REPO / "data" / "research" / "portfolio_optimization" / "sleeve_d1"
SLEEVE_A3_DIR = REPO / "data" / "research" / "portfolio_optimization" / "p3_rs_cashyield"

SWEEP_N = (2, 3, 4)
SWEEP_ENTRY_SLIPPAGE = (0.005, 0.010, 0.015, 0.020)
SWEEP_CB_THRESHOLD = (0.10, 0.15, 0.20)
SWEEP_EXIT = ("D", "A")
DELIST_WINDOW = 60
MIN_UNIQUE_EVENTS = 100
CAPACITY_SIZES = (5e9, 10e9, 20e9)
UNCAPPED_PORTFOLIO_VND = 100e9


@dataclass(frozen=True)
class D1Config:
    n_floor_days: int
    entry_slippage: float
    cb_threshold: float
    exit_mode: Literal["D", "A"]

    @property
    def config_id(self) -> str:
        return (
            f"N{self.n_floor_days}_slip{self.entry_slippage:.3f}"
            f"_cb{int(self.cb_threshold * 100)}_{self.exit_mode}"
        )


@dataclass
class RawEvent:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    consecutive_floor_days: int
    last_floor_close: float
    unlock_open: float
    adv50: float


class D1CapitulationAdapter(SleeveAdapter):
    name = "D1"
    signal_family = "capitulation_floor_lock_mean_reversion"
    regime_gate_description = "None (all regimes); circuit-breaker suppresses mass-panic dates"

    def __init__(self, n_floor: int = 3, cb_threshold: float = 0.15, exit_mode: str = "D"):
        self.n_floor = n_floor
        self.cb_threshold = cb_threshold
        self.exit_mode = exit_mode

    def generate_trades(
        self, panel: pd.DataFrame, vnx: pd.DataFrame, gate: pd.Series
    ) -> pd.DataFrame:
        del vnx, gate
        adv = _build_adv50_map(panel)
        universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
        cache = build_ohlcv_cache(panel, universe)
        daily_frac = _build_daily_floor_fraction(cache, universe)
        events = scan_raw_events(cache, adv, daily_frac, self.n_floor, self.cb_threshold)
        events = apply_slot_rationing(events, MAX_POSITIONS)
        return _events_to_ideal_trades(events, cache, self.exit_mode)


def _build_daily_floor_fraction(
    cache: dict[str, dict], universe: set[str]
) -> dict[pd.Timestamp, float]:
    """Fraction of universe floor-locked on each date."""
    by_date: dict[pd.Timestamp, list[bool]] = {}
    for sym in universe:
        data = cache.get(sym)
        if data is None:
            continue
        close = data["close"]
        dates = data["dates"]
        for i in range(1, len(close)):
            dt = pd.Timestamp(dates[i]).normalize()
            locked = is_floor_locked(float(close[i]), float(close[i - 1]))
            by_date.setdefault(dt, []).append(locked)
    return {dt: float(np.mean(vals)) for dt, vals in by_date.items()}


def _precompute_symbol_floors(cache: dict[str, dict]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for sym, data in cache.items():
        close = data["close"]
        locked = np.zeros(len(close), dtype=bool)
        for i in range(1, len(close)):
            locked[i] = is_floor_locked(float(close[i]), float(close[i - 1]))
        out[sym] = locked
    return out


def scan_raw_events_fast(
    cache: dict[str, dict],
    adv50_map: dict,
    floor_locked: dict[str, np.ndarray],
    n_floor: int,
) -> list[RawEvent]:
    """Scan all break events without circuit-breaker (filter CB later)."""
    events: list[RawEvent] = []
    for sym, data in cache.items():
        close = data["close"]
        opn = data["open"]
        dates = data["dates"]
        locked = floor_locked[sym]
        n = len(close)
        streak = 0
        for i in range(1, n):
            if locked[i]:
                streak += 1
                continue
            if streak >= n_floor and i < n:
                signal_dt = pd.Timestamp(dates[i - 1]).normalize()
                adv50 = _adv50_at(adv50_map, sym, signal_dt)
                if adv50 > 0:
                    events.append(
                        RawEvent(
                            symbol=sym,
                            signal_date=signal_dt,
                            entry_date=pd.Timestamp(dates[i]).normalize(),
                            consecutive_floor_days=streak,
                            last_floor_close=float(close[i - 1]),
                            unlock_open=float(opn[i]),
                            adv50=adv50,
                        )
                    )
            streak = 0
    return events


def filter_events_by_cb(
    events: list[RawEvent],
    daily_floor_frac: dict[pd.Timestamp, float],
    cb_threshold: float,
) -> list[RawEvent]:
    return [
        e
        for e in events
        if daily_floor_frac.get(e.signal_date, 0.0) <= cb_threshold
    ]


def scan_raw_events(
    cache: dict[str, dict],
    adv50_map: dict,
    daily_floor_frac: dict[pd.Timestamp, float],
    n_floor: int,
    cb_threshold: float,
    *,
    apply_cb: bool = True,
) -> list[RawEvent]:
    events: list[RawEvent] = []
    for sym, data in cache.items():
        close = data["close"]
        opn = data["open"]
        dates = data["dates"]
        n = len(close)
        if n < n_floor + 5:
            continue

        streak = 0
        for i in range(1, n):
            if is_floor_locked(float(close[i]), float(close[i - 1])):
                streak += 1
                continue
            if streak >= n_floor and i < n:
                signal_dt = pd.Timestamp(dates[i - 1]).normalize()
                entry_dt = pd.Timestamp(dates[i]).normalize()
                if apply_cb:
                    frac = daily_floor_frac.get(signal_dt, 0.0)
                    if frac > cb_threshold:
                        streak = 0
                        continue
                adv50 = _adv50_at(adv50_map, sym, signal_dt)
                if adv50 <= 0:
                    streak = 0
                    continue
                events.append(
                    RawEvent(
                        symbol=sym,
                        signal_date=signal_dt,
                        entry_date=entry_dt,
                        consecutive_floor_days=streak,
                        last_floor_close=float(close[i - 1]),
                        unlock_open=float(opn[i]),
                        adv50=adv50,
                    )
                )
            streak = 0
    return events


def _adv50_at(adv50_map: dict, sym: str, dt: pd.Timestamp) -> float:
    s = adv50_map.get(sym)
    if s is None:
        return 0.0
    valid = s[s.index <= dt].dropna()
    return float(valid.iloc[-1]) if not valid.empty else 0.0


def apply_slot_rationing(events: list[RawEvent], max_slots: int) -> list[RawEvent]:
    if not events:
        return events
    df = pd.DataFrame([e.__dict__ for e in events])
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    kept: list[RawEvent] = []
    for _, grp in df.groupby("entry_date", sort=True):
        if len(grp) <= max_slots:
            kept.extend(RawEvent(**row) for row in grp.to_dict("records"))
            continue
        top = grp.sort_values(
            ["consecutive_floor_days", "adv50"],
            ascending=[False, False],
        ).head(max_slots)
        kept.extend(RawEvent(**row) for row in top.to_dict("records"))
    return kept


def _ideal_exit_index(
    close: np.ndarray,
    ma20: np.ndarray,
    entry_i: int,
    exit_mode: str,
) -> int:
    n = len(close)
    hard_cap = 20 if exit_mode == "D" else 10
    last_i = min(entry_i + hard_cap, n - 1)
    for j in range(entry_i + 1, last_i + 1):
        if exit_mode == "D" and j < len(ma20) and np.isfinite(ma20[j]):
            if close[j] >= ma20[j]:
                return j
    return last_i


def _events_to_ideal_trades(
    events: list[RawEvent],
    cache: dict[str, dict],
    exit_mode: str,
) -> pd.DataFrame:
    rows: list[dict] = []
    for ev in events:
        data = cache.get(ev.symbol)
        if data is None:
            continue
        dates = data["dates"]
        close = data["close"]
        entry_i = _date_index(dates, ev.entry_date)
        if entry_i is None:
            continue
        ma20 = pd.Series(close).rolling(20, min_periods=20).mean().values
        exit_i = _ideal_exit_index(close, ma20, entry_i, exit_mode)
        if exit_i <= entry_i:
            continue
        gross = float(close[exit_i] / close[entry_i] - 1.0) if close[entry_i] > 0 else np.nan
        rows.append(
            {
                "symbol": ev.symbol,
                "signal_date": ev.signal_date.date(),
                "entry_date": ev.entry_date.date(),
                "exit_date": pd.Timestamp(dates[exit_i]).date(),
                "ep1": float(close[entry_i]),
                "ep2": None,
                "blended_ep": float(close[entry_i]),
                "t1_frac": 0.5,
                "total_frac": 0.5,
                "has_pullback": False,
                "gross_return": gross,
                "net_return": gross - COST_RT_P0,
                "hold_bars": exit_i - entry_i,
                "exit_reason": f"d1_{exit_mode.lower()}_exit",
                "consecutive_floor_days": ev.consecutive_floor_days,
                "adv50_value": ev.adv50,
            }
        )
    return normalize_trades(pd.DataFrame(rows))


def _date_index(dates: np.ndarray, dt: pd.Timestamp) -> int | None:
    dt = pd.Timestamp(dt).normalize()
    for i, d in enumerate(dates):
        if pd.Timestamp(d).normalize() == dt:
            return i
    return None


def _is_delisted_within_window(
    dates: np.ndarray,
    entry_i: int,
    global_last: pd.Timestamp,
    window: int = DELIST_WINDOW,
) -> bool:
    sym_last = pd.Timestamp(dates[-1]).normalize()
    if sym_last >= global_last - pd.Timedelta(days=5):
        return False
    bars_remaining = len(dates) - entry_i - 1
    return bars_remaining <= window


def apply_d1_p0_reprice(
    ideal_trades: pd.DataFrame,
    ohlcv_cache: dict[str, dict],
    adv50_map: dict,
    *,
    entry_slippage: float,
    global_last: pd.Timestamp,
    portfolio_vnd: float = PORTFOLIO_VND,
) -> pd.DataFrame:
    """P0 reprice with separate entry slippage (unlock-day gap model)."""
    slot_vnd = portfolio_vnd / MAX_POSITIONS
    t1_target = slot_vnd * 0.5
    rows: list[dict] = []

    for _, tr in ideal_trades.iterrows():
        sym = str(tr["symbol"])
        data = ohlcv_cache.get(sym)
        if data is None:
            continue

        open_arr = data["open"]
        close_arr = data["close"]
        dates = data["dates"]
        n = len(dates)

        entry_dt = pd.Timestamp(tr["entry_date"]).normalize()
        exit_dt = pd.Timestamp(tr["exit_date"]).normalize()
        entry_i = _date_index(dates, entry_dt)
        exit_i = _date_index(dates, exit_dt)
        if entry_i is None or exit_i is None or entry_i >= n:
            continue

        if _is_delisted_within_window(dates, entry_i, global_last):
            rows.append(
                _trade_row_delisted(tr, sym, entry_dt, dates, entry_i, adv50_map, entry_slippage)
            )
            continue

        entry_px = float(open_arr[entry_i]) * (1.0 + entry_slippage)
        if entry_px <= 0 or np.isnan(entry_px):
            continue

        min_exit_i = earliest_exit_bar(dates, entry_i)
        target_exit_i = max(exit_i, min_exit_i)
        floor_delay = 0
        exit_delayed = False
        fill_i = target_exit_i + 1

        for k in range(target_exit_i, min(n - 1, target_exit_i + 10)):
            prior_c = close_arr[k - 1] if k > 0 else close_arr[k]
            if is_floor_locked(float(close_arr[k]), float(prior_c)):
                floor_delay += 1
                exit_delayed = True
                continue
            fill_i = k + 1
            break

        if fill_i >= n:
            fill_i = n - 1
        exit_px = float(open_arr[fill_i])
        if exit_px <= 0 or np.isnan(exit_px):
            continue

        gross = exit_px / entry_px - 1.0
        net = net_return_from_gross(gross)

        adv50 = _adv50_at(adv50_map, sym, entry_dt)
        binds = adv_cap_binds(adv50, t1_target)
        exit_slip = SLIPPAGE_PENALTY if (binds or exit_delayed) else 0.0
        net -= exit_slip

        rows.append(
            {
                "symbol": sym,
                "signal_date": tr.get("signal_date", pd.Timestamp(dates[entry_i - 1]).date()),
                "entry_date": entry_dt.date(),
                "exit_date": pd.Timestamp(dates[fill_i]).date(),
                "ep1": entry_px,
                "ep2": None,
                "blended_ep": entry_px,
                "t1_frac": tr.get("t1_frac", 0.5),
                "total_frac": tr.get("total_frac", 0.5),
                "has_pullback": False,
                "gross_return": gross,
                "net_return": net,
                "hold_bars": fill_i - entry_i,
                "exit_reason": tr.get("exit_reason", "d1_p0"),
                "adv50_value": adv50,
                "entry_slippage": entry_slippage,
                "exit_slippage_penalty": exit_slip,
                "floor_exit_delay_bars": floor_delay,
                "delisted": False,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df


def _trade_row_delisted(
    tr: pd.Series,
    sym: str,
    entry_dt: pd.Timestamp,
    dates: np.ndarray,
    entry_i: int,
    adv50_map: dict,
    entry_slippage: float,
) -> dict:
    exit_i = min(entry_i + DELIST_WINDOW, len(dates) - 1)
    return {
        "symbol": sym,
        "signal_date": tr.get("signal_date"),
        "entry_date": entry_dt.date(),
        "exit_date": pd.Timestamp(dates[exit_i]).date(),
        "ep1": np.nan,
        "ep2": None,
        "blended_ep": np.nan,
        "t1_frac": 0.5,
        "total_frac": 0.5,
        "has_pullback": False,
        "gross_return": -1.0,
        "net_return": -1.0,
        "hold_bars": exit_i - entry_i,
        "exit_reason": "delisted_punitive",
        "adv50_value": _adv50_at(adv50_map, sym, entry_dt),
        "entry_slippage": entry_slippage,
        "exit_slippage_penalty": 0.0,
        "floor_exit_delay_bars": 0,
        "delisted": True,
    }


def evaluate_d1_trades(
    trades: pd.DataFrame,
    adv50_map: dict,
    *,
    portfolio_vnd: float = PORTFOLIO_VND,
) -> dict[str, Any]:
    tagged = _tag_adv50(trades, adv50_map)
    eq_in = tagged.drop(columns=["ema_dist_at_entry", "rs_score_at_entry"], errors="ignore")
    eq, _liq = _build_equity_adv_capped_v2(
        eq_in,
        MAX_POSITIONS,
        portfolio_vnd,
        ADV_PARTICIPATION,
        GK_MULT,
        rank_col="consecutive_floor_days" if "consecutive_floor_days" in eq_in.columns else None,
    )
    m = portfolio_metrics(eq, eq_in) if not eq.empty else {}
    rets = trades["net_return"].dropna() if not trades.empty else pd.Series(dtype=float)
    avg_win = float(rets[rets > 0].mean()) if (rets > 0).any() else np.nan
    avg_loss = float(rets[rets < 0].mean()) if (rets < 0).any() else np.nan

    row: dict[str, Any] = {
        "mar_full": m.get("mar", np.nan),
        "cagr": m.get("cagr", np.nan),
        "max_dd": m.get("max_dd", np.nan),
        "win_rate": m.get("hit_rate", np.nan),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "n_trades": m.get("n_trades", len(trades)),
        "equity": eq,
    }
    for yr in YEAR_COLS:
        row[f"y{yr}"] = _annual_return(eq, yr) if not eq.empty else np.nan
    return row


def compute_ex_best_year_mar(eq: pd.Series) -> float:
    if eq.empty:
        return np.nan
    by_year = eq.groupby(eq.index.year).last().pct_change().dropna()
    if len(by_year) < 2:
        return np.nan
    best_y = by_year.idxmax()
    sub = eq[eq.index.year != best_y]
    if len(sub) < 5:
        return np.nan
    return float(portfolio_metrics(sub, pd.DataFrame()).get("mar", np.nan))


def compute_ex_years_mar(eq: pd.Series, exclude_years: set[int]) -> float:
    if eq.empty:
        return np.nan
    mask = ~eq.index.year.isin(exclude_years)
    sub = eq[mask]
    if len(sub) < 5:
        return np.nan
    m = portfolio_metrics(sub, pd.DataFrame())
    return float(m.get("mar", np.nan))


def compute_unlock_gap_distribution(events: list[RawEvent]) -> dict[str, Any]:
    gaps = []
    for ev in events:
        if ev.last_floor_close > 0 and ev.unlock_open > 0:
            gaps.append(ev.unlock_open / ev.last_floor_close - 1.0)
    if not gaps:
        return {"n": 0, "mean": np.nan, "median": np.nan, "p5": np.nan, "p95": np.nan}
    arr = np.array(gaps)
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p5": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
    }


def compute_a3_correlation(d1_trades: pd.DataFrame, adv: dict) -> dict[str, float]:
    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)]
    vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    honest_cache = _build_honest_cache(panel)
    a3_honest = _simulate_honest_trades(honest_cache, gate, adv)
    rs_scores = _compute_rs_scores(panel, a3_honest)
    a3_honest["rs_score"] = rs_scores
    a3_tagged = _tag_adv50(a3_honest.copy(), adv)
    eq_a3 = _build_equity_from_trades(
        a3_tagged.drop(columns=["ema_dist_at_entry"], errors="ignore"),
        rank_col="rs_score",
    )
    eq_d1 = _build_equity_from_trades(_tag_adv50(d1_trades.copy(), adv))

    combined = pd.DataFrame({"A3_RS": eq_a3, "D1": eq_d1}).dropna()
    if combined.empty or len(combined) < 20:
        return {"annual_corr": np.nan, "daily_corr": np.nan, "n_daily_obs": len(combined)}

    a3_ann = pd.read_csv(SLEEVE_A3_DIR / "p3_annual_returns.csv")
    d1_ann_years = d1_trades.copy()
    d1_ann_years["entry_date"] = pd.to_datetime(d1_ann_years["entry_date"])
    d1_by_year = (
        d1_ann_years.groupby(d1_ann_years["entry_date"].dt.year)["net_return"].mean()
        if not d1_ann_years.empty
        else pd.Series(dtype=float)
    )
    ann = pd.DataFrame({"year": a3_ann["year"], "A3_RS": a3_ann["rs_ranked"]})
    ann["D1"] = ann["year"].map(d1_by_year)
    ann = ann.dropna()
    annual_corr = float(ann[["A3_RS", "D1"]].corr().iloc[0, 1]) if len(ann) >= 3 else np.nan

    daily_ret = combined.pct_change().dropna()
    daily_corr = float(daily_ret["A3_RS"].corr(daily_ret["D1"])) if len(daily_ret) >= 10 else np.nan
    return {
        "annual_corr": annual_corr,
        "daily_corr": daily_corr,
        "n_daily_obs": int(len(daily_ret)),
    }


def evaluate_kill_criteria(
    best: dict[str, Any],
    slip_005: dict[str, Any],
    slip_010: dict[str, Any],
    corr: dict[str, float],
) -> dict[str, str]:
    mar = best.get("mar_full", np.nan)
    verdicts: dict[str, str] = {}

    verdicts["K1"] = "KILL" if (np.isfinite(mar) and mar <= 0) else "PASS"
    verdicts["K2"] = (
        "KILL"
        if (np.isfinite(corr.get("daily_corr", np.nan)) and corr["daily_corr"] > 0.4)
        else "PASS"
    )
    verdicts["K3"] = (
        "KILL"
        if (np.isfinite(corr.get("annual_corr", np.nan)) and corr["annual_corr"] > 0.6)
        else "PASS"
    )
    ex_best = best.get("mar_ex_best_year", np.nan)
    verdicts["K4"] = (
        "KILL"
        if (np.isfinite(mar) and np.isfinite(ex_best) and mar > 0 and ex_best < 0.5 * mar)
        else "PASS"
    )
    mar_005 = slip_005.get("mar_full", np.nan)
    mar_010 = slip_010.get("mar_full", np.nan)
    if np.isfinite(mar_005) and np.isfinite(mar_010) and mar_005 > 0:
        verdicts["K5"] = "KILL" if mar_010 < mar_005 * 0.5 else "PASS"
    else:
        verdicts["K5"] = "FLAG"

    mar_5b = best.get("mar_5b", np.nan)
    mar_uncapped = best.get("mar_uncapped", np.nan)
    if np.isfinite(mar_5b) and np.isfinite(mar_uncapped) and mar_uncapped > 0:
        decay = 1.0 - mar_5b / mar_uncapped
        verdicts["K6"] = "FLAG" if decay > 0.30 else "PASS"
    else:
        verdicts["K6"] = "FLAG"

    return verdicts


def run_config_sweep(
    cache: dict[str, dict],
    adv: dict,
    daily_frac: dict,
    global_last: pd.Timestamp,
    floor_locked: dict[str, np.ndarray],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict] = []
    events_by_n: dict[int, list[RawEvent]] = {
        n: scan_raw_events_fast(cache, adv, floor_locked, n) for n in SWEEP_N
    }
    ideal_cache: dict[tuple[int, float, str], tuple[pd.DataFrame, int, int]] = {}

    total = len(SWEEP_N) * len(SWEEP_ENTRY_SLIPPAGE) * len(SWEEP_CB_THRESHOLD) * len(SWEEP_EXIT)
    done = 0
    for cfg in itertools.product(SWEEP_N, SWEEP_ENTRY_SLIPPAGE, SWEEP_CB_THRESHOLD, SWEEP_EXIT):
        d1_cfg = D1Config(*cfg)
        done += 1
        if done % 12 == 0:
            print(f"  sweep {done}/{total} ...", flush=True)

        ide_key = (d1_cfg.n_floor_days, d1_cfg.cb_threshold, d1_cfg.exit_mode)
        if ide_key not in ideal_cache:
            raw = filter_events_by_cb(
                events_by_n[d1_cfg.n_floor_days], daily_frac, d1_cfg.cb_threshold
            )
            rationed = apply_slot_rationing(raw, MAX_POSITIONS)
            ideal = _events_to_ideal_trades(rationed, cache, d1_cfg.exit_mode)
            ideal_cache[ide_key] = (ideal, len(raw), len(rationed))
        ideal, raw_count, rationed_count = ideal_cache[ide_key]
        honest = apply_d1_p0_reprice(
            ideal,
            cache,
            adv,
            entry_slippage=d1_cfg.entry_slippage,
            global_last=global_last,
        )
        m = evaluate_d1_trades(honest, adv)
        eq = m.pop("equity", pd.Series(dtype=float))

        row = {
            "config_id": d1_cfg.config_id,
            "n_floor_days": d1_cfg.n_floor_days,
            "entry_slippage": d1_cfg.entry_slippage,
            "cb_threshold": d1_cfg.cb_threshold,
            "exit_mode": d1_cfg.exit_mode,
            "n_raw_events": raw_count,
            "n_trades_after_rationing": rationed_count,
            "n_honest_trades": len(honest),
            "research_label": RESEARCH_LABEL,
            **{k: v for k, v in m.items()},
        }
        row["mar_ex_best_year"] = compute_ex_best_year_mar(eq)
        row["mar_ex_2021_2022"] = compute_ex_years_mar(eq, {2021, 2022})
        for size in CAPACITY_SIZES:
            tag = f"mar_{int(size / 1e9)}b"
            ms = evaluate_d1_trades(honest, adv, portfolio_vnd=size)
            row[tag] = ms.get("mar_full", np.nan)
        mu = evaluate_d1_trades(honest, adv, portfolio_vnd=UNCAPPED_PORTFOLIO_VND)
        row["mar_uncapped"] = mu.get("mar_full", np.nan)
        rows.append(row)

    sweep_df = pd.DataFrame(rows)
    aux = {
        "events_by_n": {n: len(ev) for n, ev in events_by_n.items()},
        "unique_events_n3": len({(e.symbol, e.entry_date) for e in events_by_n.get(3, [])}),
    }
    return sweep_df, aux


def run_full_pipeline(out_dir: Path | None = None) -> dict[str, Any]:
    dest = out_dir or OUT_DIR
    dest.mkdir(parents=True, exist_ok=True)

    print("Loading panel...", flush=True)
    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)].copy()
    global_last = pd.Timestamp(panel["date"].max()).normalize()
    adv = _build_adv50_map(panel)
    universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
    print("Building OHLCV cache...", flush=True)
    cache = build_ohlcv_cache(panel, universe)
    print("Precomputing floor-lock flags...", flush=True)
    floor_locked = _precompute_symbol_floors(cache)
    daily_frac = _build_daily_floor_fraction(cache, universe)

    raw_n3 = scan_raw_events_fast(cache, adv, floor_locked, n_floor=3)
    gap_stats = compute_unlock_gap_distribution(raw_n3)
    unique_events = len({(e.symbol, e.entry_date) for e in raw_n3})
    print(f"D1 N=3 raw events (no CB): {len(raw_n3)} | unique (symbol, entry): {unique_events}")

    print("Running 72-config sweep...", flush=True)
    sweep_df, aux = run_config_sweep(cache, adv, daily_frac, global_last, floor_locked)
    sweep_df.to_csv(dest / "d1_sweep_summary.csv", index=False, float_format="%.6f")

    best_idx = sweep_df["mar_full"].astype(float).idxmax()
    best_row = sweep_df.loc[best_idx]
    best_cfg = D1Config(
        int(best_row["n_floor_days"]),
        float(best_row["entry_slippage"]),
        float(best_row["cb_threshold"]),
        str(best_row["exit_mode"]),
    )

    raw = filter_events_by_cb(
        scan_raw_events_fast(cache, adv, floor_locked, best_cfg.n_floor_days),
        daily_frac,
        best_cfg.cb_threshold,
    )
    rationed = apply_slot_rationing(raw, MAX_POSITIONS)
    ideal = _events_to_ideal_trades(rationed, cache, best_cfg.exit_mode)
    honest_best = apply_d1_p0_reprice(
        ideal, cache, adv, entry_slippage=best_cfg.entry_slippage, global_last=global_last
    )
    honest_best.to_csv(dest / "d1_honest_p0_trades.csv", index=False, float_format="%.6f")

    corr = compute_a3_correlation(honest_best, adv)

    slip_005_row = sweep_df[
        (sweep_df["n_floor_days"] == best_cfg.n_floor_days)
        & (sweep_df["cb_threshold"] == best_cfg.cb_threshold)
        & (sweep_df["exit_mode"] == best_cfg.exit_mode)
        & (np.isclose(sweep_df["entry_slippage"], 0.005))
    ]
    slip_010_row = sweep_df[
        (sweep_df["n_floor_days"] == best_cfg.n_floor_days)
        & (sweep_df["cb_threshold"] == best_cfg.cb_threshold)
        & (sweep_df["exit_mode"] == best_cfg.exit_mode)
        & (np.isclose(sweep_df["entry_slippage"], 0.010))
    ]
    slip_005 = slip_005_row.iloc[0].to_dict() if not slip_005_row.empty else {}
    slip_010 = slip_010_row.iloc[0].to_dict() if not slip_010_row.empty else {}

    best_dict = best_row.to_dict()
    best_eq = evaluate_d1_trades(honest_best, adv).get("equity", pd.Series(dtype=float))
    best_dict["mar_ex_best_year"] = compute_ex_best_year_mar(best_eq)
    kill = evaluate_kill_criteria(best_dict, slip_005, slip_010, corr)

    sample_flag = "DO-NOT-ADVANCE" if unique_events < MIN_UNIQUE_EVENTS else "OK"

    meta = {
        "generated": str(date.today()),
        "sleeve": "D1",
        "signal_family": "capitulation_floor_lock_mean_reversion",
        "production_status": RESEARCH_LABEL,
        "regime_gate": "None (circuit-breaker only)",
        "best_config": best_cfg.config_id,
        "honest_mar": float(best_row.get("mar_full", np.nan)),
        "honest_cagr": float(best_row.get("cagr", np.nan)),
        "honest_max_dd": float(best_row.get("max_dd", np.nan)),
        "honest_n_trades": int(best_row.get("n_honest_trades", 0)),
        "unique_d1_events_n3": unique_events,
        "sample_size_flag": sample_flag,
        "unlock_gap_distribution": gap_stats,
        "a3_correlation": corr,
        "kill_criteria": kill,
        "a3_baseline_mar": 0.381,
        "p0_realism": {
            "fills": "next_open",
            "entry_slippage_swept": list(SWEEP_ENTRY_SLIPPAGE),
            "exit_slippage_penalty": SLIPPAGE_PENALTY,
            "floor_ceiling_lock": True,
            "settlement_bdays": SETTLEMENT_BDAY,
            "cost_rt": BUY_COMM + SELL_COMM + SELL_TAX,
            "delisting_punitive": True,
        },
        "sweep_grid_size": len(sweep_df),
        "events_by_n": aux["events_by_n"],
    }
    (dest / "d1_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    report = _format_report(meta, sweep_df, kill, gap_stats)
    (dest / "d1_report.md").write_text(report, encoding="utf-8")
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return meta


def _format_report(
    meta: dict[str, Any],
    sweep_df: pd.DataFrame,
    kill: dict[str, str],
    gap: dict[str, Any],
) -> str:
    lines = [
        "# D1 Capitulation Sleeve — Gate Results",
        "",
        f"**Label:** {RESEARCH_LABEL}",
        f"**Sample size (unique N=3 events):** {meta['unique_d1_events_n3']} — **{meta['sample_size_flag']}**",
        "",
        "## Best config",
        f"- {meta['best_config']}",
        f"- MAR={meta['honest_mar']:.4f}, CAGR={meta['honest_cagr']:.4f}, "
        f"MaxDD={meta['honest_max_dd']:.4f}, n_trades={meta['honest_n_trades']}",
        "",
        "## Unlock-day gap distribution (prior floor close -> unlock open)",
        f"- n={gap['n']}, mean={gap.get('mean')}, median={gap.get('median')}, "
        f"p5={gap.get('p5')}, p95={gap.get('p95')}",
        "",
        "## A3 correlation",
        f"- annual={meta['a3_correlation'].get('annual_corr')}, "
        f"daily={meta['a3_correlation'].get('daily_corr')} "
        f"(n={meta['a3_correlation'].get('n_daily_obs')})",
        "",
        "## Kill criteria",
    ]
    for k, v in kill.items():
        lines.append(f"- **{k}:** {v}")
    lines.extend(["", "## Sweep top 5 by MAR", ""])
    top = sweep_df.nlargest(5, "mar_full")[
        ["config_id", "mar_full", "cagr", "max_dd", "n_honest_trades", "win_rate"]
    ]
    lines.append(top.to_string(index=False))
    return "\n".join(lines)


def probe_n3() -> int:
    panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)]
    adv = _build_adv50_map(panel)
    universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
    cache = build_ohlcv_cache(panel, universe)
    floor_locked = _precompute_symbol_floors(cache)
    events = scan_raw_events_fast(cache, adv, floor_locked, n_floor=3)
    unique = len({(e.symbol, e.entry_date) for e in events})
    print(f"N=3 floor-lock break events: {len(events)} (unique symbol-entry: {unique})")
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description="D1 capitulation floor-lock backtest")
    parser.add_argument("--probe", action="store_true", help="Print N=3 event count only")
    parser.add_argument("--sweep", action="store_true", help="Run full 72-config sweep")
    args = parser.parse_args()

    if args.probe:
        raise SystemExit(0 if probe_n3() > 0 else 1)
    run_full_pipeline()


if __name__ == "__main__":
    main()
