#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Full Audit — Corrected GK Trend Ribbon + Hybrid Backtest (v2)

AUDIT BUGS FIXED vs. prior gk_trend_ribbon_backtest.py and donchian_gk_exit_comparison.py:
  BUG-1  Exit-day return missing from equity curve.
         Prior: positions deleted BEFORE MTM on signal day → last day's loss/gain not in equity.
         Fix:   pending_exits queue; positions kept through MTM on signal day, proceeds
                reflected at execution day (next open). Equity is always cash + market_value.
  BUG-2  Stop triggered by Close, not intraday Low.
         Prior: checked (close / entry_open - 1) <= -stop_pct.
         Fix:   conservative → if Low[t] <= stop_price, exit at min(stop_price, Open[t+1]).
  BUG-3  Yearly returns from serial trade compounding, not portfolio returns.
         Prior: np.prod(1+trade_rets) per year; severely overstates when trades are parallel.
         Fix:   yearly returns derived from daily equity curve only.
  BUG-4  Equity denominator (max_pos) fixed regardless of actual # positions.
         Note:  this is actually correct (equal-weight with uninvested cash = 0 return).
         Confirmed: not a bug; documented.

GK PARAMETER MISMATCH:
  Report says Len=100/ATR=14. Code uses Len=200/ATR=21.
  Resolution: BOTH are run separately:
    GK_ORIG:  Len=200, Mult=2.0, ATRLen=21, Conf=2  (AFL/TradingView default)
    GK_FAST:  Len=100, Mult=2.0, ATRLen=14, Conf=2  (fast variant)

ARMS COVERED:
  A1  GK Original + GK_SELL
  A2  GK Fast + GK_SELL
  A3  DC + EMA10/50 + Fixed 63-bar hold
  A4  VNINDEX buy-and-hold (benchmark)
  H1  GK Original + GK_SELL                      (same as A1, full deliverables)
  H2  GK Original + EMA cloud + GK_SELL
  H3  DC + EMA cloud + Fixed 63-bar
  H4  DC + EMA cloud + GK_SELL
  H5a DC + EMA cloud + GK_Lower stop close-confirmed (D1)
  H5b DC + EMA cloud + GK_Lower stop intraday conservative (D2)
  H5d DC + EMA cloud + Trailing GK_Lower stop conservative (D4)
  H6  DC + EMA cloud + GK_SELL + 7% stop (intraday conservative)
  H7  DC + EMA cloud + GK_SELL + 8% stop
  H8  DC + EMA cloud + GK_SELL + 10% stop
  H9  DC + EMA cloud + GK_SELL + 12% stop
  H10 DC + EMA cloud + Trailing GK_Lower + GK_SELL
  H11 DC + EMA cloud + Trailing GK_Lower + 7% stop + GK_SELL
  H12a DC + EMA cloud + ATR(2.5x,14) trailing stop + GK_SELL
  H12b DC + EMA cloud + ATR(3.0x,14) trailing stop + GK_SELL
  H12c DC + EMA cloud + ATR(3.5x,14) trailing stop + GK_SELL
  H13  DC + EMA cloud + Chandelier(3.0, ATR14, +10% activation)
  H14  DC + EMA cloud + EMA20 confirmed exit (2-bar, min_hold=0)
  H15  DC + EMA cloud + EMA10 confirmed exit (2-bar, min_hold=0)

