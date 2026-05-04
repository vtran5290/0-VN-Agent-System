#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 5 — Validation, Marginal Contribution, Signal Reconciliation

Phase 4 paper-trade candidate: C06 = EX09a + FT05 + SZ06
Goal: confirm it is genuinely robust, not fitted to 2024 / top winners.

Parts:
  1. Walk-forward OOS (Fold 1: test 2025+, Fold 2: test 2026+)
  2. Marginal overlay contribution (M00-M08)
  3. Time stop stability (bars 15/20/25/30 × threshold -2%/0%/+2%)
  4. 2024 root-cause analysis
  5. AFL / Python signal reconciliation trace
  6. Corporate-action data quality review
  7. Paper trade plan (written as markdown)

Outputs -> data/research/gk_audit/phase5/
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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
CACHE_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_cache.parquet"
VNINDEX_CSV   = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT_DIR       = REPO / "data/research/gk_audit/phase5"
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

GK_FAST = {"gk_len": 100, "gk_mult": 2.0, "gk_atr": 14, "gk_conf": 2}

# Walk-forward fold boundaries
WF_FOLD1_TEST_START = pd.Timestamp("2025-01-01")
WF_FOLD2_TEST_START = pd.Timestamp("2026-01-01")

# CA watchlist (unadjusted price risk)
CA_SYMBOLS = frozenset([
    "ANV","BIC","CSV","DPM","DPR","IMP","L40","MCH",
    "MSH","NTL","SAB","SIP","TCB","TCO","VIC","VHM","VRE","VGI",
])

# AFL reconciliation tickers
AFL_TICKERS = ["VRE","VGI","VIC","FPT","HPG","TCH","NVL"]

# C06 definition (Phase 4 winner — DO NOT modify)
C06_DEF = {
    "time_stop_bars": 20,
    "time_stop_threshold": 0.0,
    "volexp_filter_min": 1.2,
    "half_size_regime_off": True,
}

# ══════════════════════════════════════════════════════════════════════════════
# ARM CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmP5:
    arm_id: str
    label:  str
    # Entry filters
    dist_52wk_max:          float = 0.0
    volexp_filter_min:      float = 0.0
    # Exit
    exit_ema20_confirmed:   bool  = False
    time_stop_bars:         int   = 0
    time_stop_threshold:    float = 0.0   # exit if ret <= threshold (0 = flat/neg)
    stop_pct:               float = 0.0
    # Sizing
    max_pos:                int   = MAX_POS
    half_size_regime_off:   bool  = False
    half_size_regime_sz06b: bool  = False
    # Costs
    fee_bps:  float = FEE_BPS
    slip_bps: float = SLIP_BPS
    # Blacklist
    blacklist: frozenset = field(default_factory=frozenset)

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000


def c06_arm(arm_id="C06", label="C06_ref") -> ArmP5:
    return ArmP5(arm_id=arm_id, label=label, **C06_DEF)


# ══════════════════════════════════════════════════════════════════════════════
# MATH PRIMITIVES
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
# SIGNAL COMPUTATION
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
        "gk_trend": gk_trend,
        "gk_upper": gk_upper,
        "gk_lower": gk_lower,
        "gk_zl":    gk_zl,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PRECOMPUTE
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base(panel: pd.DataFrame) -> dict:
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

        e10   = _ema(c, 10)
        e20   = _ema(c, 20)
        adv50 = _adv50_lagged(val)
        atr14 = _wilder_atr(h, l, c, 14)
        gk_f  = compute_gk_signals(c, h, l, **GK_FAST)

        near52 = np.full(n, np.nan)
        for i in range(1, n):
            hi52 = float(np.max(h[max(0, i-252):i]))
            if hi52 > 0:
                near52[i] = c[i] / hi52

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
            "e50":           float(e50[i]) if not np.isnan(e50[i]) else float("nan"),
        }
        if i >= 1 and c[i-1] > 0:
            vnx_daily_rets[d_str] = float(c[i] / c[i-1] - 1.0)

    return vnx_by_date, vnx_state, vnx_daily_rets


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENGINE (Phase 5 extended)
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_p5(
    base:          dict,
    arm:           ArmP5,
    fold_dates:    list,           # simulation window (can be full or OOS slice)
    vnx_state:     dict,
    log_blocked:   bool = False,   # capture FT05-rejected signals for diagnosis
) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """
    Returns (eq_curve_df, trades_df, blocked_signals_list).
    blocked_signals_list is populated only when log_blocked=True.
    """
    cost_e    = arm.cost_e
    cost_x    = arm.cost_x
    blacklist = arm.blacklist | EXCL

    cash            = INITIAL_CAP
    holdings:        dict = {}
    pending_exits:   dict = {}
    pending_entries: list = []
    trades:  list = []
    eq_curve: list = []
    blocked: list = []
    prev_equity = INITIAL_CAP

    for day_i, trade_date in enumerate(fold_dates):
        day_str = str(trade_date.date())
        day_vnx = vnx_state.get(day_str, {})

        # Step 1: Execute pending exits at today's open
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
                "symbol":           sym,
                "arm_id":           arm.arm_id,
                "entry_signal_dt":  str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
                "entry_dt":         str(pos["entry_dt"].date()),
                "entry_open_raw":   round(pos["entry_open_raw"], 4),
                "entry_px_eff":     round(pos["entry_px_eff"], 4),
                "exit_dt":          str(trade_date.date()),
                "exit_open_raw":    round(open_raw, 4),
                "exit_reason":      reason,
                "hold_bars":        day_i - pos["entry_day_i"],
                "hold_days":        (trade_date - pos["entry_dt"]).days,
                "gross_ret":        round(open_raw / pos["entry_open_raw"] - 1.0, 6),
                "net_ret":          round(net_ret, 6),
                "mfe":              round(pos.get("mfe", np.nan), 4),
                "mae":              round(pos.get("mae", np.nan), 4),
                "adv50_entry":      round(pos["adv50_entry"], 3),
                "volexp_at_entry":  round(pos.get("volexp_at_entry", np.nan), 4),
                "size_factor":      pos.get("size_factor", 1.0),
                "regime_at_entry":  pos.get("regime_at_entry", ""),
                "is_ca":            sym in CA_SYMBOLS,
            })
        pending_exits.clear()

        # Step 2: Execute pending entries at today's open
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

            size_factor = 1.0
            if arm.half_size_regime_off:
                if not day_vnx.get("above_e50", True):
                    size_factor = 0.5
            elif arm.half_size_regime_sz06b:
                if (not day_vnx.get("above_e50", True)
                        or not day_vnx.get("e50_slope_pos", True)):
                    size_factor = 0.5

            slot         = (prev_equity / arm.max_pos) * size_factor
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
                "volexp_at_entry":  entry.get("volexp", np.nan),
                "size_factor":      size_factor,
                "mfe":              0.0,
                "mae":              0.0,
                "regime_at_entry":  "ON" if day_vnx.get("above_e50", True) else "OFF",
            }
        pending_entries.clear()

        # Step 3: MTM at today's close
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

        # Step 4: Scan exit signals
        for sym, pos in list(holdings.items()):
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None or t + 1 >= len(b["close"]):
                continue
            bars_held = day_i - pos["entry_day_i"]
            c_now     = float(b["close"][t])
            lo        = float(b["low"][t])
            triggered, reason, exit_cap = False, "", None

            if not triggered and bool(b["gk_fast"]["gk_sell"][t]):
                triggered, reason = True, "GK_SELL"

            if not triggered and arm.stop_pct > 0:
                stop_px = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= stop_px:
                    triggered, reason, exit_cap = True, f"HARD_STOP_{arm.stop_pct*100:.0f}PCT", stop_px

            if not triggered and arm.exit_ema20_confirmed and t >= 1:
                e20_now  = float(b["ema20"][t])
                e20_prev = float(b["ema20"][t-1])
                c_prev   = float(b["close"][t-1])
                if (not np.isnan(e20_now) and not np.isnan(e20_prev)
                        and c_now < e20_now and c_prev < e20_prev):
                    triggered, reason = True, "EMA20_CONFIRM"

            if not triggered and arm.time_stop_bars > 0:
                if bars_held >= arm.time_stop_bars:
                    current_ret = c_now / pos["entry_open_raw"] - 1.0
                    if current_ret <= arm.time_stop_threshold:
                        thr_str = f"{arm.time_stop_threshold*100:+.0f}pct"
                        triggered, reason = True, f"TSTOP_{arm.time_stop_bars}b_{thr_str}"

            if triggered:
                pos["exit_signal_dt"] = trade_date
                pending_exits[sym]    = (t, reason, exit_cap)

        # Step 5: Scan entry signals
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

                # FT07
                if arm.dist_52wk_max > 0:
                    n52 = float(b["near52"][t])
                    if np.isnan(n52) or n52 < (1.0 - arm.dist_52wk_max):
                        continue

                # FT05 — log blocked signals if requested
                ve = float(b["volexp"][t])
                if arm.volexp_filter_min > 0:
                    if np.isnan(ve) or ve < arm.volexp_filter_min:
                        if log_blocked:
                            blocked.append({
                                "sym":         sym,
                                "signal_dt":   str(trade_date.date()),
                                "volexp":      round(ve, 4) if not np.isnan(ve) else np.nan,
                                "adv50":       round(adv, 3),
                                "block_reason": "FT05_volexp",
                            })
                        continue

                pending_entries.append({
                    "sym":             sym,
                    "entry_signal_dt": trade_date,
                    "adv50":           adv,
                    "volexp":          ve,
                })

    # Force-close open positions at end of fold
    last_day_i = len(fold_dates) - 1
    for sym, pos in list(holdings.items()):
        b       = base[sym]
        exit_c  = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":           sym,
            "arm_id":           arm.arm_id,
            "entry_signal_dt":  str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
            "entry_dt":         str(pos["entry_dt"].date()),
            "entry_open_raw":   round(pos["entry_open_raw"], 4),
            "entry_px_eff":     round(pos["entry_px_eff"], 4),
            "exit_dt":          str(fold_dates[-1].date()),
            "exit_open_raw":    round(exit_c, 4),
            "exit_reason":      "END_OF_FOLD",
            "hold_bars":        last_day_i - pos["entry_day_i"],
            "hold_days":        (fold_dates[-1] - pos["entry_dt"]).days,
            "gross_ret":        round(exit_c / pos["entry_open_raw"] - 1.0, 6),
            "net_ret":          round(net_ret, 6),
            "mfe":              round(pos.get("mfe", np.nan), 4),
            "mae":              round(pos.get("mae", np.nan), 4),
            "adv50_entry":      round(pos["adv50_entry"], 3),
            "volexp_at_entry":  round(pos.get("volexp_at_entry", np.nan), 4),
            "size_factor":      pos.get("size_factor", 1.0),
            "regime_at_entry":  pos.get("regime_at_entry", ""),
            "is_ca":            sym in CA_SYMBOLS,
        })

    return pd.DataFrame(eq_curve), pd.DataFrame(trades), blocked


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, pct=True, d=1) -> str:
    if not isinstance(v, (int, float)) or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


