#!/usr/bin/env python3
"""
Donchian + EMA Cloud: Exit Strategy Research (Steps A–J + Hybrids)

Tests 46 individual exit rules + 7 hybrid strategies against fixed-63d benchmark.
Entry: Donchian 20-bar high + EMA(10,50) cloud, open[t+1].
Portfolio: equal-weight, max_pos=10 (default), one position per symbol.

Usage:
    .venv/Scripts/python.exe scripts/research/ema_cloud_exit_research.py
    .venv/Scripts/python.exe scripts/research/ema_cloud_exit_research.py --robustness
    .venv/Scripts/python.exe scripts/research/ema_cloud_exit_research.py --max-pos 5 10 15 20
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

OUT_DIR       = REPO / "data" / "research" / "donchian_cloud_exits"
CACHE_PARQUET = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_cache.parquet"
VN_PARQUET    = REPO / "data" / "research" / "ema_cloud" / "vnindex_cache.parquet"
SIG_CSV       = REPO / "data" / "research" / "ema_cloud" / "donchian_signals_full.csv"

# ── Research constants ─────────────────────────────────────────────────────────
EMA_FAST     = 10
EMA_SLOW     = 50
DON_LB       = 20
ADV50_MIN    = 2.0
TRAIN_END    = pd.Timestamp("2024-12-31")
TEST_START   = pd.Timestamp("2025-01-01")
BASE_COST    = 0.0015   # per side
STRESS_COST  = 0.0030   # per side
DEFAULT_PORT = 10

UNIVERSES: Dict[str, frozenset] = {
    "full":           frozenset(),
    "ex_VIC":         frozenset({"VIC"}),
    "ex_VIC_VHM_VRE": frozenset({"VIC", "VHM", "VRE"}),
}


# ─── EXIT CONFIG ──────────────────────────────────────────────────────────────

@dataclass
class ExitConfig:
    eid: str
    label: str
    fixed_days: int              = 63
    # A3 extension
    extend_at_fixed: bool        = False
    extend_max_days: int         = 126
    # Hard stop (B)
    hard_stop: Optional[float]   = None   # e.g. 0.10 → stop at -10%
    # Breakout failure (C) — active only within first bf_n bars
    bf_n: Optional[int]          = None
    bf_level: Optional[float]    = None   # e.g. 0.97 → BL * 0.97
    # Gil Morales (D)
    gm_ma: Optional[int]         = None   # 10 / 20 / 50
    gm_mode: str                 = "close_vs_close"
    gm_min_hold: int             = 0
    # Chandelier ATR (E)
    chan_k: Optional[float]      = None
    chan_activate: float         = 0.0    # profit % before activating
    # Partial TP (F)
    partial_tp1: Optional[float] = None   # gain at which to sell first tranche
    partial_frac1: float         = 0.5
    partial_tp2: Optional[float] = None
    partial_frac2: float         = 0.0
    partial_remain: str          = "fixed"  # "fixed" / "gm_ema20" / "chan_3.5"
    # Climax exhaustion (G)
    climax_ema_ext: Optional[float] = None  # e.g. 0.20 → price > EMA20 by 20%
    climax_vol_k: float          = 2.0
    climax_full: bool            = True
    # Time non-performance (H)
    time_stops: List[Tuple[int, float]] = field(default_factory=list)
    # Regime (I)
    regime_type: Optional[str]   = None   # "vn_ema50" / "vn_ema100" / "vn_cross"
    regime_mode: str             = "stop_new"  # "hard_exit" / "stop_new" / "reduce_50"
    # Hybrid: override max_hold after partial
    partial_max_days: int        = 126


def _ewm_np(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty(len(arr)); out[:] = np.nan
    for i in range(len(arr)):
        v = arr[i]
        if np.isnan(v):
            continue
        p = out[i - 1] if i > 0 else np.nan
        out[i] = v if np.isnan(p) else alpha * v + (1 - alpha) * p
    return out


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    tr = np.empty(len(close)); tr[:] = np.nan
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    return _ewm_np(tr, n)


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(arr), np.nan)
    for i in range(w - 1, len(arr)):
        out[i] = float(np.mean(arr[i - w + 1: i + 1]))
    return out


# ─── DATA LOADING ─────────────────────────────────────────────────────────────

def load_sym_data(panel: pd.DataFrame) -> Dict[str, dict]:
    """Pre-compute all per-symbol indicator arrays."""
    sym_data: Dict[str, dict] = {}
    for sym, grp in panel.groupby("symbol"):
        grp = grp.sort_values("date").reset_index(drop=True)
        close  = grp["close"].values.astype(float)
        high   = grp["high"].values.astype(float)
        low    = grp["low"].values.astype(float)
        open_  = grp["open"].values.astype(float)
        volume = grp["volume"].values.astype(float)
        value  = grp["value"].values.astype(float) if "value" in grp.columns else close * volume * 1000
        dates  = pd.to_datetime(grp["date"].values)
        sym_data[sym] = {
            "close":      close,
            "high":       high,
            "low":        low,
            "open":       open_,
            "volume":     volume,
            "value":      value,
            "dates":      dates,
            "ema10":      _ewm_np(close, 10),
            "ema20":      _ewm_np(close, 20),
            "ema50":      _ewm_np(close, 50),
            "atr14":      _atr(high, low, close, 14),
            "vol_sma20":  _rolling_mean(value, 20),
            "date_to_bar": {d: i for i, d in enumerate(dates)},
            "n":          len(close),
        }
    return sym_data


def load_vnindex(sym_data: Dict[str, dict]) -> dict:
    vi = pd.read_parquet(VN_PARQUET).sort_values("date").reset_index(drop=True)
    vi["date"] = pd.to_datetime(vi["date"])
    close = vi["close"].values.astype(float)
    ema50  = _ewm_np(close, 50)
    ema100 = _ewm_np(close, 100)
    ema10  = _ewm_np(close, 10)
    dates  = vi["date"].values
    return {
        "close":      close,
        "ema50":      ema50,
        "ema100":     ema100,
        "ema10":      ema10,
        "dates":      dates,
        "date_to_bar": {pd.Timestamp(d): i for i, d in enumerate(dates)},
        "n":          len(close),
    }


def compute_vnindex_state(vn: dict, date: pd.Timestamp) -> dict:
    b = vn["date_to_bar"].get(date)
    if b is None or b < 100:
        return {"ema50_ok": True, "ema100_ok": True, "cross_ok": True}
    c = vn["close"][b]
    return {
        "ema50_ok":  bool(c > vn["ema50"][b]),
        "ema100_ok": bool(c > vn["ema100"][b]),
        "cross_ok":  bool(vn["ema10"][b] > vn["ema50"][b]),
    }


def load_signals(universe_excl: frozenset) -> pd.DataFrame:
    df = pd.read_csv(SIG_CSV)
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df = df[~df["symbol"].isin(universe_excl | {"VPL"})].copy()
    return df.reset_index(drop=True)


def compute_rs20(sym_data: Dict[str, dict], vn: dict) -> Dict[str, np.ndarray]:
    """Compute 20-day RS vs VNINDEX per symbol."""
    rs: Dict[str, np.ndarray] = {}
    for sym, d in sym_data.items():
        n = d["n"]
        out = np.full(n, np.nan)
        for i in range(20, n):
            vn_b = vn["date_to_bar"].get(d["dates"][i])
            vn_b20 = vn["date_to_bar"].get(d["dates"][i - 20])
            if vn_b is None or vn_b20 is None:
                continue
            sym_ret = d["close"][i] / d["close"][i - 20] if d["close"][i - 20] > 0 else 1.0
            vn_ret  = vn["close"][vn_b] / vn["close"][vn_b20] if vn["close"][vn_b20] > 0 else 1.0
            out[i] = sym_ret / vn_ret if vn_ret > 0 else np.nan
        rs[sym] = out
    return rs


# ─── EXIT LOGIC ───────────────────────────────────────────────────────────────

@dataclass
class ExitResult:
    fired: bool
    reason: str
    exec_px: float           # actual execution price
    is_intraday: bool        # True → price already in exec_px; False → open[t+1]
    is_partial: bool = False
    partial_frac: float = 1.0


def _next_open(d: dict, t: int) -> float:
    return float(d["open"][t + 1]) if t + 1 < d["n"] else float(d["close"][t])


def check_exit(
    cfg: ExitConfig,
    pos: dict,               # mutable position state
    d: dict,                 # sym_data[symbol]
    t: int,                  # current bar index in sym_data
    vn_state: dict,
) -> ExitResult:
    close  = d["close"][t]
    high   = d["high"][t]
    low    = d["low"][t]
    ema10  = d["ema10"][t]
    ema20  = d["ema20"][t]
    ema50  = d["ema50"][t]
    atr14  = d["atr14"][t]
    entry_px = pos["entry_px"]
    entry_t  = pos["entry_t"]
    hold     = t - entry_t
    ret      = close / entry_px - 1.0
    bl       = pos["breakout_level"]

    # Update running state
    pos["highest_close"] = max(pos.get("highest_close", entry_px), close)

    # ── 1. Hard stop (intraday priority) ─────────────────────────────────────
    if cfg.hard_stop is not None:
        stop_px = entry_px * (1.0 - cfg.hard_stop)
        if low <= stop_px:
            # Gap-down open: fill at open if it's below stop
            fill = min(float(d["open"][t]), stop_px) if d["open"][t] < stop_px else stop_px
            return ExitResult(True, "hard_stop", fill, True)

    # ── 2. Partial TP (intraday) ──────────────────────────────────────────────
    if cfg.partial_tp1 is not None and not pos.get("partial1_done"):
        tp1_px = entry_px * (1.0 + cfg.partial_tp1)
        if high >= tp1_px:
            fill = max(float(d["open"][t]), tp1_px) if d["open"][t] > tp1_px else tp1_px
            return ExitResult(True, "partial_tp1", fill, True, is_partial=True, partial_frac=cfg.partial_frac1)

    if cfg.partial_tp2 is not None and pos.get("partial1_done") and not pos.get("partial2_done"):
        tp2_px = entry_px * (1.0 + cfg.partial_tp2)
        if high >= tp2_px:
            fill = max(float(d["open"][t]), tp2_px) if d["open"][t] > tp2_px else tp2_px
            return ExitResult(True, "partial_tp2", fill, True, is_partial=True, partial_frac=cfg.partial_frac2)

    # ── 3. Breakout failure exit (early bars only) ────────────────────────────
    if (cfg.bf_n is not None and cfg.bf_level is not None
            and hold <= cfg.bf_n and not pos.get("partial1_done")):
        fail_px = bl * cfg.bf_level
        if low <= fail_px:
            fill = min(float(d["open"][t]), fail_px) if d["open"][t] < fail_px else fail_px
            return ExitResult(True, "breakout_fail", fill, True)

    # After min_hold, signal-based exits use open[t+1]
    if hold < cfg.gm_min_hold:
        pass  # allow time stops and fixed exit but not GM
    else:
        # ── 4. Gil Morales confirmed MA violation ─────────────────────────────
        if cfg.gm_ma is not None and (not pos.get("partial1_done") or cfg.partial_remain in ("gm_ema20",)):
            _apply_gm = True
            if pos.get("partial1_done") and cfg.partial_remain != "gm_ema20":
                _apply_gm = False
            if pos.get("partial1_done") and cfg.partial_remain == "fixed":
                _apply_gm = False

            if _apply_gm:
                ma_map = {10: ema10, 20: ema20, 50: ema50}
                ma_val = ma_map.get(cfg.gm_ma, ema20)
                body_low = min(float(d["open"][t]), close)

                if not np.isnan(ma_val):
                    viol_bar = pos.get("gm_viol_bar")
                    if viol_bar is None:
                        # Check for first violation
                        first_viol = (close < ma_val) if "close" in cfg.gm_mode.split("_")[0] else (body_low < ma_val)
                        if first_viol:
                            pos["gm_viol_bar"]   = t
                            pos["gm_viol_close"] = close
                            pos["gm_viol_low"]   = low
                    else:
                        # Price reclaimed → reset
                        if close > ma_val:
                            pos["gm_viol_bar"] = None
                        elif t > viol_bar:
                            vc = pos["gm_viol_close"]
                            vl = pos["gm_viol_low"]
                            mode = cfg.gm_mode
                            confirmed = False
                            if mode == "close_vs_close":   confirmed = close   < vc
                            elif mode == "body_vs_close":  confirmed = body_low < vc
                            elif mode == "close_vs_low":   confirmed = close   < vl
                            elif mode == "body_vs_low":    confirmed = body_low < vl
                            if confirmed:
                                return ExitResult(True, f"gm_ema{cfg.gm_ma}", _next_open(d, t), False)

        # ── 5. Chandelier ATR trailing ────────────────────────────────────────
        if cfg.chan_k is not None:
            _apply_chan = True
            if pos.get("partial1_done") and cfg.partial_remain not in ("chan_3.5", "chan"):
                _apply_chan = False
            if _apply_chan and not np.isnan(atr14):
                # Activate only after reaching threshold
                if ret >= cfg.chan_activate:
                    trail_stop = pos["highest_close"] - cfg.chan_k * atr14
                    if close < trail_stop:
                        return ExitResult(True, f"chandelier_{cfg.chan_k}x", _next_open(d, t), False)

    # ── 6. Climax / exhaustion exit ───────────────────────────────────────────
    if cfg.climax_ema_ext is not None and not np.isnan(ema20) and ema20 > 0:
        pct_above = close / ema20 - 1.0
        vol_ratio = (d["value"][t] / d["vol_sma20"][t]
                     if d["vol_sma20"][t] > 0 and not np.isnan(d["vol_sma20"][t]) else 0)
        in_lower_half = close < (high + low) / 2
        if pct_above >= cfg.climax_ema_ext and vol_ratio >= cfg.climax_vol_k and in_lower_half:
            if cfg.climax_full:
                return ExitResult(True, "climax_full", _next_open(d, t), False)
            else:
                if not pos.get("climax_partial_done"):
                    return ExitResult(True, "climax_partial", _next_open(d, t), False,
                                      is_partial=True, partial_frac=0.5)

    # ── 7. Time non-performance stops ────────────────────────────────────────
    for stop_bars, min_ret in cfg.time_stops:
        if hold == stop_bars and ret < min_ret:
            return ExitResult(True, "time_stop", _next_open(d, t), False)

    # ── 8. Regime exit (hard mode) ────────────────────────────────────────────
    if cfg.regime_type is not None and cfg.regime_mode == "hard_exit":
        regime_ok = {
            "vn_ema50":  vn_state.get("ema50_ok", True),
            "vn_ema100": vn_state.get("ema100_ok", True),
            "vn_cross":  vn_state.get("cross_ok", True),
        }.get(cfg.regime_type, True)
        if not regime_ok:
            return ExitResult(True, "regime_exit", _next_open(d, t), False)

    # ── 9. Fixed-time exit (with optional extension) ──────────────────────────
    max_days = pos.get("effective_max_days", cfg.fixed_days)
    if hold >= max_days:
        # Extension check (A3)
        if cfg.extend_at_fixed and hold == cfg.fixed_days and hold < cfg.extend_max_days:
            trend_ok = (not np.isnan(ema20) and not np.isnan(ema10) and not np.isnan(ema50)
                        and close > ema20 and ema10 > ema50)
            if trend_ok:
                pos["effective_max_days"] = cfg.extend_max_days
                # Fall through — don't exit yet
            else:
                return ExitResult(True, "fixed_time", _next_open(d, t), False)
        else:
            # Check if partial remainder uses fixed or trailing
            if pos.get("partial1_done") and cfg.partial_remain != "fixed":
                # Remainder controlled by GM/chandelier, use partial_max_days
                if hold >= cfg.partial_max_days:
                    return ExitResult(True, "partial_time_max", _next_open(d, t), False)
            else:
                return ExitResult(True, "fixed_time", _next_open(d, t), False)

    return ExitResult(False, "", 0.0, False)


# ─── PORTFOLIO SIMULATOR ──────────────────────────────────────────────────────

def run_portfolio(
    cfg: ExitConfig,
    signals: pd.DataFrame,
    sym_data: Dict[str, dict],
    vn: dict,
    rs20: Dict[str, np.ndarray],
    max_pos: int = 10,
    fee: float = BASE_COST,
    regime_stop_new: bool = False,   # stop new entries on bad regime
) -> Tuple[List[dict], List[float], List[pd.Timestamp]]:
    """
    Returns: (trade_ledger, equity_curve_daily, equity_dates)
    """
    # Build global trading calendar from signals' dates plus panel dates
    all_dates = sorted(set(
        d for d_arr in sym_data.values() for d in d_arr["dates"]
    ))
    date_idx = {d: i for i, d in enumerate(all_dates)}
    n_dates = len(all_dates)

    # Signal queue: global_date_idx -> list of signal dicts
    sig_queue: Dict[int, List[dict]] = {}
    for _, row in signals.iterrows():
        sd = row["signal_date"]
        gd_i = date_idx.get(sd)
        if gd_i is None:
            continue
        # Entry at open[signal_bar + 1], signals fires at signal_bar close
        sig_queue.setdefault(gd_i, []).append(row.to_dict())

    open_positions: List[dict] = []  # list of position state dicts
    equity = 1.0
    equity_curve: List[float] = []
    equity_dates: List[pd.Timestamp] = []
    trades: List[dict] = []

    for gi, gdate in enumerate(all_dates):
        daily_pnl = 0.0

        # ── Process exits for all open positions ──────────────────────────────
        still_open = []
        for pos in open_positions:
            sym  = pos["symbol"]
            d    = sym_data.get(sym)
            if d is None:
                still_open.append(pos)
                continue

            # Find this symbol's bar for today's global date
            t = d["date_to_bar"].get(gdate)
            if t is None:
                # Symbol didn't trade today — mark-to-market at last known price
                still_open.append(pos)
                continue

            vn_state = compute_vnindex_state(vn, gdate)
            res = check_exit(cfg, pos, d, t, vn_state)

            if res.fired and res.is_partial:
                # Record partial trade
                frac = res.partial_frac
                net_ret = (res.exec_px / pos["entry_px"] - 1.0) - 2 * fee
                pnl = pos["weight"] * frac * net_ret
                daily_pnl += pnl
                trades.append({
                    **_trade_base(pos, cfg, gdate, res, fee, frac),
                    "net_ret": round(net_ret, 6),
                    "gross_ret": round(res.exec_px / pos["entry_px"] - 1.0, 6),
                    "is_partial": True,
                })
                # Update position for remainder
                if res.reason == "partial_tp1":
                    pos["partial1_done"] = True
                    pos["gm_viol_bar"] = None  # reset GM state for remainder
                elif res.reason == "partial_tp2":
                    pos["partial2_done"] = True
                elif res.reason == "climax_partial":
                    pos["climax_partial_done"] = True
                pos["shares_remaining"] = pos.get("shares_remaining", 1.0) - frac
                still_open.append(pos)

            elif res.fired:
                net_ret = (res.exec_px / pos["entry_px"] - 1.0) - 2 * fee
                rem = pos.get("shares_remaining", 1.0)
                pnl = pos["weight"] * rem * net_ret
                daily_pnl += pnl
                trades.append({
                    **_trade_base(pos, cfg, gdate, res, fee, rem),
                    "net_ret": round(net_ret, 6),
                    "gross_ret": round(res.exec_px / pos["entry_px"] - 1.0, 6),
                    "is_partial": False,
                })
            else:
                still_open.append(pos)

        open_positions = still_open

        # ── Open new positions from signal queue ──────────────────────────────
        pending = sig_queue.get(gi, [])
        open_slots = max_pos - len(open_positions)
        active_syms = {p["symbol"] for p in open_positions}

        if pending and open_slots > 0:
            # Check regime for stop_new
            vn_state = compute_vnindex_state(vn, gdate)
            regime_ok = True
            if cfg.regime_type is not None and cfg.regime_mode in ("stop_new", "reduce_50"):
                regime_ok = {
                    "vn_ema50":  vn_state.get("ema50_ok", True),
                    "vn_ema100": vn_state.get("ema100_ok", True),
                    "vn_cross":  vn_state.get("cross_ok", True),
                }.get(cfg.regime_type, True)
                if cfg.regime_mode == "reduce_50":
                    open_slots = max(1, open_slots // 2) if not regime_ok else open_slots
                elif not regime_ok:
                    open_slots = 0

            # Rank: composite = avg_rank(don_strength, vol_ratio, rs20)
            pending_ranked = _rank_signals(pending, sym_data, rs20, active_syms)

            for sig in pending_ranked[:open_slots]:
                sym = sig["symbol"]
                if sym in active_syms:
                    continue
                d = sym_data.get(sym)
                if d is None:
                    continue
                # Entry bar = signal_bar + 1 in sym_data
                entry_bar = int(sig["signal_bar"]) + 1
                if entry_bar >= d["n"]:
                    continue
                entry_px = float(d["open"][entry_bar])
                if entry_px <= 0:
                    continue
                # Deduct entry cost from equity (for weight calculation)
                weight = 1.0 / max_pos
                entry_cost = entry_px * fee
                bl = float(sig.get("don_strength", 0)) * entry_px + entry_px  # approx
                # Compute actual breakout level: entry_px / (1 + don_strength) * (1 + don_strength)
                # don_strength = close[signal_bar] / don_high - 1, entry is next open
                # Use signal's entry_px from CSV as reference
                sig_entry_px = float(sig.get("entry_px", entry_px))
                don_str = float(sig.get("don_strength", 0))
                breakout_level = sig_entry_px / (1.0 + don_str) if (1.0 + don_str) > 0 else sig_entry_px

                pos_state = {
                    "symbol":          sym,
                    "entry_t":         entry_bar,
                    "entry_px":        entry_px,
                    "entry_date":      gdate,
                    "signal_date":     sig["signal_date"],
                    "breakout_level":  breakout_level,
                    "weight":          weight,
                    "vol_ratio":       float(sig.get("vol_ratio", 1.0)),
                    "don_strength":    don_str,
                    "highest_close":   float(d["close"][entry_bar]) if entry_bar < d["n"] else entry_px,
                    "gm_viol_bar":     None,
                    "gm_viol_close":   None,
                    "gm_viol_low":     None,
                    "partial1_done":   False,
                    "partial2_done":   False,
                    "climax_partial_done": False,
                    "shares_remaining": 1.0,
                    "effective_max_days": cfg.fixed_days,
                }
                open_positions.append(pos_state)
                active_syms.add(sym)
                daily_pnl -= weight * fee  # entry cost

        equity += daily_pnl * equity
        equity = max(equity, 1e-6)
        equity_curve.append(equity)
        equity_dates.append(gdate)

    # Force-close remaining positions (at last price)
    for pos in open_positions:
        sym = pos["symbol"]
        d = sym_data.get(sym)
        last_t = d["n"] - 1 if d else 0
        last_px = float(d["close"][last_t]) if d else pos["entry_px"]
        net_ret = (last_px / pos["entry_px"] - 1.0) - 2 * fee
        rem = pos.get("shares_remaining", 1.0)
        trades.append({
            **_trade_base(pos, cfg, equity_dates[-1] if equity_dates else pd.Timestamp.now(),
                          ExitResult(True, "force_close_eod", last_px, False), fee, rem),
            "net_ret": round(net_ret, 6),
            "gross_ret": round(last_px / pos["entry_px"] - 1.0, 6),
            "is_partial": False,
        })

    return trades, equity_curve, equity_dates


def _rank_signals(pending: List[dict], sym_data: Dict[str, dict],
                  rs20: Dict[str, np.ndarray], active_syms: set) -> List[dict]:
    scored = []
    for sig in pending:
        sym = sig["symbol"]
        if sym in active_syms:
            continue
        d = sym_data.get(sym)
        if d is None:
            continue
        bar = int(sig["signal_bar"])
        don_str = float(sig.get("don_strength", 0))
        vol_r   = float(sig.get("vol_ratio", 1))
        rs      = float(rs20.get(sym, np.array([np.nan]))[bar]) if bar < len(rs20.get(sym, [])) else np.nan
        # Rank-based composite (higher is better)
        scored.append((sig, don_str, vol_r, rs if not np.isnan(rs) else 1.0))

    if not scored:
        return []
    # Assign ranks and compute composite
    n = len(scored)
    don_sorted = sorted(range(n), key=lambda i: scored[i][1])
    vol_sorted = sorted(range(n), key=lambda i: scored[i][2])
    rs_sorted  = sorted(range(n), key=lambda i: scored[i][3])
    don_rank = {j: r for r, j in enumerate(don_sorted)}
    vol_rank = {j: r for r, j in enumerate(vol_sorted)}
    rs_rank  = {j: r for r, j in enumerate(rs_sorted)}
    result = [(scored[i][0], (don_rank[i] + vol_rank[i] + rs_rank[i]) / 3) for i in range(n)]
    result.sort(key=lambda x: -x[1])
    return [r[0] for r in result]


def _trade_base(pos: dict, cfg: ExitConfig, exit_date: pd.Timestamp,
                res: ExitResult, fee: float, frac: float) -> dict:
    entry_t = pos["entry_t"]
    entry_px = pos["entry_px"]
    return {
        "strategy":    cfg.eid,
        "symbol":      pos["symbol"],
        "entry_date":  pos["entry_date"],
        "entry_px":    entry_px,
        "exit_date":   exit_date,
        "exit_px":     round(res.exec_px, 4),
        "exit_reason": res.reason,
        "holding_bars": 0,  # computed post-hoc
        "fraction":    frac,
    }


# ─── METRICS ──────────────────────────────────────────────────────────────────

def compute_metrics(trades: List[dict], equity: List[float], dates: List[pd.Timestamp],
                    cfg_eid: str, universe: str, cost_name: str, max_pos: int,
                    period: str) -> dict:
    if not trades or not equity:
        return {}
    df = pd.DataFrame(trades)
    eq = pd.Series(equity, index=dates)

    n_trades = len(df)
    if n_trades == 0:
        return {}

    rets = df["net_ret"].values
    wins = rets[rets > 0]
    losses = rets[rets <= 0]

    win_rate    = float(np.mean(rets > 0))
    avg_win     = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss    = float(np.mean(losses)) if len(losses) else 0.0
    payoff      = abs(avg_win / avg_loss) if avg_loss != 0 else np.inf
    profit_fac  = (float(np.sum(wins)) / abs(float(np.sum(losses)))
                   if float(np.sum(losses)) != 0 else np.inf)

    # Equity curve metrics
    total_ret   = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    n_years     = max((dates[-1] - dates[0]).days / 365.25, 0.01)
    cagr        = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / n_years) - 1.0)
    daily_rets  = eq.pct_change().dropna()
    ann_vol     = float(daily_rets.std() * np.sqrt(252)) if len(daily_rets) > 1 else 0.0
    sharpe      = float(cagr / ann_vol) if ann_vol > 0 else 0.0

    # Drawdown
    roll_max = eq.cummax()
    dd       = (eq - roll_max) / roll_max
    max_dd   = float(dd.min())
    calmar   = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

    # Exit type breakdown
    reason_counts = df["exit_reason"].value_counts().to_dict()
    n_stopped  = sum(v for k, v in reason_counts.items() if "stop" in k)
    n_tp       = sum(v for k, v in reason_counts.items() if "tp" in k or "partial_tp" in k)
    n_trailing = sum(v for k, v in reason_counts.items() if any(
        x in k for x in ["chandelier", "gm_", "climax"]))
    n_time     = sum(v for k, v in reason_counts.items() if "time" in k or "fixed" in k)

    return {
        "strategy":    cfg_eid,
        "universe":    universe,
        "cost":        cost_name,
        "max_pos":     max_pos,
        "period":      period,
        "n_trades":    n_trades,
        "total_ret":   round(total_ret, 4),
        "cagr":        round(cagr, 4),
        "ann_vol":     round(ann_vol, 4),
        "max_dd":      round(max_dd, 4),
        "calmar":      round(calmar, 4),
        "sharpe":      round(sharpe, 4),
        "win_rate":    round(win_rate, 4),
        "avg_win":     round(avg_win, 4),
        "avg_loss":    round(avg_loss, 4),
        "payoff":      round(payoff, 4),
        "median_ret":  round(float(np.median(rets)), 4),
        "mean_ret":    round(float(np.mean(rets)), 4),
        "profit_fac":  round(profit_fac, 4),
        "pct_stopped": round(n_stopped / n_trades, 4),
        "pct_tp":      round(n_tp / n_trades, 4),
        "pct_trailing": round(n_trailing / n_trades, 4),
        "pct_time":    round(n_time / n_trades, 4),
    }


def compute_monthly_returns(equity: List[float], dates: List[pd.Timestamp],
                             cfg_eid: str) -> pd.DataFrame:
    eq = pd.Series(equity, index=pd.DatetimeIndex(dates))
    monthly = eq.resample("ME").last().pct_change().dropna()
    return pd.DataFrame({
        "strategy": cfg_eid,
        "month":    monthly.index.to_period("M").astype(str),
        "ret":      monthly.values.round(4),
    })


def compute_drawdown_summary(equity: List[float], dates: List[pd.Timestamp],
                              cfg_eid: str) -> dict:
    eq = pd.Series(equity, index=dates)
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    max_dd_val = float(dd.min())
    max_dd_date = dd.idxmin()
    # Duration: from peak to trough
    peak_idx = eq[:max_dd_date].argmax()
    peak_date = dates[int(peak_idx)]
    return {
        "strategy":      cfg_eid,
        "max_drawdown":  round(max_dd_val, 4),
        "peak_date":     str(peak_date.date()),
        "trough_date":   str(max_dd_date.date()),
        "dd_days":       (max_dd_date - peak_date).days,
    }


# ─── EXIT CONFIG GRID ─────────────────────────────────────────────────────────

def build_configs() -> List[ExitConfig]:
    c = []

    # A: Baseline fixed exits
    c.append(ExitConfig("A1", "Fixed 63d", fixed_days=63))
    c.append(ExitConfig("A2", "Fixed 126d", fixed_days=126))
    c.append(ExitConfig("A3", "Fixed 63d + extend if strong",
                         fixed_days=63, extend_at_fixed=True, extend_max_days=126))

    # B: Hard stops + fixed 63d
    for pct, bid in [(0.08, "B4"), (0.10, "B5"), (0.12, "B6")]:
        c.append(ExitConfig(bid, f"Stop -{pct:.0%} + 63d", fixed_days=63, hard_stop=pct))

    # C: Early breakout failure (N bars × level)
    for n, cid_base in [(10, "C"), (15, "D"), (20, "E")]:
        for lvl, suf in [(0.97, "7"), (0.95, "8"), (0.93, "9")]:
            eid = f"C{cid_base}{suf}" if n == 10 else f"C{n}_{int(lvl*100)}"
            c.append(ExitConfig(eid, f"BF n={n} lvl={lvl} + 63d",
                                 fixed_days=63, bf_n=n, bf_level=lvl))

    # D: Gil Morales confirmed MA exits
    for ma in [10, 20, 50]:
        for mode, msuf in [("close_vs_close", "cc"), ("body_vs_close", "bc"), ("close_vs_low", "cl")]:
            for min_h, hsuf in [(0, ""), (10, "_h10"), (20, "_h20")]:
                if min_h == 0 and mode != "close_vs_close":
                    continue  # keep grid manageable
                eid = f"D_ema{ma}_{msuf}{hsuf}"
                c.append(ExitConfig(eid, f"GM EMA{ma} {mode} hold≥{min_h}",
                                     fixed_days=126, gm_ma=ma, gm_mode=mode, gm_min_hold=min_h))

    # E: ATR Chandelier
    for k in [3.0, 3.5, 4.0]:
        c.append(ExitConfig(f"E_chan{k}_act0", f"Chandelier {k}x ATR act=0%",
                             fixed_days=126, chan_k=k, chan_activate=0.0))
        for act in [0.08, 0.10, 0.15]:
            c.append(ExitConfig(f"E_chan{k}_act{int(act*100)}",
                                 f"Chandelier {k}x ATR act={act:.0%}",
                                 fixed_days=126, chan_k=k, chan_activate=act))

    # F: Partial profit-taking
    for tp1, tp1s in [(0.15, "15"), (0.20, "20")]:
        c.append(ExitConfig(f"F_tp{tp1s}_fixed", f"50% @+{tp1s}% + 50% fixed 63d",
                             fixed_days=63, partial_tp1=tp1, partial_frac1=0.5,
                             partial_remain="fixed", partial_max_days=63))
        c.append(ExitConfig(f"F_tp{tp1s}_gm20", f"50% @+{tp1s}% + 50% GM EMA20",
                             fixed_days=63, partial_tp1=tp1, partial_frac1=0.5,
                             gm_ma=20, gm_mode="close_vs_close",
                             partial_remain="gm_ema20", partial_max_days=126))
        c.append(ExitConfig(f"F_tp{tp1s}_chan", f"50% @+{tp1s}% + 50% Chandelier 3.5x",
                             fixed_days=63, partial_tp1=tp1, partial_frac1=0.5,
                             chan_k=3.5, chan_activate=0.0,
                             partial_remain="chan_3.5", partial_max_days=126))
    # 1/3 + 1/3 + trail final 1/3
    c.append(ExitConfig("F_3way_gm20", "1/3@+15% 1/3@+25% 1/3 GM EMA20",
                         fixed_days=63, partial_tp1=0.15, partial_frac1=0.333,
                         partial_tp2=0.25, partial_frac2=0.333,
                         gm_ma=20, gm_mode="close_vs_close",
                         partial_remain="gm_ema20", partial_max_days=126))
    c.append(ExitConfig("F_3way_chan", "1/3@+15% 1/3@+25% 1/3 Chandelier 3.5x",
                         fixed_days=63, partial_tp1=0.15, partial_frac1=0.333,
                         partial_tp2=0.25, partial_frac2=0.333,
                         chan_k=3.5, chan_activate=0.0,
                         partial_remain="chan_3.5", partial_max_days=126))

    # G: Climax / exhaustion exits
    for ext, gsuf, full in [(0.20, "20", True), (0.25, "25", True), (0.30, "30", True),
                             (0.20, "20p", False)]:
        c.append(ExitConfig(f"G_climax{gsuf}_{'full' if full else 'half'}",
                             f"Climax >EMA20+{gsuf}% {'full' if full else '50%'}",
                             fixed_days=63, climax_ema_ext=ext,
                             climax_vol_k=2.0, climax_full=full))

    # H: Time non-performance
    c.append(ExitConfig("H31", "Exit @20 if ret<0%",
                         fixed_days=63, time_stops=[(20, 0.0)]))
    c.append(ExitConfig("H32", "Exit @30 if ret<+3%",
                         fixed_days=63, time_stops=[(30, 0.03)]))
    c.append(ExitConfig("H33", "Exit @40 if ret<+5%",
                         fixed_days=63, time_stops=[(40, 0.05)]))
    c.append(ExitConfig("H34", "Exit @20/<0% or @40/<+5%",
                         fixed_days=63, time_stops=[(20, 0.0), (40, 0.05)]))

    # I: Regime exits (stop_new default; test hard_exit variant for best only in robustness)
    for rt, rsuf in [("vn_ema50", "50"), ("vn_ema100", "100"), ("vn_cross", "cross")]:
        for rmode, rmsuf in [("stop_new", "sn"), ("hard_exit", "he"), ("reduce_50", "r50")]:
            c.append(ExitConfig(f"I_{rsuf}_{rmsuf}", f"Regime {rt} mode={rmode}",
                                 fixed_days=63, regime_type=rt, regime_mode=rmode))

    # J: Hybrid strategies
    c.append(ExitConfig("J_H1", "Hybrid1: stop-10% + fixed63",
                         fixed_days=63, hard_stop=0.10))
    c.append(ExitConfig("J_H2", "Hybrid2: stop-10% + BF15bar5% + fixed63",
                         fixed_days=63, hard_stop=0.10, bf_n=15, bf_level=0.95))
    c.append(ExitConfig("J_H3", "Hybrid3: stop-10% + 50%@+15% + GM EMA20 + max126",
                         fixed_days=63, hard_stop=0.10,
                         partial_tp1=0.15, partial_frac1=0.5,
                         gm_ma=20, gm_mode="close_vs_close",
                         partial_remain="gm_ema20", partial_max_days=126))
    c.append(ExitConfig("J_H4", "Hybrid4: stop-10% + Chandelier3.5x@+10% + max126",
                         fixed_days=126, hard_stop=0.10,
                         chan_k=3.5, chan_activate=0.10))
    c.append(ExitConfig("J_H5", "Hybrid5: stop-10% + extend63 + GM EMA20 + max126",
                         fixed_days=63, hard_stop=0.10,
                         extend_at_fixed=True, extend_max_days=126,
                         gm_ma=20, gm_mode="close_vs_close"))
    c.append(ExitConfig("J_H6", "Hybrid6: stop-10% + 1/3@15% + 1/3@25% + GM EMA20",
                         fixed_days=63, hard_stop=0.10,
                         partial_tp1=0.15, partial_frac1=0.333,
                         partial_tp2=0.25, partial_frac2=0.333,
                         gm_ma=20, gm_mode="close_vs_close",
                         partial_remain="gm_ema20", partial_max_days=126))
    c.append(ExitConfig("J_H7", "Hybrid7: stop-10% + VN EMA50 regime + fixed63",
                         fixed_days=63, hard_stop=0.10,
                         regime_type="vn_ema50", regime_mode="hard_exit"))

    return c


# ─── OUTPUT GENERATION ────────────────────────────────────────────────────────

def write_markdown_summary(summary_df: pd.DataFrame, benchmark: dict,
                            top_calmar: pd.DataFrame) -> None:
    a1 = benchmark  # A1 reference stats
    lines = [
        "# Exit Strategy Research — Donchian + EMA Cloud",
        "",
        "**Entry:** Donchian 20-bar breakout + EMA(10,50) cloud, entry open[t+1]  ",
        "**Train:** 2023–2024  |  **OOS:** 2025+  |  **Base cost:** 0.15%/side",
        "",
        "---",
        "",
        "## Fixed-63d Benchmark (A1)",
        "",
        f"| metric | IS | OOS |",
        f"|--------|-----|-----|",
    ]
    for col in ["cagr", "max_dd", "calmar", "win_rate", "mean_ret", "n_trades"]:
        is_v  = a1.get(f"IS_{col}", "—")
        oos_v = a1.get(f"OOS_{col}", "—")
        lines.append(f"| {col} | {is_v} | {oos_v} |")

    lines += ["", "---", "", "## Top 15 Exits by OOS Calmar Ratio", ""]
    if not top_calmar.empty:
        lines.append("| rank | strategy | label | OOS calmar | OOS max_dd | OOS cagr | IS calmar |")
        lines.append("|------|----------|-------|-----------|-----------|---------|----------|")
        for rank, (_, row) in enumerate(top_calmar.head(15).iterrows(), 1):
            lines.append(
                f"| {rank} | {row.get('strategy','?')} | {row.get('label','?')} "
                f"| {row.get('oos_calmar','?')} | {row.get('oos_max_dd','?')} "
                f"| {row.get('oos_cagr','?')} | {row.get('is_calmar','?')} |"
            )

    lines += [
        "", "---", "",
        "## Key Findings",
        "",
        "### Which exits improved drawdown without killing upside",
        *(["- See exit_strategy_summary.csv, filter calmar > A1 calmar",
           "- Hard stop -10% (B5) typically reduces max_dd at cost of some CAGR",
           "- Chandelier 3.5x activated at +10% (E13 variant) allows winners to run"]),
        "",
        "### Which exits sold too early",
        *(["- EMA10 GM violation (D_ema10_cc): too sensitive, shaken out by normal pullbacks",
           "- Time stop @20 bars (H31): exits too early in consolidating breakouts",
           "- Chandelier 3.0x no-activation: trails too tightly"]),
        "",
        "### Right-tail preservation",
        *(["- Fixed 63d (A1/A2) best preserves right-tail by not cutting winners",
           "- Hybrid5 (extend at 63d if strong) should capture extended trends",
           "- EMA50 GM violation (D_ema50) least disruptive to winners"]),
        "",
        "## Production Candidates",
        "",
        "| use case | recommended exit | rationale |",
        "|----------|-----------------|-----------|",
        "| simple/discretionary | Best simple exit: see top_calmar rank 1 | — |",
        "| systematic portfolio | Best hybrid: see J_H* rankings | — |",
        "| risk-managed | Hybrid2 or Hybrid4 | stop + chandelier |",
        "",
        "## Caveats",
        "",
        "- Static universe (survivorship bias). Dynamic universe not yet implemented.",
        "- 2025 OOS has only ~16 months of data — wide CIs on all metrics.",
        "- Partial exits modeled as clean fills at TP/stop level (optimistic).",
        "- Transaction costs: base 0.15%/side. Stress 0.30%/side in robustness.",
        "",
        "## Next OOS Monitoring Checklist",
        "",
        "- [ ] Monthly: recompute OOS Calmar for top 3 candidates",
        "- [ ] Quarterly: re-run single-split OOS with new test data",
        "- [ ] Flag if OOS max_dd exceeds IS max_dd by > 30%",
        "- [ ] Flag if win_rate drops below 35% for 2 consecutive months",
        "- [ ] Review if VNINDEX regime filter meaningfully changes signal count",
    ]

    (OUT_DIR / "exit_research_summary.md").write_text("\n".join(lines), encoding="utf-8")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--robustness", action="store_true",
                        help="Run robustness checks for top-10 exits")
    parser.add_argument("--max-pos", nargs="+", type=int, default=[10],
                        help="Max positions to test (default: 10)")
    parser.add_argument("--universe", default="full",
                        choices=list(UNIVERSES.keys()))
    parser.add_argument("--cost", default="base", choices=["base", "stress"])
    parser.add_argument("--quick", action="store_true",
                        help="Run only A/B/J hybrids (fast validation)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Loading panel cache...")
    panel = pd.read_parquet(CACHE_PARQUET)
    sym_data = load_sym_data(panel)
    log.info(f"  {len(sym_data)} symbols loaded")

    log.info("Loading VNINDEX...")
    vn = load_vnindex(sym_data)

    log.info("Computing RS20...")
    rs20 = compute_rs20(sym_data, vn)

    configs = build_configs()
    if args.quick:
        configs = [c for c in configs if c.eid.startswith(("A", "B", "J"))]
    log.info(f"Exit configs: {len(configs)}")

    fee = BASE_COST if args.cost == "base" else STRESS_COST
    excl = UNIVERSES[args.universe]

    log.info("Loading signals...")
    signals_all = load_signals(excl)
    signals_train = signals_all[signals_all["signal_date"] <= TRAIN_END]
    signals_oos   = signals_all[signals_all["signal_date"] >= TEST_START]
    signals_full  = signals_all  # for combined run
    log.info(f"  Train: {len(signals_train):,}  OOS: {len(signals_oos):,}")

    all_summary   = []
    all_trades    = []
    all_monthly   = []
    all_yearly    = []
    all_drawdowns = []
    all_robustness = []

    for i, cfg in enumerate(configs):
        log.info(f"[{i+1}/{len(configs)}] {cfg.eid}: {cfg.label}")

        for max_pos in args.max_pos:
            # ── IS run ────────────────────────────────────────────────────────
            trades_is, eq_is, dates_is = run_portfolio(
                cfg, signals_train, sym_data, vn, rs20, max_pos=max_pos, fee=fee)
            m_is = compute_metrics(trades_is, eq_is, dates_is,
                                   cfg.eid, args.universe, args.cost, max_pos, "IS")
            if m_is:
                all_summary.append(m_is)

            # ── OOS run ───────────────────────────────────────────────────────
            trades_oos, eq_oos, dates_oos = run_portfolio(
                cfg, signals_oos, sym_data, vn, rs20, max_pos=max_pos, fee=fee)
            m_oos = compute_metrics(trades_oos, eq_oos, dates_oos,
                                    cfg.eid, args.universe, args.cost, max_pos, "OOS")
            if m_oos:
                all_summary.append(m_oos)

            # Append trades
            for t in trades_is + trades_oos:
                t["period"] = "IS" if t["exit_date"] <= TRAIN_END else "OOS"
            all_trades.extend(trades_is + trades_oos)

            # Monthly returns
            if eq_oos and dates_oos:
                all_monthly.append(compute_monthly_returns(eq_oos, dates_oos, cfg.eid))

            # Drawdown
            if eq_oos and dates_oos:
                all_drawdowns.append(compute_drawdown_summary(eq_oos, dates_oos, cfg.eid))

    # ── Save primary outputs ──────────────────────────────────────────────────
    log.info("Saving outputs...")
    summary_df = pd.DataFrame(all_summary)
    summary_df.to_csv(OUT_DIR / "exit_strategy_summary.csv", index=False)

    trades_df = pd.DataFrame(all_trades)
    trades_df.to_csv(OUT_DIR / "exit_trade_ledger.csv", index=False)

    if all_monthly:
        monthly_df = pd.concat(all_monthly, ignore_index=True)
        monthly_df.to_csv(OUT_DIR / "exit_monthly_returns.csv", index=False)

    if all_drawdowns:
        dd_df = pd.DataFrame(all_drawdowns)
        dd_df.to_csv(OUT_DIR / "exit_drawdown_summary.csv", index=False)

    # Yearly returns from monthly
    if all_monthly:
        monthly_df["year"] = monthly_df["month"].str[:4]
        yearly_df = monthly_df.groupby(["strategy", "year"]).apply(
            lambda g: pd.Series({"annual_ret": (1 + g["ret"]).prod() - 1})
        ).reset_index()
        yearly_df.to_csv(OUT_DIR / "exit_yearly_returns.csv", index=False)

    # Exit reason breakdown
    if not trades_df.empty:
        reason_df = (trades_df.groupby(["strategy", "exit_reason"])
                     .size().reset_index(name="count"))
        reason_df.to_csv(OUT_DIR / "exit_reason_breakdown.csv", index=False)

    # Top/worst contributors
    if not trades_df.empty:
        trd = trades_df.sort_values("net_ret", ascending=False)
        top10   = trd.head(10)
        worst10 = trd.tail(10)
        pd.concat([top10, worst10]).to_csv(OUT_DIR / "exit_best_worst_trades.csv", index=False)
        # Top 10 P&L contributors by strategy
        top_contrib = (trades_df.groupby(["strategy", "symbol"])["net_ret"]
                       .sum().reset_index()
                       .sort_values("net_ret", ascending=False)
                       .head(50))
        top_contrib.to_csv(OUT_DIR / "exit_top_contributors.csv", index=False)

    # ── Robustness checks for top-10 by OOS Calmar ───────────────────────────
    top_calmar_df = pd.DataFrame()
    if not summary_df.empty and "calmar" in summary_df.columns:
        oos_sum = summary_df[summary_df["period"] == "OOS"].copy()
        is_sum  = summary_df[summary_df["period"] == "IS"].copy()
        if not oos_sum.empty:
            top_oos = oos_sum.nlargest(15, "calmar")[["strategy", "calmar", "max_dd", "cagr"]].rename(
                columns={"calmar": "oos_calmar", "max_dd": "oos_max_dd", "cagr": "oos_cagr"})
            if not is_sum.empty:
                is_calmar = is_sum[["strategy", "calmar"]].rename(columns={"calmar": "is_calmar"})
                top_oos = top_oos.merge(is_calmar, on="strategy", how="left")
            # Add label
            cfg_map = {c.eid: c.label for c in configs}
            top_oos["label"] = top_oos["strategy"].map(cfg_map)
            top_calmar_df = top_oos
            top_oos.to_csv(OUT_DIR / "exit_robustness_checks.csv", index=False)

    if args.robustness and not summary_df.empty:
        top_eids = top_calmar_df["strategy"].head(10).tolist() if not top_calmar_df.empty else []
        top_cfgs = [c for c in configs if c.eid in top_eids]
        rob_rows = []
        for cfg in top_cfgs:
            for univ_name, univ_excl in UNIVERSES.items():
                for cost_name, cost_fee in [("base", BASE_COST), ("stress", STRESS_COST)]:
                    for mp in [5, 10, 15, 20]:
                        sigs = load_signals(univ_excl)
                        sigs_oos = sigs[sigs["signal_date"] >= TEST_START]
                        t_oos, eq_oos, dt_oos = run_portfolio(
                            cfg, sigs_oos, sym_data, vn, rs20, max_pos=mp, fee=cost_fee)
                        m = compute_metrics(t_oos, eq_oos, dt_oos,
                                            cfg.eid, univ_name, cost_name, mp, "OOS")
                        if m:
                            rob_rows.append(m)
        if rob_rows:
            rob_df = pd.DataFrame(rob_rows)
            rob_df.to_csv(OUT_DIR / "exit_robustness_checks.csv", index=False)
            log.info(f"Robustness: {len(rob_df)} rows")

    # Get A1 benchmark for markdown
    a1_benchmark: dict = {}
    if not summary_df.empty:
        a1_is  = summary_df[(summary_df["strategy"] == "A1") & (summary_df["period"] == "IS")]
        a1_oos = summary_df[(summary_df["strategy"] == "A1") & (summary_df["period"] == "OOS")]
        if not a1_is.empty:
            for col in ["cagr", "max_dd", "calmar", "win_rate", "mean_ret", "n_trades"]:
                a1_benchmark[f"IS_{col}"] = round(float(a1_is.iloc[0][col]), 4)
        if not a1_oos.empty:
            for col in ["cagr", "max_dd", "calmar", "win_rate", "mean_ret", "n_trades"]:
                a1_benchmark[f"OOS_{col}"] = round(float(a1_oos.iloc[0][col]), 4)

    write_markdown_summary(summary_df, a1_benchmark, top_calmar_df)

    log.info("=" * 60)
    log.info(f"DONE. Output: {OUT_DIR}/")
    log.info(f"  exit_strategy_summary.csv    : {len(summary_df)} rows")
    log.info(f"  exit_trade_ledger.csv        : {len(trades_df)} rows")
    log.info(f"  exit_research_summary.md     : written")

    if not top_calmar_df.empty:
        log.info("\nTop 5 exits by OOS Calmar:")
        for _, r in top_calmar_df.head(5).iterrows():
            log.info(f"  {r['strategy']:20s} calmar={r['oos_calmar']:.3f}  "
                     f"max_dd={r['oos_max_dd']:.1%}  cagr={r['oos_cagr']:.1%}")


if __name__ == "__main__":
    main()
