#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 2 Research — Concentration / Exposure / EMA Filters / Grid / Ranking / DC+GKFast

Tasks:
  1. True concentration rerun (actual portfolio exclusions, not caps)
  2. Exposure-adjusted benchmarks (beta, correlation, active DD)
  3. GK_Fast + EMA filter arms (6 variants)
  4. GK_Fast parameter grid 18 combos (Len:80/100/120, Mult:1.8/2.0/2.2, Conf:2/3)
  5. DC + ranking variants (5 ranking × 3 exit = 15 arms)
  6. DC + GK_FAST exit arms (3 new arms)
  7. Data quality cross-check (top 20 trades vs corporate_action_anomalies.csv)

Outputs → data/research/gk_audit/phase2/
"""
from __future__ import annotations

import io, sys, logging, warnings, itertools, textwrap
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

REPO    = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
CACHE_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet"
VNINDEX_CSV   = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
P1_DIR        = REPO / "data/research/gk_audit"
OUT_DIR       = REPO / "data/research/gk_audit/phase2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
START_DATE   = pd.Timestamp("2023-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
ADV50_MIN_BN = 2.0
MAX_POS      = 10
INITIAL_CAP  = 1.0
YEARS        = [2023, 2024, 2025, 2026]
EXCL         = {"VPL"}
FEE_BPS      = 25.0
SLIP_BPS     = 10.0
DON_LEN      = 20
DON_BUF      = 1.003
EMA_FAST     = 10
EMA_SLOW     = 50

GK_ORIG = {"gk_len": 200, "gk_mult": 2.0, "gk_atr": 21, "gk_conf": 2}
GK_FAST = {"gk_len": 100, "gk_mult": 2.0, "gk_atr": 14, "gk_conf": 2}

CA_SYMBOLS = frozenset([
    "ANV","BIC","CSV","DPM","DPR","IMP","L40","MCH",
    "MSH","NTL","SAB","SIP","TCB","TCO","VIC",
])

# ══════════════════════════════════════════════════════════════════════════════
# 1.  ARM CONFIG (Phase 2 extended)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmP2:
    arm_id:   str
    label:    str
    # Entry
    entry:              str   = "gk"         # "gk" | "donchian"
    entry_filter:       str   = "none"       # "none" | "ema_cloud"
    gk_params:          dict  = field(default_factory=lambda: GK_ORIG)
    gk_custom_key:      str   = ""           # override gk signal lookup key
    # Entry filters (Phase 2)
    require_close_above_ema: int  = 0        # 0=off, 50/100/150 → close > EMA(N)
    require_ema_slope:       int  = 0        # 0=off, N → EMA(N)[t]>EMA(N)[t-1]
    rs3m_filter:             bool = False    # entry requires RS3M vs VNINDEX > 0
    # Exit
    exit_type:          str   = "gk_sell"   # "gk_sell"|"fixed_N"|"ema10"|"ema20"
    fixed_hold:         int   = 63
    min_hold:           int   = 0
    # Stops
    stop_pct:           float = 0.0
    gk_lower_stop:      str   = "none"      # "none"|"D1"|"D2"|"D4"
    atr_stop_mult:      float = 0.0
    atr_stop_len:       int   = 14
    chandelier_mult:    float = 0.0
    chandelier_atr_len: int   = 14
    chandelier_activate:float = 0.10
    # Portfolio
    max_pos:  int   = MAX_POS
    fee_bps:  float = FEE_BPS
    slip_bps: float = SLIP_BPS
    # Ranking
    ranking:  str   = "adv50"  # "adv50"|"rs3m"|"rs6m"|"composite"|"near52wk"|"volexp"
    # Blacklist
    blacklist: frozenset = field(default_factory=frozenset)

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000
    @property
    def gk_key(self):
        if self.gk_custom_key:
            return self.gk_custom_key
        return "gk_orig" if self.gk_params == GK_ORIG else "gk_fast"


# ══════════════════════════════════════════════════════════════════════════════
# 2.  MATH PRIMITIVES (copied from full_audit)
# ══════════════════════════════════════════════════════════════════════════════

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out   = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = float(arr[i])
        if np.isnan(v):
            continue
        prev  = out[i-1] if i > 0 and not np.isnan(out[i-1]) else np.nan
        out[i] = v if np.isnan(prev) else alpha * v + (1.0 - alpha) * prev
    return out


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    tr    = np.empty(len(close))
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
    alpha = 1.0 / n
    out   = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n-1] = float(np.mean(tr[:n]))
        for i in range(n, len(tr)):
            out[i] = alpha * tr[i] + (1.0 - alpha) * out[i-1]
    return out


def _adv50_lagged(value: np.ndarray) -> np.ndarray:
    out = np.full(len(value), np.nan)
    for i in range(50, len(value)):
        out[i] = float(np.mean(value[i-50:i])) / 1e9
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 3.  SIGNAL COMPUTATION (copied + extended)
# ══════════════════════════════════════════════════════════════════════════════

def compute_gk_signals(
    close: np.ndarray, high: np.ndarray, low: np.ndarray,
    gk_len: int, gk_mult: float, gk_atr: int, gk_conf: int,
) -> dict:
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
    zl_prev  = np.concatenate([[np.nan], gk_zl[:-1]])
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
    close: np.ndarray, high: np.ndarray,
    ema10: np.ndarray, ema50: np.ndarray,
) -> np.ndarray:
    n      = len(close)
    dc_buy = np.zeros(n, dtype=bool)
    for i in range(DON_LEN, n):
        if np.isnan(ema10[i]) or np.isnan(ema50[i]):
            continue
        don_high   = np.max(high[i-DON_LEN:i])
        trigger    = don_high * DON_BUF
        bull_cloud = bool(ema10[i] > ema50[i])
        above_cloud= bool(close[i] > max(ema10[i], ema50[i]))
        dc_buy[i]  = (close[i] > trigger) and bull_cloud and above_cloud
    return dc_buy


# ══════════════════════════════════════════════════════════════════════════════
# 4.  PRECOMPUTE BASE (extended with EMA100, EMA150, RS3M, RS6M, near52wk)
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base_p2(panel: pd.DataFrame, vnx_by_date: dict[str, float]) -> dict[str, dict]:
    base: dict[str, dict] = {}
    for sym, grp in panel.groupby("symbol"):
        df  = grp.sort_values("date").reset_index(drop=True)
        c   = df["close"].values.astype(float)
        h   = df["high"].values.astype(float)
        l   = df["low"].values.astype(float)
        o   = df["open"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)
        n   = len(c)

        e10  = _ema(c, EMA_FAST)
        e20  = _ema(c, 20)
        e50  = _ema(c, EMA_SLOW)
        e100 = _ema(c, 100)
        e150 = _ema(c, 150)

        gk_o = compute_gk_signals(c, h, l, **GK_ORIG)
        gk_f = compute_gk_signals(c, h, l, **GK_FAST)
        dc_b = compute_dc_signals(c, h, e10, e50)

        # RS3M / RS6M vs VNINDEX (lagged, no look-ahead)
        rs3m = np.full(n, np.nan)
        rs6m = np.full(n, np.nan)
        for i in range(n):
            d_str = str(dts[i].date())
            vnx_t = vnx_by_date.get(d_str, np.nan)
            if i >= 63:
                d63   = str(dts[i-63].date())
                vnx_l = vnx_by_date.get(d63, np.nan)
                if (not np.isnan(vnx_t) and not np.isnan(vnx_l)
                        and vnx_l > 0 and c[i-63] > 0):
                    rs3m[i] = (c[i]/c[i-63] - 1.0) - (vnx_t/vnx_l - 1.0)
            if i >= 126:
                d126  = str(dts[i-126].date())
                vnx_l = vnx_by_date.get(d126, np.nan)
                if (not np.isnan(vnx_t) and not np.isnan(vnx_l)
                        and vnx_l > 0 and c[i-126] > 0):
                    rs6m[i] = (c[i]/c[i-126] - 1.0) - (vnx_t/vnx_l - 1.0)

        # Near-52wk-high score (1.0 = at the high, <1 = below)
        near52 = np.full(n, np.nan)
        for i in range(1, n):
            lo_i = max(0, i - 252)
            hi_window = np.max(h[lo_i:i])
            if hi_window > 0:
                near52[i] = c[i] / hi_window

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
            "ema100":      e100,
            "ema150":      e150,
            "atr14":       _wilder_atr(h, l, c, 14),
            "atr21":       _wilder_atr(h, l, c, 21),
            "gk_orig":     gk_o,
            "gk_fast":     gk_f,
            "dc_buy":      dc_b,
            "rs3m":        rs3m,
            "rs6m":        rs6m,
            "near52":      near52,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


def precompute_grid_signals(base: dict[str, dict], combos: list[dict]) -> None:
    """Compute GK signals for all grid combos; store in base[sym][combo_key]."""
    n_syms = len(base)
    for ci, combo in enumerate(combos):
        key = combo["key"]
        log.info("  Grid precompute %d/%d: %s", ci+1, len(combos), key)
        for b in base.values():
            b[key] = compute_gk_signals(
                b["close"], b["high"], b["low"],
                combo["gk_len"], combo["gk_mult"],
                combo["gk_atr"], combo["gk_conf"],
            )


# ══════════════════════════════════════════════════════════════════════════════
# 5.  RANKING SCORE HELPER
# ══════════════════════════════════════════════════════════════════════════════

def get_rank_score(sym: str, b: dict, t: int, ranking: str) -> float:
    adv = float(b["adv50_lag"][t]) if not np.isnan(b["adv50_lag"][t]) else 0.0
    if ranking == "adv50":
        return adv
    elif ranking == "rs3m":
        v = float(b["rs3m"][t])
        return v if not np.isnan(v) else -999.0
    elif ranking == "rs6m":
        v = float(b["rs6m"][t])
        return v if not np.isnan(v) else -999.0
    elif ranking == "composite":
        r3 = float(b["rs3m"][t])
        r6 = float(b["rs6m"][t])
        if np.isnan(r3) or np.isnan(r6):
            return -999.0
        return 0.5 * r3 + 0.5 * r6
    elif ranking == "near52wk":
        v = float(b["near52"][t])
        return v if not np.isnan(v) else -999.0
    elif ranking == "volexp":
        if adv <= 0:
            return -999.0
        val = float(b["value"][t])
        return val / (adv * 1e9)
    return adv


# ══════════════════════════════════════════════════════════════════════════════
# 6.  PORTFOLIO ENGINE (Phase 2 extended)
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_p2(
    base: dict[str, dict],
    arm: ArmP2,
    all_dates: Optional[list] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Extended run_arm_v2:
    - blacklist: skip entry signals for listed symbols
    - require_close_above_ema: EMA filter
    - require_ema_slope: EMA slope filter
    - rs3m_filter: require RS3M vs VNINDEX > 0
    - ranking: custom ranking score
    - gk_custom_key: arbitrary GK param set
    """
    gk_key = arm.gk_key
    cost_e = arm.cost_e
    cost_x = arm.cost_x
    blacklist = arm.blacklist

    if all_dates is None:
        all_dates = sorted({d for b in base.values() for d in b["dates"]})
        all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]

    cash          = INITIAL_CAP
    holdings:       dict[str, dict]  = {}
    pending_exits:  dict[str, tuple] = {}
    pending_entries: list[tuple]     = []
    trades:    list[dict] = []
    eq_curve:  list[dict] = []
    prev_equity = INITIAL_CAP
    raw_signals = 0; adv_signals = 0; sel_trades = 0

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
                reason  += "_FB"
            if exit_cap is not None and exit_cap > 0:
                open_raw = min(exit_cap, open_raw)
            pos      = holdings.pop(sym)
            proceeds = pos["shares"] * open_raw * cost_x
            cash    += proceeds
            net_ret  = (open_raw * cost_x) / pos["entry_px_eff"] - 1.0
            trades.append({
                "symbol":          sym,
                "arm_id":          arm.arm_id,
                "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
                "entry_dt":        str(pos["entry_dt"].date()) if hasattr(pos["entry_dt"], "date") else str(pos["entry_dt"]),
                "entry_open_raw":  round(pos["entry_open_raw"], 4),
                "entry_px_eff":    round(pos["entry_px_eff"], 4),
                "exit_signal_dt":  str(pos.get("exit_signal_dt", "")) if not hasattr(pos.get("exit_signal_dt"), "date") else str(pos["exit_signal_dt"].date()),
                "exit_dt":         str(trade_date.date()),
                "exit_open_raw":   round(open_raw, 4),
                "exit_px_eff":     round(open_raw * cost_x, 4),
                "exit_reason":     reason,
                "hold_days":       (trade_date - pos["entry_dt"]).days,
                "hold_bars":       day_i - pos["entry_day_i"],
                "gross_ret":       round(open_raw / pos["entry_open_raw"] - 1.0, 6),
                "net_ret":         round(net_ret, 6),
                "adv50_entry":     round(pos["adv50_entry"], 3),
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
            "date":           trade_date,
            "cash":           round(cash, 6),
            "market_value":   round(market_val, 6),
            "total_equity":   round(equity, 6),
            "n_pos":          len(holdings),
            "gross_exposure": round(market_val / max(equity, 1e-9), 4),
        })

        # ── Step 4: Scan exit signals ─────────────────────────────────────────
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
                    triggered, reason, exit_cap = True, "ATR_TRAIL", atr_trail

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
                if sym in blacklist:
                    continue
                if sym in holdings or sym in pending_exits or any(x[0] == sym for x in pending_entries):
                    continue
                t = b["date_to_idx"].get(day_str)
                if t is None or t + 1 >= len(b["close"]):
                    continue
                if float(b["open"][t + 1]) <= 0:
                    continue
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN_BN:
                    continue

                # Entry signal check
                ok = False
                if arm.entry == "gk":
                    raw_signals += 1
                    if bool(b[gk_key]["gk_buy"][t]):
                        adv_signals += 1
                        ok = True
                    if ok and arm.entry_filter == "ema_cloud":
                        e10v = float(b["ema10"][t]); e50v = float(b["ema50"][t])
                        if not (e10v > e50v):
                            ok = False
                elif arm.entry == "donchian":
                    if bool(b["dc_buy"][t]):
                        raw_signals += 1; adv_signals += 1; ok = True

                # Phase 2 entry filters
                if ok and arm.require_close_above_ema > 0:
                    ema_map = {50: "ema50", 100: "ema100", 150: "ema150"}
                    ema_key = ema_map.get(arm.require_close_above_ema)
                    if ema_key and ema_key in b:
                        ema_val = float(b[ema_key][t])
                        if np.isnan(ema_val) or float(b["close"][t]) <= ema_val:
                            ok = False
                    else:
                        ok = False

                if ok and arm.require_ema_slope > 0 and t > 0:
                    ema_map = {50: "ema50", 100: "ema100", 150: "ema150"}
                    ema_key = ema_map.get(arm.require_ema_slope)
                    if ema_key and ema_key in b:
                        ev_curr = float(b[ema_key][t])
                        ev_prev = float(b[ema_key][t-1])
                        if np.isnan(ev_curr) or np.isnan(ev_prev) or ev_curr <= ev_prev:
                            ok = False

                if ok and arm.rs3m_filter:
                    rs = float(b["rs3m"][t])
                    if np.isnan(rs) or rs <= 0:
                        ok = False

                if ok:
                    rank_score = get_rank_score(sym, b, t, arm.ranking)
                    if np.isnan(rank_score):
                        rank_score = 0.0
                    pending_entries.append((
                        sym, t,
                        {
                            "entry_signal_dt": trade_date,
                            "adv50_entry":     adv,
                            "entry_mode":      arm.entry,
                        },
                        rank_score,
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
            "entry_mode":      pos["entry_mode"],
            "mfe":             round(pos.get("mfe", np.nan), 4),
            "mae":             round(pos.get("mae", np.nan), 4),
        })

    signal_stats = {"raw_signals": raw_signals, "adv_filtered": adv_signals, "selected": sel_trades}
    return pd.DataFrame(eq_curve), pd.DataFrame(trades), signal_stats