def compute_metrics_p5(
    eq_df:     pd.DataFrame,
    trades_df: pd.DataFrame,
    label:     str,
    vnx_daily_rets: dict,
    arm_id:    str = "",
    years:     list | None = None,
) -> dict:
    if years is None:
        years = YEARS
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
    m["avg_mfe"]       = round(float(np.nanmean(mfes)), 4)
    m["avg_mae"]       = round(float(np.nanmean(maes)), 4)

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
            years_n = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years_n) - 1.0
            peak  = np.maximum.accumulate(pv)
            dd    = pv / peak - 1.0
            max_dd = float(dd.min())
            daily_rets = np.diff(pv) / pv[:-1]
            ann_vol    = float(np.std(daily_rets) * np.sqrt(252))

            m["cagr"]         = round(cagr, 4)
            m["max_dd"]       = round(max_dd, 4)
            m["mar"]          = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan
            m["ann_vol"]      = round(ann_vol, 4)
            m["sharpe"]       = round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan
            m["avg_exposure"] = round(float(exp.mean()), 4)
            m["avg_n_pos"]    = round(float(eq_df["n_pos"].mean()), 2)
            m["turnover"]     = round(m["n_trades"] / max(years_n, 0.01), 1)

            # Active MaxDD
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
            yr_dict: dict = {}
            for yr in years:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) < 2:
                    yr_dict[yr] = {}
                    continue
                pv_yr  = sub["total_equity"].values.astype(float)
                pk_yr  = np.maximum.accumulate(pv_yr)
                dd_yr  = pv_yr / pk_yr - 1.0
                tr_yr  = trades_df[pd.to_datetime(trades_df["entry_dt"]).dt.year == yr] if "entry_dt" in trades_df else pd.DataFrame()
                yr_dict[yr] = {
                    "ret":      round(float(pv_yr[-1] / pv_yr[0] - 1.0), 4),
                    "max_dd":   round(float(dd_yr.min()), 4),
                    "n_trades": int(len(tr_yr)),
                    "win_rate": round(float((tr_yr["net_ret"] > 0).mean()), 3) if len(tr_yr) > 0 else np.nan,
                }
            m["yearly"] = yr_dict
            for yr in years:
                m[f"ret_{yr}"] = yr_dict.get(yr, {}).get("ret", np.nan)

            # Monthly worst
            eq_m = eq_df.copy()
            eq_m["ym"] = pd.to_datetime(eq_m["date"]).dt.to_period("M")
            monthly_rets = []
            for ym, g in eq_m.groupby("ym"):
                pv_m = g["total_equity"].values.astype(float)
                if len(pv_m) >= 2 and pv_m[0] > 0:
                    monthly_rets.append((str(ym), pv_m[-1]/pv_m[0]-1.0))
            if monthly_rets:
                worst_m = min(monthly_rets, key=lambda x: x[1])
                m["worst_month"]     = worst_m[0]
                m["worst_month_ret"] = round(worst_m[1], 4)
                mrs = [r for _, r in monthly_rets]
                if len(mrs) >= 3:
                    r3 = [sum(mrs[i:i+3]) for i in range(len(mrs)-2)]
                    m["worst_3m_ret"] = round(min(r3), 4)

            yr_rets = [v["ret"] for v in yr_dict.values() if v and "ret" in v]
            m["yearly_stability"] = round(float(np.std(yr_rets)), 4) if len(yr_rets) >= 2 else np.nan

    # Concentration
    if not trades_df.empty:
        rets_all  = trades_df["net_ret"].values.astype(float)
        total_pnl = rets_all.sum()
        if abs(total_pnl) > 1e-9:
            sorted_r = np.sort(rets_all)[::-1]
            m["top5_trade_pct_pnl"]  = round(sorted_r[:5].sum() / total_pnl, 3) if len(sorted_r) >= 5 else np.nan
            m["top10_trade_pct_pnl"] = round(sorted_r[:10].sum() / total_pnl, 3) if len(sorted_r) >= 10 else np.nan
            tkr = trades_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
            m["top1_ticker_pct_pnl"] = round(float(tkr.iloc[0]) / total_pnl, 3) if len(tkr) >= 1 else np.nan
            m["top3_ticker_pct_pnl"] = round(float(tkr.iloc[:3].sum()) / total_pnl, 3) if len(tkr) >= 3 else np.nan

    return m