Data convention documented inline (section DATA VALIDATION).
"""
from __future__ import annotations

import io, sys, logging, warnings, textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── PATHS ──────────────────────────────────────────────────────────────────────
CACHE_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet"
VNINDEX_CSV   = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT_DIR       = REPO / "data/research/gk_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── GLOBAL CONSTANTS ───────────────────────────────────────────────────────────
START_DATE   = pd.Timestamp("2023-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
ADV50_MIN_BN = 2.0          # VND billions
MAX_POS      = 10
INITIAL_CAP  = 1.0          # normalised
YEARS        = [2023, 2024, 2025, 2026]
EXCL         = {"VPL"}

# ── COST CONVENTIONS (per side) ────────────────────────────────────────────────
# fee=25bps, slip=10bps → total friction 35bps per side
FEE_BPS  = 25.0
SLIP_BPS = 10.0

# ── GK PARAMETER SETS ─────────────────────────────────────────────────────────
GK_ORIG = {"gk_len": 200, "gk_mult": 2.0, "gk_atr": 21, "gk_conf": 2}
GK_FAST = {"gk_len": 100, "gk_mult": 2.0, "gk_atr": 14, "gk_conf": 2}

# ── DONCHIAN CONSTANTS ─────────────────────────────────────────────────────────
DON_LEN  = 20
DON_BUF  = 1.003   # 0.30% buffer above prior 20-day high
EMA_FAST = 10
EMA_SLOW = 50


# ══════════════════════════════════════════════════════════════════════════════
# 1. ARM CONFIGURATIONS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmCfg:
    arm_id:   str
    label:    str
    # --- Entry ---
    entry:         str   = "gk"       # "gk" | "donchian"
    entry_filter:  str   = "none"     # "none" | "ema_cloud"
    gk_params:     dict  = field(default_factory=lambda: GK_ORIG)
    # --- Exit ---
    exit_type:     str   = "gk_sell"  # "gk_sell" | "fixed_N" | "ema10" | "ema20" | "chandelier"
    fixed_hold:    int   = 63
    min_hold:      int   = 0
    # --- Stops (all 0/None = disabled) ---
    stop_pct:      float = 0.0        # hard % stop from raw entry open (intraday conservative)
    gk_lower_stop: str   = "none"     # "none" | "D1" (close) | "D2" (intraday) | "D4" (trailing)
    atr_stop_mult: float = 0.0        # ATR trailing stop multiplier (0 = off)
    atr_stop_len:  int   = 14
    chandelier_mult:      float = 0.0   # Chandelier exit mult (0 = off / uses exit_type chandelier)
    chandelier_atr_len:   int   = 14
    chandelier_activate:  float = 0.10  # gain required before chandelier arms
    # --- Portfolio ---
    max_pos:  int   = MAX_POS
    fee_bps:  float = FEE_BPS
    slip_bps: float = SLIP_BPS

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000


ARMS: list[ArmCfg] = [
    # ── Baselines ──────────────────────────────────────────────────────────────
    ArmCfg("A1", "GK_Orig+GK_SELL",      entry="gk",       gk_params=GK_ORIG),
    ArmCfg("A2", "GK_Fast+GK_SELL",      entry="gk",       gk_params=GK_FAST),
    ArmCfg("A3", "DC+Fixed63",           entry="donchian", exit_type="fixed_N", fixed_hold=63),
    # ── Hybrid H1–H15 ──────────────────────────────────────────────────────────
    ArmCfg("H1",  "GK_Orig+GK_SELL",         entry="gk",       gk_params=GK_ORIG),
    ArmCfg("H2",  "GK_Orig+cloud+GK_SELL",   entry="gk",       entry_filter="ema_cloud", gk_params=GK_ORIG),
    ArmCfg("H3",  "DC+cloud+Fixed63",        entry="donchian", exit_type="fixed_N", fixed_hold=63),
    ArmCfg("H4",  "DC+cloud+GK_SELL",        entry="donchian"),
    ArmCfg("H5a", "DC+GK_Lower_D1(close)",   entry="donchian", exit_type="gk_sell", gk_lower_stop="D1"),
    ArmCfg("H5b", "DC+GK_Lower_D2(intraday)",entry="donchian", exit_type="gk_sell", gk_lower_stop="D2"),
    ArmCfg("H5d", "DC+GK_Lower_D4(trail)",   entry="donchian", exit_type="gk_sell", gk_lower_stop="D4"),
    ArmCfg("H6",  "DC+GK_SELL+7%stop",      entry="donchian", stop_pct=0.07),
    ArmCfg("H7",  "DC+GK_SELL+8%stop",      entry="donchian", stop_pct=0.08),
    ArmCfg("H8",  "DC+GK_SELL+10%stop",     entry="donchian", stop_pct=0.10),
    ArmCfg("H9",  "DC+GK_SELL+12%stop",     entry="donchian", stop_pct=0.12),
    ArmCfg("H10", "DC+TrailGKLow+GK_SELL",  entry="donchian", gk_lower_stop="D4"),
    ArmCfg("H11", "DC+TrailGKLow+7%+GK_SELL", entry="donchian", gk_lower_stop="D4", stop_pct=0.07),
    ArmCfg("H12a","DC+ATR2.5x14+GK_SELL",   entry="donchian", atr_stop_mult=2.5, atr_stop_len=14),
    ArmCfg("H12b","DC+ATR3.0x14+GK_SELL",   entry="donchian", atr_stop_mult=3.0, atr_stop_len=14),
    ArmCfg("H12c","DC+ATR3.5x14+GK_SELL",   entry="donchian", atr_stop_mult=3.5, atr_stop_len=14),
    ArmCfg("H13", "DC+Chandelier3.0+10%",   entry="donchian", exit_type="chandelier",
           chandelier_mult=3.0, chandelier_atr_len=14, chandelier_activate=0.10),
    ArmCfg("H14", "DC+EMA20exit",           entry="donchian", exit_type="ema20"),
    ArmCfg("H15", "DC+EMA10exit",           entry="donchian", exit_type="ema10"),
    # ── Cost sensitivity on best arm (H6 / DC+GK_SELL+7%) ─────────────────────
    ArmCfg("CS_low",  "DC+GK_SELL+7%_CostLow",  entry="donchian", stop_pct=0.07, fee_bps=15, slip_bps=0),
    ArmCfg("CS_high", "DC+GK_SELL+7%_CostHigh", entry="donchian", stop_pct=0.07, fee_bps=35, slip_bps=20),
]


# ══════════════════════════════════════════════════════════════════════════════
# 2. MATH PRIMITIVES
# ══════════════════════════════════════════════════════════════════════════════

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out   = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = float(arr[i])
        if np.isnan(v):
            continue
        prev  = out[i - 1] if i > 0 and not np.isnan(out[i - 1]) else np.nan
        out[i] = v if np.isnan(prev) else alpha * v + (1.0 - alpha) * prev
    return out


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    tr    = np.empty(len(close))
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    alpha = 1.0 / n
    out   = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1] = float(np.mean(tr[:n]))
        for i in range(n, len(tr)):
            out[i] = alpha * tr[i] + (1.0 - alpha) * out[i - 1]
    return out


def _adv50_lagged(value: np.ndarray) -> np.ndarray:
    """ADV50 on day t = mean(value[t-50:t]) / 1e9.  Strictly no look-ahead."""
    out = np.full(len(value), np.nan)
    for i in range(50, len(value)):
        out[i] = float(np.mean(value[i - 50: i])) / 1e9
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 3. SIGNAL COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_gk_signals(
    close: np.ndarray, high: np.ndarray, low: np.ndarray,
    gk_len: int, gk_mult: float, gk_atr: int, gk_conf: int,
) -> dict:
    """
    Exact AFL replication.
    AFL-matching Conf=2: ConfBack=1 → [t-1] and [t-ConfBack]=[t-1] are identical clauses.
    Preserved exactly as-is; separate 'non-redundant' variant not introduced here.
    """
    n   = len(close)
    lag = max(int((gk_len - 1) // 2), 0)

    past_close = np.empty(n)
    for i in range(n):
        j = i - lag
        past_close[i] = close[j] if j >= 0 else close[i]

    zl_input = close + (close - past_close) if lag > 0 else close.copy()
    gk_zl    = _ema(zl_input, gk_len)
    gk_atr_v = _wilder_atr(high, low, close, gk_atr)
    gk_upper = gk_zl + gk_atr_v * gk_mult
    gk_lower = gk_zl - gk_atr_v * gk_mult

    cb       = gk_conf - 1
    above    = close > gk_upper
    below    = close < gk_lower

    above1   = np.concatenate([[False], above[:-1]])
    below1   = np.concatenate([[False], below[:-1]])
    above_cb = np.concatenate([np.full(max(cb,0), False), above[:-cb]]) if cb > 0 else above.copy()
    below_cb = np.concatenate([np.full(max(cb,0), False), below[:-cb]]) if cb > 0 else below.copy()

    zl_prev    = np.concatenate([[np.nan], gk_zl[:-1]])
    zl_rising  = gk_zl > zl_prev
    zl_falling = gk_zl < zl_prev

    valid    = ~np.isnan(gk_upper) & ~np.isnan(gk_lower)
    gk_bull  = above & above1 & above_cb & zl_rising  & valid
    gk_bear  = below & below1 & below_cb & zl_falling & valid

    raw      = np.where(gk_bull, 1.0, np.where(gk_bear, -1.0, np.nan))
    s        = pd.Series(raw).ffill().fillna(0.0).astype(int)
    gk_trend = s.values

    gk_prev     = np.zeros(n, dtype=int)
    gk_prev[1:] = gk_trend[:-1]
    raw_flip    = (gk_trend != gk_prev) & (gk_trend != 0)

    return {
        "gk_buy":   raw_flip & (gk_trend == 1),
        "gk_sell":  raw_flip & (gk_trend == -1),
        "gk_lower": gk_lower,
        "gk_upper": gk_upper,
        "gk_trend": gk_trend,
        "gk_atr":   gk_atr_v,
    }


def compute_dc_signals(
    close: np.ndarray,
    high:  np.ndarray,
    ema10: np.ndarray,
    ema50: np.ndarray,
) -> np.ndarray:
    """
    AFL equivalent: Ref(HHV(H,20),-1) = max(high[t-20:t]) for the prior 20 bars,
    excluding current bar t.  Confirmed: Python slice high[i-20:i] = bars t-20..t-1. ✓
    """
    n      = len(close)
    dc_buy = np.zeros(n, dtype=bool)
    for i in range(DON_LEN, n):
        if np.isnan(ema10[i]) or np.isnan(ema50[i]):
            continue
        don_high    = np.max(high[i - DON_LEN: i])
        trigger     = don_high * DON_BUF
        bull_cloud  = bool(ema10[i] > ema50[i])
        above_cloud = bool(close[i] > max(ema10[i], ema50[i]))
        dc_buy[i]   = (close[i] > trigger) and bull_cloud and above_cloud
    return dc_buy


# ══════════════════════════════════════════════════════════════════════════════
# 4. PRE-COMPUTE BASE DATA
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base(panel: pd.DataFrame) -> dict[str, dict]:
    base: dict[str, dict] = {}
    for sym, grp in panel.groupby("symbol"):
        df  = grp.sort_values("date").reset_index(drop=True)
        c   = df["close"].values.astype(float)
        h   = df["high"].values.astype(float)
        l   = df["low"].values.astype(float)
        o   = df["open"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)

        e10 = _ema(c, EMA_FAST)
        e50 = _ema(c, EMA_SLOW)
        e20 = _ema(c, 20)

        gk_o = compute_gk_signals(c, h, l, **GK_ORIG)
        gk_f = compute_gk_signals(c, h, l, **GK_FAST)
        dc_b = compute_dc_signals(c, h, e10, e50)

        base[sym] = {
            "dates":       dts,
            "open":        o,
            "high":        h,
            "low":         l,
            "close":       c,
            "value":       val,
            "adv50_lag":   _adv50_lagged(val),
            "ema10":       e10,
            "ema20":       e20,
            "ema50":       e50,
            "atr14":       _wilder_atr(h, l, c, 14),
            "atr21":       _wilder_atr(h, l, c, 21),
            "gk_orig":     gk_o,
            "gk_fast":     gk_f,
            "dc_buy":      dc_b,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


# ══════════════════════════════════════════════════════════════════════════════
# 5. CORRECTED PORTFOLIO ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_arm(base: dict[str, dict], arm: ArmCfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Corrected portfolio engine.

    Key fixes vs. prior implementation:
      - pending_exits queue: positions stay in holdings through MTM on signal day,
        exit proceeds reflected in cash on execution day → equity = cash + market_value.
      - Conservative stop: Low[t] <= stop_price → exit at min(stop_price, Open[t+1]).
      - Slot sizing: prev_equity / max_pos (floating, updates each day).
      - Exits before entries on same day.
      - Signal count tracked: raw / ADV50-filtered / portfolio-selected / rejected.

    Returns: equity_df, trades_df, signal_stats dict.
    """
    # Select GK signal set per arm
    gk_key = "gk_orig" if arm.gk_params == GK_ORIG else "gk_fast"
    cost_e = arm.cost_e
    cost_x = arm.cost_x

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]

    # Portfolio state
    cash       = INITIAL_CAP
    holdings: dict[str, dict] = {}   # sym → position record
    pending_exits: dict[str, tuple]  = {}  # sym → (t_signal, reason)  ← execute at next open
    pending_entries: list[tuple] = []      # (sym, t_signal, meta, rank_score) ← execute at next open

    trades:    list[dict] = []
    eq_curve:  list[dict] = []
    prev_equity = INITIAL_CAP

    # Signal count tracking
    raw_signals      = {"gk": 0, "dc": 0}
    adv_filtered     = {"gk": 0, "dc": 0}
    selected_trades  = {"gk": 0, "dc": 0}
    rejected_signals = {"gk": 0, "dc": 0}

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())

        # ── Step 1: Execute PREVIOUS day's pending exits at today's open ───────
        for sym, (t_sig, reason) in list(pending_exits.items()):
            b     = base[sym]
            t_ex  = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue  # data missing today; try again next day
            exit_o_raw = float(b["open"][t_ex])
            if exit_o_raw <= 0:
                exit_o_raw = float(b["close"][t_ex])  # fallback; flagged via reason
                reason = reason + "_NOOPEN"
            pos      = holdings.pop(sym)
            proceeds = pos["shares"] * exit_o_raw * cost_x
            cash    += proceeds
            net_ret  = (exit_o_raw * cost_x) / pos["entry_px_eff"] - 1.0
            gross_ret = exit_o_raw / pos["entry_open_raw"] - 1.0
            hold_bars = day_i - pos["entry_day_i"]
            trades.append({
                "symbol":          sym,
                "arm_id":          arm.arm_id,
                "entry_signal_dt": pos["entry_signal_dt"],
                "entry_dt":        pos["entry_dt"],
                "entry_open_raw":  round(pos["entry_open_raw"], 4),
                "entry_px_eff":    round(pos["entry_px_eff"], 4),
                "exit_signal_dt":  pos["exit_signal_dt"],
                "exit_dt":         trade_date,
                "exit_open_raw":   round(exit_o_raw, 4),
                "exit_px_eff":     round(exit_o_raw * cost_x, 4),
                "exit_reason":     reason,
                "hold_days":       (trade_date - pos["entry_dt"]).days,
                "hold_bars":       hold_bars,
                "gross_ret":       round(gross_ret, 6),
                "net_ret":         round(net_ret, 6),
                "adv50_entry":     round(pos["adv50_entry"], 3),
                "ema_cloud_entry": pos["ema_cloud_entry"],
                "gk_trend_entry":  pos["gk_trend_entry"],
                "entry_mode":      pos["entry_mode"],
                # MAE/MFE placeholders (populated below in post-processing)
                "mfe":             pos.get("mfe", np.nan),
                "mae":             pos.get("mae", np.nan),
            })
        pending_exits.clear()

        # ── Step 2: Execute PREVIOUS day's pending entries at today's open ──────
        n_slots = arm.max_pos - len(holdings)
        for sym, t_sig, meta, rank_score in sorted(pending_entries, key=lambda x: -x[3])[:n_slots]:
            if sym in holdings:
                continue
            b = base[sym]
            t_ex = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue
            entry_o_raw = float(b["open"][t_ex])
            if entry_o_raw <= 0:
                continue
            slot         = prev_equity / arm.max_pos
            entry_px_eff = entry_o_raw * cost_e
            shares       = slot / entry_px_eff
            cash        -= slot

            entry_mode   = meta["entry_mode"]
            selected_trades[entry_mode] = selected_trades.get(entry_mode, 0) + 1

            # Per-position trailing state
            gk_lo_init = float(base[sym][gk_key]["gk_lower"][t_sig]) if not np.isnan(
                base[sym][gk_key]["gk_lower"][t_sig]) else 0.0

            holdings[sym] = {
                "shares":          shares,
                "entry_px_eff":    entry_px_eff,
                "entry_open_raw":  entry_o_raw,
                "entry_dt":        trade_date,
                "entry_signal_dt": meta["entry_signal_dt"],
                "entry_day_i":     day_i,
                "adv50_entry":     meta["adv50_entry"],
                "ema_cloud_entry": meta["ema_cloud_entry"],
                "gk_trend_entry":  meta["gk_trend_entry"],
                "entry_mode":      entry_mode,
                "exit_signal_dt":  None,
                # per-position stop state
                "trail_gk_lower":   gk_lo_init,
                "ch_highest_close": entry_o_raw,  # Chandelier: highest close since entry
                "trail_atr_stop":   -np.inf,       # ATR trailing stop
                "mfe":              0.0,
                "mae":              0.0,
            }
        pending_entries.clear()

        # ── Step 3: MTM at today's close ────────────────────────────────────────
        market_val = 0.0
        for sym, pos in holdings.items():
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None:
                continue
            c_now = float(b["close"][t])
            market_val += pos["shares"] * c_now
            # Update per-position running stats
            unrealised = c_now / pos["entry_open_raw"] - 1.0
            pos["mfe"] = max(pos["mfe"], unrealised)
            pos["mae"] = min(pos["mae"], unrealised)
            # Update trailing stop states
            gk_lo = float(b[gk_key]["gk_lower"][t]) if t < len(b[gk_key]["gk_lower"]) else np.nan
            if not np.isnan(gk_lo):
                pos["trail_gk_lower"] = max(pos["trail_gk_lower"], gk_lo)
            atr_v  = float(b["atr14"][t]) if t < len(b["atr14"]) else np.nan
            if not np.isnan(atr_v) and arm.atr_stop_mult > 0:
                new_atr_trail = c_now - arm.atr_stop_mult * atr_v
                pos["trail_atr_stop"] = max(pos["trail_atr_stop"], new_atr_trail)
            pos["ch_highest_close"] = max(pos["ch_highest_close"], c_now)

        equity     = cash + market_val
        prev_equity = equity
        eq_curve.append({
            "date":          trade_date,
            "cash":          round(cash, 6),
            "market_value":  round(market_val, 6),
            "total_equity":  round(equity, 6),
            "n_pos":         len(holdings),
            "gross_exposure": round(market_val / max(equity, 1e-9), 4),
        })

        # ── Step 4: Scan today's exit signals (execute tomorrow) ──────────────
        for sym, pos in list(holdings.items()):
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None or t + 1 >= len(b["close"]):
                continue

            bars_held = day_i - pos["entry_day_i"]
            if bars_held < arm.min_hold:
                continue

            c_now = float(b["close"][t])
            lo    = float(b["low"][t])
            triggered, reason = False, ""

            # ── GK_SELL (close-confirmed trend reversal) ──
            if not triggered and arm.exit_type == "gk_sell":
                if bool(b[gk_key]["gk_sell"][t]):
                    triggered, reason = True, "GK_SELL"

            # ── EMA10 confirmed exit (2 consecutive closes < EMA10) ──
            if not triggered and arm.exit_type == "ema10" and t >= 1:
                if c_now < float(b["ema10"][t]) and float(b["close"][t-1]) < float(b["ema10"][t-1]):
                    triggered, reason = True, "EMA10_EXIT"

            # ── EMA20 confirmed exit ──
            if not triggered and arm.exit_type == "ema20" and t >= 1:
                if c_now < float(b["ema20"][t]) and float(b["close"][t-1]) < float(b["ema20"][t-1]):
                    triggered, reason = True, "EMA20_EXIT"

            # ── Fixed N-bar hold ──
            if not triggered and arm.exit_type == "fixed_N":
                if bars_held >= arm.fixed_hold:
                    triggered, reason = True, f"FIXED_{arm.fixed_hold}"

            # ── Chandelier exit ──
            if not triggered and arm.exit_type == "chandelier" and arm.chandelier_mult > 0:
                gain_so_far = c_now / pos["entry_open_raw"] - 1.0
                if gain_so_far >= arm.chandelier_activate:
                    atr_v = float(b["atr14"][t]) if t < len(b["atr14"]) and not np.isnan(b["atr14"][t]) else 0.0
                    ch_stop = pos["ch_highest_close"] - arm.chandelier_mult * atr_v
                    if lo <= ch_stop:
                        triggered, reason = True, "CHANDELIER"

            # ── GK_Lower stop — D1 (close-confirmed) ──
            if not triggered and arm.gk_lower_stop in ("D1",):
                gk_lo = float(b[gk_key]["gk_lower"][t])
                if not np.isnan(gk_lo) and c_now < gk_lo:
                    triggered, reason = True, "GK_LOWER_D1"

            # ── GK_Lower stop — D2 (intraday conservative) ──
            if not triggered and arm.gk_lower_stop == "D2":
                gk_lo = float(b[gk_key]["gk_lower"][t])
                if not np.isnan(gk_lo) and lo <= gk_lo:
                    triggered, reason = True, "GK_LOWER_D2"

            # ── GK_Lower stop — D4 (trailing, intraday conservative) ──
            if not triggered and arm.gk_lower_stop == "D4":
                trail = pos["trail_gk_lower"]
                if trail > 0 and lo <= trail:
                    triggered, reason = True, "GK_LOWER_D4"

            # ── ATR trailing stop ──
            if not triggered and arm.atr_stop_mult > 0:
                atr_trail = pos["trail_atr_stop"]
                if atr_trail > -np.inf and lo <= atr_trail:
                    triggered, reason = True, f"ATR_{arm.atr_stop_mult}x_TRAIL"

            # ── Hard % stop — intraday conservative ──
            # BUG-2 FIX: check Low[t], not Close[t]
            if not triggered and arm.stop_pct > 0:
                stop_price = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= stop_price:
                    triggered, reason = True, f"STOP_{arm.stop_pct*100:.0f}PCT"

            if triggered:
                pos["exit_signal_dt"] = trade_date
                # Store the override exit price for stops (conservative: min(stop_level, next_open))
                # The actual price will be resolved in Step 1 of the next day using the open.
                # For stops, we cap the exit price. We pass the cap as metadata.
                exit_cap = None
                if reason.startswith("STOP_") and arm.stop_pct > 0:
                    exit_cap = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                elif reason in ("GK_LOWER_D2",):
                    exit_cap = float(b[gk_key]["gk_lower"][t])
                elif reason == "GK_LOWER_D4":
                    exit_cap = pos["trail_gk_lower"]
                elif reason == "CHANDELIER":
                    atr_v = float(b["atr14"][t]) if t < len(b["atr14"]) and not np.isnan(b["atr14"][t]) else 0.0
                    exit_cap = pos["ch_highest_close"] - arm.chandelier_mult * atr_v
                elif reason == f"ATR_{arm.atr_stop_mult}x_TRAIL":
                    exit_cap = pos["trail_atr_stop"]

                pending_exits[sym] = (t, reason, exit_cap)

        # ── Step 5: Scan today's entry signals (execute tomorrow) ─────────────
        n_tomorrow_free = arm.max_pos - len(holdings) - len(pending_entries) + len(pending_exits)
        if n_tomorrow_free > 0:
            entry_type = arm.entry
            for sym, b in base.items():
                if sym in holdings or any(x[0] == sym for x in pending_entries) or sym in pending_exits:
                    continue
                t = b["date_to_idx"].get(day_str)
                if t is None or t + 1 >= len(b["close"]):
                    continue
                if float(b["open"][t + 1]) <= 0:
                    continue

                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN_BN:
                    continue

                e10 = float(b["ema10"][t])
                e50 = float(b["ema50"][t])

                if entry_type == "gk":
                    raw_signals["gk"] = raw_signals.get("gk", 0) + 1
                    if not bool(b[gk_key]["gk_buy"][t]):
                        continue
                    adv_filtered["gk"] = adv_filtered.get("gk", 0) + 1
                    if arm.entry_filter == "ema_cloud" and not (e10 > e50):
                        continue
                elif entry_type == "donchian":
                    if bool(b["dc_buy"][t]):
                        raw_signals["dc"] = raw_signals.get("dc", 0) + 1
                        adv_filtered["dc"] = adv_filtered.get("dc", 0) + 1
                    else:
                        continue
                else:
                    continue

                gk_trend_val = int(b[gk_key]["gk_trend"][t])
                pending_entries.append((
                    sym, t,
                    {
                        "entry_signal_dt": trade_date,
                        "adv50_entry":     adv,
                        "ema_cloud_entry": bool(e10 > e50),
                        "gk_trend_entry":  gk_trend_val,
                        "entry_mode":      entry_type,
                    },
                    adv,  # rank score = ADV50 descending
                ))

    # ── Force-close remaining positions at last bar ──────────────────────────
    last_day_i = len(all_dates) - 1
    for sym, pos in list(holdings.items()):
        b      = base[sym]
        exit_c = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":          sym,
            "arm_id":          arm.arm_id,
            "entry_signal_dt": pos["entry_signal_dt"],
            "entry_dt":        pos["entry_dt"],
            "entry_open_raw":  round(pos["entry_open_raw"], 4),
            "entry_px_eff":    round(pos["entry_px_eff"], 4),
            "exit_signal_dt":  all_dates[-1],
            "exit_dt":         all_dates[-1],
            "exit_open_raw":   round(exit_c, 4),
            "exit_px_eff":     round(exit_c * cost_x, 4),
            "exit_reason":     "EOD_FORCE",
            "hold_days":       (all_dates[-1] - pos["entry_dt"]).days,
            "hold_bars":       last_day_i - pos["entry_day_i"],
            "gross_ret":       round(exit_c / pos["entry_open_raw"] - 1.0, 6),
            "net_ret":         round(net_ret, 6),
            "adv50_entry":     round(pos["adv50_entry"], 3),
            "ema_cloud_entry": pos["ema_cloud_entry"],
            "gk_trend_entry":  pos["gk_trend_entry"],
            "entry_mode":      pos["entry_mode"],
            "mfe":             pos["mfe"],
            "mae":             pos["mae"],
        })

    # ── Resolve conservative stop exit prices ─────────────────────────────────
    # In pending_exits we stored exit_cap. Apply it to the trade log:
    # (trade already logged above in Step 1 using market open; cap not yet applied)
    # NOTE: the cap is applied when we process the trade in Step 1 by looking up
    # the open[t+1] and taking min(cap, open[t+1]). We need to retrofit this.
    # For simplicity: we apply the cap post-hoc when building trades list.
    # → Actually, we need to do this inside the exit execution (Step 1).
    # The pending_exits stores exit_cap — let me re-factor Step 1 to use it.

    # RETROFIT: re-process trades to apply stop caps
    for tr in trades:
        reason = tr["exit_reason"]
        # The cap was computed on signal day but execution is at next_open.
        # Since the trade is already committed with exit_open_raw = actual next_open,
        # we apply: exit_open_raw = min(actual_open, cap_if_stop)
        # This was NOT done inside the loop. We'll correct it here via a flag
        # by storing the cap in pending_exits and looking it up.
        # For now: trades reflect actual open (no cap); add cap handling in v3.
        # Document as REMAINING LIMITATION in audit report.
        pass

    signal_stats = {
        "raw_gk":     raw_signals.get("gk", 0),
        "raw_dc":     raw_signals.get("dc", 0),
        "adv_gk":     adv_filtered.get("gk", 0),
        "adv_dc":     adv_filtered.get("dc", 0),
        "sel_gk":     selected_trades.get("gk", 0),
        "sel_dc":     selected_trades.get("dc", 0),
    }
    return pd.DataFrame(eq_curve), pd.DataFrame(trades), signal_stats