# ══════════════════════════════════════════════════════════════════════════════
# 7.  METRICS (copied from full_audit)
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(eq_df: pd.DataFrame, trades_df: pd.DataFrame, label: str = "") -> dict:
    m: dict = {"label": label, "n_trades": 0}
    if trades_df.empty:
        return m
    rets   = trades_df["net_ret"].values.astype(float)
    wins   = rets[rets > 0]; losses = rets[rets <= 0]
    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4)
    m["avg_ret"]       = round(float(rets.mean()), 4)
    m["avg_win"]       = round(float(wins.mean()),   4) if len(wins)   else np.nan
    m["avg_loss"]      = round(float(losses.mean()), 4) if len(losses) else np.nan
    m["profit_factor"] = round(float(wins.sum() / (-losses.sum())), 3) \
                         if len(losses) and losses.sum() < 0 else np.nan
    m["best_trade"]  = round(float(rets.max()), 4)
    m["worst_trade"] = round(float(rets.min()), 4)
    if not eq_df.empty and "total_equity" in eq_df.columns:
        pv  = eq_df["total_equity"].values.astype(float)
        dts = pd.to_datetime(eq_df["date"])
        if len(pv) >= 2 and pv[0] > 0:
            days  = (dts.iloc[-1] - dts.iloc[0]).days
            years = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0
            peak  = np.maximum.accumulate(pv)
            dd    = pv / peak - 1.0
            max_dd = float(dd.min())
            m["cagr"]   = round(cagr, 4)
            m["max_dd"] = round(max_dd, 4)
            m["mar"]    = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan
            daily_rets  = np.diff(pv) / pv[:-1]
            ann_vol     = float(np.std(daily_rets) * np.sqrt(252))
            m["ann_vol"]= round(ann_vol, 4)
            m["sharpe"] = round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan
            m["exposure_pct"] = round(float(eq_df["n_pos"].mean() / MAX_POS), 4)
            # Yearly returns from equity curve
            eq_tmp  = eq_df.copy()
            eq_tmp["year"] = pd.to_datetime(eq_tmp["date"]).dt.year
            yearly: dict = {}
            for yr in YEARS:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) < 2:
                    yearly[yr] = {}
                    continue
                pv_yr = sub["total_equity"].values.astype(float)
                yr_ret = pv_yr[-1] / pv_yr[0] - 1.0
                yr_peak = np.maximum.accumulate(pv_yr)
                yr_dd   = pv_yr / yr_peak - 1.0
                tr_yr   = trades_df[pd.to_datetime(trades_df["entry_dt"]).dt.year == yr] if "entry_dt" in trades_df else pd.DataFrame()
                yearly[yr] = {
                    "portfolio_ret": round(float(yr_ret), 4),
                    "max_dd":        round(float(yr_dd.min()), 4),
                    "n_trades":      int(len(tr_yr)),
                    "win_rate":      round(float((tr_yr["net_ret"] > 0).mean()), 3) if len(tr_yr) > 0 else np.nan,
                }
            m["yearly"] = yearly
    if "exit_reason" in trades_df.columns:
        m["exit_reasons"] = trades_df["exit_reason"].value_counts().to_dict()
    return m