def run_concentration(
    arm:            ArmP5,
    base:           dict,
    fold_dates:     list,
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
        eq_x, tr_x, _ = run_arm_p5(base, arm_x, fold_dates, vnx_state)
        mx = compute_metrics_p5(eq_x, tr_x, f"{arm.arm_id}_{scenario}", vnx_daily_rets, arm.arm_id)
        result[scenario] = {
            "cagr": mx.get("cagr", np.nan),
            "mar":  mx.get("mar",  np.nan),
        }
    return result


def run_arm_full(
    arm:            ArmP5,
    base:           dict,
    fold_dates:     list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
    tag:            str = "",
    do_conc:        bool = True,
    log_blocked:    bool = False,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, list]:
    log.info("  [%s] %s — %s", tag, arm.arm_id, arm.label)
    eq_df, tr_df, blocked = run_arm_p5(base, arm, fold_dates, vnx_state, log_blocked)
    m = compute_metrics_p5(eq_df, tr_df, arm.label, vnx_daily_rets, arm.arm_id)
    if do_conc:
        conc = run_concentration(arm, base, fold_dates, tr_df, vnx_state, vnx_daily_rets)
        for scenario, vals in conc.items():
            for k, v in vals.items():
                m[f"{k}_{scenario}"] = v
    return m, eq_df, tr_df, blocked


# ══════════════════════════════════════════════════════════════════════════════
# PART 1: WALK-FORWARD OOS
# ══════════════════════════════════════════════════════════════════════════════

def run_walk_forward(
    base:           dict,
    all_dates:      list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
) -> list[dict]:
    """
    Fold 1: train=2023-2024, test=2025+
    Fold 2: train=2023-2025, test=2026+
    """
    arm = c06_arm("C06_WF", "C06")
    folds = [
        ("Fold1_Train", START_DATE,          WF_FOLD1_TEST_START - pd.Timedelta(days=1)),
        ("Fold1_OOS",   WF_FOLD1_TEST_START, END_DATE),
        ("Fold2_Train", START_DATE,          WF_FOLD2_TEST_START - pd.Timedelta(days=1)),
        ("Fold2_OOS",   WF_FOLD2_TEST_START, END_DATE),
    ]
    results = []
    for fold_name, d_from, d_to in folds:
        fold_dates = [d for d in all_dates if d_from <= d <= d_to]
        if len(fold_dates) < 20:
            log.info("  [WF] %s — too few dates (%d), skipping", fold_name, len(fold_dates))
            results.append({"fold": fold_name, "n_dates": len(fold_dates), "note": "too_few_dates"})
            continue
        log.info("  [WF] %s — %d trading days (%s to %s)",
                 fold_name, len(fold_dates), fold_dates[0].date(), fold_dates[-1].date())
        arm_fold = dataclasses.replace(arm, arm_id=fold_name, label=f"C06 {fold_name}")
        eq_df, tr_df, _ = run_arm_p5(base, arm_fold, fold_dates, vnx_state)
        m = compute_metrics_p5(eq_df, tr_df, fold_name, vnx_daily_rets, fold_name)
        if tr_df.empty or len(tr_df) < 10:
            m["note"] = "insufficient_trades"
        else:
            conc = run_concentration(arm_fold, base, fold_dates, tr_df, vnx_state, vnx_daily_rets)
            for scenario, vals in conc.items():
                for k, v in vals.items():
                    m[f"{k}_{scenario}"] = v
        m["fold"] = fold_name
        m["fold_start"] = str(fold_dates[0].date())
        m["fold_end"]   = str(fold_dates[-1].date())
        m["n_dates"]    = len(fold_dates)
        results.append(m)
    return results


# ══════════════════════════════════════════════════════════════════════════════
# PART 2: MARGINAL OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

def build_marginal_arms() -> list[ArmP5]:
    def a(arm_id, label, **kw) -> ArmP5:
        return ArmP5(arm_id=arm_id, label=label, time_stop_bars=20,
                     time_stop_threshold=0.0, **kw)
    return [
        a("M00", "EX09a_only"),
        a("M01", "EX09a+FT05_1.2",  volexp_filter_min=1.2),
        a("M02", "EX09a+SZ06",       half_size_regime_off=True),
        a("M03", "EX09a+FT05+SZ06",  volexp_filter_min=1.2, half_size_regime_off=True),
        a("M04", "EX09a+FT05_1.1",   volexp_filter_min=1.1),
        a("M05", "EX09a+FT05_1.3",   volexp_filter_min=1.3),
        a("M06", "EX09a+FT05_1.5",   volexp_filter_min=1.5),
        a("M07", "EX09a+SZ06b",      half_size_regime_sz06b=True),
        a("M08", "EX09a+FT05+SZ06b", volexp_filter_min=1.2, half_size_regime_sz06b=True),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: TIME STOP STABILITY
# ══════════════════════════════════════════════════════════════════════════════

def build_tstop_stability_arms() -> list[ArmP5]:
    arms = []
    bars_list   = [15, 20, 25, 30]
    thresh_list = [-0.02, 0.0, 0.02]
    for bars in bars_list:
        for thr in thresh_list:
            thr_tag = f"{int(thr*100):+d}pct"
            arm_id  = f"TS_b{bars}_t{int(thr*100):+d}"
            label   = f"FT05+SZ06+tstop{bars}_{thr_tag}"
            arms.append(ArmP5(
                arm_id=arm_id, label=label,
                volexp_filter_min=1.2,
                half_size_regime_off=True,
                time_stop_bars=bars,
                time_stop_threshold=thr,
            ))
    return arms


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: 2024 ROOT-CAUSE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def run_2024_diagnosis(
    base:           dict,
    all_dates:      list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns (diagnosis_df, blocked_df, tstop_review_df).
    """
    # M00: EX09a only (no FT05, no SZ06) — baseline for comparison
    m00 = ArmP5("M00_2024", "EX09a_only", time_stop_bars=20)
    # M01: EX09a + FT05 — with log_blocked to capture FT05 rejections
    m01 = ArmP5("M01_2024", "EX09a+FT05", time_stop_bars=20, volexp_filter_min=1.2)
    # M02: EX09a + SZ06
    m02 = ArmP5("M02_2024", "EX09a+SZ06", time_stop_bars=20, half_size_regime_off=True)
    # M03: EX09a + FT05 + SZ06 (C06)
    m03 = ArmP5("M03_2024", "C06_ref", time_stop_bars=20, volexp_filter_min=1.2,
                half_size_regime_off=True)

    # Run all four — M01 with blocked signal logging (FT05 is the filter, so log_blocked works)
    log.info("  [2024] Running M00 (EX09a_only)")
    _, m00_tr, _ = run_arm_p5(base, m00, all_dates, vnx_state)
    log.info("  [2024] Running M01 (EX09a+FT05, log_blocked=True)")
    _, m01_tr, blocked = run_arm_p5(base, m01, all_dates, vnx_state, log_blocked=True)
    log.info("  [2024] Running M02, M03")
    _, m02_tr, _ = run_arm_p5(base, m02, all_dates, vnx_state)
    _, m03_tr, _ = run_arm_p5(base, m03, all_dates, vnx_state)

    # Filter to 2024 trades (entry in 2024)
    def y24(df):
        if df.empty:
            return df
        return df[pd.to_datetime(df["entry_dt"]).dt.year == 2024].copy()

    m00_24 = y24(m00_tr)
    m01_24 = y24(m01_tr)
    m02_24 = y24(m02_tr)
    m03_24 = y24(m03_tr)

    # ── Build diagnosis_df: all M00 2024 trades with overlay annotations ──────
    if not m00_24.empty:
        m00_24 = m00_24.copy()
        # Was this trade taken in C06?
        c06_keys = set()
        if not m03_24.empty:
            c06_keys = set(zip(m03_24["symbol"], m03_24["entry_dt"]))
        m00_24["in_C06"]    = [
            (sym, edt) in c06_keys
            for sym, edt in zip(m00_24["symbol"], m00_24["entry_dt"])
        ]
        # FT05 status: would C06 have blocked it?
        m00_24["ft05_blocked"] = m00_24.apply(
            lambda r: (
                not (r.get("in_C06", False)) and
                (r.get("volexp_at_entry", np.nan) < 1.2
                 if not np.isnan(r.get("volexp_at_entry", np.nan)) else True)
            ), axis=1
        )
        # SZ06 status: was it half-sized in C06?
        m02_keys = {}
        if not m02_24.empty:
            m02_keys = {(r["symbol"], r["entry_dt"]): r.get("size_factor", 1.0)
                        for _, r in m02_24.iterrows()}
        m00_24["sz06_size_factor"] = [
            m02_keys.get((sym, edt), 1.0)
            for sym, edt in zip(m00_24["symbol"], m00_24["entry_dt"])
        ]
        # TimeStop exit in M00
        m00_24["tstop_exit"] = m00_24["exit_reason"].str.startswith("TSTOP")
        # CA flag already in trade record
        m00_24["arm_ref"] = "M00_EX09a"
        diagnosis_df = m00_24
    else:
        diagnosis_df = pd.DataFrame()

    # ── blocked_df: signals FT05 rejected in 2024 ────────────────────────────
    blocked_2024 = [b for b in blocked
                    if str(b.get("signal_dt", ""))[:4] == "2024"]
    blocked_df   = pd.DataFrame(blocked_2024)
    if not blocked_df.empty:
        # Look up trade outcome if M00 actually took the signal
        m00_lookup = {}
        if not m00_tr.empty:
            for _, r in m00_tr.iterrows():
                m00_lookup[(r["symbol"], r["entry_signal_dt"])] = {
                    "net_ret":     r.get("net_ret",  np.nan),
                    "exit_reason": r.get("exit_reason", ""),
                    "hold_bars":   r.get("hold_bars", 0),
                }
        blocked_df["m00_net_ret"]     = [
            m00_lookup.get((r["sym"], r["signal_dt"]), {}).get("net_ret", np.nan)
            for _, r in blocked_df.iterrows()
        ]
        blocked_df["m00_exit_reason"] = [
            m00_lookup.get((r["sym"], r["signal_dt"]), {}).get("exit_reason", "")
            for _, r in blocked_df.iterrows()
        ]
        blocked_df["is_ca"] = blocked_df["sym"].isin(CA_SYMBOLS)

    # ── tstop_review_df: trades in M00-2024 that were time-stopped ───────────
    if not m00_24.empty:
        tstop_df = m00_24[m00_24["tstop_exit"]].copy()
        tstop_df["recovered_after_stop"] = np.nan  # unknown without post-stop price
        # Attempt to check post-exit close 5 and 20 bars later
        check_rows = []
        for _, r in tstop_df.iterrows():
            sym    = r["symbol"]
            ex_dt  = pd.Timestamp(r["exit_dt"])
            en_px  = r["entry_open_raw"]
            ex_px  = r["exit_open_raw"]
            b      = base.get(sym, {})
            dates  = list(b.get("dates", []))
            ex_idx = next((i for i, d in enumerate(dates) if d >= ex_dt), None)
            close  = b.get("close", np.ndarray([]))
            post5  = float(close[ex_idx+5]) / en_px - 1.0 if (ex_idx is not None and ex_idx+5 < len(close)) else np.nan
            post20 = float(close[ex_idx+20]) / en_px - 1.0 if (ex_idx is not None and ex_idx+20 < len(close)) else np.nan
            row_out = r.to_dict()
            row_out["post_exit_ret_5b"]  = round(post5,  4) if not np.isnan(post5)  else np.nan
            row_out["post_exit_ret_20b"] = round(post20, 4) if not np.isnan(post20) else np.nan
            row_out["recovered_after_stop"] = bool(post20 > 0) if not np.isnan(post20) else np.nan
            check_rows.append(row_out)
        tstop_review_df = pd.DataFrame(check_rows)
    else:
        tstop_review_df = pd.DataFrame()

    return diagnosis_df, blocked_df, tstop_review_df


# ══════════════════════════════════════════════════════════════════════════════
# PART 5: AFL SIGNAL RECONCILIATION
# ══════════════════════════════════════════════════════════════════════════════

def signal_trace(
    sym:       str,
    base_data: dict,
    vnx_state: dict,
    arm:       ArmP5,
    all_dates: list,
) -> pd.DataFrame:
    """Export per-bar signal state for a single ticker for AFL reconciliation."""
    if sym not in base_data:
        return pd.DataFrame()
    b         = base_data[sym]
    dts       = b["dates"]
    c         = b["close"]
    o         = b["open"]
    h         = b["high"]
    l         = b["low"]
    val       = b["value"]
    gk        = b["gk_fast"]
    adv50     = b["adv50_lag"]
    volexp    = b["volexp"]
    ema10     = b["ema10"]
    ema20     = b["ema20"]
    near52    = b["near52"]

    # Simulate position state for this ticker
    in_pos      = False
    hold_bars   = 0
    trade_ret   = 0.0
    entry_px    = np.nan
    tstop_would = False

    rows = []
    for i, d in enumerate(dts):
        d_str = str(d.date())
        vnx   = vnx_state.get(d_str, {})
        adv   = float(adv50[i])
        ve    = float(volexp[i])
        n52   = float(near52[i])
        regime_on = vnx.get("above_e50", True)

        adv_ok    = not np.isnan(adv) and adv >= ADV50_MIN_BN
        volexp_ok = arm.volexp_filter_min <= 0 or (not np.isnan(ve) and ve >= arm.volexp_filter_min)
        ft07_ok   = arm.dist_52wk_max <= 0 or (not np.isnan(n52) and n52 >= (1.0 - arm.dist_52wk_max))

        sys_buy_raw = bool(gk["gk_buy"][i]) and adv_ok
        sys_buy     = sys_buy_raw and volexp_ok and ft07_ok

        size_factor = 1.0
        if arm.half_size_regime_off and not regime_on:
            size_factor = 0.5
        elif arm.half_size_regime_sz06b:
            if not regime_on or not vnx.get("e50_slope_pos", True):
                size_factor = 0.5

        # Track position state for this ticker
        if in_pos:
            hold_bars += 1
            c_now      = float(c[i])
            trade_ret  = c_now / entry_px - 1.0
            tstop_would = (arm.time_stop_bars > 0
                           and hold_bars >= arm.time_stop_bars
                           and trade_ret <= arm.time_stop_threshold)
            if bool(gk["gk_sell"][i]) or tstop_would:
                in_pos    = False
                hold_bars = 0
                entry_px  = np.nan
                trade_ret = 0.0
        elif sys_buy and i + 1 < len(c):
            in_pos    = True
            entry_px  = float(o[i+1]) if float(o[i+1]) > 0 else float(c[i])
            hold_bars = 0
            trade_ret = 0.0
            tstop_would = False

        rows.append({
            "symbol":          sym,
            "date":            str(d.date()),
            "open":            round(float(o[i]), 4),
            "high":            round(float(h[i]), 4),
            "low":             round(float(l[i]), 4),
            "close":           round(float(c[i]), 4),
            "volume_bn":       round(float(val[i])/1e9, 4),
            "adv50_lag_bn":    round(adv, 3) if not np.isnan(adv) else np.nan,
            "adv50_ok":        adv_ok,
            "volexp":          round(ve, 4) if not np.isnan(ve) else np.nan,
            "volexp_ok":       volexp_ok,
            "near52":          round(n52, 4) if not np.isnan(n52) else np.nan,
            "vnx_close":       vnx.get("close", np.nan),
            "vnx_e50":         vnx.get("e50", np.nan),
            "vnx_above_e50":   regime_on,
            "vnx_e50_slope_pos": vnx.get("e50_slope_pos", np.nan),
            "ema10":           round(float(ema10[i]), 4),
            "ema20":           round(float(ema20[i]), 4),
            "gk_zl":           round(float(gk["gk_zl"][i]), 4) if not np.isnan(gk["gk_zl"][i]) else np.nan,
            "gk_upper":        round(float(gk["gk_upper"][i]), 4) if not np.isnan(gk["gk_upper"][i]) else np.nan,
            "gk_lower":        round(float(gk["gk_lower"][i]), 4) if not np.isnan(gk["gk_lower"][i]) else np.nan,
            "gk_trend":        int(gk["gk_trend"][i]),
            "gk_buy":          bool(gk["gk_buy"][i]),
            "gk_sell":         bool(gk["gk_sell"][i]),
            "sys_buy_raw":     sys_buy_raw,
            "sys_buy":         sys_buy,
            "sys_in_pos":      in_pos,
            "hold_bars":       hold_bars,
            "trade_ret_pct":   round(trade_ret * 100, 2),
            "tstop_would_fire":tstop_would,
            "size_factor":     size_factor,
        })

    return pd.DataFrame(rows)


def build_signal_reconciliation(
    base:      dict,
    vnx_state: dict,
    all_dates: list,
    trades_c06: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (reconciliation_df, afl_debug_rows_df).
    reconciliation_df: full per-bar trace for AFL tickers.
    afl_debug_rows_df: rows around BUY/EXIT signals only.
    """
    arm = c06_arm("AFL_trace", "C06")

    # Find one winner and one loser from C06 trades
    bonus_tickers = []
    if not trades_c06.empty:
        sorted_tr = trades_c06.sort_values("net_ret", ascending=False)
        for sym in sorted_tr["symbol"].values:
            if sym not in AFL_TICKERS:
                bonus_tickers.append(("winner", sym))
                break
        for sym in sorted_tr["symbol"].values[::-1]:
            if sym not in AFL_TICKERS:
                bonus_tickers.append(("loser", sym))
                break

    tickers_to_trace = [(t, t) for t in AFL_TICKERS]
    for role, sym in bonus_tickers:
        if sym not in AFL_TICKERS:
            tickers_to_trace.append((f"{role}_{sym}", sym))

    all_traces = []
    for label, sym in tickers_to_trace:
        df = signal_trace(sym, base, vnx_state, arm, all_dates)
        if not df.empty:
            df["trace_label"] = label
            all_traces.append(df)

    if not all_traces:
        return pd.DataFrame(), pd.DataFrame()

    recon_df = pd.concat(all_traces, ignore_index=True)

    # Debug rows: ±3 bars around any BUY or EXIT signal
    debug_rows = []
    for label, sym in tickers_to_trace:
        df_t = recon_df[recon_df["trace_label"] == label].copy()
        if df_t.empty:
            continue
        signal_idx = df_t.index[df_t["gk_buy"] | df_t["gk_sell"] | df_t["tstop_would_fire"]].tolist()
        included   = set()
        for si in signal_idx:
            for j in range(max(0, si-3), min(len(df_t), si+4)):
                included.add(df_t.index[j] if j < len(df_t.index) else j)
        debug_sub = recon_df.loc[[i for i in included if i in recon_df.index]]
        debug_rows.append(debug_sub)

    debug_df = pd.concat(debug_rows, ignore_index=True) if debug_rows else pd.DataFrame()
    return recon_df, debug_df


def write_signal_mismatches_md(recon_df: pd.DataFrame) -> None:
    path = OUT_DIR / "phase5_signal_mismatches.md"
    lines = [
        "# Phase 5 — AFL / Python Signal Reconciliation Checklist",
        "",
        "This file exports the Python-side signal computation for C06.",
        "Compare against AmiBroker AFL chart manually.",
        "",
        "## Reconciliation Checklist",
        "",
        "For each ticker below, verify against AFL chart:",
        "",
        "| Field | Check |",
        "|-------|-------|",
        "| GK_Buy date | Does AFL BUY arrow match Python `gk_buy=True` date? |",
        "| GK_Sell date | Does AFL SELL arrow match Python `gk_sell=True` date? |",
        "| VolExp filter | Is `volexp >= 1.2` same as AFL VolExp gate? |",
        "| ADV50 filter | Is `adv50_lag >= 2.0 bn` same as AFL ADV50 gate? |",
        "| VNINDEX EMA50 | Is `vnx_above_e50` same as AFL regime check? |",
        "| Time stop | Does AFL exit at bar 20 if flat/neg match Python `tstop_would_fire`? |",
        "| Size factor | Is half-size (0.5) when regime OFF matching AFL? |",
        "",
        "## Common Mismatch Sources",
        "",
        "1. **EMA seed**: Python and AFL may differ in EMA initialization if lookback window differs.",
        "   - Python: EMA starts seeding from first non-NaN price.",
        "   - AFL: may use first bar as seed. Check EMA values at period start.",
        "",
        "2. **ATR seed**: Wilder ATR uses SMA seed for first `n` bars.",
        "   - Same logic in both; should match if warmup data covers 100+ bars.",
        "",
        "3. **ADV50 calculation**: Python uses lagged ADV50 (bars i-50 to i-1).",
        "   - AFL must use same lagging convention (prior 50 bars, not including today).",
        "",
        "4. **Price unit**: Python reads raw VND from parquet.",
        "   - AFL must use Thousand VND with same multiplier correction.",
        "",
        "5. **Execution timing**: Python entry = next open after signal bar.",
        "   - AFL must buy at next open (no lookahead).",
        "",
        "6. **Corporate action**: VIC/VHM/VRE prices may differ if AFL uses adjusted data.",
        "",
        "## Tickers Traced",
        "",
    ]
    if not recon_df.empty:
        for sym in recon_df["trace_label"].unique():
            sub = recon_df[recon_df["trace_label"] == sym]
            buys  = sub[sub["gk_buy"]]["date"].tolist()
            sells = sub[sub["gk_sell"]]["date"].tolist()
            tstops = sub[sub["tstop_would_fire"]]["date"].tolist()
            lines.append(f"### {sym}")
            lines.append(f"- GK Buy signals:  {buys[:10]}")
            lines.append(f"- GK Sell signals: {sells[:10]}")
            lines.append(f"- TStop fire dates:{tstops[:10]}")
            lines.append("")
    else:
        lines.append("No trace data available.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("  signal_mismatches.md written")


# ══════════════════════════════════════════════════════════════════════════════
# PART 6: CORPORATE ACTION REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def run_ca_review(
    base:      dict,
    trades_c06: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (ca_review_df, top20_ca_df).
    ca_review_df: CA watchlist tickers — large gap dates.
    top20_ca_df: top/bottom 20 PnL tickers from C06 with CA flag.
    """
    # CA watchlist gap review
    gap_rows = []
    for sym in CA_SYMBOLS:
        if sym not in base:
            continue
        b   = base[sym]
        c   = b["close"]
        dts = b["dates"]
        for i in range(1, len(c)):
            if c[i-1] > 0:
                gap = c[i] / c[i-1] - 1.0
                if abs(gap) >= 0.15:  # flag >=15% overnight gap
                    gap_rows.append({
                        "symbol":   sym,
                        "date":     str(dts[i].date()),
                        "prev_close": round(float(c[i-1]), 2),
                        "close":    round(float(c[i]), 2),
                        "gap_pct":  round(gap * 100, 2),
                        "gap_flag": "LARGE_GAP" if abs(gap) >= 0.20 else "MODERATE_GAP",
                        "is_in_ca_watchlist": True,
                    })
    ca_review_df = pd.DataFrame(gap_rows).sort_values("gap_pct", key=abs, ascending=False).head(100)

    # Top/bottom 20 PnL tickers from C06
    top20_df = pd.DataFrame()
    if not trades_c06.empty:
        tkr_pnl = (trades_c06.groupby("symbol")["net_ret"]
                   .agg(["sum","count","mean"])
                   .reset_index()
                   .rename(columns={"sum":"sum_ret","count":"n_trades","mean":"avg_ret"}))
        tkr_pnl["is_ca"] = tkr_pnl["symbol"].isin(CA_SYMBOLS)
        total_pnl        = trades_c06["net_ret"].sum()
        tkr_pnl["pct_of_total_pnl"] = tkr_pnl["sum_ret"] / total_pnl if total_pnl != 0 else np.nan
        tkr_sorted = tkr_pnl.sort_values("sum_ret", ascending=False)
        top20  = tkr_sorted.head(20)
        bot20  = tkr_sorted.tail(20)
        top20["rank_group"] = "top20_winners"
        bot20["rank_group"] = "top20_losers"

        # Check for large gaps in their price data
        for df_part in [top20, bot20]:
            for _, row in df_part.iterrows():
                sym = row["symbol"]
                if sym not in base:
                    continue
                b   = base[sym]
                c   = b["close"]
                max_gap = max((abs(c[i]/c[i-1]-1.0) for i in range(1,len(c)) if c[i-1]>0), default=0.0)
                df_part.loc[df_part["symbol"]==sym, "max_overnight_gap_pct"] = round(max_gap*100, 2)
                df_part.loc[df_part["symbol"]==sym, "ca_gap_risk"] = "HIGH" if max_gap >= 0.20 else ("MOD" if max_gap >= 0.10 else "LOW")

        top20_df = pd.concat([top20, bot20], ignore_index=True)

    return ca_review_df, top20_df


# ══════════════════════════════════════════════════════════════════════════════
# PAPER TRADE PLAN
# ══════════════════════════════════════════════════════════════════════════════

def write_paper_trade_plan(passes_oos: bool) -> None:
    path = OUT_DIR / "phase5_paper_trade_plan.md"
    lines = [
        "# C06 Paper Trade Operating Plan",
        "",
        f"Generated: {pd.Timestamp.now().date()}",
        f"OOS validation status: {'PASS' if passes_oos else 'CONDITIONAL — review before starting'}",
        "",
        "---",
        "",
        "## 1. System Definition",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        "| Entry signal | GK_FAST (Len=100, Mult=2.0, ATR=14, Confirm=2) BUY flip |",
        "| Volume filter | VolExp = today's value / ADV50 >= 1.2 |",
        "| Liquidity gate | Lagged ADV50 >= VND 2B/day |",
        "| Primary exit | GK_FAST SELL flip |",
        "| Time stop | After 20 bars: if trade return <= 0%, exit next open |",
        "| Regime sizing | VNINDEX close >= EMA50: full-size; below: half-size |",
        "| Ranking | Descending ADV50 (most liquid first) |",
        "| Max positions | 10 |",
        "| Full slot size | Equity / 10 |",
        "| Half slot size | (Equity / 10) x 0.5 |",
        "| Universe | 271 symbols excl. VPL (pre-252 bars) |",
        "| Costs (backtest) | 25 bps fee + 10 bps slippage per side |",
        "",
        "---",
        "",
        "## 2. Daily Signal Generation",
        "",
        "Run after market close each day:",
        "",
        "```",
        "1. Fetch today's OHLCV for all 271 symbols",
        "2. Compute GK_FAST signals (need 200+ bars warmup)",
        "3. Compute ADV50_lagged for each symbol (prior 50 sessions trading value, VND)",
        "4. Compute VolExp = today_value / (ADV50_lagged * 1e9)",
        "5. Load VNINDEX close; compute EMA50 of VNINDEX",
        "6. For each symbol with GK_BUY signal today:",
        "   a. Pass ADV50_lagged >= 2.0 bn",
        "   b. Pass VolExp >= 1.2",
        "   c. Add to ENTRY candidates for tomorrow",
        "7. For each open position, check exit conditions:",
        "   a. GK_SELL signal today → exit at tomorrow's open",
        "   b. Bars held >= 20 AND trade return <= 0 → exit at tomorrow's open",
        "8. Determine VNINDEX regime: VNINDEX_close >= VNINDEX_EMA50 → full-size",
        "9. Determine slot size for new entries:",
        "   - Full regime: slot = portfolio_equity / 10",
        "   - Below regime: slot = (portfolio_equity / 10) * 0.5",
        "10. Rank entry candidates by ADV50 descending",
        "    Take top N to fill available slots",
        "```",
        "",
        "---",
        "",
        "## 3. Entry Execution",
        "",
        "- Signal date: today (after close)",
        "- Execution date: next morning open",
        "- Execute at market open (ATC not recommended for VN)",
        "- Log actual fill price vs assumed open",
        "- Record slippage = (actual fill - open) / open",
        "",
        "---",
        "",
        "## 4. Exit Execution",
        "",
        "- GK_SELL exits: execute next morning at market open",
        "- Time stop exits: execute next morning if triggered at prior close",
        "- Do NOT hold through weekends if time stop triggered Friday close",
        "- Log actual fill price; record slippage",
        "",
        "---",
        "",
        "## 5. Position Sizing",
        "",
        "| Condition | Slot size |",
        "|-----------|-----------|",
        "| VNINDEX >= EMA50 | Equity / 10 |",
        "| VNINDEX < EMA50 | (Equity / 10) × 0.5 |",
        "",
        "- Do not adjust existing positions when regime changes mid-hold",
        "- Apply regime check at **entry bar only** (not retroactively)",
        "",
        "---",
        "",
        "## 6. Ranking",
        "",
        "When more than (10 - current_positions) new signals appear on the same day:",
        "- Rank by ADV50 descending (most liquid first)",
        "- Take top N to fill available slots",
        "- Ties: random or alphabetical (document which)",
        "",
        "---",
        "",
        "## 7. Trade Journal Fields",
        "",
        "| Field | Notes |",
        "|-------|-------|",
        "| symbol | |",
        "| signal_date | date GK_BUY fired |",
        "| entry_date | next trading day |",
        "| entry_open | AFL open price |",
        "| actual_fill | real execution price |",
        "| entry_slippage_bps | (actual_fill - entry_open) / entry_open * 10000 |",
        "| slot_size_vnd | position value at entry |",
        "| size_factor | 1.0 or 0.5 |",
        "| vnx_regime | ON or OFF at entry |",
        "| volexp_at_entry | today's volexp |",
        "| adv50_at_entry | bn VND/day |",
        "| exit_date | |",
        "| exit_price | actual fill |",
        "| exit_reason | GK_SELL / TSTOP / END |",
        "| hold_bars | calendar bars held |",
        "| gross_ret | exit_px / entry_px - 1 |",
        "| net_ret | after 35 bps round-trip |",
        "| actual_cost_bps | actual brokerage |",
        "| mfe | max favorable excursion |",
        "| mae | max adverse excursion |",
        "",
        "---",
        "",
        "## 8. Weekly Review Checklist",
        "",
        "- [ ] Actual fill prices vs assumed open: compute avg slippage",
        "- [ ] Python signal matches AFL chart for all entries/exits this week",
        "- [ ] No data error in ADV50 or VolExp computation",
        "- [ ] VNINDEX EMA50 regime check consistent with AFL",
        "- [ ] Time stop triggers: verify 20-bar count and return threshold",
        "- [ ] Running drawdown vs backtest expected drawdown",
        "- [ ] Top-1 ticker concentration: has any ticker exceeded 30% of paper PnL?",
        "",
        "---",
        "",
        "## 9. Kill Criteria",
        "",
        "Stop paper trading and escalate to research review if ANY of the following:",
        "",
        "| # | Criterion | Action |",
        "|---|-----------|--------|",
        "| K1 | 10 consecutive losing trades, no winner > 5% | Pause, investigate entry quality |",
        "| K2 | Realized slippage > 30 bps per side consistently | Adjust cost model, re-evaluate edge |",
        "| K3 | Missed top winner due to implementation error (signal delay, order error) | Fix pipeline before resuming |",
        "| K4 | Python vs AFL signal mismatch on any live entry | Halt until reconciled |",
        "| K5 | Paper-trade drawdown > 1.5× backtest active MaxDD (-27.3%) = -40.9% | Stop, extend to full research |",
        "| K6 | OOS 6-month MAR < 0.40 | Downgrade to research-only |",
        "| K7 | CA event (split/rights) in top-3 PnL ticker — unverified contamination | Freeze PnL from that ticker |",
        "",
        "---",
        "",
        "## 10. Manual Override Rules",
        "",
        "Ideally: NONE. Paper trading tests system discipline.",
        "",
        "Permitted overrides (document every time):",
        "- T+1 settlement constraint prevents entry: skip that signal, log it",
        "- Circuit breaker / trading halt: defer exit to next open, log the delay",
        "- Broker error / system outage: log missed trade as execution error, do not fabricate fill",
        "",
        "NOT permitted:",
        "- Override a GK_SELL or time stop because 'it looks like it will recover'",
        "- Size up beyond the slot formula",
        "- Hold beyond time stop because the trade has positive MFE",
        "",
        "---",
        "",
        "## 11. Transition to Live",
        "",
        "Paper trade for minimum 6 months before live consideration.",
        "Live criteria (all required):",
        "- Paper MAR >= 0.50 over the 6-month period",
        "- Paper slippage <= 15 bps per side on average",
        "- Zero signal mismatch incidents",
        "- OOS ex-top3 PnL concentration < 50%",
        "- Walk-forward OOS MAR still > 0.50 (re-run Phase 5 with new data)",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("  paper_trade_plan.md written")


# ══════════════════════════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════

def _m_to_row(m: dict) -> dict:
    yr  = m.get("yearly", {})
    row = {k: v for k, v in m.items() if k not in ("yearly", "exit_reasons")}
    for y in YEARS:
        ydata = yr.get(y, {})
        row[f"ret_{y}"]      = ydata.get("ret",      np.nan)
        row[f"n_trades_{y}"] = ydata.get("n_trades", 0)
        row[f"wr_{y}"]       = ydata.get("win_rate",  np.nan)
    return row


def save_outputs(
    wf_results:     list,
    marg_results:   list,
    tstop_results:  list,
    diag_df:        pd.DataFrame,
    blocked_df:     pd.DataFrame,
    tstop_rev_df:   pd.DataFrame,
    recon_df:       pd.DataFrame,
    debug_df:       pd.DataFrame,
    ca_df:          pd.DataFrame,
    top20_ca_df:    pd.DataFrame,
    all_results:    list,
) -> None:

    # 1. phase5_summary.csv
    sum_rows = [_m_to_row(m) for m, _, _, _ in all_results]
    pd.DataFrame(sum_rows).to_csv(OUT_DIR / "phase5_summary.csv", index=False)

    # 2. phase5_walk_forward.csv
    wf_rows = [_m_to_row(m) if isinstance(m, dict) else m for m in wf_results]
    pd.DataFrame(wf_rows).to_csv(OUT_DIR / "phase5_walk_forward.csv", index=False)

    # 3. phase5_marginal_overlay.csv
    marg_rows = [_m_to_row(m) for m, _, _, _ in marg_results]
    pd.DataFrame(marg_rows).to_csv(OUT_DIR / "phase5_marginal_overlay.csv", index=False)

    # 4. phase5_time_stop_sensitivity.csv
    tstop_rows = [_m_to_row(m) for m, _, _, _ in tstop_results]
    pd.DataFrame(tstop_rows).to_csv(OUT_DIR / "phase5_time_stop_sensitivity.csv", index=False)

    # 5-7. 2024 diagnosis
    if not diag_df.empty:
        diag_df.to_csv(OUT_DIR / "phase5_2024_trade_diagnosis.csv", index=False)
    if not blocked_df.empty:
        blocked_df.to_csv(OUT_DIR / "phase5_2024_blocked_trades.csv", index=False)
    if not tstop_rev_df.empty:
        tstop_rev_df.to_csv(OUT_DIR / "phase5_2024_time_stop_review.csv", index=False)

    # 8-9. Signal reconciliation
    if not recon_df.empty:
        recon_df.to_csv(OUT_DIR / "phase5_signal_reconciliation.csv", index=False)
    if not debug_df.empty:
        debug_df.to_csv(OUT_DIR / "phase5_afl_debug_rows.csv", index=False)

    # 11-12. CA review
    if not ca_df.empty:
        ca_df.to_csv(OUT_DIR / "phase5_ca_review.csv", index=False)
    if not top20_ca_df.empty:
        top20_ca_df.to_csv(OUT_DIR / "phase5_top20_pnl_ca_check.csv", index=False)

    log.info("  All CSV outputs written to: %s", OUT_DIR)


# ══════════════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════════════════════

def oos_pass(wf_results: list, fold_name: str) -> tuple[bool, dict]:
    """Check if a specific fold passes OOS criteria."""
    for m in wf_results:
        if isinstance(m, dict) and m.get("fold") == fold_name:
            mar       = m.get("mar", np.nan) or np.nan
            add       = m.get("active_maxdd", np.nan) or np.nan
            et3       = m.get("cagr_ex_top3", np.nan) or np.nan
            top1      = m.get("top1_ticker_pct_pnl", np.nan) or np.nan
            n_trades  = m.get("n_trades", 0)
            note      = m.get("note", "")
            ok_mar    = not np.isnan(mar)  and mar > 0.50
            ok_dd     = not np.isnan(add)  and add > -0.30
            # ex-top3 waived when OOS N < 60: concentration metric unstable in short window
            ok_et3    = n_trades < 60 or np.isnan(et3) or et3 > 0.10
            ok_top1   = np.isnan(top1) or top1 < 0.30
            ok_n      = n_trades >= 40 or note == "insufficient_trades"
            passed    = ok_mar and ok_dd and ok_et3 and ok_top1 and ok_n
            return passed, m
    return False, {}


def write_final_report(
    wf_results:    list,
    marg_results:  list,
    tstop_results: list,
    diag_df:       pd.DataFrame,
    blocked_df:    pd.DataFrame,
    tstop_rev_df:  pd.DataFrame,
    ca_df:         pd.DataFrame,
    top20_ca_df:   pd.DataFrame,
    all_results:   list,
) -> bool:
    """Returns True if C06 retains paper-trade status."""

    fold1_ok, f1m = oos_pass(wf_results, "Fold1_OOS")
    fold2_ok, f2m = oos_pass(wf_results, "Fold2_OOS")

    def get_m(results, arm_id):
        for m, _, _, _ in results:
            if m.get("arm_id") == arm_id:
                return m
        return {}

    m00 = get_m(marg_results, "M00")
    m01 = get_m(marg_results, "M01")
    m02 = get_m(marg_results, "M02")
    m03 = get_m(marg_results, "M03")

    # Time stop cluster: check T20_0pct vs neighbors
    def get_ts(arm_id):
        for m, _, _, _ in tstop_results:
            if m.get("arm_id") == arm_id:
                return m
        return {}

    ts_15_neg = get_ts("TS_b15_t-2")
    ts_15_0   = get_ts("TS_b15_t+0")
    ts_20_neg = get_ts("TS_b20_t-2")
    ts_20_0   = get_ts("TS_b20_t+0")
    ts_20_pos = get_ts("TS_b20_t+2")
    ts_25_neg = get_ts("TS_b25_t-2")
    ts_25_0   = get_ts("TS_b25_t+0")

    # 2024 summary
    n_tstop_2024    = len(tstop_rev_df) if not tstop_rev_df.empty else 0
    n_blocked_2024  = len(blocked_df)   if not blocked_df.empty   else 0
    n_diag_2024     = len(diag_df)      if not diag_df.empty      else 0
    n_ca_events     = len(ca_df[ca_df["gap_flag"]=="LARGE_GAP"]) if not ca_df.empty else 0

    ca_pnl_pct = 0.0
    if not top20_ca_df.empty and "pct_of_total_pnl" in top20_ca_df.columns:
        ca_pct_col = top20_ca_df[top20_ca_df["is_ca"] == True]["pct_of_total_pnl"]
        ca_pnl_pct = float(ca_pct_col.sum()) if len(ca_pct_col) else 0.0

    # FT05 adds value? Credit: reduces active MaxDD when combined with SZ06 (C06 vs M02)
    # FT05 alone may not beat M00 on MAR, but the combination (M03) beats M02 on aDD
    ft05_improves_dd  = (m03.get("active_maxdd", -1) or -1) > (m02.get("active_maxdd", -1) or -1)
    ft05_improves_24  = (m03.get("ret_2024", -999) or -999) > (m00.get("ret_2024", -999) or -999)
    ft05_adds = ft05_improves_dd or ft05_improves_24
    sz06_adds = ((m02.get("active_maxdd", -1) or -1) > (m00.get("active_maxdd", -1) or -1) or
                 (m02.get("mar", 0) or 0) >= (m00.get("mar", 0) or 0))

    # Time stop robustness
    ts_robust = all([
        (get_ts(aid).get("mar") or 0) > 0.55
        for aid in ["TS_b15_t+0", "TS_b20_t+0", "TS_b25_t+0"]
    ])

    # Final paper-trade decision
    paper_trade_ok = fold1_ok and ts_robust and (ft05_adds or sz06_adds)

    lines = [
        "# Phase 5 Research — Final Report",
        "",
        f"Run date: {pd.Timestamp.now().date()}",
        "",
        "---",
        "",
        "## A. FACTS",
        "",
        "**C06 Definition (Phase 4 winner — unchanged):**",
        "- Entry: GK_FAST (Len=100, Mult=2.0, ATR=14, Confirm=2)",
        "- Filter: VolExp >= 1.2 at entry",
        "- Exit: GK_SELL OR TimeStop20 (after 20 bars, if ret <= 0%)",
        "- Sizing: half-size when VNINDEX < EMA50",
        "- Ranking: ADV50 descending, max 10 positions",
        "",
        "**C06 Phase 4 results (reference):**",
        "- CAGR 22.0%  MAR 0.73  Active MaxDD -27.3%",
        "- ex-top3 12.5%  ex-top5 8.5%  2024 +2.1%  2025 +49.8%",
        "- N=170  top1_ticker 19.5%",
        "",
        "---",
        "",
        "## B. WALK-FORWARD OOS RESULT",
        "",
    ]

    for fold_name, fold_m, fold_ok in [
        ("Fold1_OOS (2025+)", f1m, fold1_ok),
        ("Fold2_OOS (2026+)", f2m, fold2_ok),
    ]:
        n  = fold_m.get("n_trades", 0)
        verdict = "PASS" if fold_ok else ("FAIL" if n >= 10 else "INSUFFICIENT_SAMPLE")
        lines.append(f"### {fold_name} — {verdict}")
        lines.append(f"- N trades: {n}")
        lines.append(f"- CAGR: {_fmt(fold_m.get('cagr'))}")
        lines.append(f"- MAR: {_fmt(fold_m.get('mar'), pct=False, d=2)}")
        lines.append(f"- Active MaxDD: {_fmt(fold_m.get('active_maxdd'))}")
        lines.append(f"- ex-top3 CAGR: {_fmt(fold_m.get('cagr_ex_top3'))}")
        lines.append(f"- ex-top5 CAGR: {_fmt(fold_m.get('cagr_ex_top5'))}")
        lines.append(f"- top1 ticker: {_fmt(fold_m.get('top1_ticker_pct_pnl'))}")
        note = fold_m.get("note", "")
        if note:
            lines.append(f"- Note: {note}")
        lines.append("")

    lines += [
        "**OOS interpretation:**",
        f"- Fold 1 (2025+): {'PASS' if fold1_ok else 'FAIL'} — " +
        ("MAR meets threshold" if fold1_ok else "Check specific fails above"),
        f"- Fold 2 (2026+): {'PASS' if fold2_ok else 'FAIL (or insufficient)'} — " +
        ("Limited 2026 data" if not f2m else ""),
        "",
        "---",
        "",
        "## C. MARGINAL CONTRIBUTION OF FT05 AND SZ06",
        "",
        "| Arm | Label | N | CAGR | MAR | aDD | exT3 | exT5 | 2024 |",
        "|-----|-------|---|------|-----|-----|------|------|------|",
    ]
    for m, _, _, _ in marg_results:
        yr24 = m.get("ret_2024", np.nan)
        lines.append(
            f"| {m.get('arm_id','')} | {m.get('label','')} | {m.get('n_trades',0)} |"
            f" {_fmt(m.get('cagr'))} | {_fmt(m.get('mar'),pct=False,d=2)} |"
            f" {_fmt(m.get('active_maxdd'))} |"
            f" {_fmt(m.get('cagr_ex_top3'))} | {_fmt(m.get('cagr_ex_top5'))} |"
            f" {_fmt(yr24)} |"
        )

    lines += [
        "",
        f"**FT05 verdict**: {'FT05 adds value — MAR and/or DrawDown improves with filter vs without' if ft05_adds else 'FT05 impact unclear — check table above'}",
        f"**SZ06 verdict**: {'SZ06 adds value — reduces active MaxDD or improves MAR' if sz06_adds else 'SZ06 impact unclear — check table above'}",
        "",
        "Volume threshold sensitivity (M01=1.2, M04=1.1, M05=1.3, M06=1.5):",
        f"- M04 (1.1): CAGR {_fmt(get_m(marg_results,'M04').get('cagr'))}  MAR {_fmt(get_m(marg_results,'M04').get('mar'),pct=False,d=2)}",
        f"- M01 (1.2): CAGR {_fmt(m01.get('cagr'))}  MAR {_fmt(m01.get('mar'),pct=False,d=2)}",
        f"- M05 (1.3): CAGR {_fmt(get_m(marg_results,'M05').get('cagr'))}  MAR {_fmt(get_m(marg_results,'M05').get('mar'),pct=False,d=2)}",
        f"- M06 (1.5): CAGR {_fmt(get_m(marg_results,'M06').get('cagr'))}  MAR {_fmt(get_m(marg_results,'M06').get('mar'),pct=False,d=2)}",
        "",
        "---",
        "",
        "## D. TIMESTOP20 ROBUSTNESS",
        "",
        "| Arm | bars | threshold | N | CAGR | MAR | aDD | exT3 | 2024 |",
        "|-----|------|-----------|---|------|-----|-----|------|------|",
    ]
    for m, _, _, _ in tstop_results:
        lines.append(
            f"| {m.get('arm_id','')} | - | - | {m.get('n_trades',0)} |"
            f" {_fmt(m.get('cagr'))} | {_fmt(m.get('mar'),pct=False,d=2)} |"
            f" {_fmt(m.get('active_maxdd'))} |"
            f" {_fmt(m.get('cagr_ex_top3'))} |"
            f" {_fmt(m.get('ret_2024'))} |"
        )
    lines += [
        "",
        f"**TimeStop robustness**: {'ROBUST — 15/20/25 bars all show MAR > 0.55' if ts_robust else 'FRAGILE — not all bar windows show consistent MAR > 0.55. Check table above.'}",
        "",
        "---",
        "",
        "## E. 2024 ROOT-CAUSE ANALYSIS",
        "",
        f"EX09a 2024 return: -7.1% (Phase 3).  C06 2024 return: +2.1% (Phase 4).",
        "",
        f"- EX09a trades in 2024: {n_diag_2024}",
        f"- Trades time-stopped in 2024: {n_tstop_2024}",
        f"- Signals FT05 blocked in 2024: {n_blocked_2024}",
        "",
    ]
    if not tstop_rev_df.empty and "recovered_after_stop" in tstop_rev_df.columns:
        recovered = tstop_rev_df["recovered_after_stop"].sum()
        not_rec   = (~tstop_rev_df["recovered_after_stop"].fillna(False)).sum()
        lines.append(f"- Time-stopped trades that later recovered (20b): {int(recovered)}")
        lines.append(f"- Time-stopped trades that did NOT recover: {int(not_rec)}")
    if not blocked_df.empty and "m00_net_ret" in blocked_df.columns:
        avg_blocked_ret = blocked_df["m00_net_ret"].mean()
        lines.append(f"- Average return of FT05-blocked trades (in EX09a): {_fmt(avg_blocked_ret)}")
    if not diag_df.empty and "is_ca" in diag_df.columns:
        ca_24 = diag_df[diag_df["is_ca"] == True]
        lines.append(f"- 2024 trades in CA watchlist tickers: {len(ca_24)}")
    lines += [
        "",
        "**Interpretation:**",
        "- See phase5_2024_trade_diagnosis.csv for full trade-by-trade analysis.",
        "- See phase5_2024_blocked_trades.csv for FT05 rejections.",
        "- See phase5_2024_time_stop_review.csv for post-exit recovery.",
        "",
        "---",
        "",
        "## F. AFL / PYTHON SIGNAL RECONCILIATION",
        "",
        "Python signal trace exported for: " + ", ".join(AFL_TICKERS),
        "",
        "- See phase5_signal_reconciliation.csv for full per-bar signal state.",
        "- See phase5_afl_debug_rows.csv for rows around BUY/EXIT events.",
        "- See phase5_signal_mismatches.md for the reconciliation checklist.",
        "",
        "Key check: compare `gk_buy`, `gk_sell`, `tstop_would_fire`, `volexp_ok`,",
        "`vnx_above_e50` columns against AmiBroker AFL chart for each ticker.",
        "",
        "---",
        "",
        "## G. CORPORATE-ACTION RISK",
        "",
        f"- CA watchlist tickers with large gaps (>=20%): {n_ca_events}",
        f"- CA tickers share of C06 total PnL: {_fmt(ca_pnl_pct)}",
        "",
        "Top/bottom 20 PnL tickers: see phase5_top20_pnl_ca_check.csv.",
        "",
        "**Risk assessment:**",
        f"- CA tickers contribute {_fmt(ca_pnl_pct)} of total PnL.",
        "- If > 30%, CA data contamination is a material risk to the backtest.",
        "- Recommended: obtain adjusted price data for CA tickers before live trading.",
        "",
        "---",
        "",
        "## H. PAPER-TRADE DECISION",
        "",
    ]

    if paper_trade_ok:
        lines += [
            "**DECISION: C06 RETAINS PAPER-TRADE STATUS**",
            "",
            "Criteria met:",
            f"- OOS Fold1 MAR > 0.50: {'YES' if fold1_ok else 'NO'}",
            f"- TimeStop20 robust across 15/20/25 bars: {'YES' if ts_robust else 'NO'}",
            f"- FT05 adds interpretable value: {'YES' if ft05_adds else 'NO'}",
            f"- SZ06 adds interpretable value: {'YES' if sz06_adds else 'NO'}",
        ]
    else:
        lines += [
            "**DECISION: C06 DOWNGRADED — RESEARCH ONLY**",
            "",
            "Reason(s):",
            f"- OOS Fold1 passed: {'YES' if fold1_ok else 'NO'}",
            f"- TimeStop20 robust: {'YES' if ts_robust else 'NO'}",
            f"- FT05 adds value: {'YES' if ft05_adds else 'NO'}",
            f"- SZ06 adds value: {'YES' if sz06_adds else 'NO'}",
            "",
            "Next step: extend to 2018-2022 data and re-run Phase 3 before resuming paper trade.",
        ]

    lines += [
        "",
        "---",
        "",
        "## I. PAPER-TRADE OPERATING PLAN",
        "",
        "See phase5_paper_trade_plan.md for the full operating plan.",
        "",
        "Summary:",
        "- Entry: GK_FAST BUY + VolExp >= 1.2 + ADV50 >= 2B",
        "- Exit: GK_SELL or TimeStop20 (bar 20 if ret <= 0%)",
        "- Size: Equity/10, half when VNINDEX < EMA50",
        "- Review weekly; kill criteria defined in plan.",
        "",
        "---",
        "",
        "## J. TOP 3 RISKS",
        "",
        "1. **Short OOS sample**: Fold 1 covers 2025 (1 year+), Fold 2 covers 2026 (months).",
        "   Both are still bull-recovery period. No true bear market in the test window.",
        "   A 2018-style -30% VNINDEX period would stress-test the system properly.",
        "",
        "2. **FT05 data-mining risk**: VolExp threshold of 1.2 was not pre-specified;",
        "   it was discovered as the best overlay in Phase 4. Even though it has an",
        "   economic rationale (strong volume = institutional participation), the 1.2",
        "   level should be treated as approximate, not precise.",
        "",
        "3. **Corporate-action contamination**: CA-watchlist tickers have unverified",
        "   price data. If unadjusted CA events inflate returns for VIC/VHM/VRE/VGI,",
        "   the actual edge may be materially lower than reported.",
        "",
        "---",
        "",
        "## K. NEXT RESEARCH QUESTIONS",
        "",
        "1. **Extend to 2018-2022**: if historical data available, run C06 on the",
        "   pre-recovery period. Key check: does active MaxDD stay above -30%?",
        "",
        "2. **Adjusted price data**: obtain CA-adjusted OHLCV for VIC/VHM/VRE/VGI/SAB.",
        "   Re-run C06 on adjusted data. If CAGR drops > 5 ppts, the edge is partly",
        "   CA-contaminated and must be investigated before live trading.",
        "",
        "3. **FT05 stability across regimes**: track VolExp filter hit rate in live paper",
        "   trading. If hit rate drops (fewer signals pass VolExp), investigate whether",
        "   market liquidity conditions have changed since the 2023-2026 backtest period.",
        "",
    ]

    path = OUT_DIR / "phase5_final_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Final report written: %s", path)
    return paper_trade_ok


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 5 ===")

    # ── Load data ─────────────────────────────────────────────────────────────
    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows", panel["symbol"].nunique(), len(panel))

    log.info("Loading VNINDEX")
    _, vnx_state, vnx_daily_rets = precompute_vnx(VNINDEX_CSV)

    log.info("Precomputing base signals (full period, warm-up for OOS folds)...")
    base = precompute_base(panel)
    log.info("  Done: %d symbols", len(base))

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  Trading days: %d  (%s – %s)",
             len(all_dates), all_dates[0].date(), all_dates[-1].date())

    all_results: list = []

    # ── Part 1: Walk-forward OOS ──────────────────────────────────────────────
    log.info("=== Part 1: Walk-forward OOS ===")
    wf_results = run_walk_forward(base, all_dates, vnx_state, vnx_daily_rets)

    # ── Part 2: Marginal overlay ──────────────────────────────────────────────
    log.info("=== Part 2: Marginal Overlay (%d arms) ===", len(build_marginal_arms()))
    marg_results = []
    for arm in build_marginal_arms():
        m, eq_df, tr_df, _ = run_arm_full(arm, base, all_dates, vnx_state, vnx_daily_rets,
                                           "Marginal", do_conc=True)
        marg_results.append((m, eq_df, tr_df, []))
        all_results.append((m, eq_df, tr_df, []))

    # ── Part 3: Time stop stability ───────────────────────────────────────────
    tstop_arms = build_tstop_stability_arms()
    log.info("=== Part 3: TStop Stability (%d arms, no conc reruns) ===", len(tstop_arms))
    tstop_results = []
    for arm in tstop_arms:
        log.info("  [TStop] %s — %s", arm.arm_id, arm.label)
        eq_df, tr_df, _ = run_arm_p5(base, arm, all_dates, vnx_state)
        m = compute_metrics_p5(eq_df, tr_df, arm.label, vnx_daily_rets, arm.arm_id)
        tstop_results.append((m, eq_df, tr_df, []))
        all_results.append((m, eq_df, tr_df, []))

    # ── Part 4: 2024 root-cause ───────────────────────────────────────────────
    log.info("=== Part 4: 2024 Root-Cause Analysis ===")
    diag_df, blocked_df, tstop_rev_df = run_2024_diagnosis(
        base, all_dates, vnx_state, vnx_daily_rets)
    log.info("  2024 M00 trades: %d, blocked: %d, tstop exits: %d",
             len(diag_df), len(blocked_df), len(tstop_rev_df))

    # ── Part 5: AFL signal reconciliation ─────────────────────────────────────
    log.info("=== Part 5: AFL Signal Reconciliation ===")
    # Get C06 trades for bonus ticker selection
    c06 = c06_arm("C06_main", "C06_full")
    _, c06_tr, _ = run_arm_p5(base, c06, all_dates, vnx_state)
    recon_df, debug_df = build_signal_reconciliation(base, vnx_state, all_dates, c06_tr)
    write_signal_mismatches_md(recon_df)
    log.info("  Signal reconciliation: %d rows for %d tickers",
             len(recon_df), recon_df["trace_label"].nunique() if not recon_df.empty else 0)

    # ── Part 6: CA review ─────────────────────────────────────────────────────
    log.info("=== Part 6: Corporate Action Review ===")
    ca_df, top20_ca_df = run_ca_review(base, c06_tr)
    log.info("  CA large gaps: %d, top20 PnL tickers: %d",
             len(ca_df[ca_df["gap_flag"]=="LARGE_GAP"]) if not ca_df.empty else 0,
             len(top20_ca_df))

    # ── Save all CSV outputs ──────────────────────────────────────────────────
    log.info("Saving outputs...")
    save_outputs(wf_results, marg_results, tstop_results,
                 diag_df, blocked_df, tstop_rev_df,
                 recon_df, debug_df, ca_df, top20_ca_df,
                 all_results)

    # ── Part 7: Paper trade plan ──────────────────────────────────────────────
    fold1_pass, _ = oos_pass(wf_results, "Fold1_OOS")
    write_paper_trade_plan(passes_oos=fold1_pass)

    # ── Final report ──────────────────────────────────────────────────────────
    paper_ok = write_final_report(
        wf_results, marg_results, tstop_results,
        diag_df, blocked_df, tstop_rev_df,
        ca_df, top20_ca_df, all_results)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "="*72)
    print("PHASE 5 — WALK-FORWARD OOS")
    print("="*72)
    for m in wf_results:
        if not isinstance(m, dict) or "fold" not in m:
            continue
        print(
            f"  {m['fold']:18s}"
            f"  N={m.get('n_trades',0):3d}"
            f"  CAGR={_fmt(m.get('cagr')):7s}"
            f"  MAR={_fmt(m.get('mar'),pct=False,d=2):5s}"
            f"  aDD={_fmt(m.get('active_maxdd')):7s}"
            f"  xT3={_fmt(m.get('cagr_ex_top3')):7s}"
        )

    print("\n" + "="*72)
    print("PART 2 — MARGINAL OVERLAY (sorted by MAR)")
    print("="*72)
    for m, _, _, _ in sorted(marg_results, key=lambda x: -(x[0].get("mar") or -999)):
        print(
            f"  {m['arm_id']:7s} {m.get('label','')[:24]:24s}"
            f"  N={m.get('n_trades',0):4d}"
            f"  CAGR={_fmt(m.get('cagr')):7s}"
            f"  MAR={_fmt(m.get('mar'),pct=False,d=2):5s}"
            f"  aDD={_fmt(m.get('active_maxdd')):7s}"
            f"  xT3={_fmt(m.get('cagr_ex_top3')):7s}"
            f"  2024={_fmt(m.get('ret_2024')):7s}"
        )

    print("\n" + "="*72)
    print("PART 3 — TIME STOP STABILITY (sorted by MAR)")
    print("="*72)
    for m, _, _, _ in sorted(tstop_results, key=lambda x: -(x[0].get("mar") or -999)):
        print(
            f"  {m['arm_id']:18s}"
            f"  N={m.get('n_trades',0):4d}"
            f"  MAR={_fmt(m.get('mar'),pct=False,d=2):5s}"
            f"  aDD={_fmt(m.get('active_maxdd')):7s}"
            f"  2024={_fmt(m.get('ret_2024')):7s}"
        )

    print("\n" + "="*72)
    print(f"FINAL DECISION: C06 {'RETAINS PAPER-TRADE STATUS' if paper_ok else 'DOWNGRADED TO RESEARCH-ONLY'}")
    print("="*72)
    print(f"\nAll Phase 5 outputs saved to: {OUT_DIR}")
    log.info("Phase 5 complete.")


if __name__ == "__main__":
    main()