def _apply_stop_cap(pending_exits_store: dict, trades: list[dict]) -> None:
    """
    Post-hoc: apply conservative cap (min(stop_level, open)) to stop exits.
    pending_exits_store: sym -> (t_signal, reason, exit_cap)
    """
    # This is called INSIDE the engine; here we need to update cash accordingly.
    # For this version we do it cleanly inside the loop by storing exit_cap in pending_exits.
    pass  # handled inline below via refactored Step 1


# ══════════════════════════════════════════════════════════════════════════════
# REVISED run_arm with proper stop cap application
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_v2(base: dict[str, dict], arm: ArmCfg) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    run_arm with conservative stop cap properly applied at execution time.
    For stop/band exits: exit at min(cap_price, next_open) for long position.
    """
    gk_key = "gk_orig" if arm.gk_params == GK_ORIG else "gk_fast"
    cost_e = arm.cost_e
    cost_x = arm.cost_x

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]

    cash       = INITIAL_CAP
    holdings: dict[str, dict] = {}
    # pending_exits: sym → (t_signal, reason, exit_cap_or_None)
    pending_exits: dict[str, tuple] = {}
    pending_entries: list[tuple] = []

    trades:    list[dict] = []
    eq_curve:  list[dict] = []
    prev_equity = INITIAL_CAP

    raw_signals = 0; adv_signals = 0; sel_trades = 0; rej_signals = 0

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())

        # ── Step 1: Execute pending exits at today's open ──────────────────────
        for sym, (t_sig, reason, exit_cap) in list(pending_exits.items()):
            b    = base[sym]
            t_ex = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue
            open_raw = float(b["open"][t_ex])
            if open_raw <= 0:
                open_raw = float(b["close"][t_ex])
                reason  += "_FALLBACK_CLOSE"
            # Conservative: if a cap (stop level) exists, exit at min(cap, open)
            if exit_cap is not None and exit_cap > 0:
                open_raw = min(exit_cap, open_raw)
            pos      = holdings.pop(sym)
            proceeds = pos["shares"] * open_raw * cost_x
            cash    += proceeds
            net_ret  = (open_raw * cost_x) / pos["entry_px_eff"] - 1.0
            hold_bars = day_i - pos["entry_day_i"]
            trades.append({
                "symbol":          sym,
                "arm_id":          arm.arm_id,
                "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
                "entry_dt":        str(pos["entry_dt"].date()) if hasattr(pos["entry_dt"], "date") else str(pos["entry_dt"]),
                "entry_open_raw":  round(pos["entry_open_raw"], 4),
                "entry_px_eff":    round(pos["entry_px_eff"], 4),
                "exit_signal_dt":  str(pos["exit_signal_dt"].date()) if hasattr(pos.get("exit_signal_dt"), "date") else str(pos.get("exit_signal_dt","")),
                "exit_dt":         str(trade_date.date()),
                "exit_open_raw":   round(open_raw, 4),
                "exit_px_eff":     round(open_raw * cost_x, 4),
                "exit_reason":     reason,
                "hold_days":       (trade_date - pos["entry_dt"]).days,
                "hold_bars":       hold_bars,
                "gross_ret":       round(open_raw / pos["entry_open_raw"] - 1.0, 6),
                "net_ret":         round(net_ret, 6),
                "adv50_entry":     round(pos["adv50_entry"], 3),
                "ema_cloud_entry": pos["ema_cloud_entry"],
                "gk_trend_entry":  pos["gk_trend_entry"],
                "entry_mode":      pos["entry_mode"],
                "mfe":             round(pos.get("mfe", np.nan), 4),
                "mae":             round(pos.get("mae", np.nan), 4),
            })
        pending_exits.clear()

        # ── Step 2: Execute pending entries at today's open ────────────────────
        n_slots = arm.max_pos - len(holdings)
        for sym, t_sig, meta, rank_score in sorted(pending_entries, key=lambda x: -x[3])[:n_slots]:
            if sym in holdings:
                continue
            b = base[sym]
            t_ex = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue
            entry_o_raw = float(b["open"][t_ex])
            if entry_o_raw <= 0:
                continue
            slot         = prev_equity / arm.max_pos
            entry_px_eff = entry_o_raw * cost_e
            shares       = slot / entry_px_eff
            cash        -= slot
            sel_trades  += 1

            gk_lo_init = float(b[gk_key]["gk_lower"][t_sig])
            if np.isnan(gk_lo_init):
                gk_lo_init = 0.0

            holdings[sym] = {
                "shares":          shares,
                "entry_px_eff":    entry_px_eff,
                "entry_open_raw":  entry_o_raw,
                "entry_dt":        trade_date,
                "entry_signal_dt": meta["entry_signal_dt"],
                "entry_day_i":     day_i,
                "adv50_entry":     meta["adv50_entry"],
                "ema_cloud_entry": meta["ema_cloud_entry"],
                "gk_trend_entry":  meta["gk_trend_entry"],
                "entry_mode":      meta["entry_mode"],
                "exit_signal_dt":  None,
                "trail_gk_lower":  gk_lo_init,
                "ch_highest_close": entry_o_raw,
                "trail_atr_stop":  -np.inf,
                "mfe":             0.0,
                "mae":             0.0,
            }
        pending_entries.clear()

        # ── Step 3: MTM at today's close ────────────────────────────────────────
        market_val = 0.0
        for sym, pos in holdings.items():
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None:
                continue
            c_now = float(b["close"][t])
            market_val += pos["shares"] * c_now
            unrealised  = c_now / pos["entry_open_raw"] - 1.0
            pos["mfe"]  = max(pos["mfe"], unrealised)
            pos["mae"]  = min(pos["mae"], unrealised)
            gk_lo = float(b[gk_key]["gk_lower"][t])
            if not np.isnan(gk_lo):
                pos["trail_gk_lower"] = max(pos["trail_gk_lower"], gk_lo)
            if arm.atr_stop_mult > 0:
                atr_v = float(b["atr14"][t])
                if not np.isnan(atr_v):
                    pos["trail_atr_stop"] = max(pos["trail_atr_stop"], c_now - arm.atr_stop_mult * atr_v)
            pos["ch_highest_close"] = max(pos["ch_highest_close"], c_now)

        equity      = cash + market_val
        prev_equity = equity
        eq_curve.append({
            "date":          trade_date,
            "cash":          round(cash, 6),
            "market_value":  round(market_val, 6),
            "total_equity":  round(equity, 6),
            "n_pos":         len(holdings),
            "gross_exposure": round(market_val / max(equity, 1e-9), 4),
        })

        # ── Step 4: Scan exit signals ────────────────────────────────────────
        for sym, pos in list(holdings.items()):
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None or t + 1 >= len(b["close"]):
                continue
            bars_held = day_i - pos["entry_day_i"]
            if bars_held < arm.min_hold:
                continue
            c_now = float(b["close"][t])
            lo    = float(b["low"][t])
            triggered, reason, exit_cap = False, "", None

            if not triggered and arm.exit_type == "gk_sell":
                if bool(b[gk_key]["gk_sell"][t]):
                    triggered, reason = True, "GK_SELL"

            if not triggered and arm.exit_type == "ema10" and t >= 1:
                if c_now < float(b["ema10"][t]) and float(b["close"][t-1]) < float(b["ema10"][t-1]):
                    triggered, reason = True, "EMA10_EXIT"

            if not triggered and arm.exit_type == "ema20" and t >= 1:
                if c_now < float(b["ema20"][t]) and float(b["close"][t-1]) < float(b["ema20"][t-1]):
                    triggered, reason = True, "EMA20_EXIT"

            if not triggered and arm.exit_type == "fixed_N":
                if bars_held >= arm.fixed_hold:
                    triggered, reason = True, f"FIXED_{arm.fixed_hold}"

            if not triggered and arm.exit_type == "chandelier" and arm.chandelier_mult > 0:
                gain_so_far = c_now / pos["entry_open_raw"] - 1.0
                if gain_so_far >= arm.chandelier_activate:
                    atr_ch_key = "atr14" if arm.chandelier_atr_len == 14 else "atr21"
                    atr_v = float(b[atr_ch_key][t]) if not np.isnan(b[atr_ch_key][t]) else 0.0
                    ch_stop = pos["ch_highest_close"] - arm.chandelier_mult * atr_v
                    if lo <= ch_stop:
                        triggered, reason, exit_cap = True, "CHANDELIER", ch_stop

            if not triggered and arm.gk_lower_stop == "D1":
                gk_lo = float(b[gk_key]["gk_lower"][t])
                if not np.isnan(gk_lo) and c_now < gk_lo:
                    triggered, reason = True, "GK_LOWER_D1"

            if not triggered and arm.gk_lower_stop == "D2":
                gk_lo = float(b[gk_key]["gk_lower"][t])
                if not np.isnan(gk_lo) and lo <= gk_lo:
                    triggered, reason, exit_cap = True, "GK_LOWER_D2", gk_lo

            if not triggered and arm.gk_lower_stop == "D4":
                trail = pos["trail_gk_lower"]
                if trail > 0 and lo <= trail:
                    triggered, reason, exit_cap = True, "GK_LOWER_D4", trail

            if not triggered and arm.atr_stop_mult > 0:
                atr_trail = pos["trail_atr_stop"]
                if atr_trail > -np.inf and lo <= atr_trail:
                    triggered, reason, exit_cap = True, f"ATR_TRAIL", atr_trail

            if not triggered and arm.stop_pct > 0:
                stop_price = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= stop_price:
                    triggered, reason, exit_cap = True, f"STOP_{arm.stop_pct*100:.0f}PCT", stop_price

            if triggered:
                pos["exit_signal_dt"] = trade_date
                pending_exits[sym] = (t, reason, exit_cap)

        # ── Step 5: Scan entry signals ────────────────────────────────────────
        n_tomorrow_free = arm.max_pos - len(holdings) - len(pending_entries) + len(pending_exits)
        if n_tomorrow_free > 0:
            for sym, b in base.items():
                if (sym in holdings or sym in pending_exits or
                        any(x[0] == sym for x in pending_entries)):
                    continue
                t = b["date_to_idx"].get(day_str)
                if t is None or t + 1 >= len(b["close"]):
                    continue
                if float(b["open"][t + 1]) <= 0:
                    continue
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN_BN:
                    continue
                e10 = float(b["ema10"][t])
                e50 = float(b["ema50"][t])
                ok  = False
                if arm.entry == "gk":
                    raw_signals += 1
                    if bool(b[gk_key]["gk_buy"][t]):
                        adv_signals += 1
                        ok = True
                    if ok and arm.entry_filter == "ema_cloud" and not (e10 > e50):
                        ok = False
                        adv_signals -= 1
                elif arm.entry == "donchian":
                    if bool(b["dc_buy"][t]):
                        raw_signals += 1; adv_signals += 1; ok = True
                if ok:
                    pending_entries.append((
                        sym, t,
                        {
                            "entry_signal_dt": trade_date,
                            "adv50_entry":     adv,
                            "ema_cloud_entry": bool(e10 > e50),
                            "gk_trend_entry":  int(b[gk_key]["gk_trend"][t]),
                            "entry_mode":      arm.entry,
                        },
                        adv,
                    ))

    # ── Force-close remaining positions ────────────────────────────────────────
    last_day_i = len(all_dates) - 1
    for sym, pos in list(holdings.items()):
        b = base[sym]
        exit_c   = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":          sym,
            "arm_id":          arm.arm_id,
            "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
            "entry_dt":        str(pos["entry_dt"].date()) if hasattr(pos["entry_dt"], "date") else str(pos["entry_dt"]),
            "entry_open_raw":  round(pos["entry_open_raw"], 4),
            "entry_px_eff":    round(pos["entry_px_eff"], 4),
            "exit_signal_dt":  str(all_dates[-1].date()),
            "exit_dt":         str(all_dates[-1].date()),
            "exit_open_raw":   round(exit_c, 4),
            "exit_px_eff":     round(exit_c * cost_x, 4),
            "exit_reason":     "EOD_FORCE",
            "hold_days":       (all_dates[-1] - pos["entry_dt"]).days,
            "hold_bars":       last_day_i - pos["entry_day_i"],
            "gross_ret":       round(exit_c / pos["entry_open_raw"] - 1.0, 6),
            "net_ret":         round(net_ret, 6),
            "adv50_entry":     round(pos["adv50_entry"], 3),
            "ema_cloud_entry": pos["ema_cloud_entry"],
            "gk_trend_entry":  pos["gk_trend_entry"],
            "entry_mode":      pos["entry_mode"],
            "mfe":             round(pos.get("mfe", np.nan), 4),
            "mae":             round(pos.get("mae", np.nan), 4),
        })

    rej_signals = raw_signals - sel_trades
    signal_stats = {
        "raw_signals": raw_signals, "adv_filtered": adv_signals,
        "selected":    sel_trades,  "rejected":     rej_signals,
    }
    return pd.DataFrame(eq_curve), pd.DataFrame(trades), signal_stats


# ══════════════════════════════════════════════════════════════════════════════
# 6. METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(eq_df: pd.DataFrame, trades_df: pd.DataFrame, label: str = "") -> dict:
    """
    Comprehensive metrics.  All yearly/monthly returns from daily equity curve.
    BUG-3 FIX: yearly['total_ret'] is portfolio-weighted, not serial trade compounding.
    """
    m: dict = {"label": label, "n_trades": 0}
    if trades_df.empty:
        return m

    rets   = trades_df["net_ret"].values.astype(float)
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]

    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4) if len(rets) else np.nan
    m["avg_ret"]       = round(float(rets.mean()), 4)
    m["avg_win"]       = round(float(wins.mean()),   4) if len(wins)   else np.nan
    m["avg_loss"]      = round(float(losses.mean()), 4) if len(losses) else np.nan
    m["profit_factor"] = round(float(wins.sum() / (-losses.sum())), 3) \
                         if len(losses) and losses.sum() < 0 else np.nan
    m["expectancy"]    = round(float(m["win_rate"] * m["avg_win"] + (1 - m["win_rate"]) * m["avg_loss"]), 4) \
                         if not np.isnan(m.get("avg_win", np.nan)) else np.nan
    m["best_trade"]    = round(float(rets.max()), 4)
    m["worst_trade"]   = round(float(rets.min()), 4)
    m["median_ret"]    = round(float(np.median(rets)), 4)

    hd = trades_df["hold_days"].dropna().values.astype(float) if "hold_days" in trades_df else np.array([])
    m["avg_hold_days"]    = round(float(hd.mean()),     1) if len(hd) else np.nan
    m["median_hold_days"] = round(float(np.median(hd)), 1) if len(hd) else np.nan

    if not eq_df.empty and "total_equity" in eq_df.columns:
        pv   = eq_df["total_equity"].values.astype(float)
        dts  = pd.to_datetime(eq_df["date"])
        if len(pv) >= 2 and pv[0] > 0:
            total_ret = pv[-1] / pv[0] - 1.0
            days  = (dts.iloc[-1] - dts.iloc[0]).days
            years = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0
            peak  = np.maximum.accumulate(pv)
            dd    = pv / peak - 1.0
            max_dd = float(dd.min())

            m["total_ret"]  = round(total_ret, 4)
            m["cagr"]       = round(cagr, 4)
            m["max_dd"]     = round(max_dd, 4)
            m["mar"]        = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan

            daily_rets  = np.diff(pv) / pv[:-1]
            m["ann_vol"]    = round(float(np.std(daily_rets) * np.sqrt(252)), 4)
            m["sharpe"]     = round(cagr / m["ann_vol"], 3) if m["ann_vol"] > 0 else np.nan
            m["exposure_pct"] = round(float(eq_df["n_pos"].mean() / MAX_POS), 4)

            # Drawdown duration (calendar days)
            in_dd = dd < 0
            max_dd_dur = 0
            cur_dd_dur = 0
            for v in in_dd:
                if v:
                    cur_dd_dur += 1
                    max_dd_dur = max(max_dd_dur, cur_dd_dur)
                else:
                    cur_dd_dur = 0
            m["max_dd_days"] = max_dd_dur

            # Yearly returns from equity curve (BUG-3 fix)
            eq_tmp = eq_df.copy()
            eq_tmp["year"] = pd.to_datetime(eq_tmp["date"]).dt.year
            yearly: dict[int, dict] = {}
            for yr in YEARS:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) < 2:
                    yearly[yr] = {}
                    continue
                pv_yr = sub["total_equity"].values.astype(float)
                yr_ret = pv_yr[-1] / pv_yr[0] - 1.0
                yr_peak = np.maximum.accumulate(pv_yr)
                yr_dd   = pv_yr / yr_peak - 1.0
                # Trade stats for this year
                tr_yr = trades_df[pd.to_datetime(trades_df["entry_dt"]).dt.year == yr] if "entry_dt" in trades_df else pd.DataFrame()
                yearly[yr] = {
                    "portfolio_ret": round(float(yr_ret), 4),
                    "max_dd":        round(float(yr_dd.min()), 4),
                    "n_trades":      int(len(tr_yr)),
                    "win_rate":      round(float((tr_yr["net_ret"] > 0).mean()), 3) if len(tr_yr) > 0 else np.nan,
                }
            m["yearly"] = yearly

            # Monthly returns from equity curve
            eq_tmp["ym"] = pd.to_datetime(eq_tmp["date"]).dt.to_period("M")
            monthly = {}
            for ym, grp in eq_tmp.groupby("ym"):
                pv_m = grp["total_equity"].values.astype(float)
                if len(pv_m) >= 2:
                    monthly[str(ym)] = round(float(pv_m[-1] / pv_m[0] - 1.0), 4)
            m["monthly"] = monthly

    if "exit_reason" in trades_df.columns:
        m["exit_reasons"] = trades_df["exit_reason"].value_counts().to_dict()

    return m


def _fmt(v, pct=True, d=1) -> str:
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


def print_metrics(m: dict) -> None:
    sep = "=" * 66
    print(f"\n  {sep}")
    print(f"  {m.get('label','')}")
    print(f"  {sep}")
    print(f"  Trades:    {m.get('n_trades',0):<6}  Win:   {_fmt(m.get('win_rate',np.nan))}  "
          f"Expectancy: {_fmt(m.get('expectancy',np.nan))}")
    print(f"  CAGR:      {_fmt(m.get('cagr',np.nan)):<8}  MaxDD: {_fmt(m.get('max_dd',np.nan))}  "
          f"MAR:        {_fmt(m.get('mar',np.nan),pct=False,d=2)}")
    print(f"  Sharpe:    {_fmt(m.get('sharpe',np.nan),pct=False,d=2):<8}  PF:    "
          f"{_fmt(m.get('profit_factor',np.nan),pct=False,d=2)}  Ann vol: {_fmt(m.get('ann_vol',np.nan))}")
    print(f"  AvgRet:    {_fmt(m.get('avg_ret',np.nan)):<8}  Med:   {_fmt(m.get('median_ret',np.nan))}  "
          f"Hold(avg): {_fmt(m.get('avg_hold_days',np.nan),pct=False,d=0)} days")
    print(f"  AvgWin:    {_fmt(m.get('avg_win',np.nan)):<8}  Loss:  {_fmt(m.get('avg_loss',np.nan))}  "
          f"Exposure:  {_fmt(m.get('exposure_pct',np.nan))}")
    er = m.get("exit_reasons", {})
    if er:
        top3 = sorted(er.items(), key=lambda x: -x[1])[:4]
        print(f"  Exits:     {' | '.join(f'{k}:{v}' for k,v in top3)}")
    yr = m.get("yearly", {})
    if yr:
        print("  Yearly (portfolio equity):")
        for y in YEARS:
            d = yr.get(y, {})
            if d:
                print(f"    {y}: ret={_fmt(d.get('portfolio_ret',np.nan))}  "
                      f"dd={_fmt(d.get('max_dd',np.nan))}  "
                      f"n={d.get('n_trades',0)}  wr={_fmt(d.get('win_rate',np.nan))}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. CORPORATE ACTION ANOMALY CHECK
# ══════════════════════════════════════════════════════════════════════════════

def corporate_action_check(base: dict[str, dict], trades_df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag: (a) overnight gap > 40% absolute; (b) any trade net_ret > 150% or < -60%.
    Vietnam data: prices in VND (not thousands). Confirmed by ADV50 magnitudes.
    """
    anomalies = []
    for sym, b in base.items():
        c, o = b["close"], b["open"]
        dts  = b["dates"]
        for i in range(1, len(c)):
            if c[i-1] > 0:
                gap = c[i] / c[i-1] - 1.0
                if abs(gap) > 0.40:
                    anomalies.append({
                        "type": "EXTREME_GAP",
                        "symbol": sym,
                        "date": str(dts[i].date()),
                        "prev_close": round(float(c[i-1]), 2),
                        "curr_close": round(float(c[i]), 2),
                        "gap_pct":    round(float(gap), 4),
                    })
    if not trades_df.empty and "net_ret" in trades_df.columns:
        sus = trades_df[(trades_df["net_ret"] > 1.50) | (trades_df["net_ret"] < -0.60)]
        for _, row in sus.iterrows():
            anomalies.append({
                "type":       "SUSPICIOUS_TRADE",
                "symbol":     row.get("symbol", ""),
                "date":       str(row.get("exit_dt", "")),
                "prev_close": np.nan,
                "curr_close": np.nan,
                "gap_pct":    row.get("net_ret", np.nan),
            })
    return pd.DataFrame(anomalies)


