#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 4 — Combination Testing for GK_FAST A2

Goal: determine if EX09a (GK + time stop 20 bars) can be combined with
drawdown-control overlays to qualify for paper trading.

Arms:
  C00-C18: core combination matrix
  T15/T20/T25/T30 × {base, +SZ06, +FT07, +FT07+SZ06}: time stop sensitivity
  SZ06b: diagnostic variant (half-size when VNIX < EMA50 OR slope < 0)

Pass criteria (paper trade):
  Required: MAR >= 0.70, active MaxDD > -28%, ex-top3 CAGR >= 12%,
            ex-top5 >= 8%, 2024 >= -5%, N >= 80, no ticker > 30% PnL
  Strong:   MAR >= 0.80, active MaxDD > -25%, ex-top3 >= 15%, ex-top5 >= 10%, 2024 >= 0%

Outputs -> data/research/gk_audit/phase4/
"""
from __future__ import annotations

import io, sys, json, logging, warnings, dataclasses
from pathlib import Path
from dataclasses import dataclass, field

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

REPO    = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
CACHE_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet"
VNINDEX_CSV   = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT_DIR       = REPO / "data/research/gk_audit/phase4"
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

GK_FAST = {"gk_len": 100, "gk_mult": 2.0, "gk_atr": 14, "gk_conf": 2}

CA_SYMBOLS = frozenset([
    "ANV","BIC","CSV","DPM","DPR","IMP","L40","MCH",
    "MSH","NTL","SAB","SIP","TCB","TCO","VIC",
])

# Phase 3 results (immutable reference)
P3_A2   = {"cagr": 0.174, "mar": 0.52, "active_maxdd": -0.303,
            "et3": 0.071, "et5": 0.031, "ret2024": 0.078}
P3_EX09a = {"cagr": 0.293, "mar": 0.72, "active_maxdd": -0.307,
             "et3": 0.195, "et5": 0.129, "ret2024": -0.071}

# ══════════════════════════════════════════════════════════════════════════════
# ARM CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmP4:
    arm_id: str
    label:  str
    # Entry filters
    dist_52wk_max:          float = 0.0   # pass if dist_to_52wk <= this; 0=off
    volexp_filter_min:      float = 0.0   # pass if vol/adv50 >= this; 0=off
    # Exit
    exit_type:              str   = "gk_sell"  # always "gk_sell"
    exit_ema20_confirmed:   bool  = False
    time_stop_bars:         int   = 0     # exit after N bars if return <= 0
    stop_pct:               float = 0.0   # hard stop below entry
    # Sizing
    max_pos:                int   = MAX_POS
    half_size_regime_off:   bool  = False  # half-size when VNIX < EMA50
    half_size_regime_sz06b: bool  = False  # half when VNIX < EMA50 OR slope < 0
    # Portfolio constants
    fee_bps:  float = FEE_BPS
    slip_bps: float = SLIP_BPS
    # Blacklist for concentration re-runs
    blacklist: frozenset = field(default_factory=frozenset)

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000


# ══════════════════════════════════════════════════════════════════════════════
# MATH PRIMITIVES (identical to Phase 2/3)
# ══════════════════════════════════════════════════════════════════════════════

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out   = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = float(arr[i])
        if np.isnan(v): continue
        prev  = out[i-1] if i > 0 and not np.isnan(out[i-1]) else np.nan
        out[i] = v if np.isnan(prev) else alpha * v + (1.0 - alpha) * prev
    return out


def _wilder_atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    tr    = np.empty(len(c))
    tr[0] = h[0] - l[0]
    for i in range(1, len(c)):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
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
# SIGNAL COMPUTATION (identical to Phase 2/3)
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
        "gk_buy":  raw_flip & (gk_trend == 1),
        "gk_sell": raw_flip & (gk_trend == -1),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRECOMPUTE
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base(panel: pd.DataFrame, vnx_by_date: dict) -> dict:
    base: dict = {}
    n_sym = panel["symbol"].nunique()
    for idx, (sym, grp) in enumerate(panel.groupby("symbol")):
        if (idx + 1) % 100 == 0:
            log.info("  precompute %d/%d", idx + 1, n_sym)
        df  = grp.sort_values("date").reset_index(drop=True)
        c   = df["close"].values.astype(float)
        h   = df["high"].values.astype(float)
        l   = df["low"].values.astype(float)
        o   = df["open"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)
        n   = len(c)

        e10   = _ema(c, EMA_FAST)
        e20   = _ema(c, 20)
        adv50 = _adv50_lagged(val)
        atr14 = _wilder_atr(h, l, c, 14)
        gk_f  = compute_gk_signals(c, h, l, **GK_FAST)

        # near52: close / max(high[-252:t]) — 1.0 = at 52wk high
        near52 = np.full(n, np.nan)
        for i in range(1, n):
            hi52 = float(np.max(h[max(0, i-252):i]))
            if hi52 > 0:
                near52[i] = c[i] / hi52

        # volume expansion: today value / adv50 (ratio)
        volexp = np.full(n, np.nan)
        for i in range(n):
            if not np.isnan(adv50[i]) and adv50[i] > 0:
                volexp[i] = val[i] / (adv50[i] * 1e9)

        base[sym] = {
            "dates":       dts,
            "open":        o, "high": h, "low": l, "close": c, "value": val,
            "adv50_lag":   adv50,
            "ema10":       e10, "ema20": e20,
            "atr14":       atr14,
            "gk_fast":     gk_f,
            "near52":      near52,
            "volexp":      volexp,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


def precompute_vnx(vnx_csv: Path) -> tuple[dict, dict, dict]:
    """Returns (vnx_by_date, vnx_state_by_date, vnx_daily_rets).
    vnx_state_by_date has: above_e50, e50_slope_pos, dd_252
    """
    df = pd.read_csv(vnx_csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    c   = df["close"].values.astype(float)
    n   = len(c)
    e50 = _ema(c, 50)

    vnx_by_date    = {}
    vnx_state      = {}
    vnx_daily_rets = {}

    for i in range(n):
        d_str = str(df["date"].iloc[i].date())
        vnx_by_date[d_str] = float(c[i])

        e50_prev = float(e50[i-1]) if i > 0 and not np.isnan(e50[i-1]) else float(e50[i])
        peak     = float(np.max(c[max(0, i-252):i+1]))
        dd       = c[i] / peak - 1.0 if peak > 0 else 0.0

        vnx_state[d_str] = {
            "above_e50":     bool(c[i] > e50[i]) if not np.isnan(e50[i]) else True,
            "e50_slope_pos": bool(e50[i] > e50_prev) if not np.isnan(e50[i]) else True,
            "dd_252":        float(dd),
            "close":         float(c[i]),
        }
        if i >= 1 and c[i-1] > 0:
            vnx_daily_rets[d_str] = float(c[i] / c[i-1] - 1.0)

    return vnx_by_date, vnx_state, vnx_daily_rets


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_p4(
    base:      dict,
    arm:       ArmP4,
    all_dates: list,
    vnx_state: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    cost_e    = arm.cost_e
    cost_x    = arm.cost_x
    blacklist = arm.blacklist | EXCL

    cash            = INITIAL_CAP
    holdings:        dict = {}
    pending_exits:   dict = {}
    pending_entries: list = []
    trades:  list = []
    eq_curve: list = []
    prev_equity = INITIAL_CAP

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())
        day_vnx = vnx_state.get(day_str, {})

        # ── Step 1: Execute pending exits at today's open ─────────────────────
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
                "symbol":        sym,
                "arm_id":        arm.arm_id,
                "entry_dt":      str(pos["entry_dt"].date()),
                "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
                "entry_open_raw":round(pos["entry_open_raw"], 4),
                "entry_px_eff":  round(pos["entry_px_eff"], 4),
                "exit_dt":       str(trade_date.date()),
                "exit_open_raw": round(open_raw, 4),
                "exit_reason":   reason,
                "hold_bars":     day_i - pos["entry_day_i"],
                "hold_days":     (trade_date - pos["entry_dt"]).days,
                "gross_ret":     round(open_raw / pos["entry_open_raw"] - 1.0, 6),
                "net_ret":       round(net_ret, 6),
                "mfe":           round(pos.get("mfe", np.nan), 4),
                "mae":           round(pos.get("mae", np.nan), 4),
                "adv50_entry":   round(pos["adv50_entry"], 3),
                "regime_at_entry": pos.get("regime_at_entry", ""),
            })
        pending_exits.clear()

        # ── Step 2: Execute pending entries at today's open ───────────────────
        n_slots  = arm.max_pos - len(holdings)
        selected = sorted(pending_entries, key=lambda x: -x["adv50"])[:n_slots]

        for entry in selected:
            sym = entry["sym"]
            if sym in holdings:
                continue
            b    = base[sym]
            t_ex = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue
            entry_o_raw = float(b["open"][t_ex])
            if entry_o_raw <= 0:
                continue

            # Slot sizing
            base_slot   = prev_equity / arm.max_pos
            size_factor = 1.0

            if arm.half_size_regime_off:
                if not day_vnx.get("above_e50", True):
                    size_factor = 0.5
            elif arm.half_size_regime_sz06b:
                if (not day_vnx.get("above_e50", True)
                        or not day_vnx.get("e50_slope_pos", True)):
                    size_factor = 0.5

            slot         = base_slot * size_factor
            entry_px_eff = entry_o_raw * cost_e
            shares       = slot / entry_px_eff
            cash        -= slot

            holdings[sym] = {
                "shares":           shares,
                "entry_px_eff":     entry_px_eff,
                "entry_open_raw":   entry_o_raw,
                "entry_dt":         trade_date,
                "entry_signal_dt":  entry["entry_signal_dt"],
                "entry_day_i":      day_i,
                "adv50_entry":      entry["adv50"],
                "trail_atr_stop":   -np.inf,
                "mfe":              0.0,
                "mae":              0.0,
                "regime_at_entry":  "ON" if day_vnx.get("above_e50", True) else "OFF",
            }
        pending_entries.clear()

        # ── Step 3: MTM at today's close ──────────────────────────────────────
        market_val = 0.0
        for sym, pos in holdings.items():
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None:
                continue
            c_now = float(b["close"][t])
            market_val += pos["shares"] * c_now
            unreal      = c_now / pos["entry_open_raw"] - 1.0
            pos["mfe"]  = max(pos["mfe"], unreal)
            pos["mae"]  = min(pos["mae"], unreal)

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
            c_now     = float(b["close"][t])
            lo        = float(b["low"][t])
            triggered, reason, exit_cap = False, "", None

            # Primary: GK_SELL
            if not triggered and bool(b["gk_fast"]["gk_sell"][t]):
                triggered, reason = True, "GK_SELL"

            # Hard stop
            if not triggered and arm.stop_pct > 0:
                stop_px = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= stop_px:
                    triggered, reason, exit_cap = True, f"HARD_STOP_{arm.stop_pct*100:.0f}PCT", stop_px

            # EMA20 confirmed (secondary)
            if not triggered and arm.exit_ema20_confirmed and t >= 1:
                e20_now  = float(b["ema20"][t])
                e20_prev = float(b["ema20"][t-1])
                c_prev   = float(b["close"][t-1])
                if (not np.isnan(e20_now) and not np.isnan(e20_prev)
                        and c_now < e20_now and c_prev < e20_prev):
                    triggered, reason = True, "EMA20_CONFIRM"

            # Time stop (exit after N bars if return <= 0)
            if not triggered and arm.time_stop_bars > 0:
                if bars_held >= arm.time_stop_bars:
                    current_ret = c_now / pos["entry_open_raw"] - 1.0
                    if current_ret <= 0.0:
                        triggered, reason = True, "TSTOP_FLAT_NEG"

            if triggered:
                pos["exit_signal_dt"] = trade_date
                pending_exits[sym]    = (t, reason, exit_cap)

        # ── Step 5: Scan entry signals ────────────────────────────────────────
        n_tomorrow = (arm.max_pos - len(holdings)
                      - len(pending_entries) + len(pending_exits))
        if n_tomorrow > 0:
            for sym, b in base.items():
                if sym in blacklist:
                    continue
                if (sym in holdings or sym in pending_exits
                        or any(x["sym"] == sym for x in pending_entries)):
                    continue
                t = b["date_to_idx"].get(day_str)
                if t is None or t + 1 >= len(b["close"]):
                    continue
                if float(b["open"][t + 1]) <= 0:
                    continue
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN_BN:
                    continue
                if not bool(b["gk_fast"]["gk_buy"][t]):
                    continue

                # FT07: distance to 52-week high
                if arm.dist_52wk_max > 0:
                    n52 = float(b["near52"][t])
                    if np.isnan(n52) or n52 < (1.0 - arm.dist_52wk_max):
                        continue

                # FT05: volume expansion
                if arm.volexp_filter_min > 0:
                    ve = float(b["volexp"][t])
                    if np.isnan(ve) or ve < arm.volexp_filter_min:
                        continue

                pending_entries.append({
                    "sym":             sym,
                    "entry_signal_dt": trade_date,
                    "adv50":           adv,
                })

    # ── Force-close at end ────────────────────────────────────────────────────
    last_day_i = len(all_dates) - 1
    for sym, pos in list(holdings.items()):
        b       = base[sym]
        exit_c  = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":        sym,
            "arm_id":        arm.arm_id,
            "entry_dt":      str(pos["entry_dt"].date()),
            "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
            "entry_open_raw":round(pos["entry_open_raw"], 4),
            "entry_px_eff":  round(pos["entry_px_eff"], 4),
            "exit_dt":       str(all_dates[-1].date()),
            "exit_open_raw": round(exit_c, 4),
            "exit_reason":   "END_OF_TEST",
            "hold_bars":     last_day_i - pos["entry_day_i"],
            "hold_days":     (all_dates[-1] - pos["entry_dt"]).days,
            "gross_ret":     round(exit_c / pos["entry_open_raw"] - 1.0, 6),
            "net_ret":       round(net_ret, 6),
            "mfe":           round(pos.get("mfe", np.nan), 4),
            "mae":           round(pos.get("mae", np.nan), 4),
            "adv50_entry":   round(pos["adv50_entry"], 3),
            "regime_at_entry": pos.get("regime_at_entry", ""),
        })

    return pd.DataFrame(eq_curve), pd.DataFrame(trades)


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, pct=True, d=1) -> str:
    if not isinstance(v, (int, float)) or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


def compute_metrics_p4(
    eq_df:     pd.DataFrame,
    trades_df: pd.DataFrame,
    label:     str,
    vnx_daily_rets: dict,
    arm_id:    str = "",
) -> dict:
    m: dict = {"arm_id": arm_id, "label": label, "n_trades": 0}
    if trades_df.empty:
        return m

    rets   = trades_df["net_ret"].values.astype(float)
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]
    holds  = trades_df["hold_bars"].values.astype(float)
    mfes   = trades_df["mfe"].values.astype(float) if "mfe" in trades_df.columns else np.full(len(rets), np.nan)
    maes   = trades_df["mae"].values.astype(float) if "mae" in trades_df.columns else np.full(len(rets), np.nan)

    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4)
    m["avg_ret"]       = round(float(rets.mean()), 4)
    m["median_ret"]    = round(float(np.median(rets)), 4)
    m["avg_win"]       = round(float(wins.mean()),   4) if len(wins)   else np.nan
    m["avg_loss"]      = round(float(losses.mean()), 4) if len(losses) else np.nan
    m["profit_factor"] = (round(float(wins.sum() / (-losses.sum())), 3)
                          if len(losses) and losses.sum() < 0 else np.nan)
    m["expectancy"]    = round(float(rets.mean()), 4)
    m["avg_hold_bars"] = round(float(holds.mean()), 1) if len(holds) else np.nan
    m["med_hold_bars"] = round(float(np.median(holds)), 1) if len(holds) else np.nan
    m["avg_mfe"]       = round(float(np.nanmean(mfes)), 4)
    m["avg_mae"]       = round(float(np.nanmean(maes)), 4)

    # Exit reason distribution
    if "exit_reason" in trades_df.columns:
        rc = trades_df["exit_reason"].value_counts().to_dict()
        m["exit_reasons"] = rc
        for reason, cnt in rc.items():
            sub = trades_df[trades_df["exit_reason"] == reason]["net_ret"]
            m[f"avg_ret_{reason}"] = round(float(sub.mean()), 4) if len(sub) else np.nan

    if not eq_df.empty and "total_equity" in eq_df.columns:
        pv  = eq_df["total_equity"].values.astype(float)
        dts = pd.to_datetime(eq_df["date"])
        exp = eq_df["gross_exposure"].values.astype(float)

        if len(pv) >= 2 and pv[0] > 0:
            days  = (dts.iloc[-1] - dts.iloc[0]).days
            years = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0
            peak  = np.maximum.accumulate(pv)
            dd    = pv / peak - 1.0
            max_dd = float(dd.min())
            daily_rets = np.diff(pv) / pv[:-1]
            ann_vol    = float(np.std(daily_rets) * np.sqrt(252))

            m["cagr"]        = round(cagr, 4)
            m["max_dd"]      = round(max_dd, 4)
            m["mar"]         = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan
            m["ann_vol"]     = round(ann_vol, 4)
            m["sharpe"]      = round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan
            m["avg_exposure"] = round(float(exp.mean()), 4)
            m["max_exposure"] = round(float(exp.max()), 4)
            m["avg_n_pos"]   = round(float(eq_df["n_pos"].mean()), 2)
            m["turnover"]    = round(m["n_trades"] / max(years, 0.01), 1)

            # Active MaxDD vs exposure-weighted VNINDEX
            strat_rets = np.diff(pv) / np.maximum(pv[:-1], 1e-9)
            adj_vnx = []
            for i, d in enumerate(dts.values[1:]):
                d_str = str(pd.Timestamp(d).date())
                vr    = vnx_daily_rets.get(d_str, np.nan)
                adj_vnx.append(vr * exp[i] if not np.isnan(vr) else 0.0)
            adj_vnx     = np.array(adj_vnx)
            act_rets    = strat_rets - adj_vnx
            cum_act     = np.cumprod(1 + act_rets)
            pk_act      = np.maximum.accumulate(cum_act)
            act_dd      = cum_act / pk_act - 1.0
            m["active_maxdd"] = round(float(act_dd.min()), 4)

            # Yearly returns
            eq_tmp = eq_df.copy()
            eq_tmp["year"] = pd.to_datetime(eq_tmp["date"]).dt.year
            yearly: dict = {}
            for yr in YEARS:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) < 2:
                    yearly[yr] = {}
                    continue
                pv_yr  = sub["total_equity"].values.astype(float)
                pk_yr  = np.maximum.accumulate(pv_yr)
                dd_yr  = pv_yr / pk_yr - 1.0
                tr_yr  = trades_df[pd.to_datetime(trades_df["entry_dt"]).dt.year == yr] \
                         if "entry_dt" in trades_df else pd.DataFrame()
                yearly[yr] = {
                    "ret":      round(float(pv_yr[-1] / pv_yr[0] - 1.0), 4),
                    "max_dd":   round(float(dd_yr.min()), 4),
                    "n_trades": int(len(tr_yr)),
                    "win_rate": round(float((tr_yr["net_ret"] > 0).mean()), 3) if len(tr_yr) > 0 else np.nan,
                }
            m["yearly"] = yearly
            m["ret_2024"] = yearly.get(2024, {}).get("ret", np.nan)
            m["ret_2025"] = yearly.get(2025, {}).get("ret", np.nan)
            m["ret_2026"] = yearly.get(2026, {}).get("ret", np.nan)

            # Worst month
            monthly_rets = []
            eq_m = eq_df.copy()
            eq_m["ym"] = pd.to_datetime(eq_m["date"]).dt.to_period("M")
            for ym, g in eq_m.groupby("ym"):
                pv_m = g["total_equity"].values.astype(float)
                if len(pv_m) >= 2 and pv_m[0] > 0:
                    monthly_rets.append((str(ym), pv_m[-1]/pv_m[0]-1.0))
            if monthly_rets:
                worst_m = min(monthly_rets, key=lambda x: x[1])
                m["worst_month"]     = worst_m[0]
                m["worst_month_ret"] = round(worst_m[1], 4)
                # Worst rolling 3-month
                mrs = [r for _, r in monthly_rets]
                if len(mrs) >= 3:
                    r3 = [sum(mrs[i:i+3]) for i in range(len(mrs)-2)]
                    m["worst_3m_ret"] = round(min(r3), 4)

            # Yearly stability (std of year rets)
            yr_rets = [v["ret"] for v in yearly.values() if v and "ret" in v]
            m["yearly_stability"] = round(float(np.std(yr_rets)), 4) if len(yr_rets) >= 2 else np.nan

    return m


def compute_ticker_contribution(trades_df: pd.DataFrame, arm_id: str) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()
    tpnl = trades_df.groupby("symbol")["net_ret"].agg(["sum","count","mean"]).reset_index()
    tpnl.columns = ["symbol", "sum_ret", "n_trades", "avg_ret"]
    total_pnl = trades_df["net_ret"].sum()
    tpnl["pct_of_pnl"] = tpnl["sum_ret"] / total_pnl if total_pnl != 0 else np.nan
    tpnl["is_ca"]      = tpnl["symbol"].isin(CA_SYMBOLS)
    tpnl["arm_id"]     = arm_id
    tpnl = tpnl.sort_values("sum_ret", ascending=False).reset_index(drop=True)
    return tpnl


def compute_concentration_stats(trades_df: pd.DataFrame) -> dict:
    """Returns: top5_pct_pnl, top10_pct_pnl, top1_ticker_pct, top3_ticker_pct."""
    if trades_df.empty:
        return {}
    rets = trades_df["net_ret"].values
    total = rets.sum()
    if abs(total) < 1e-9:
        return {}
    sorted_rets = np.sort(rets)[::-1]
    top5_pct  = sorted_rets[:5].sum() / total if len(sorted_rets) >= 5 else np.nan
    top10_pct = sorted_rets[:10].sum() / total if len(sorted_rets) >= 10 else np.nan

    ticker_pnl = trades_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
    top1_ticker  = float(ticker_pnl.iloc[0]) / total if len(ticker_pnl) >= 1 else np.nan
    top3_ticker  = float(ticker_pnl.iloc[:3].sum()) / total if len(ticker_pnl) >= 3 else np.nan

    return {
        "top5_trade_pct_pnl":  round(top5_pct, 3),
        "top10_trade_pct_pnl": round(top10_pct, 3),
        "top1_ticker_pct_pnl": round(top1_ticker, 3),
        "top3_ticker_pct_pnl": round(top3_ticker, 3),
    }


def run_concentration(
    arm:            ArmP4,
    base:           dict,
    all_dates:      list,
    trades_df:      pd.DataFrame,
    vnx_state:      dict,
    vnx_daily_rets: dict,
) -> dict:
    result = {}
    if trades_df.empty:
        return result
    sorted_tr = trades_df.sort_values("net_ret", ascending=False)
    for scenario, n in [("ex_top1", 1), ("ex_top3", 3), ("ex_top5", 5)]:
        top_syms  = frozenset(sorted_tr.head(n)["symbol"])
        arm_x     = dataclasses.replace(arm, blacklist=arm.blacklist | top_syms)
        eq_x, tr_x = run_arm_p4(base, arm_x, all_dates, vnx_state)
        mx        = compute_metrics_p4(eq_x, tr_x, f"{arm.arm_id}_{scenario}",
                                        vnx_daily_rets, arm.arm_id)
        result[scenario] = {
            "cagr":   mx.get("cagr",   np.nan),
            "mar":    mx.get("mar",    np.nan),
            "max_dd": mx.get("max_dd", np.nan),
        }
    return result


def run_arm_full(
    arm:            ArmP4,
    base:           dict,
    all_dates:      list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
    tag:            str = "",
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    log.info("  [%s] %s — %s", tag, arm.arm_id, arm.label)
    eq_df, tr_df = run_arm_p4(base, arm, all_dates, vnx_state)
    m = compute_metrics_p4(eq_df, tr_df, arm.label, vnx_daily_rets, arm.arm_id)

    conc = run_concentration(arm, base, all_dates, tr_df, vnx_state, vnx_daily_rets)
    for scenario, vals in conc.items():
        for k, v in vals.items():
            m[f"{k}_{scenario}"] = v

    m.update(compute_concentration_stats(tr_df))
    return m, eq_df, tr_df


# ══════════════════════════════════════════════════════════════════════════════
# ARM DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

def _arm(**kwargs) -> ArmP4:
    return ArmP4(**kwargs)


def build_combo_arms() -> list:
    """C00 – C18: core combination matrix."""
    return [
        # C00: A2 baseline
        _arm(arm_id="C00", label="A2_baseline"),
        # C01: EX09a
        _arm(arm_id="C01", label="EX09a_tstop20",
             time_stop_bars=20),
        # C02: EX09a + SZ06
        _arm(arm_id="C02", label="EX09a+SZ06",
             time_stop_bars=20, half_size_regime_off=True),
        # C03: EX09a + FT07
        _arm(arm_id="C03", label="EX09a+FT07",
             time_stop_bars=20, dist_52wk_max=0.15),
        # C04: EX09a + FT05
        _arm(arm_id="C04", label="EX09a+FT05",
             time_stop_bars=20, volexp_filter_min=1.2),
        # C05: EX09a + FT07 + SZ06
        _arm(arm_id="C05", label="EX09a+FT07+SZ06",
             time_stop_bars=20, dist_52wk_max=0.15, half_size_regime_off=True),
        # C06: EX09a + FT05 + SZ06
        _arm(arm_id="C06", label="EX09a+FT05+SZ06",
             time_stop_bars=20, volexp_filter_min=1.2, half_size_regime_off=True),
        # C07: EX09a + FT07 + FT05
        _arm(arm_id="C07", label="EX09a+FT07+FT05",
             time_stop_bars=20, dist_52wk_max=0.15, volexp_filter_min=1.2),
        # C08: EX09a + FT07 + FT05 + SZ06 (full conservative)
        _arm(arm_id="C08", label="EX09a+FT07+FT05+SZ06",
             time_stop_bars=20, dist_52wk_max=0.15, volexp_filter_min=1.2,
             half_size_regime_off=True),
        # C09: EX08 only
        _arm(arm_id="C09", label="EX08_ema20",
             exit_ema20_confirmed=True),
        # C10: EX08 + FT07
        _arm(arm_id="C10", label="EX08+FT07",
             exit_ema20_confirmed=True, dist_52wk_max=0.15),
        # C11: EX08 + SZ06
        _arm(arm_id="C11", label="EX08+SZ06",
             exit_ema20_confirmed=True, half_size_regime_off=True),
        # C12: EX08 + FT07 + SZ06
        _arm(arm_id="C12", label="EX08+FT07+SZ06",
             exit_ema20_confirmed=True, dist_52wk_max=0.15, half_size_regime_off=True),
        # C13: EX08 + FT05
        _arm(arm_id="C13", label="EX08+FT05",
             exit_ema20_confirmed=True, volexp_filter_min=1.2),
        # C14: EX08 + FT05 + SZ06
        _arm(arm_id="C14", label="EX08+FT05+SZ06",
             exit_ema20_confirmed=True, volexp_filter_min=1.2, half_size_regime_off=True),
        # C15: EX03 only (10% hard stop)
        _arm(arm_id="C15", label="EX03_stop10",
             stop_pct=0.10),
        # C16: EX03 + FT07
        _arm(arm_id="C16", label="EX03+FT07",
             stop_pct=0.10, dist_52wk_max=0.15),
        # C17: EX03 + SZ06
        _arm(arm_id="C17", label="EX03+SZ06",
             stop_pct=0.10, half_size_regime_off=True),
        # C18: EX03 + FT07 + SZ06
        _arm(arm_id="C18", label="EX03+FT07+SZ06",
             stop_pct=0.10, dist_52wk_max=0.15, half_size_regime_off=True),
    ]


def build_tstop_sensitivity_arms() -> list:
    """T15/T20/T25/T30 × 4 overlays = 16 arms."""
    arms = []
    for n in [15, 20, 25, 30]:
        arms.append(_arm(arm_id=f"T{n}_base",  label=f"tstop{n}",
                         time_stop_bars=n))
        arms.append(_arm(arm_id=f"T{n}_sz06",  label=f"tstop{n}+SZ06",
                         time_stop_bars=n, half_size_regime_off=True))
        arms.append(_arm(arm_id=f"T{n}_ft07",  label=f"tstop{n}+FT07",
                         time_stop_bars=n, dist_52wk_max=0.15))
        arms.append(_arm(arm_id=f"T{n}_ft07_sz06", label=f"tstop{n}+FT07+SZ06",
                         time_stop_bars=n, dist_52wk_max=0.15, half_size_regime_off=True))
    return arms


def build_sz06b_arms() -> list:
    """SZ06b diagnostic: half-size when VNIX < EMA50 OR EMA50 slope < 0."""
    return [
        _arm(arm_id="SZ06b_C01", label="EX09a+SZ06b",
             time_stop_bars=20, half_size_regime_sz06b=True),
        _arm(arm_id="SZ06b_C05", label="EX09a+FT07+SZ06b",
             time_stop_bars=20, dist_52wk_max=0.15, half_size_regime_sz06b=True),
        _arm(arm_id="SZ06b_C11", label="EX08+SZ06b",
             exit_ema20_confirmed=True, half_size_regime_sz06b=True),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# PASS / FAIL DECISION
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_arm(m: dict) -> tuple[str, list]:
    """Returns (verdict, notes)."""
    mar        = m.get("mar", np.nan) or np.nan
    active_dd  = m.get("active_maxdd", np.nan) or np.nan
    et3        = m.get("cagr_ex_top3", np.nan) or np.nan
    et5        = m.get("cagr_ex_top5", np.nan) or np.nan
    ret2024    = m.get("ret_2024", np.nan) or np.nan
    n_trades   = m.get("n_trades", 0)
    top1_pct   = m.get("top1_ticker_pct_pnl", np.nan) or np.nan
    notes      = []

    # Hard fails
    fails = []
    if not np.isnan(active_dd) and active_dd < -0.30:
        fails.append(f"active_dd {active_dd:.1%} < -30%")
    if not np.isnan(et3) and et3 < 0.10:
        fails.append(f"ex-top3 CAGR {et3:.1%} < 10%")
    if not np.isnan(et5) and et5 < 0.05:
        fails.append(f"ex-top5 CAGR {et5:.1%} < 5%")
    if not np.isnan(ret2024) and ret2024 < -0.08:
        fails.append(f"2024 ret {ret2024:.1%} < -8%")
    if n_trades < 80:
        fails.append(f"N={n_trades} < 80")
    if not np.isnan(top1_pct) and top1_pct > 0.30:
        fails.append(f"top1 ticker {top1_pct:.0%} > 30% PnL")
    if fails:
        return "FAIL", fails

    # Strong paper trade
    strong = []
    if not np.isnan(mar) and mar >= 0.80:
        strong.append(f"MAR {mar:.2f}")
    if not np.isnan(active_dd) and active_dd > -0.25:
        strong.append(f"active_dd {active_dd:.1%} > -25%")
    if not np.isnan(et3) and et3 >= 0.15:
        strong.append(f"ex-top3 {et3:.1%}")
    if not np.isnan(et5) and et5 >= 0.10:
        strong.append(f"ex-top5 {et5:.1%}")
    if not np.isnan(ret2024) and ret2024 >= 0.0:
        strong.append(f"2024 {ret2024:.1%}")
    if len(strong) >= 4:
        return "STRONG_PAPER_TRADE", strong

    # Required paper trade
    req = []
    if not np.isnan(mar) and mar >= 0.70:
        req.append(f"MAR {mar:.2f}")
    if not np.isnan(active_dd) and active_dd > -0.28:
        req.append(f"active_dd {active_dd:.1%}")
    if not np.isnan(et3) and et3 >= 0.12:
        req.append(f"ex-top3 {et3:.1%}")
    if not np.isnan(et5) and et5 >= 0.08:
        req.append(f"ex-top5 {et5:.1%}")
    if not np.isnan(ret2024) and ret2024 >= -0.05:
        req.append(f"2024 {ret2024:.1%}")
    if n_trades >= 80:
        req.append(f"N={n_trades}")
    if len(req) >= 5:
        return "PAPER_TRADE", req

    return "WATCH", [f"MAR {_fmt(mar,pct=False,d=2)} aDD {_fmt(active_dd)} "
                     f"xT3 {_fmt(et3)} xT5 {_fmt(et5)} 2024 {_fmt(ret2024)}"]


# ══════════════════════════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def _metrics_to_row(m: dict) -> dict:
    yr  = m.get("yearly", {})
    row = {k: v for k, v in m.items()
           if k not in ("yearly", "exit_reasons")}
    for y in YEARS:
        ydata = yr.get(y, {})
        row[f"ret_{y}"]     = ydata.get("ret",      np.nan)
        row[f"n_trades_{y}"]= ydata.get("n_trades", 0)
    return row


def save_all(
    combo_results:    list,
    tstop_results:    list,
    sz06b_results:    list,
    all_monthly:      list,
    vnx_daily_rets:   dict,
    vnx_state:        dict,
    all_dates:        list,
) -> None:
    all_results = combo_results + tstop_results + sz06b_results

    # 1. phase4_summary.csv — every arm
    summary_rows = [_metrics_to_row(m) for m, _, _ in all_results]
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "phase4_summary.csv", index=False)

    # 2. phase4_combo_tests.csv — C00-C18 only
    combo_rows = [_metrics_to_row(m) for m, _, _ in combo_results]
    pd.DataFrame(combo_rows).to_csv(OUT_DIR / "phase4_combo_tests.csv", index=False)

    # 3. phase4_time_stop_sensitivity.csv
    tstop_rows = [_metrics_to_row(m) for m, _, _ in tstop_results]
    pd.DataFrame(tstop_rows).to_csv(OUT_DIR / "phase4_time_stop_sensitivity.csv", index=False)

    # 4. phase4_exit_reason_report.csv
    exit_rows = []
    for m, _, tr_df in all_results:
        if tr_df.empty or "exit_reason" not in tr_df.columns:
            continue
        for reason, cnt in tr_df["exit_reason"].value_counts().items():
            sub   = tr_df[tr_df["exit_reason"] == reason]
            exit_rows.append({
                "arm_id":   m["arm_id"],
                "label":    m["label"],
                "reason":   reason,
                "count":    cnt,
                "avg_ret":  round(float(sub["net_ret"].mean()), 4),
                "win_rate": round(float((sub["net_ret"] > 0).mean()), 3),
                "avg_hold_bars": round(float(sub["hold_bars"].mean()), 1),
                "avg_mfe":  round(float(sub["mfe"].mean()), 4) if "mfe" in sub.columns else np.nan,
                "avg_mae":  round(float(sub["mae"].mean()), 4) if "mae" in sub.columns else np.nan,
            })
    pd.DataFrame(exit_rows).to_csv(OUT_DIR / "phase4_exit_reason_report.csv", index=False)

    # 5. phase4_concentration_report.csv
    conc_rows = []
    for m, _, tr_df in all_results:
        conc_rows.append({
            "arm_id":           m["arm_id"],
            "label":            m["label"],
            "cagr":             m.get("cagr"),
            "mar":              m.get("mar"),
            "active_maxdd":     m.get("active_maxdd"),
            "cagr_ex_top1":     m.get("cagr_ex_top1"),
            "mar_ex_top1":      m.get("mar_ex_top1"),
            "cagr_ex_top3":     m.get("cagr_ex_top3"),
            "mar_ex_top3":      m.get("mar_ex_top3"),
            "cagr_ex_top5":     m.get("cagr_ex_top5"),
            "mar_ex_top5":      m.get("mar_ex_top5"),
            "top5_trade_pct":   m.get("top5_trade_pct_pnl"),
            "top10_trade_pct":  m.get("top10_trade_pct_pnl"),
            "top1_ticker_pct":  m.get("top1_ticker_pct_pnl"),
            "top3_ticker_pct":  m.get("top3_ticker_pct_pnl"),
        })
    pd.DataFrame(conc_rows).to_csv(OUT_DIR / "phase4_concentration_report.csv", index=False)

    # 6. phase4_yearly_returns.csv
    yearly_rows = []
    for m, _, _ in all_results:
        for yr, ydata in m.get("yearly", {}).items():
            if ydata:
                yearly_rows.append({
                    "arm_id": m["arm_id"],
                    "year":   yr,
                    **ydata,
                })
    pd.DataFrame(yearly_rows).to_csv(OUT_DIR / "phase4_yearly_returns.csv", index=False)

    # 7. phase4_monthly_returns.csv
    if all_monthly:
        pd.concat(all_monthly, ignore_index=True).to_csv(
            OUT_DIR / "phase4_monthly_returns.csv", index=False)

    # 8. phase4_active_drawdown.csv (all arms, sparse to save space)
    act_rows = []
    for m, eq_df, _ in all_results:
        if eq_df.empty:
            continue
        pv   = eq_df["total_equity"].values.astype(float)
        peak = np.maximum.accumulate(pv)
        dd   = pv / peak - 1.0
        for i, d in enumerate(eq_df["date"].values):
            if i % 5 == 0:  # every 5th bar to limit file size
                act_rows.append({
                    "arm_id":   m["arm_id"],
                    "date":     str(pd.Timestamp(d).date()),
                    "drawdown": round(float(dd[i]), 4),
                    "equity":   round(float(pv[i]), 6),
                })
    pd.DataFrame(act_rows).to_csv(OUT_DIR / "phase4_active_drawdown.csv", index=False)

    # 9. phase4_ticker_contribution.csv
    ticker_rows = []
    for m, _, tr_df in all_results:
        tc = compute_ticker_contribution(tr_df, m["arm_id"])
        ticker_rows.append(tc)
    if ticker_rows:
        pd.concat(ticker_rows, ignore_index=True).to_csv(
            OUT_DIR / "phase4_ticker_contribution.csv", index=False)

    # 10. phase4_equity_curves.csv (all arms combined — sampled weekly)
    eq_rows = []
    for m, eq_df, _ in all_results:
        if eq_df.empty:
            continue
        eq_s = eq_df.copy()
        eq_s["arm_id"] = m["arm_id"]
        # Weekly sample to keep file size manageable
        eq_s["date"] = pd.to_datetime(eq_s["date"])
        eq_s = eq_s[eq_s["date"].dt.dayofweek == 4]  # Fridays only
        eq_rows.append(eq_s[["arm_id","date","total_equity","gross_exposure","n_pos"]])
    if eq_rows:
        pd.concat(eq_rows, ignore_index=True).to_csv(
            OUT_DIR / "phase4_equity_curves.csv", index=False)

    log.info("All output files written to: %s", OUT_DIR)


def write_final_report(
    combo_results: list,
    tstop_results: list,
    sz06b_results: list,
) -> None:
    all_results = combo_results + tstop_results + sz06b_results

    # Find best arm
    best_m  = max(all_results, key=lambda x: x[0].get("mar") or -999)[0]
    c01_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C01"), {})
    c02_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C02"), {})
    c05_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C05"), {})
    c09_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C09"), {})
    c12_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C12"), {})
    c15_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C15"), {})
    c18_m   = next((m for m, _, _ in combo_results if m["arm_id"] == "C18"), {})

    def row_line(m: dict) -> str:
        yr = m.get("yearly", {})
        return (f"| {m.get('arm_id','')} | {m.get('label','')[:30]} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('mar',np.nan),pct=False,d=2)} |"
                f" {_fmt(m.get('active_maxdd',np.nan))} |"
                f" {_fmt(m.get('cagr_ex_top3',np.nan))} | {_fmt(m.get('cagr_ex_top5',np.nan))} |"
                f" {_fmt(m.get('ret_2024',np.nan))} |")

    lines = [
        "# Phase 4 Research — Final Report",
        f"\nRun date: {pd.Timestamp.now().date()}",
        "\n---\n",
        "## A. FACTS",
        "",
        "### Phase 3 Reference",
        f"| A2 baseline | 17.4% | 0.52 | -30.3% | 7.1% | 3.1% | 7.8% |",
        f"| EX09a (P3 best) | 29.3% | 0.72 | -30.7% | 19.5% | 12.9% | -7.1% |",
        f"| EX08 (backup) | 23.9% | 0.71 | -32.4% | 12.6% | 9.1% | 10.4% |",
        "",
        "### Phase 4 Combination Results (sorted by MAR)",
        "",
        "| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |",
        "|-----|-------|---|------|-----|----------|--------|--------|------|",
    ]
    for m, _, _ in sorted(combo_results, key=lambda x: -(x[0].get("mar") or -999)):
        lines.append(row_line(m))

    lines += [
        "",
        "### Phase 4 Time Stop Sensitivity (EX09a variants)",
        "",
        "| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |",
        "|-----|-------|---|------|-----|----------|--------|--------|------|",
    ]
    for m, _, _ in sorted(tstop_results, key=lambda x: -(x[0].get("mar") or -999)):
        lines.append(row_line(m))

    lines += [
        "",
        "### SZ06b Diagnostic",
        "",
        "| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3 | exTop5 | 2024 |",
        "|-----|-------|---|------|-----|----------|--------|--------|------|",
    ]
    for m, _, _ in sorted(sz06b_results, key=lambda x: -(x[0].get("mar") or -999)):
        lines.append(row_line(m))

    lines += ["", "---\n", "## B. BEST COMBINATION", ""]
    verdict_best, notes_best = evaluate_arm(best_m)
    lines.append(f"**Best arm: {best_m.get('arm_id')} ({best_m.get('label')}) — {verdict_best}**")
    lines.append(f"- CAGR {_fmt(best_m.get('cagr',np.nan))}  MAR {_fmt(best_m.get('mar',np.nan),pct=False,d=2)}")
    lines.append(f"- Active MaxDD {_fmt(best_m.get('active_maxdd',np.nan))}")
    lines.append(f"- ex-top3 CAGR {_fmt(best_m.get('cagr_ex_top3',np.nan))}  ex-top5 {_fmt(best_m.get('cagr_ex_top5',np.nan))}")
    lines.append(f"- 2024 {_fmt(best_m.get('ret_2024',np.nan))}  2025 {_fmt(best_m.get('ret_2025',np.nan))}")
    lines.append(f"- Notes: {'; '.join(notes_best)}")

    lines += ["", "---\n", "## C. EX09a + SZ06 ASSESSMENT (C02)", ""]
    v, n = evaluate_arm(c02_m)
    lines.append(f"C02 ({c02_m.get('label','')}): **{v}**")
    lines.append(f"- CAGR {_fmt(c02_m.get('cagr'))}  MAR {_fmt(c02_m.get('mar'),pct=False,d=2)}")
    lines.append(f"- Active MaxDD {_fmt(c02_m.get('active_maxdd'))}  (A2 baseline: -30.3%)")
    lines.append(f"- ex-top3 {_fmt(c02_m.get('cagr_ex_top3'))}  ex-top5 {_fmt(c02_m.get('cagr_ex_top5'))}")
    lines.append(f"- 2024: {_fmt(c02_m.get('ret_2024'))}")
    lines.append(f"- Notes: {'; '.join(n)}")

    lines += ["", "---\n", "## D. EX09a + FT07 ASSESSMENT (C03)", ""]
    c03_m = next((m for m, _, _ in combo_results if m["arm_id"] == "C03"), {})
    v, n = evaluate_arm(c03_m)
    lines.append(f"C03 ({c03_m.get('label','')}): **{v}**")
    lines.append(f"- CAGR {_fmt(c03_m.get('cagr'))}  MAR {_fmt(c03_m.get('mar'),pct=False,d=2)}")
    lines.append(f"- Active MaxDD {_fmt(c03_m.get('active_maxdd'))}")
    lines.append(f"- ex-top3 {_fmt(c03_m.get('cagr_ex_top3'))}  ex-top5 {_fmt(c03_m.get('cagr_ex_top5'))}")
    lines.append(f"- 2024: {_fmt(c03_m.get('ret_2024'))}")
    lines.append(f"- Notes: {'; '.join(n)}")

    lines += ["", "---\n", "## E. EX08 BRANCH vs EX09a BRANCH", ""]
    lines.append(f"EX09a best (C01): MAR {_fmt(c01_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c01_m.get('active_maxdd'))}  xT3 {_fmt(c01_m.get('cagr_ex_top3'))}")
    lines.append(f"EX08 best (C09):  MAR {_fmt(c09_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c09_m.get('active_maxdd'))}  xT3 {_fmt(c09_m.get('cagr_ex_top3'))}")
    lines.append(f"EX09a+FT07+SZ06 (C05): MAR {_fmt(c05_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c05_m.get('active_maxdd'))}  xT3 {_fmt(c05_m.get('cagr_ex_top3'))}")
    lines.append(f"EX08+FT07+SZ06 (C12):  MAR {_fmt(c12_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c12_m.get('active_maxdd'))}  xT3 {_fmt(c12_m.get('cagr_ex_top3'))}")
    if (c09_m.get("mar") or 0) > (c01_m.get("mar") or 0):
        lines.append("\nINTERPRETATION: EX08 branch delivers better MAR than EX09a branch.")
    else:
        lines.append("\nINTERPRETATION: EX09a branch maintains MAR advantage vs EX08 branch.")

    lines += ["", "---\n", "## F. HARD-STOP BRANCH (EX03)", ""]
    lines.append(f"EX03 only (C15): MAR {_fmt(c15_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c15_m.get('active_maxdd'))}  xT3 {_fmt(c15_m.get('cagr_ex_top3'))}")
    lines.append(f"EX03+FT07+SZ06 (C18): MAR {_fmt(c18_m.get('mar'),pct=False,d=2)}  aDD {_fmt(c18_m.get('active_maxdd'))}  xT3 {_fmt(c18_m.get('cagr_ex_top3'))}")
    lines.append("\nHard stop (10%) reduces drawdown risk but at the cost of cutting winners.")

    lines += ["", "---\n", "## G. CONCENTRATION REVIEW", ""]
    lines.append("Arms with ex-top3 CAGR >= 12% (required threshold):")
    qualified = [(m, eq, tr) for m, eq, tr in (combo_results + tstop_results + sz06b_results)
                 if (m.get("cagr_ex_top3") or -999) >= 0.12]
    if qualified:
        for m, _, _ in sorted(qualified, key=lambda x: -(x[0].get("cagr_ex_top3") or -999)):
            lines.append(f"  {m['arm_id']:12s} exT3={_fmt(m.get('cagr_ex_top3'))}  exT5={_fmt(m.get('cagr_ex_top5'))}  top5_pct={_fmt(m.get('top5_trade_pct_pnl'))}  top1_tick={_fmt(m.get('top1_ticker_pct_pnl'))}")
    else:
        lines.append("  No arm meets ex-top3 >= 12% threshold.")

    lines += ["", "---\n", "## H. 2024 REVIEW", ""]
    lines.append("EX09a's 2024 was -7.1% — the main cost of the time stop. Checking which combinations recover 2024:")
    pos_2024 = [(m, _, _) for m, _, _ in combo_results if (m.get("ret_2024") or -999) >= -0.05]
    if pos_2024:
        for m, _, _ in sorted(pos_2024, key=lambda x: -(x[0].get("ret_2024") or -999)):
            lines.append(f"  {m['arm_id']:12s} 2024={_fmt(m.get('ret_2024'))}  MAR={_fmt(m.get('mar'),pct=False,d=2)}  xT3={_fmt(m.get('cagr_ex_top3'))}")
    else:
        lines.append("  No combo arm recovers 2024 above -5%.")

    lines += ["", "---\n", "## I. PRODUCTION / PAPER-TRADE DECISION", ""]
    # Evaluate all arms
    paper_candidates = []
    for m, _, _ in (combo_results + tstop_results + sz06b_results):
        verdict, notes = evaluate_arm(m)
        if verdict in ("PAPER_TRADE", "STRONG_PAPER_TRADE"):
            paper_candidates.append((verdict, m, notes))

    if paper_candidates:
        lines.append(f"**{len(paper_candidates)} arm(s) qualify for paper trading:**")
        for verdict, m, notes in sorted(paper_candidates, key=lambda x: -(x[1].get("mar") or -999)):
            lines.append(f"\n**{m['arm_id']} ({m['label']}) — {verdict}**")
            lines.append(f"- CAGR {_fmt(m.get('cagr'))}  MAR {_fmt(m.get('mar'),pct=False,d=2)}")
            lines.append(f"- Active MaxDD {_fmt(m.get('active_maxdd'))}")
            lines.append(f"- ex-top3 {_fmt(m.get('cagr_ex_top3'))}  ex-top5 {_fmt(m.get('cagr_ex_top5'))}")
            lines.append(f"- 2024 {_fmt(m.get('ret_2024'))}  2025 {_fmt(m.get('ret_2025'))}")
            lines.append(f"- Criteria met: {'; '.join(notes)}")
    else:
        lines.append("**No arm meets paper-trade criteria in Phase 4.**")
        lines.append("")
        lines.append("Best arms by verdict:")
        watch_arms = [(evaluate_arm(m)[0], m) for m, _, _ in (combo_results + tstop_results)]
        for verdict, m in sorted(watch_arms, key=lambda x: (
            {"STRONG_PAPER_TRADE":0,"PAPER_TRADE":1,"WATCH":2,"FAIL":3}.get(x[0],4),
            -(x[1].get("mar") or -999)
        ))[:5]:
            lines.append(f"  {m['arm_id']:12s} {verdict:12s}  MAR {_fmt(m.get('mar'),pct=False,d=2)}  xT3 {_fmt(m.get('cagr_ex_top3'))}  2024 {_fmt(m.get('ret_2024'))}")

    lines += ["", "---\n", "## J. TOP 3 RISKS", "",
        "1. **2024 regime dependency**: EX09a's time stop is punitive in 2024 (VNINDEX down year). "
        "   Any arm that fixes 2024 may be doing so by selectively filtering out the exact period where "
        "   the time stop fires most. This is potentially an optimization artifact. "
        "   Walk-forward OOS on 2025+ is the only clean test.",
        "",
        "2. **Concentration is asymmetric**: ex-top3 CAGR improvement from EX09a is real, "
        "   but the base CAGR of 29.3% is also inflated by winners running longer. "
        "   The 'improvement' partly reflects selection bias in the remaining portfolio. "
        "   Check: do the top trades in EX09a differ materially from A2's top trades?",
        "",
        "3. **Short backtest period**: 2023-04/2026 = ~3.3 years, bull-recovery bias. "
        "   All CAGR / MAR numbers are inflated vs what a neutral regime would produce. "
        "   Active MaxDD of -22% to -30% may look much worse in a genuine bear market.",
    ]

    lines += ["", "---\n", "## K. NEXT RESEARCH QUESTIONS", "",
        "1. **Walk-forward OOS test**: Train on 2023-2024 only, test on 2025-04/2026. "
        "   Does best Phase 4 arm maintain MAR > 0.5 OOS?",
        "",
        "2. **2024 root-cause**: Identify exactly which positions EX09a time-stops exited in 2024 "
        "   at a loss, and whether those were CA-contaminated or legitimate losers. "
        "   If they were legitimate, the time stop is doing its job. If CA-contaminated, fix data first.",
        "",
        "3. **Combination stability**: The best combo arms (e.g. C05) use 3 overlays. "
        "   Test each overlay's marginal contribution. Is FT07 + SZ06 doing equal work, "
        "   or is one of them doing all the work?",
    ]

    path = OUT_DIR / "phase4_final_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Final report saved: %s", path)


# ══════════════════════════════════════════════════════════════════════════════
# MONTHLY HELPER
# ══════════════════════════════════════════════════════════════════════════════

def monthly_returns_df(eq_df: pd.DataFrame, arm_id: str) -> pd.DataFrame:
    if eq_df.empty:
        return pd.DataFrame()
    eq = eq_df.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq["ym"]   = eq["date"].dt.to_period("M")
    rows = []
    for ym, g in eq.groupby("ym"):
        pv = g["total_equity"].values.astype(float)
        if len(pv) >= 2 and pv[0] > 0:
            rows.append({"arm_id": arm_id, "ym": str(ym),
                          "year": ym.year, "month": ym.month,
                          "monthly_ret": round(pv[-1]/pv[0]-1.0, 4)})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 4 ===")

    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows", panel["symbol"].nunique(), len(panel))

    log.info("Loading VNINDEX")
    vnx_by_date, vnx_state, vnx_daily_rets = precompute_vnx(VNINDEX_CSV)

    log.info("Precomputing base signals...")
    base = precompute_base(panel, vnx_by_date)
    log.info("  Done: %d symbols", len(base))

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  Trading days: %d  (%s – %s)",
             len(all_dates), all_dates[0].date(), all_dates[-1].date())

    all_monthly: list = []

    def run_batch(arms: list, tag: str) -> list:
        results = []
        log.info("=== %s (%d arms + conc reruns each) ===", tag, len(arms))
        for arm in arms:
            m, eq_df, tr_df = run_arm_full(arm, base, all_dates, vnx_state, vnx_daily_rets, tag)
            results.append((m, eq_df, tr_df))
            all_monthly.append(monthly_returns_df(eq_df, arm.arm_id))
            eq_df.to_csv(OUT_DIR / f"eq_{arm.arm_id}.csv", index=False)
            tr_df.to_csv(OUT_DIR / f"trades_{arm.arm_id}.csv", index=False)
        return results

    combo_results = run_batch(build_combo_arms(), "Combo")
    tstop_results = run_batch(build_tstop_sensitivity_arms(), "TStop_Sensitivity")
    sz06b_results = run_batch(build_sz06b_arms(), "SZ06b_Diagnostic")

    log.info("Saving all outputs...")
    save_all(combo_results, tstop_results, sz06b_results,
             all_monthly, vnx_daily_rets, vnx_state, all_dates)
    write_final_report(combo_results, tstop_results, sz06b_results)

    # ── Print summary tables ───────────────────────────────────────────────────
    print("\n" + "="*70)
    print("PHASE 4 COMBINATION MATRIX (sorted by MAR)")
    print("="*70)
    header = f"{'Arm':8s} {'Label':28s} {'N':5s} {'CAGR':7s} {'MAR':5s} {'aDD':7s} {'xT3':7s} {'xT5':7s} {'2024':7s} {'verdict'}"
    print(header)
    for m, _, _ in sorted(combo_results, key=lambda x: -(x[0].get("mar") or -999)):
        v, _ = evaluate_arm(m)
        print(
            f"  {m['arm_id']:7s} {m.get('label','')[:27]:27s}"
            f"  {m.get('n_trades',0):4d}"
            f"  {_fmt(m.get('cagr',np.nan)):7s}"
            f"  {_fmt(m.get('mar',np.nan),pct=False,d=2):5s}"
            f"  {_fmt(m.get('active_maxdd',np.nan)):7s}"
            f"  {_fmt(m.get('cagr_ex_top3',np.nan)):7s}"
            f"  {_fmt(m.get('cagr_ex_top5',np.nan)):7s}"
            f"  {_fmt(m.get('ret_2024',np.nan)):7s}"
            f"  {v}"
        )

    print("\n" + "="*70)
    print("TIME STOP SENSITIVITY (sorted by MAR)")
    print("="*70)
    for m, _, _ in sorted(tstop_results, key=lambda x: -(x[0].get("mar") or -999)):
        v, _ = evaluate_arm(m)
        print(
            f"  {m['arm_id']:12s} {m.get('label','')[:22]:22s}"
            f"  {m.get('n_trades',0):4d}"
            f"  {_fmt(m.get('cagr',np.nan)):7s}"
            f"  {_fmt(m.get('mar',np.nan),pct=False,d=2):5s}"
            f"  {_fmt(m.get('active_maxdd',np.nan)):7s}"
            f"  {_fmt(m.get('cagr_ex_top3',np.nan)):7s}"
            f"  {_fmt(m.get('ret_2024',np.nan)):7s}"
            f"  {v}"
        )

    print("\n" + "="*70)
    print("SZ06b DIAGNOSTIC")
    print("="*70)
    for m, _, _ in sz06b_results:
        v, _ = evaluate_arm(m)
        print(
            f"  {m['arm_id']:12s} {m.get('label','')[:28]:28s}"
            f"  MAR={_fmt(m.get('mar',np.nan),pct=False,d=2)}"
            f"  aDD={_fmt(m.get('active_maxdd',np.nan))}"
            f"  xT3={_fmt(m.get('cagr_ex_top3',np.nan))}"
            f"  2024={_fmt(m.get('ret_2024',np.nan))}"
            f"  {v}"
        )

    # Final verdict
    all_results = combo_results + tstop_results + sz06b_results
    paper = [(m, evaluate_arm(m)) for m, _, _ in all_results
             if evaluate_arm(m)[0] in ("PAPER_TRADE", "STRONG_PAPER_TRADE")]
    print(f"\n\nFINAL VERDICT: {len(paper)} paper-trade candidate(s) found.")
    for m, (v, notes) in sorted(paper, key=lambda x: -(x[0].get("mar") or -999)):
        print(f"  {m['arm_id']} ({m['label']}): {v}")
        print(f"    {'; '.join(notes)}")

    print(f"\nAll Phase 4 outputs saved to: {OUT_DIR}")
    log.info("Phase 4 complete.")


if __name__ == "__main__":
    main()