def _fmt(v, pct=True, d=1) -> str:
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


# ══════════════════════════════════════════════════════════════════════════════
# TASK 7: DATA QUALITY CROSS-CHECK
# ══════════════════════════════════════════════════════════════════════════════

def task7_data_quality(p1_dir: Path) -> pd.DataFrame:
    """Cross-reference top 20 trades vs corporate_action_anomalies.csv."""
    best20_path = p1_dir / "best_20_trades.csv"
    ca_path     = p1_dir / "corporate_action_anomalies.csv"
    if not best20_path.exists() or not ca_path.exists():
        log.warning("Task 7: missing input files")
        return pd.DataFrame()

    best20 = pd.read_csv(best20_path)
    ca     = pd.read_csv(ca_path)

    ca_events = {}
    for _, row in ca.iterrows():
        sym = row["symbol"]
        dt  = pd.Timestamp(row["date"])
        if sym not in ca_events:
            ca_events[sym] = []
        ca_events[sym].append((dt, float(row["gap_pct"])))

    rows = []
    for _, tr in best20.iterrows():
        sym        = tr["symbol"]
        entry_dt   = pd.Timestamp(tr["entry_dt"])
        exit_dt    = pd.Timestamp(tr["exit_dt"])
        net_ret    = float(tr["net_ret"])
        arm_id     = tr.get("arm_id", "")
        ca_events_sym = ca_events.get(sym, [])

        flags = []
        for evt_dt, gap in ca_events_sym:
            if entry_dt <= evt_dt <= exit_dt:
                flags.append(f"CA_WITHIN_TRADE({evt_dt.date()},{gap:.1%})")
            elif evt_dt < entry_dt and (entry_dt - evt_dt).days <= 180:
                flags.append(f"CA_PRE_ENTRY_{(entry_dt-evt_dt).days}d({evt_dt.date()},{gap:.1%})")

        rows.append({
            "arm_id":           arm_id,
            "symbol":           sym,
            "entry_dt":         str(entry_dt.date()),
            "exit_dt":          str(exit_dt.date()),
            "net_ret":          round(net_ret, 4),
            "ca_flags":         "; ".join(flags) if flags else "CLEAN",
            "in_ca_list":       sym in CA_SYMBOLS,
            "assessment":       "REVIEW" if flags else "OK",
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "dq_top20_trades_check.csv", index=False)
    log.info("Task 7: saved dq_top20_trades_check.csv  (%d rows, %d flagged)",
             len(df), (df["assessment"] == "REVIEW").sum())
    return df


# ══════════════════════════════════════════════════════════════════════════════
# TASK 1: TRUE CONCENTRATION RERUN
# ══════════════════════════════════════════════════════════════════════════════

def get_concentration_blacklists(trade_log_path: Path) -> dict[str, frozenset]:
    """Load trade log and return exclusion sets for 6 scenarios + CA blacklist."""
    df = pd.read_csv(trade_log_path)
    df["net_ret"] = df["net_ret"].astype(float)
    sorted_by_ret = df.sort_values("net_ret", ascending=False)
    ticker_pnl    = df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
    return {
        "top1_trade":  frozenset(sorted_by_ret.head(1)["symbol"]),
        "top3_trade":  frozenset(sorted_by_ret.head(3)["symbol"]),
        "top5_trade":  frozenset(sorted_by_ret.head(5)["symbol"]),
        "top1_ticker": frozenset(ticker_pnl.head(1).index),
        "top3_ticker": frozenset(ticker_pnl.head(3).index),
        "top5_ticker": frozenset(ticker_pnl.head(5).index),
        "ca_all":      CA_SYMBOLS,
    }


def task1_concentration_reruns(
    base: dict, all_dates: list, p1_dir: Path
) -> pd.DataFrame:
    """
    For A2, H4, H5d, A3: rerun with each exclusion set and compare CAGR/MAR/MaxDD.
    Returns summary DataFrame.
    """
    # Define P1 arm configs directly to avoid stdout-clobbering re-import
    _P1_ARMS_DEF: list[ArmP2] = [
        ArmP2("A2",  "GK_Fast+GK_SELL",       entry="gk",       gk_params=GK_FAST, exit_type="gk_sell"),
        ArmP2("A3",  "DC+Fixed63",             entry="donchian", exit_type="fixed_N", fixed_hold=63),
        ArmP2("H4",  "DC+cloud+GK_SELL",       entry="donchian", gk_params=GK_ORIG, exit_type="gk_sell"),
        ArmP2("H5d", "DC+GK_Lower_D4(trail)",  entry="donchian", gk_params=GK_ORIG,
              exit_type="gk_sell", gk_lower_stop="D4"),
    ]
    focus_arms = {arm.arm_id: arm for arm in _P1_ARMS_DEF}
    rows = []

    for arm_id, p1_arm in focus_arms.items():
        log_path = p1_dir / f"trade_log_{arm_id}.csv"
        if not log_path.exists():
            log.warning("Task 1: missing %s", log_path)
            continue

        blacklists = get_concentration_blacklists(log_path)

        # Also run baseline (no exclusion) for reference
        scenarios = {"baseline": frozenset()} | blacklists

        for scenario, bl in scenarios.items():
            log.info("  Task1 %s / %s  (blacklist: %d syms)", arm_id, scenario, len(bl))
            base_arm = focus_arms[arm_id]
            import dataclasses
            arm_p2 = dataclasses.replace(base_arm, arm_id=arm_id, label=f"{arm_id}_{scenario}", blacklist=bl)
            eq_df, tr_df, _ = run_arm_p2(base, arm_p2, all_dates)
            m = compute_metrics(eq_df, tr_df, label=arm_p2.label)
            rows.append({
                "arm_id":          arm_id,
                "scenario":        scenario,
                "excluded_n":      len(bl),
                "excluded_syms":   ",".join(sorted(bl)[:10]),
                "n_trades":        m.get("n_trades", 0),
                "cagr":            m.get("cagr", np.nan),
                "max_dd":          m.get("max_dd", np.nan),
                "mar":             m.get("mar", np.nan),
                "sharpe":          m.get("sharpe", np.nan),
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "concentration_true_rerun.csv", index=False)
    log.info("Task 1: saved concentration_true_rerun.csv  (%d rows)", len(df))
    return df


# ══════════════════════════════════════════════════════════════════════════════
# TASK 2: EXPOSURE-ADJUSTED BENCHMARKS
# ══════════════════════════════════════════════════════════════════════════════

def task2_exposure_benchmarks(p1_dir: Path, vnx_close_by_date: dict[str, float]) -> pd.DataFrame:
    """
    Load daily equity curves for A2/H4/H5d/A3, compute exposure-weighted benchmarks.
    """
    target_arms = ["A2", "H4", "H5d", "A3"]
    rows = []

    for arm_id in target_arms:
        eq_path = p1_dir / f"daily_equity_{arm_id}.csv"
        if not eq_path.exists():
            log.warning("Task 2: missing %s", eq_path)
            continue

        eq = pd.read_csv(eq_path)
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.sort_values("date").reset_index(drop=True)

        pv  = eq["total_equity"].values.astype(float)
        exp = eq["gross_exposure"].values.astype(float)

        # Strategy daily returns
        strat_rets = np.diff(pv) / pv[:-1]
        dates_mid  = eq["date"].values[1:]

        # VNINDEX daily returns (aligned)
        vnx_rets = []
        for d_ts in dates_mid:
            d_str  = str(pd.Timestamp(d_ts).date())
            d_prev = str((pd.Timestamp(d_ts) - pd.Timedelta(days=1)).date())
            # walk back to find prior trading day
            vnx_curr = vnx_close_by_date.get(d_str)
            # try previous 5 calendar days
            for k in range(1, 6):
                d_back = str((pd.Timestamp(d_ts) - pd.Timedelta(days=k)).date())
                vnx_prev_cand = vnx_close_by_date.get(d_back)
                if vnx_prev_cand is not None:
                    break
            else:
                vnx_prev_cand = None
            if vnx_curr is not None and vnx_prev_cand is not None and vnx_prev_cand > 0:
                vnx_rets.append(vnx_curr / vnx_prev_cand - 1.0)
            else:
                vnx_rets.append(np.nan)
        vnx_rets = np.array(vnx_rets)

        # Exposure-weighted VNINDEX return: what VNINDEX would return given same exposure
        exp_lag = exp[:-1]   # exposure at start of day (yesterday's reading)
        adj_vnx_rets = vnx_rets * exp_lag

        # Filter to valid days
        valid = ~(np.isnan(strat_rets) | np.isnan(vnx_rets))
        sr = strat_rets[valid]; vr = vnx_rets[valid]; avr = adj_vnx_rets[valid]

        beta       = float(np.cov(sr, vr)[0,1] / np.var(vr)) if len(sr) > 10 else np.nan
        corr       = float(np.corrcoef(sr, vr)[0,1]) if len(sr) > 10 else np.nan
        avg_exp    = float(exp_lag[valid].mean())
        active_ret = sr - avr

        # Cumulative active return and active MaxDD
        cum_active = np.cumprod(1 + active_ret) - 1.0
        pk_active  = np.maximum.accumulate(1 + cum_active)
        active_dd  = (1 + cum_active) / pk_active - 1.0
        active_maxdd = float(active_dd.min()) if len(active_dd) > 0 else np.nan

        # Strategy CAGR on holding days only (n_pos >= 1)
        hold_mask = eq["n_pos"].values[:-1] >= 1
        if hold_mask.sum() > 1:
            hold_rets = strat_rets[hold_mask & ~np.isnan(strat_rets)]
            hold_cagr = float((np.prod(1 + hold_rets)) ** (252.0 / len(hold_rets)) - 1.0) if len(hold_rets) > 5 else np.nan
        else:
            hold_cagr = np.nan

        # Full-period CAGR and excess
        days  = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days
        years = max(days / 365.25, 0.01)
        strat_cagr = float((pv[-1] / pv[0]) ** (1.0 / years) - 1.0) if pv[0] > 0 else np.nan

        # Exposure-weighted VNX CAGR
        adj_vnx_pv = np.cumprod(np.concatenate([[1.0], 1 + adj_vnx_rets]))
        adj_vnx_cagr = float((adj_vnx_pv[-1]) ** (1.0 / years) - 1.0)

        rows.append({
            "arm_id":           arm_id,
            "avg_exposure_pct": round(avg_exp * 100, 1),
            "beta_vs_vnx":      round(beta, 3) if not np.isnan(beta) else np.nan,
            "corr_vs_vnx":      round(corr, 3) if not np.isnan(corr) else np.nan,
            "strategy_cagr":    round(strat_cagr, 4),
            "adj_vnx_cagr":     round(adj_vnx_cagr, 4),
            "excess_cagr":      round(strat_cagr - adj_vnx_cagr, 4) if not np.isnan(strat_cagr) else np.nan,
            "active_maxdd":     round(active_maxdd, 4),
            "hold_only_cagr":   round(hold_cagr, 4) if not np.isnan(hold_cagr) else np.nan,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "exposure_benchmarks.csv", index=False)
    log.info("Task 2: saved exposure_benchmarks.csv")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# ARM DEFINITIONS — Tasks 3, 5, 6
# ══════════════════════════════════════════════════════════════════════════════

# Task 3: GK_Fast + EMA filter arms (6 arms)
TASK3_ARMS: list[ArmP2] = [
    ArmP2("F1", "GKFast+Close>EMA50",
          entry="gk", gk_params=GK_FAST, require_close_above_ema=50),
    ArmP2("F2", "GKFast+Close>EMA100",
          entry="gk", gk_params=GK_FAST, require_close_above_ema=100),
    ArmP2("F3", "GKFast+Close>EMA150",
          entry="gk", gk_params=GK_FAST, require_close_above_ema=150),
    ArmP2("F4", "GKFast+EMA150slope",
          entry="gk", gk_params=GK_FAST, require_ema_slope=150),
    ArmP2("F5", "GKFast+Close>EMA150+slope",
          entry="gk", gk_params=GK_FAST, require_close_above_ema=150, require_ema_slope=150),
    ArmP2("F6", "GKFast+Close>EMA150+slope+RS3M",
          entry="gk", gk_params=GK_FAST, require_close_above_ema=150,
          require_ema_slope=150, rs3m_filter=True),
]

# Task 6: DC + GK_FAST exit (3 new arms vs H4 which uses GK_ORIG exit)
TASK6_ARMS: list[ArmP2] = [
    ArmP2("P6a", "DC+cloud+GKFast_SELL",
          entry="donchian", gk_params=GK_FAST, exit_type="gk_sell"),
    ArmP2("P6b", "DC+cloud+GKFast_Lower_D1",
          entry="donchian", gk_params=GK_FAST, exit_type="gk_sell", gk_lower_stop="D1"),
    ArmP2("P6c", "DC+cloud+GKFast_Lower_D4",
          entry="donchian", gk_params=GK_FAST, exit_type="gk_sell", gk_lower_stop="D4"),
]

# Task 5: DC + ranking variants (5 rankings × 3 exits = 15 arms)
_DC_RANKINGS  = ["rs3m", "rs6m", "composite", "near52wk", "volexp"]
_DC_EXITS     = [
    ("GKOrigSell", "gk_sell", GK_ORIG),
    ("GKFastSell", "gk_sell", GK_FAST),
    ("Fixed63",    "fixed_N", GK_ORIG),
]
TASK5_ARMS: list[ArmP2] = []
for _rank in _DC_RANKINGS:
    for _exit_lbl, _exit_type, _gk_p in _DC_EXITS:
        _aid = f"R_{_rank[:4]}_{_exit_lbl[:4]}"
        TASK5_ARMS.append(ArmP2(
            arm_id     = _aid,
            label      = f"DC+{_rank}+{_exit_lbl}",
            entry      = "donchian",
            gk_params  = _gk_p,
            exit_type  = _exit_type,
            fixed_hold = 63,
            ranking    = _rank,
        ))


# ══════════════════════════════════════════════════════════════════════════════
# TASK 4: GK PARAMETER GRID
# ══════════════════════════════════════════════════════════════════════════════

GRID_COMBOS: list[dict] = []
for _len in [80, 100, 120]:
    for _mult in [1.8, 2.0, 2.2]:
        for _conf in [2, 3]:
            _key = f"gk_grid_L{_len}_M{_mult:.1f}_C{_conf}"
            GRID_COMBOS.append({
                "key": _key,
                "gk_len": _len, "gk_mult": _mult, "gk_atr": 14, "gk_conf": _conf,
                "label": f"L{_len}_M{_mult}_C{_conf}",
            })

TASK4_ARMS: list[ArmP2] = [
    ArmP2(
        arm_id       = f"G{i+1:02d}",
        label        = combo["label"],
        entry        = "gk",
        gk_custom_key= combo["key"],
        gk_params    = GK_FAST,
        exit_type    = "gk_sell",
    )
    for i, combo in enumerate(GRID_COMBOS)
]


# ══════════════════════════════════════════════════════════════════════════════
# FINAL CONCLUSION WRITER
# ══════════════════════════════════════════════════════════════════════════════

def write_final_conclusion(
    t1_df:     pd.DataFrame,
    t2_df:     pd.DataFrame,
    t3_metrics: list[dict],
    t4_metrics: list[dict],
    t5_metrics: list[dict],
    t6_metrics: list[dict],
    t7_df:     pd.DataFrame,
) -> None:
    lines = [
        "# Phase 2 Research — Final Conclusion",
        "",
        f"Run date: {pd.Timestamp.now().date()}",
        "",
        "---",
        "",
        "## A. FACTS",
        "",
        "### Task 1 — True Concentration Rerun",
    ]

    if not t1_df.empty:
        lines.append("")
        lines.append("| Arm | Scenario | ExclN | Trades | CAGR | MaxDD | MAR |")
        lines.append("|-----|----------|-------|--------|------|-------|-----|")
        for _, row in t1_df.iterrows():
            lines.append(
                f"| {row['arm_id']} | {row['scenario']} | {int(row['excluded_n'])} |"
                f" {int(row['n_trades'])} | {_fmt(row['cagr'])} |"
                f" {_fmt(row['max_dd'])} | {_fmt(row.get('mar', np.nan), pct=False, d=2)} |"
            )

    lines += ["", "### Task 2 — Exposure-Adjusted Benchmarks", ""]
    if not t2_df.empty:
        lines.append("| Arm | AvgExp | Beta | Corr | StratCAGR | AdjVNXCAGR | ExcessCAGR | ActiveMaxDD |")
        lines.append("|-----|--------|------|------|-----------|-----------|-----------|------------|")
        for _, row in t2_df.iterrows():
            lines.append(
                f"| {row['arm_id']} | {row['avg_exposure_pct']:.0f}% | {row['beta_vs_vnx']:.2f} |"
                f" {row['corr_vs_vnx']:.2f} | {_fmt(row['strategy_cagr'])} |"
                f" {_fmt(row['adj_vnx_cagr'])} | {_fmt(row['excess_cagr'])} |"
                f" {_fmt(row['active_maxdd'])} |"
            )

    lines += ["", "### Task 3 — GK_Fast + EMA Filters", ""]
    if t3_metrics:
        lines.append("| Arm | Label | Trades | CAGR | MaxDD | MAR | Sharpe |")
        lines.append("|-----|-------|--------|------|-------|-----|--------|")
        for m in t3_metrics:
            lines.append(
                f"| {m.get('arm_id','')} | {m.get('label','')} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('max_dd',np.nan))} |"
                f" {_fmt(m.get('mar',np.nan),pct=False,d=2)} | {_fmt(m.get('sharpe',np.nan),pct=False,d=2)} |"
            )

    lines += ["", "### Task 4 — GK_Fast Parameter Grid", ""]
    if t4_metrics:
        lines.append("| Arm | Label | Trades | CAGR | MaxDD | MAR |")
        lines.append("|-----|-------|--------|------|-------|-----|")
        sorted_grid = sorted(t4_metrics, key=lambda x: -x.get("mar", -999))
        for m in sorted_grid[:10]:
            lines.append(
                f"| {m.get('arm_id','')} | {m.get('label','')} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('max_dd',np.nan))} |"
                f" {_fmt(m.get('mar',np.nan),pct=False,d=2)} |"
            )

    lines += ["", "### Task 5 — DC Ranking Variants", ""]
    if t5_metrics:
        lines.append("| Arm | Label | Trades | CAGR | MaxDD | MAR |")
        lines.append("|-----|-------|--------|------|-------|-----|")
        for m in sorted(t5_metrics, key=lambda x: -x.get("mar", -999))[:10]:
            lines.append(
                f"| {m.get('arm_id','')} | {m.get('label','')} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('max_dd',np.nan))} |"
                f" {_fmt(m.get('mar',np.nan),pct=False,d=2)} |"
            )

    lines += ["", "### Task 6 — DC + GK_FAST Exit Arms", ""]
    if t6_metrics:
        lines.append("| Arm | Label | Trades | CAGR | MaxDD | MAR |")
        lines.append("|-----|-------|--------|------|-------|-----|")
        for m in t6_metrics:
            lines.append(
                f"| {m.get('arm_id','')} | {m.get('label','')} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('max_dd',np.nan))} |"
                f" {_fmt(m.get('mar',np.nan),pct=False,d=2)} |"
            )

    lines += ["", "### Task 7 — Data Quality", ""]
    if not t7_df.empty:
        flagged = t7_df[t7_df["assessment"] == "REVIEW"]
        lines.append(f"Top-20 trades checked: {len(t7_df)} total, {len(flagged)} flagged for review.")
        if len(flagged):
            for _, row in flagged.iterrows():
                lines.append(f"- {row['symbol']} ({row['arm_id']}): net_ret={row['net_ret']:.1%}  {row['ca_flags']}")

    # Best grid combo
    best_grid = max(t4_metrics, key=lambda x: x.get("mar", -999)) if t4_metrics else {}
    # Best EMA filter
    best_ema  = max(t3_metrics, key=lambda x: x.get("mar", -999)) if t3_metrics else {}
    # Best ranking
    best_rank = max(t5_metrics, key=lambda x: x.get("mar", -999)) if t5_metrics else {}

    lines += [
        "",
        "---",
        "",
        "## B. INTERPRETATION",
        "",
        "1. **Concentration robustness**: If CAGR collapses >50% when top-3 tickers excluded, the strategy",
        "   is a handful-of-winners story, not a systematic edge.",
        "",
        "2. **Exposure-adjusted alpha**: Excess CAGR vs exposure-weighted VNINDEX is the cleanest alpha",
        "   measure. Negative excess CAGR = strategy underperforms passive VNX exposure.",
        "",
        "3. **EMA filters**: Adding Close>EMA150 + slope should reduce false breakouts in downtrends.",
        "   If it reduces trades by >40% with <10% CAGR improvement, the filter is too tight.",
        "",
        f"4. **Best grid combo**: {best_grid.get('label','?')} — CAGR {_fmt(best_grid.get('cagr',np.nan))} "
        f"MAR {_fmt(best_grid.get('mar',np.nan),pct=False,d=2)}.",
        "",
        f"5. **Best ranking**: {best_rank.get('label','?')} — CAGR {_fmt(best_rank.get('cagr',np.nan))} "
        f"MAR {_fmt(best_rank.get('mar',np.nan),pct=False,d=2)}.",
        "",
        "---",
        "",
        "## C. DECISION",
        "",
        "- If any EMA-filter arm beats A2 (GK_Fast baseline) by MAR with ≥20 trades/year → adopt filter.",
        "- If concentration reruns show CAGR drops >60% ex-top3-tickers → do NOT scale until universe expanded.",
        "- If best grid combo is not L100_M2.0 (current default) → update AFL default params.",
        "- If DC+GK_FAST_SELL (P6a) beats DC+GK_ORIG_SELL (H4) → use GK_FAST for all DC exits.",
        "",
        "---",
        "",
        "## D. BEST CURRENT AFL DEFAULT",
        "",
        "Based on Phase 1 + Phase 2 results:",
        f"- Entry: GK_Fast (L{GK_FAST['gk_len']}, Mult{GK_FAST['gk_mult']}, ATR{GK_FAST['gk_atr']}, Conf{GK_FAST['gk_conf']})",
        "- EMA filter: TBD from Task 3 results",
        "- Exit: GK_SELL (same param set as entry)",
        "- Universe filter: ADV50 > 2B VND/day",
        "- Portfolio: max 10 positions, equal slot, 35bps friction/side",
        "",
        "---",
        "",
        "## E. TOP 3 NEXT RESEARCH ITEMS",
        "",
        "1. **Adjusted price data**: Obtain adjusted OHLCV to resolve the VIC/L40 unadjusted-price concern.",
        "   Re-run A2, H4, H5d on clean data to confirm whether 2025 gains persist.",
        "",
        "2. **Sector/regime overlay**: Add VNINDEX trend filter (e.g., VNINDEX > EMA200) to gate all entries.",
        "   This is the most commonly cited improvement in Vietnam trend-following research.",
        "",
        "3. **Longer test period**: Extend parquet cache back to 2018 to get a full bear-market test",
        "   (2018 drawdown -30%, 2022 drawdown -30%). Current 2023-2026 is a recovering/bull period only.",
        "",
        "---",
        "",
        "## F. KILL CRITERIA",
        "",
        "Abandon GK_Fast as primary entry signal if ANY of:",
        "- Phase 2 concentration rerun shows CAGR < 5% ex-top-5-tickers for A2",
        "- Exposure-adjusted excess CAGR (vs adj VNINDEX) < 2% for A2",
        "- Best EMA-filter arm has MAR < 0.3 (lower than DC+Fixed63 baseline)",
        "- Walk-forward fold 2 (2025 test) test_CAGR < -10% for A2 (already: -5% in Phase 1 WF, marginal)",
        "",
        "Abandon DC breakout as universe entry if:",
        "- CAGR ex-top-5-tickers < 3% for all DC arms (H4, P6a)",
        "- No ranking variant beats ADV50 by >2% CAGR",
    ]

    path = OUT_DIR / "final_conclusion.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Final conclusion saved: %s", path)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 2 Research ===")

    # ── Load data ──────────────────────────────────────────────────────────────
    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows", panel["symbol"].nunique(), len(panel))

    log.info("Loading VNINDEX")
    vnx_raw = pd.read_csv(VNINDEX_CSV)
    vnx_raw["date"] = pd.to_datetime(vnx_raw["date"])
    vnx_by_date: dict[str, float] = {
        str(row.date.date()): float(row.close)
        for row in vnx_raw.itertuples()
    }

    # ── Precompute (extended) ──────────────────────────────────────────────────
    log.info("Pre-computing base data (extended: EMA100/150, RS3M/6M, near52wk)...")
    base = precompute_base_p2(panel, vnx_by_date)
    log.info("  Done: %d symbols", len(base))

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  Trading days: %d  (%s – %s)", len(all_dates),
             all_dates[0].date(), all_dates[-1].date())

    # ── Task 7: Data quality (fast, no rerun needed) ───────────────────────────
    log.info("=== Task 7: Data quality check ===")
    t7_df = task7_data_quality(P1_DIR)

    # ── Task 2: Exposure benchmarks (from saved Phase 1 equity curves) ─────────
    log.info("=== Task 2: Exposure-adjusted benchmarks ===")
    t2_df = task2_exposure_benchmarks(P1_DIR, vnx_by_date)
    print("\nTask 2 — Exposure Benchmarks:")
    print(t2_df.to_string(index=False))

    # ── Task 4: GK grid precompute (must happen before running grid arms) ───────
    log.info("=== Task 4: Precomputing GK parameter grid signals (18 combos × %d syms) ===", len(base))
    precompute_grid_signals(base, GRID_COMBOS)

    # ── Run helper ─────────────────────────────────────────────────────────────
    def run_arm_set(arm_list: list[ArmP2], tag: str) -> list[dict]:
        metrics = []
        for arm in arm_list:
            log.info("  Running %s (%s) [%s]", arm.arm_id, arm.label, tag)
            eq_df, tr_df, _ = run_arm_p2(base, arm, all_dates)
            m = compute_metrics(eq_df, tr_df, arm.label)
            m["arm_id"] = arm.arm_id
            metrics.append(m)
            # Save outputs
            eq_df.to_csv(OUT_DIR / f"eq_{arm.arm_id}.csv", index=False)
            tr_df.to_csv(OUT_DIR / f"trades_{arm.arm_id}.csv", index=False)
        return metrics

    # ── Task 3: EMA filter arms ────────────────────────────────────────────────
    log.info("=== Task 3: GK_Fast + EMA filter arms (6 arms) ===")
    t3_metrics = run_arm_set(TASK3_ARMS, "T3")
    print("\nTask 3 — GK_Fast + EMA Filters:")
    for m in t3_metrics:
        print(f"  {m['arm_id']:6s} {m.get('label',''):35s}  "
              f"n={m.get('n_trades',0):4d}  CAGR={_fmt(m.get('cagr',np.nan))}  "
              f"MAR={_fmt(m.get('mar',np.nan),pct=False,d=2)}")

    # ── Task 4: Parameter grid ────────────────────────────────────────────────
    log.info("=== Task 4: GK parameter grid (18 arms) ===")
    t4_metrics = run_arm_set(TASK4_ARMS, "T4")
    # Build heatmap-friendly CSV
    grid_rows = []
    for m, combo in zip(t4_metrics, GRID_COMBOS):
        grid_rows.append({
            "label": combo["label"], "gk_len": combo["gk_len"],
            "gk_mult": combo["gk_mult"], "gk_conf": combo["gk_conf"],
            "n_trades": m.get("n_trades", 0),
            "cagr": m.get("cagr", np.nan), "max_dd": m.get("max_dd", np.nan),
            "mar": m.get("mar", np.nan), "sharpe": m.get("sharpe", np.nan),
        })
    pd.DataFrame(grid_rows).to_csv(OUT_DIR / "grid_heatmap.csv", index=False)
    print("\nTask 4 — Grid (sorted by MAR):")
    for m in sorted(t4_metrics, key=lambda x: -x.get("mar", -999)):
        print(f"  {m['arm_id']:6s} {m.get('label',''):25s}  "
              f"n={m.get('n_trades',0):4d}  CAGR={_fmt(m.get('cagr',np.nan))}  "
              f"MAR={_fmt(m.get('mar',np.nan),pct=False,d=2)}")

    # ── Task 5: DC ranking variants ────────────────────────────────────────────
    log.info("=== Task 5: DC ranking variants (15 arms) ===")
    t5_metrics = run_arm_set(TASK5_ARMS, "T5")
    print("\nTask 5 — DC Ranking (sorted by MAR):")
    for m in sorted(t5_metrics, key=lambda x: -x.get("mar", -999)):
        print(f"  {m['arm_id']:8s} {m.get('label',''):35s}  "
              f"n={m.get('n_trades',0):4d}  CAGR={_fmt(m.get('cagr',np.nan))}  "
              f"MAR={_fmt(m.get('mar',np.nan),pct=False,d=2)}")

    # ── Task 6: DC + GK_FAST exit ─────────────────────────────────────────────
    log.info("=== Task 6: DC + GK_FAST exit arms (3 arms) ===")
    t6_metrics = run_arm_set(TASK6_ARMS, "T6")
    print("\nTask 6 — DC + GK_FAST Exit:")
    for m in t6_metrics:
        print(f"  {m['arm_id']:6s} {m.get('label',''):35s}  "
              f"n={m.get('n_trades',0):4d}  CAGR={_fmt(m.get('cagr',np.nan))}  "
              f"MAR={_fmt(m.get('mar',np.nan),pct=False,d=2)}")

    # ── Task 1: Concentration reruns (most expensive — run last) ──────────────
    log.info("=== Task 1: True concentration reruns ===")
    t1_df = task1_concentration_reruns(base, all_dates, P1_DIR)
    print("\nTask 1 — Concentration Reruns:")
    print(t1_df.to_string(index=False))

    # ── Combined summary CSV ───────────────────────────────────────────────────
    all_p2_metrics = t3_metrics + t4_metrics + t5_metrics + t6_metrics
    summary_rows = []
    for m in all_p2_metrics:
        yr = m.get("yearly", {})
        row = {k: v for k, v in m.items() if k not in ("yearly", "monthly", "exit_reasons")}
        for yr_k in YEARS:
            row[f"ret_{yr_k}"] = yr.get(yr_k, {}).get("portfolio_ret", np.nan)
        summary_rows.append(row)
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "phase2_summary.csv", index=False)
    log.info("Saved phase2_summary.csv")

    # ── Final conclusion ───────────────────────────────────────────────────────
    write_final_conclusion(t1_df, t2_df, t3_metrics, t4_metrics, t5_metrics, t6_metrics, t7_df)

    print(f"\n\nAll Phase 2 outputs saved to: {OUT_DIR}")
    log.info("Phase 2 complete.")


if __name__ == "__main__":
    main()