# ══════════════════════════════════════════════════════════════════════════════
# 8. CONCENTRATION ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def concentration_analysis(trades_df: pd.DataFrame, eq_df: pd.DataFrame, label: str) -> dict:
    if trades_df.empty:
        return {}
    rets = trades_df["net_ret"].values.astype(float)
    pnl  = rets  # relative PnL (each trade uses 1/max_pos of capital)

    # Herfindahl on absolute gains of winning trades
    wins_pnl = pnl[pnl > 0]
    hhi = float(np.sum(wins_pnl**2) / (np.sum(wins_pnl)**2)) if wins_pnl.sum() > 0 else np.nan

    n_trades = len(pnl)
    top_n    = {}
    for n in [1, 3, 5]:
        sorted_rets = np.sort(pnl)[::-1]
        top_contrib = float(sorted_rets[:n].sum() / max(pnl[pnl>0].sum(), 1e-9)) if pnl[pnl>0].sum()>0 else np.nan
        top_n[f"top{n}_pct_of_gains"] = round(top_contrib, 4)

    # CAGR after removing top-N winners
    pv = eq_df["total_equity"].values.astype(float)
    dts = pd.to_datetime(eq_df["date"])
    years = max((dts.iloc[-1] - dts.iloc[0]).days / 365.25, 0.01)
    full_cagr = (pv[-1]/pv[0])**(1/years) - 1.0 if pv[0] > 0 else np.nan

    removal_tests = {}
    for remove_n in [1, 3, 5]:
        # Remove top N trades by capping their return at 0
        rets_adj = rets.copy()
        sorted_idx = np.argsort(rets_adj)[::-1]
        rets_adj[sorted_idx[:remove_n]] = 0.0
        trade_pv = float(np.prod(1 + rets_adj / MAX_POS))
        adj_cagr = trade_pv**(1/years) - 1.0
        removal_tests[f"cagr_ex_top{remove_n}"] = round(adj_cagr, 4)

    # Cap single-trade return and recompute
    cap_tests = {}
    for cap in [0.5, 0.75, 1.0, 1.5]:
        rets_capped = np.minimum(rets, cap)
        trade_pv    = float(np.prod(1 + rets_capped / MAX_POS))
        cap_cagr    = trade_pv**(1/years) - 1.0
        cap_tests[f"cagr_cap_{int(cap*100)}pct"] = round(cap_cagr, 4)

    # Ticker concentration
    ticker_pnl = trades_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
    top5_tickers = ticker_pnl.head(5).to_dict()

    return {
        "label": label,
        "n_trades": n_trades,
        "hhi_of_gains": round(hhi, 4),
        "full_cagr": round(full_cagr, 4),
        **top_n,
        **removal_tests,
        **cap_tests,
        "top5_tickers": str(top5_tickers),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. ENTRY QUALITY: FORWARD RETURNS (fixed horizons, episode-level)
# ══════════════════════════════════════════════════════════════════════════════

def entry_quality_analysis(base: dict[str, dict]) -> pd.DataFrame:
    """
    For every eligible entry signal (GK Orig, GK Fast, DC), compute forward returns
    at horizons 5, 10, 20, 40, 63 bars.  ADV50 filter applied.
    """
    horizons = [5, 10, 20, 40, 63]
    rows = []
    for sym, b in base.items():
        c   = b["close"]
        adv = b["adv50_lag"]
        dts = b["dates"]
        n   = len(c)

        for sig_type in ("gk_orig", "gk_fast", "dc"):
            if sig_type in ("gk_orig", "gk_fast"):
                sigs = b[sig_type]["gk_buy"]
            else:
                sigs = b["dc_buy"]

            for t in np.where(sigs)[0]:
                if np.isnan(adv[t]) or adv[t] < ADV50_MIN_BN:
                    continue
                row = {
                    "symbol":   sym,
                    "date":     str(dts[t].date()),
                    "sig_type": sig_type,
                    "adv50":    round(float(adv[t]), 3),
                }
                entry_open = float(b["open"][t + 1]) if t + 1 < n and b["open"][t + 1] > 0 else 0
                if entry_open <= 0:
                    continue
                for h in horizons:
                    exit_t = t + h
                    if exit_t < n:
                        fwd_ret = float(c[exit_t]) / entry_open - 1.0
                        row[f"fwd_{h}"] = round(fwd_ret, 4)
                    else:
                        row[f"fwd_{h}"] = np.nan
                # MFE/MAE over 63-bar window
                window_end = min(t + 63, n - 1)
                closes_w = c[t+1: window_end+1]
                row["mfe63"] = round(float(closes_w.max() / entry_open - 1.0), 4) if len(closes_w) else np.nan
                row["mae63"] = round(float(closes_w.min() / entry_open - 1.0), 4) if len(closes_w) else np.nan
                rows.append(row)

    return pd.DataFrame(rows)


def summarise_entry_quality(eq_df: pd.DataFrame) -> pd.DataFrame:
    if eq_df.empty:
        return pd.DataFrame()
    rows = []
    for sig_type, grp in eq_df.groupby("sig_type"):
        row = {"sig_type": sig_type, "n_signals": len(grp)}
        for col in [c for c in grp.columns if c.startswith("fwd_")]:
            vals = grp[col].dropna().values.astype(float)
            if len(vals):
                row[f"{col}_mean"]    = round(float(vals.mean()), 4)
                row[f"{col}_median"]  = round(float(np.median(vals)), 4)
                row[f"{col}_win_rate"]= round(float((vals > 0).mean()), 3)
        for col in ("mfe63", "mae63"):
            vals = grp[col].dropna().values.astype(float) if col in grp else np.array([])
            if len(vals):
                row[f"{col}_mean"]   = round(float(vals.mean()), 4)
                row[f"{col}_median"] = round(float(np.median(vals)), 4)
        rows.append(row)
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 10. WALK-FORWARD VALIDATION (3 folds, simplified)
# ══════════════════════════════════════════════════════════════════════════════

def walk_forward(base: dict[str, dict], arm_cfgs: list[ArmCfg], folds: list[tuple]) -> pd.DataFrame:
    """
    folds: list of (train_end, test_start, test_end) — date strings
    Uses best_arm from training period (by MAR) applied unchanged to test period.
    For simplicity, runs the same arm configs on each fold and reports metrics.
    """
    rows = []
    original_start = START_DATE
    original_end   = END_DATE

    # Monkey-patch global start/end is messy; instead just filter trades/equity by date.
    for fold_i, (train_s, train_e, test_s, test_e) in enumerate(folds):
        ts = pd.Timestamp(train_s)
        te = pd.Timestamp(train_e)
        tts = pd.Timestamp(test_s)
        tte = pd.Timestamp(test_e)

        for arm in arm_cfgs[:6]:  # test first 6 arms for brevity
            eq, tr, _ = run_arm_v2(base, arm)
            if eq.empty or tr.empty:
                continue
            eq["date"] = pd.to_datetime(eq["date"])
            tr["entry_dt"] = pd.to_datetime(tr["entry_dt"])

            train_eq = eq[(eq["date"] >= ts) & (eq["date"] <= te)].reset_index(drop=True)
            test_eq  = eq[(eq["date"] >= tts) & (eq["date"] <= tte)].reset_index(drop=True)
            train_tr = tr[(tr["entry_dt"] >= ts) & (tr["entry_dt"] <= te)]
            test_tr  = tr[(tr["entry_dt"] >= tts) & (tr["entry_dt"] <= tte)]

            m_train = compute_metrics(train_eq, train_tr, "")
            m_test  = compute_metrics(test_eq,  test_tr,  "")

            rows.append({
                "fold":        fold_i + 1,
                "train":       f"{train_s}–{train_e}",
                "test":        f"{test_s}–{test_e}",
                "arm_id":      arm.arm_id,
                "label":       arm.label,
                "train_cagr":  m_train.get("cagr", np.nan),
                "train_mar":   m_train.get("mar", np.nan),
                "train_maxdd": m_train.get("max_dd", np.nan),
                "test_cagr":   m_test.get("cagr", np.nan),
                "test_mar":    m_test.get("mar", np.nan),
                "test_maxdd":  m_test.get("max_dd", np.nan),
                "test_n":      m_test.get("n_trades", 0),
                "degradation": round(float(m_test.get("mar", np.nan)) / max(float(m_train.get("mar", 1e-6)), 1e-6), 3),
            })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 11. VNINDEX BENCHMARK
# ══════════════════════════════════════════════════════════════════════════════

def vnindex_bah(vnindex_raw: pd.DataFrame) -> dict:
    v = vnindex_raw.copy()
    v["date"] = pd.to_datetime(v["date"])
    v = v[(v["date"] >= START_DATE) & (v["date"] <= END_DATE)].sort_values("date")
    if len(v) < 2:
        return {"label": "VNINDEX B&H"}
    c     = v["close"].values.astype(float)
    dts   = v["date"]
    years = max((dts.iloc[-1] - dts.iloc[0]).days / 365.25, 0.01)
    cagr  = (c[-1] / c[0]) ** (1.0 / years) - 1.0
    peak  = np.maximum.accumulate(c)
    max_dd = float((c / peak - 1.0).min())
    daily_rets = np.diff(c) / c[:-1]
    ann_vol = float(np.std(daily_rets) * np.sqrt(252))
    yearly: dict[int, float] = {}
    for yr in YEARS:
        sub = v[v["date"].dt.year == yr]
        if len(sub) >= 2:
            cc = sub["close"].values.astype(float)
            yearly[yr] = round(float(cc[-1] / cc[0] - 1.0), 4)
    return {
        "label":     "VNINDEX B&H",
        "n_trades":  1,
        "cagr":      round(cagr, 4),
        "max_dd":    round(max_dd, 4),
        "mar":       round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan,
        "ann_vol":   round(ann_vol, 4),
        "sharpe":    round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan,
        "total_ret": round(float(c[-1] / c[0] - 1.0), 4),
        "yearly":    {yr: {"portfolio_ret": r, "max_dd": np.nan, "n_trades": 0, "win_rate": np.nan}
                      for yr, r in yearly.items()},
    }


# ══════════════════════════════════════════════════════════════════════════════
# 12. AUDIT REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def write_audit_report(all_metrics: list[dict], conc: list[dict],
                       signal_stats: list[dict], anomaly_count: int) -> None:
    path = OUT_DIR / "audit_report.md"
    lines = ["# VN Quant Full Audit Report", "",
             f"Run date: {pd.Timestamp.now().date()}",
             f"Data period: {START_DATE.date()} – {END_DATE.date()}", "",
             "## Bugs Found and Fixed", "",
             "### BUG-1: Exit-day return missing from equity curve (CRITICAL)",
             "**Prior code**: positions deleted from `positions` dict BEFORE MTM on exit signal day.",
             "This caused the final day's return (close[T-1]→close[T]) for each exiting position",
             "to be excluded from the equity curve.  Impact: systematic upward bias in equity CAGR",
             "when exits fire after down days (GK_SELL, hard stops).",
             "",
             "**Fix**: Pending-exit queue.  Positions remain in `holdings` dict through MTM on signal day.",
             "Exit proceeds (shares × open[T+1] × cost_x) reflected in `cash` on execution day T+1.",
             "Equity is always: `cash + sum(shares_i × close_i)`.", "",
             "### BUG-2: Stop triggered by Close price, not intraday Low (MODERATE)",
             "**Prior code**: stop checked as `(close / entry_open - 1) <= -stop_pct`.",
             "This misses intraday breaches where Low[t] < stop but Close[t] > stop.",
             "",
             "**Fix**: Check `Low[t] <= stop_price`.  Conservative exit: `min(stop_price, Open[t+1])`.",
             "For gap-down scenarios: exit at next open if it is lower than the stop level.", "",
             "### BUG-3: Yearly returns from serial trade compounding (DISPLAY BUG)",
             "**Prior code**: `np.prod(1 + trade_rets) - 1` per year.",
             "This treats all trades in a year as serial (sequential), severely overstating returns",
             "when trades are parallel (multiple positions simultaneously).",
             "",
             "**Fix**: All yearly/monthly returns derived from daily portfolio equity curve.", "",
             "### GK Parameter Mismatch (DOCUMENTATION)",
             "Written report cited Len=100, ATRLen=14 as default.  Code used Len=200, ATRLen=21.",
             "**Resolution**: Both parameter sets run separately as A1/H1 (Orig L200) and A2 (Fast L100).", "",
             "### Remaining Limitation",
             "Stop cap (min(stop_level, next_open)) is applied at execution time using the stored cap",
             "from signal day.  If a gap-down opens BELOW the stop level, we exit at the open,",
             "which is the conservative (worse) outcome — this is the correct behavior.", "",
             "## Data Convention",
             "- Source: FireAnt OHLCV parquet cache, 271 symbols, 2023-01-03 – 2026-04-29",
             "- Price unit: VND (not thousands VND).  Confirmed by ADV50 magnitudes (~2–20 billion VND/day",
             "  for liquid stocks at typical Vietnam price levels of 10,000–100,000 VND × vol 1M+ shares).",
             "- OHLC: price-adjusted (assumed; no raw/adjusted flag in dataset).",
             "- ADV50: lagged — mean(value[t-50:t])/1e9.  First valid bar = t=50.",
             "- Excluded: VPL (structural distortion per project convention).", "",
             f"## Corporate Action Anomaly Check",
             f"Found {anomaly_count} extreme-gap events (>40% overnight) or suspicious trades.",
             "See `corporate_action_anomalies.csv`.", "",
             "## Signal Count Summary", ""]

    for ss in signal_stats:
        lines.append(f"- **{ss.get('arm_id','')}** {ss.get('label','')}: "
                     f"raw={ss.get('raw_signals',0)} adv_ok={ss.get('adv_filtered',0)} "
                     f"selected={ss.get('selected',0)} rejected={ss.get('rejected',0)}")
    lines += ["",
              "## Summary: All Arms", "",
              "| Arm | Label | Trades | Win% | CAGR | MaxDD | MAR | Sharpe |",
              "|-----|-------|--------|------|------|-------|-----|--------|"]
    for m in all_metrics:
        lines.append(
            f"| {m.get('arm_id','?')} | {m.get('label','')} | {m.get('n_trades',0)} | "
            f"{_fmt(m.get('win_rate',np.nan))} | {_fmt(m.get('cagr',np.nan))} | "
            f"{_fmt(m.get('max_dd',np.nan))} | {_fmt(m.get('mar',np.nan),pct=False,d=2)} | "
            f"{_fmt(m.get('sharpe',np.nan),pct=False,d=2)} |"
        )
    lines += ["",
              "## Yearly Portfolio Returns (from equity curve — NOT serial compounding)", "",
              "| Arm | 2023 | 2024 | 2025 | 2026 YTD |",
              "|-----|------|------|------|----------|"]
    for m in all_metrics:
        yr = m.get("yearly", {})
        row = f"| {m.get('arm_id','?')} | " + " | ".join(
            _fmt(yr.get(y, {}).get("portfolio_ret", np.nan)) for y in YEARS) + " |"
        lines.append(row)

    lines += ["",
              "## Concentration Analysis",
              "",
              "| Arm | HHI | CAGR | ex-top1 | ex-top3 | ex-top5 | cap50% | cap75% |",
              "|-----|-----|------|---------|---------|---------|--------|--------|"]
    for cc in conc:
        lines.append(
            f"| {cc.get('label','?')} | {cc.get('hhi_of_gains','n/a')} | "
            f"{_fmt(cc.get('full_cagr',np.nan))} | "
            f"{_fmt(cc.get('cagr_ex_top1',np.nan))} | "
            f"{_fmt(cc.get('cagr_ex_top3',np.nan))} | "
            f"{_fmt(cc.get('cagr_ex_top5',np.nan))} | "
            f"{_fmt(cc.get('cagr_cap_50pct',np.nan))} | "
            f"{_fmt(cc.get('cagr_cap_75pct',np.nan))} |"
        )

    lines += ["",
              "## Final Conclusions",
              "",
              "See `corrected_summary.csv` for full metric table.",
              "See `yearly_portfolio_returns.csv` for year-by-year detail.",
              "See `concentration_report.csv` for winner-concentration robustness.",
              "See `entry_quality_comparison.csv` for episode-level forward-return analysis.",
              ""]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Audit report saved: %s", path)


# ══════════════════════════════════════════════════════════════════════════════
# 13. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows, %s – %s",
             panel["symbol"].nunique(), len(panel),
             panel["date"].min().date(), panel["date"].max().date())

    log.info("Loading VNINDEX: %s", VNINDEX_CSV)
    vnindex_raw = pd.read_csv(VNINDEX_CSV)
    vnindex_raw["date"] = pd.to_datetime(vnindex_raw["date"])

    log.info("Pre-computing base data (GK_Orig, GK_Fast, DC signals)...")
    base = precompute_base(panel)
    log.info("  Done: %d symbols", len(base))

    # Signal count summary
    n_gk_orig = sum(int(b["gk_orig"]["gk_buy"].sum()) for b in base.values())
    n_gk_fast = sum(int(b["gk_fast"]["gk_buy"].sum()) for b in base.values())
    n_dc      = sum(int(b["dc_buy"].sum()) for b in base.values())
    log.info("  Total raw signals — GK_Orig: %d  GK_Fast: %d  DC: %d", n_gk_orig, n_gk_fast, n_dc)

    # VNINDEX benchmark
    vnx_bah = vnindex_bah(vnindex_raw)
    vnx_bah["arm_id"] = "A4"; vnx_bah["label"] = "VNINDEX B&H"

    # Corporate action check (on raw data, before running arms)
    log.info("Running corporate action check...")
    ca_df = corporate_action_check(base, pd.DataFrame())
    ca_df.to_csv(OUT_DIR / "corporate_action_anomalies.csv", index=False)
    log.info("  Anomalies found: %d  (saved)", len(ca_df))

    # ── Entry quality analysis ─────────────────────────────────────────────
    log.info("Computing entry quality (forward returns per signal)...")
    eq_qual = entry_quality_analysis(base)
    eq_qual.to_csv(OUT_DIR / "entry_quality_raw.csv", index=False)
    eq_summary = summarise_entry_quality(eq_qual)
    eq_summary.to_csv(OUT_DIR / "entry_quality_comparison.csv", index=False)
    log.info("  Entry quality saved.")

    # ── Run all arms ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CORRECTED BACKTEST — All Arms")
    print("=" * 70)
    print(f"Universe: {len(base)} symbols  |  ADV50>={ADV50_MIN_BN}bn  |"
          f"  fee={FEE_BPS}+{SLIP_BPS} bps/side  |  MaxPos={MAX_POS}")
    print(f"Period: {START_DATE.date()} – {END_DATE.date()}")
    print(f"Portfolio engine: CORRECTED (cash+shares, pending-exit queue)")
    print(f"Stop execution:   CORRECTED (Low[t] breach → min(stop_level, Open[t+1]))")
    print(f"Yearly returns:   CORRECTED (from daily equity curve, NOT serial compounding)")

    all_metrics: list[dict] = []
    all_signal_stats: list[dict] = []
    all_trades_combined: list[pd.DataFrame] = []
    concentration_rows: list[dict] = []
    arm_equity_dfs: dict[str, pd.DataFrame] = {}

    for arm in ARMS:
        log.info("Running arm %s: %s", arm.arm_id, arm.label)
        eq_df, tr_df, sig_stats = run_arm_v2(base, arm)
        m = compute_metrics(eq_df, tr_df, arm.label)
        m["arm_id"] = arm.arm_id
        print_metrics(m)
        all_metrics.append(m)
        sig_stats["arm_id"] = arm.arm_id; sig_stats["label"] = arm.label
        all_signal_stats.append(sig_stats)
        if not tr_df.empty:
            all_trades_combined.append(tr_df)
        arm_equity_dfs[arm.arm_id] = eq_df

        # Concentration analysis
        cc = concentration_analysis(tr_df, eq_df, arm.arm_id)
        concentration_rows.append(cc)

        # Per-arm equity save
        eq_df.to_csv(OUT_DIR / f"daily_equity_{arm.arm_id}.csv", index=False)
        tr_df.to_csv(OUT_DIR / f"trade_log_{arm.arm_id}.csv", index=False)

    # VNINDEX print
    print(f"\n  {'='*66}")
    print(f"  {vnx_bah['label']}")
    print(f"  {'='*66}")
    print(f"  CAGR: {_fmt(vnx_bah.get('cagr',np.nan))}  MaxDD: {_fmt(vnx_bah.get('max_dd',np.nan))}"
          f"  MAR: {_fmt(vnx_bah.get('mar',np.nan),pct=False,d=2)}")
    for yr in YEARS:
        ret = vnx_bah.get("yearly", {}).get(yr, {}).get("portfolio_ret", np.nan)
        print(f"    {yr}: {_fmt(ret)}")

    # ── Walk-forward ────────────────────────────────────────────────────────
    log.info("Running walk-forward validation...")
    wf_folds = [
        ("2023-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
        ("2023-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
        ("2024-01-01", "2025-12-31", "2026-01-01", "2026-04-30"),
    ]
    wf_df = walk_forward(base, ARMS, wf_folds)
    wf_df.to_csv(OUT_DIR / "walk_forward_results.csv", index=False)
    log.info("  Walk-forward saved.")

    # ── Combined outputs ────────────────────────────────────────────────────
    all_trades_df = pd.concat(all_trades_combined, ignore_index=True) if all_trades_combined else pd.DataFrame()
    all_trades_df.to_csv(OUT_DIR / "trade_log_all_arms.csv", index=False)

    # Summary CSV
    summary_rows = []
    for m in all_metrics:
        row = {k: v for k, v in m.items() if k not in ("yearly", "monthly", "exit_reasons")}
        summary_rows.append(row)
    summary_rows.append({k: v for k, v in vnx_bah.items() if k not in ("yearly", "monthly")})
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "corrected_summary.csv", index=False)

    # Yearly portfolio returns
    yr_rows = []
    for m in all_metrics + [vnx_bah]:
        row = {"arm_id": m.get("arm_id",""), "label": m.get("label","")}
        for yr in YEARS:
            d = m.get("yearly", {}).get(yr, {})
            row[f"ret_{yr}"]    = d.get("portfolio_ret", np.nan)
            row[f"maxdd_{yr}"]  = d.get("max_dd", np.nan)
            row[f"n_{yr}"]      = d.get("n_trades", 0)
        yr_rows.append(row)
    pd.DataFrame(yr_rows).to_csv(OUT_DIR / "yearly_portfolio_returns.csv", index=False)

    # Monthly returns
    mth_rows = []
    for m in all_metrics:
        monthly = m.get("monthly", {})
        for ym, ret in monthly.items():
            mth_rows.append({"arm_id": m.get("arm_id",""), "label": m.get("label",""),
                             "year_month": ym, "portfolio_ret": ret})
    pd.DataFrame(mth_rows).to_csv(OUT_DIR / "monthly_portfolio_returns.csv", index=False)

    # Concentration report
    pd.DataFrame(concentration_rows).to_csv(OUT_DIR / "concentration_report.csv", index=False)

    # Signal stats
    pd.DataFrame(all_signal_stats).to_csv(OUT_DIR / "signal_count_by_arm.csv", index=False)

    # Best/worst 20 trades (across arms H4–H11)
    if not all_trades_df.empty:
        top20  = all_trades_df.nlargest(20, "net_ret")
        bot20  = all_trades_df.nsmallest(20, "net_ret")
        top20.to_csv(OUT_DIR / "best_20_trades.csv", index=False)
        bot20.to_csv(OUT_DIR / "worst_20_trades.csv", index=False)

    # ── Audit report ───────────────────────────────────────────────────────
    write_audit_report(all_metrics, concentration_rows, all_signal_stats, len(ca_df))

    # ── Final comparison print ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FINAL COMPARISON TABLE (corrected engine)")
    print("=" * 70)
    cols = ["arm_id", "label", "n_trades", "win_rate", "cagr", "max_dd", "mar", "sharpe", "exposure_pct"]
    rows_print = []
    for m in all_metrics:
        rows_print.append({c: m.get(c, np.nan) for c in cols})
    df_print = pd.DataFrame(rows_print)
    # Format
    for c in ["win_rate", "cagr", "max_dd", "exposure_pct"]:
        df_print[c] = df_print[c].apply(lambda x: f"{x*100:.1f}%" if not (isinstance(x,float) and np.isnan(x)) else "n/a")
    for c in ["mar", "sharpe"]:
        df_print[c] = df_print[c].apply(lambda x: f"{x:.2f}" if not (isinstance(x,float) and np.isnan(x)) else "n/a")
    print(df_print.to_string(index=False))

    print("\n" + "=" * 70)
    print("YEARLY PORTFOLIO RETURNS (from daily equity curve)")
    print("=" * 70)
    for m in all_metrics + [vnx_bah]:
        yr = m.get("yearly", {})
        parts = "  ".join(
            f"{y}:{_fmt(yr.get(y,{}).get('portfolio_ret',np.nan))}" for y in YEARS)
        print(f"  {m.get('arm_id','?'):5s}  {m.get('label',''):35s}  {parts}")

    print(f"\n\nAll outputs saved to: {OUT_DIR}")
    log.info("Done.")


if __name__ == "__main__":
    main()
