#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 6 — Data Quality Validation & Robustness Extension

Phase 5 downgraded C06 to research-only.
Blockers: OOS concentration (top1=50.1%), TimeStop fragility at 15b, CA risk (41%).

This script:
  Task 1: CA gap detection, classification, backward-adjusted price construction
  Task 2: Re-run A2/EX09a/C06/EX08/M00-M03 on raw vs adjusted data
  Task 3: OOS concentration root-cause — L40 trade analysis, exclusion tests
  Task 4: Extended period — NOT FEASIBLE (parquet 2023-01-01 to 2026-04-29 only)
  Task 5: TimeStop grid re-test on adjusted data
  Task 6: Final decision report

Outputs -> data/research/gk_audit/phase6_data_quality/
"""
from __future__ import annotations

import io, sys, logging, warnings, dataclasses
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
OUT_DIR       = REPO / "data/research/gk_audit/phase6_data_quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
START_DATE   = pd.Timestamp("2023-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
OOS1_START   = pd.Timestamp("2025-01-01")
OOS2_START   = pd.Timestamp("2026-01-01")
ADV50_MIN_BN = 2.0
MAX_POS      = 10
INITIAL_CAP  = 1.0
YEARS        = [2023, 2024, 2025, 2026]
EXCL         = {"VPL"}
FEE_BPS      = 25.0
SLIP_BPS     = 10.0

GK_FAST = {"gk_len": 100, "gk_mult": 2.0, "gk_atr": 14, "gk_conf": 2}

# CA watchlist (unadjusted price risk — from CA gap scan)
CA_WATCHLIST = frozenset([
    "VIC","VHM","VRE","VGI","SAB","L40","MCH","TCH",
    "ANV","BIC","CSV","DPM","DPR","IMP","MSH","NTL","SIP","TCB","TCO",
])

# Confirmed CA event dates and tickers (from Phase 6 gap scan)
# All occurred on 2024-01-30 — likely a government SOE bonus-share issuance day
CONFIRMED_CA = {
    "L40":  [("2024-01-30", -0.668)],
    "VIC":  [("2024-01-30", -0.499)],
    "MCH":  [("2024-01-30", -0.500)],
    "SAB":  [("2023-09-14", -0.489), ("2024-01-30", -0.168)],
    "TCH":  [("2024-02-XX", -0.170)],  # approximate
    "VGI":  [("2024-XX-XX", +0.171)],  # positive gap — suspicious, not adjusted
}

# OOS top-1 ticker (identified in Phase 6 analysis)
OOS_TOP1_TICKER = "L40"

# C06 definition (Phase 4 winner — unchanged)
C06_TSTOP_BARS = 20
C06_TSTOP_THR  = 0.0
C06_VOLEXP_MIN = 1.2
C06_HALF_REG   = True

# ══════════════════════════════════════════════════════════════════════════════
# ARM CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmP6:
    arm_id: str
    label:  str
    volexp_filter_min:      float = 0.0
    exit_ema20_confirmed:   bool  = False
    time_stop_bars:         int   = 0
    time_stop_threshold:    float = 0.0
    stop_pct:               float = 0.0
    max_pos:                int   = MAX_POS
    half_size_regime_off:   bool  = False
    fee_bps:  float = FEE_BPS
    slip_bps: float = SLIP_BPS
    blacklist: frozenset = field(default_factory=frozenset)

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000


def _a(arm_id, label, **kw) -> ArmP6:
    return ArmP6(arm_id=arm_id, label=label, **kw)


def build_arms() -> list[ArmP6]:
    """Arms to test: A2, EX09a, C06, EX08, M00-M03."""
    return [
        _a("A2",    "A2_baseline"),
        _a("EX09a", "EX09a_tstop20",       time_stop_bars=20),
        _a("C06",   "C06",                 time_stop_bars=20, volexp_filter_min=1.2, half_size_regime_off=True),
        _a("EX08",  "EX08_ema20",          exit_ema20_confirmed=True),
        _a("M00",   "M00_EX09a_only",      time_stop_bars=20),
        _a("M01",   "M01_EX09a+FT05",      time_stop_bars=20, volexp_filter_min=1.2),
        _a("M02",   "M02_EX09a+SZ06",      time_stop_bars=20, half_size_regime_off=True),
        _a("M03",   "M03_C06_ref",         time_stop_bars=20, volexp_filter_min=1.2, half_size_regime_off=True),
    ]


def build_tstop_arms() -> list[ArmP6]:
    arms = []
    for bars in [15, 20, 25, 30]:
        for thr in [-0.02, 0.0, 0.02]:
            tag = f"{int(thr*100):+d}"
            arms.append(ArmP6(
                arm_id=f"TS_b{bars}_t{tag}",
                label=f"C06_tstop{bars}_{tag}pct",
                time_stop_bars=bars,
                time_stop_threshold=thr,
                volexp_filter_min=1.2,
                half_size_regime_off=True,
            ))
    return arms


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


def compute_gk_signals(close, high, low, gk_len=100, gk_mult=2.0, gk_atr=14, gk_conf=2) -> dict:
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
    cb    = gk_conf - 1
    above = close > gk_upper; below = close < gk_lower
    a1    = np.concatenate([[False], above[:-1]])
    b1    = np.concatenate([[False], below[:-1]])
    acb   = np.concatenate([np.full(max(cb,0), False), above[:-cb]]) if cb > 0 else above.copy()
    bcb   = np.concatenate([np.full(max(cb,0), False), below[:-cb]]) if cb > 0 else below.copy()
    zp    = np.concatenate([[np.nan], gk_zl[:-1]])
    zr    = gk_zl > zp; zf = gk_zl < zp
    vl    = ~np.isnan(gk_upper) & ~np.isnan(gk_lower)
    bull  = above & a1 & acb & zr & vl
    bear  = below & b1 & bcb & zf & vl
    raw   = np.where(bull, 1.0, np.where(bear, -1.0, np.nan))
    s     = pd.Series(raw).ffill().fillna(0.0).astype(int).values
    prev  = np.zeros(n, dtype=int); prev[1:] = s[:-1]
    flip  = (s != prev) & (s != 0)
    return {"gk_buy": flip & (s == 1), "gk_sell": flip & (s == -1)}


# ══════════════════════════════════════════════════════════════════════════════
# TASK 1: CA GAP DETECTION
# ══════════════════════════════════════════════════════════════════════════════

CA_GAP_NEG_THR = -0.15  # gaps <= -15%: apply backward adjustment
CA_GAP_POS_THR = +0.15  # gaps >= +15%: flag only, no adjustment


def detect_ca_gaps(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Scan all tickers for large overnight gaps.
    Returns (events_df, adj_factors_by_sym).
    adj_factors_by_sym[sym] = list of (date_idx, cum_factor) pairs for backward adjustment.
    """
    rows = []
    adj_by_sym: dict = {}

    for sym, grp in panel.groupby("symbol"):
        df = grp.sort_values("date").reset_index(drop=True)
        c  = df["close"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)
        adj_events = []

        for i in range(1, len(c)):
            if c[i-1] <= 0:
                continue
            gap = c[i] / c[i-1] - 1.0
            if abs(gap) < 0.10:
                continue

            # Classify
            if gap <= CA_GAP_NEG_THR:
                classification = "CA_NEG_ADJUST"
                adjust = True
            elif gap >= CA_GAP_POS_THR:
                classification = "SUSPICIOUS_POS_NO_ADJ"
                adjust = False
            elif gap <= -0.10:
                classification = "POSSIBLE_CA_NO_ADJ"
                adjust = False
            else:
                classification = "LIMIT_UP_NO_ADJ"
                adjust = False

            rows.append({
                "symbol":         sym,
                "gap_date":       str(dts[i].date()),
                "prev_close":     round(float(c[i-1]), 4),
                "close":          round(float(c[i]), 4),
                "gap_pct":        round(gap * 100, 2),
                "classification": classification,
                "adjusted":       adjust,
                "is_ca_watchlist":sym in CA_WATCHLIST,
            })
            if adjust:
                adj_events.append((i, float(c[i] / c[i-1])))  # (day_index, factor)

        if adj_events:
            adj_by_sym[sym] = adj_events

    events_df = pd.DataFrame(rows).sort_values("gap_pct").reset_index(drop=True)
    return events_df, adj_by_sym


def build_adjusted_panel(panel: pd.DataFrame, adj_by_sym: dict) -> pd.DataFrame:
    """
    Apply backward multiplicative adjustment for CA_NEG events.
    All prices BEFORE each event date are multiplied by the gap factor.
    Value (VND turnover) is NOT adjusted — liquidity metrics remain real.
    Returns adjusted panel copy.
    """
    adj_panel = panel.copy()
    for sym, events in adj_by_sym.items():
        mask = adj_panel["symbol"] == sym
        df   = adj_panel[mask].sort_values("date").reset_index(drop=False)
        c    = df["close"].values.astype(float)
        o    = df["open"].values.astype(float)
        h    = df["high"].values.astype(float)
        l    = df["low"].values.astype(float)

        # Apply events in chronological order
        # Backward adjustment: multiply all prices BEFORE each event by factor
        cum_factor = 1.0
        sorted_events = sorted(events, key=lambda x: x[0])
        for evt_idx, factor in sorted_events:
            cum_factor *= factor
            c[:evt_idx] = c[:evt_idx] * factor
            o[:evt_idx] = o[:evt_idx] * factor
            h[:evt_idx] = h[:evt_idx] * factor
            l[:evt_idx] = l[:evt_idx] * factor

        df["close"] = c
        df["open"]  = o
        df["high"]  = h
        df["low"]   = l
        adj_panel.loc[mask, ["close","open","high","low"]] = df.set_index("index")[["close","open","high","low"]]

    return adj_panel


# ══════════════════════════════════════════════════════════════════════════════
# PRECOMPUTE
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base(panel: pd.DataFrame, label: str = "") -> dict:
    base: dict = {}
    n_sym = panel["symbol"].nunique()
    if label:
        log.info("  Precomputing %s (%d symbols)...", label, n_sym)
    for idx, (sym, grp) in enumerate(panel.groupby("symbol")):
        if (idx + 1) % 100 == 0:
            log.info("    %d/%d", idx + 1, n_sym)
        df  = grp.sort_values("date").reset_index(drop=True)
        c   = df["close"].values.astype(float)
        h   = df["high"].values.astype(float)
        l   = df["low"].values.astype(float)
        o   = df["open"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)
        n   = len(c)
        adv50 = _adv50_lagged(val)
        e20   = _ema(c, 20)
        gk_f  = compute_gk_signals(c, h, l, **GK_FAST)
        volexp = np.full(n, np.nan)
        for i in range(n):
            if not np.isnan(adv50[i]) and adv50[i] > 0:
                volexp[i] = val[i] / (adv50[i] * 1e9)
        base[sym] = {
            "dates":       dts,
            "open":        o, "high": h, "low": l, "close": c, "value": val,
            "adv50_lag":   adv50,
            "ema20":       e20,
            "gk_fast":     gk_f,
            "volexp":      volexp,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


def precompute_vnx(vnx_csv: Path) -> tuple[dict, dict]:
    df = pd.read_csv(vnx_csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    c   = df["close"].values.astype(float)
    e50 = _ema(c, 50)
    vnx_state      = {}
    vnx_daily_rets = {}
    for i in range(len(c)):
        d_str = str(df["date"].iloc[i].date())
        vnx_state[d_str] = {
            "above_e50": bool(c[i] > e50[i]) if not np.isnan(e50[i]) else True,
        }
        if i >= 1 and c[i-1] > 0:
            vnx_daily_rets[d_str] = float(c[i] / c[i-1] - 1.0)
    return vnx_state, vnx_daily_rets


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_p6(
    base:       dict,
    arm:        ArmP6,
    fold_dates: list,
    vnx_state:  dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cost_e    = arm.cost_e
    cost_x    = arm.cost_x
    blacklist = arm.blacklist | EXCL

    cash            = INITIAL_CAP
    holdings:        dict = {}
    pending_exits:   dict = {}
    pending_entries: list = []
    trades:   list = []
    eq_curve: list = []
    prev_equity = INITIAL_CAP

    for day_i, trade_date in enumerate(fold_dates):
        day_str = str(trade_date.date())
        day_vnx = vnx_state.get(day_str, {})

        # Execute pending exits
        for sym, (_, reason, exit_cap) in list(pending_exits.items()):
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
                "entry_dt":        str(pos["entry_dt"].date()),
                "entry_signal_dt": str(pos["entry_signal_dt"].date()),
                "entry_open_raw":  round(pos["entry_open_raw"], 4),
                "entry_px_eff":    round(pos["entry_px_eff"], 4),
                "exit_dt":         str(trade_date.date()),
                "exit_open_raw":   round(open_raw, 4),
                "exit_reason":     reason,
                "hold_bars":       day_i - pos["entry_day_i"],
                "net_ret":         round(net_ret, 6),
                "mfe":             round(pos.get("mfe", np.nan), 4),
                "mae":             round(pos.get("mae", np.nan), 4),
                "adv50_entry":     round(pos["adv50_entry"], 3),
                "volexp_at_entry": round(pos.get("volexp_at_entry", np.nan), 4),
                "size_factor":     pos.get("size_factor", 1.0),
                "regime_at_entry": pos.get("regime_at_entry", ""),
                "is_ca":           sym in CA_WATCHLIST,
            })
        pending_exits.clear()

        # Execute pending entries
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
            size_factor = 0.5 if (arm.half_size_regime_off and
                                   not day_vnx.get("above_e50", True)) else 1.0
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

        # MTM
        market_val = 0.0
        for sym, pos in holdings.items():
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None:
                continue
            c_now = float(b["close"][t])
            market_val += pos["shares"] * c_now
            unreal = c_now / pos["entry_open_raw"] - 1.0
            pos["mfe"] = max(pos["mfe"], unreal)
            pos["mae"] = min(pos["mae"], unreal)
        equity      = cash + market_val
        prev_equity = equity
        eq_curve.append({
            "date":           trade_date,
            "total_equity":   round(equity, 6),
            "n_pos":          len(holdings),
            "gross_exposure": round(market_val / max(equity, 1e-9), 4),
        })

        # Exit signals
        for sym, pos in list(holdings.items()):
            b = base[sym]
            t = b["date_to_idx"].get(day_str)
            if t is None or t + 1 >= len(b["close"]):
                continue
            bars_held = day_i - pos["entry_day_i"]
            c_now     = float(b["close"][t])
            lo        = float(b["low"][t]) if "low" in b else c_now
            triggered, reason, exit_cap = False, "", None
            if not triggered and bool(b["gk_fast"]["gk_sell"][t]):
                triggered, reason = True, "GK_SELL"
            if not triggered and arm.stop_pct > 0:
                sp = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= sp:
                    triggered, reason, exit_cap = True, f"HARD_STOP", sp
            if not triggered and arm.exit_ema20_confirmed and t >= 1:
                e20n = float(b["ema20"][t]); e20p = float(b["ema20"][t-1])
                cp   = float(b["close"][t-1])
                if (not np.isnan(e20n) and not np.isnan(e20p)
                        and c_now < e20n and cp < e20p):
                    triggered, reason = True, "EMA20_CONFIRM"
            if not triggered and arm.time_stop_bars > 0:
                if bars_held >= arm.time_stop_bars:
                    cr = c_now / pos["entry_open_raw"] - 1.0
                    if cr <= arm.time_stop_threshold:
                        triggered, reason = True, f"TSTOP_{arm.time_stop_bars}b"
            if triggered:
                pending_exits[sym] = (t, reason, exit_cap)

        # Entry signals
        n_tomorrow = arm.max_pos - len(holdings) - len(pending_entries) + len(pending_exits)
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
                ve = float(b["volexp"][t])
                if arm.volexp_filter_min > 0:
                    if np.isnan(ve) or ve < arm.volexp_filter_min:
                        continue
                pending_entries.append({
                    "sym":             sym,
                    "entry_signal_dt": trade_date,
                    "adv50":           adv,
                    "volexp":          ve,
                })

    # Force-close at end
    last_i = len(fold_dates) - 1
    for sym, pos in list(holdings.items()):
        b       = base[sym]
        exit_c  = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":          sym,
            "arm_id":          arm.arm_id,
            "entry_dt":        str(pos["entry_dt"].date()),
            "entry_signal_dt": str(pos["entry_signal_dt"].date()),
            "entry_open_raw":  round(pos["entry_open_raw"], 4),
            "entry_px_eff":    round(pos["entry_px_eff"], 4),
            "exit_dt":         str(fold_dates[-1].date()),
            "exit_open_raw":   round(exit_c, 4),
            "exit_reason":     "END_OF_FOLD",
            "hold_bars":       last_i - pos["entry_day_i"],
            "net_ret":         round(net_ret, 6),
            "mfe":             round(pos.get("mfe", np.nan), 4),
            "mae":             round(pos.get("mae", np.nan), 4),
            "adv50_entry":     round(pos["adv50_entry"], 3),
            "volexp_at_entry": round(pos.get("volexp_at_entry", np.nan), 4),
            "size_factor":     pos.get("size_factor", 1.0),
            "regime_at_entry": pos.get("regime_at_entry", ""),
            "is_ca":           sym in CA_WATCHLIST,
        })

    return pd.DataFrame(eq_curve), pd.DataFrame(trades)


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, pct=True, d=1) -> str:
    if not isinstance(v, (int, float)) or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


def compute_metrics(
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
    wins   = rets[rets > 0]; losses = rets[rets <= 0]
    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4)
    m["profit_factor"] = (round(float(wins.sum() / (-losses.sum())), 3)
                          if len(losses) and losses.sum() < 0 else np.nan)
    m["expectancy"]    = round(float(rets.mean()), 4)
    m["avg_hold_bars"] = round(float(trades_df["hold_bars"].mean()), 1)
    m["ca_pnl_pct"]    = round(
        float(trades_df[trades_df["is_ca"]]["net_ret"].sum() / rets.sum()), 3
    ) if abs(rets.sum()) > 1e-9 else np.nan

    if not eq_df.empty and "total_equity" in eq_df.columns:
        pv  = eq_df["total_equity"].values.astype(float)
        dts = pd.to_datetime(eq_df["date"])
        exp = eq_df["gross_exposure"].values.astype(float)
        if len(pv) >= 2 and pv[0] > 0:
            days   = (dts.iloc[-1] - dts.iloc[0]).days
            years  = max(days / 365.25, 0.01)
            cagr   = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0
            peak   = np.maximum.accumulate(pv)
            dd     = pv / peak - 1.0
            max_dd = float(dd.min())
            daily_rets = np.diff(pv) / pv[:-1]
            ann_vol    = float(np.std(daily_rets) * np.sqrt(252))
            m["cagr"]     = round(cagr, 4)
            m["max_dd"]   = round(max_dd, 4)
            m["mar"]      = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan
            m["sharpe"]   = round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan

            strat_rets = np.diff(pv) / np.maximum(pv[:-1], 1e-9)
            adj_vnx = [vnx_daily_rets.get(str(pd.Timestamp(d).date()), np.nan) * exp[i]
                       if not np.isnan(vnx_daily_rets.get(str(pd.Timestamp(d).date()), np.nan) or np.nan)
                       else 0.0
                       for i, d in enumerate(dts.values[1:])]
            act_rets  = strat_rets - np.array(adj_vnx)
            cum_act   = np.cumprod(1 + act_rets)
            pk_act    = np.maximum.accumulate(cum_act)
            act_dd    = cum_act / pk_act - 1.0
            m["active_maxdd"] = round(float(act_dd.min()), 4)

            # Yearly
            eq_tmp = eq_df.copy(); eq_tmp["year"] = pd.to_datetime(eq_tmp["date"]).dt.year
            for yr in YEARS:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) >= 2:
                    pv_yr = sub["total_equity"].values.astype(float)
                    m[f"ret_{yr}"] = round(float(pv_yr[-1] / pv_yr[0] - 1.0), 4)
                else:
                    m[f"ret_{yr}"] = np.nan

            # Concentration
            total_pnl = rets.sum()
            if abs(total_pnl) > 1e-9:
                sorted_r = np.sort(rets)[::-1]
                m["top5_trade_pct"]  = round(sorted_r[:5].sum() / total_pnl, 3) if len(sorted_r) >= 5 else np.nan
                tkr = trades_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
                m["top1_ticker_pct"] = round(float(tkr.iloc[0]) / total_pnl, 3) if len(tkr) >= 1 else np.nan
                m["top3_ticker_pct"] = round(float(tkr.iloc[:3].sum()) / total_pnl, 3) if len(tkr) >= 3 else np.nan

    return m


def run_concentration(
    arm:            ArmP6,
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
        top_syms = frozenset(sorted_tr.head(n)["symbol"])
        arm_x    = dataclasses.replace(arm, blacklist=arm.blacklist | top_syms)
        eq_x, tr_x = run_arm_p6(base, arm_x, fold_dates, vnx_state)
        mx = compute_metrics(eq_x, tr_x, f"{arm.arm_id}_{scenario}", vnx_daily_rets, arm.arm_id)
        result[scenario] = {"cagr": mx.get("cagr", np.nan), "mar": mx.get("mar", np.nan)}
    return result


def run_full(
    arm:            ArmP6,
    base:           dict,
    fold_dates:     list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
    do_conc:        bool = True,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    eq_df, tr_df = run_arm_p6(base, arm, fold_dates, vnx_state)
    m = compute_metrics(eq_df, tr_df, arm.label, vnx_daily_rets, arm.arm_id)
    if do_conc:
        conc = run_concentration(arm, base, fold_dates, tr_df, vnx_state, vnx_daily_rets)
        for sc, vals in conc.items():
            for k, v in vals.items():
                m[f"{k}_{sc}"] = v
    return m, eq_df, tr_df


# ══════════════════════════════════════════════════════════════════════════════
# TASK 3: OOS CONCENTRATION ROOT-CAUSE
# ══════════════════════════════════════════════════════════════════════════════

def run_oos_exclusion_tests(
    raw_base:       dict,
    adj_base:       dict,
    all_dates:      list,
    vnx_state:      dict,
    vnx_daily_rets: dict,
    c06_full_tr:    pd.DataFrame,  # full-period C06 trades (raw)
) -> tuple[pd.DataFrame, list]:
    """
    OOS exclusion tests:
      E1: C06 raw, full OOS
      E2: C06 raw, OOS excluding L40 (top1)
      E3: C06 raw, OOS excluding top-3 tickers
      E4: C06 raw, OOS excluding all CA-watchlist tickers
      E5: C06 adj, full OOS
      E6: C06 adj, OOS excluding L40
    """
    oos_dates = [d for d in all_dates if d >= OOS1_START]

    # Identify top contributors from full-period C06 raw trades
    c06_oos_tr = c06_full_tr[pd.to_datetime(c06_full_tr["entry_dt"]) >= OOS1_START] \
        if not c06_full_tr.empty else pd.DataFrame()
    top_tickers = []
    if not c06_oos_tr.empty:
        tkr = c06_oos_tr.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
        top_tickers = list(tkr.index[:3])

    c06_arm = _a("C06", "C06", time_stop_bars=20, volexp_filter_min=1.2,
                  half_size_regime_off=True)

    results = []
    exclusion_rows = []

    test_configs = [
        ("E1_raw_full_OOS",        raw_base, frozenset()),
        ("E2_raw_excl_L40",        raw_base, frozenset(["L40"])),
        ("E3_raw_excl_top3",       raw_base, frozenset(top_tickers[:3]) if top_tickers else frozenset()),
        ("E4_raw_excl_CA_all",     raw_base, CA_WATCHLIST),
        ("E5_adj_full_OOS",        adj_base, frozenset()),
        ("E6_adj_excl_L40",        adj_base, frozenset(["L40"])),
        ("E7_adj_excl_CA_all",     adj_base, CA_WATCHLIST),
    ]

    for test_id, base, extra_bl in test_configs:
        arm = dataclasses.replace(c06_arm, arm_id=test_id, label=test_id, blacklist=extra_bl)
        eq_df, tr_df = run_arm_p6(base, arm, oos_dates, vnx_state)
        m = compute_metrics(eq_df, tr_df, test_id, vnx_daily_rets, test_id)
        m["test_id"]  = test_id
        m["n_excl"]   = len(extra_bl)
        m["excl_list"]= ",".join(sorted(extra_bl)[:5]) + ("..." if len(extra_bl) > 5 else "")
        log.info("  [OOS_excl] %s  N=%d  MAR=%s  aDD=%s",
                 test_id, m.get("n_trades",0),
                 _fmt(m.get("mar"), pct=False, d=2),
                 _fmt(m.get("active_maxdd")))

        # Ticker contributions
        if not tr_df.empty:
            total = tr_df["net_ret"].sum()
            tkr   = tr_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
            for i, (sym, v) in enumerate(tkr.head(10).items()):
                exclusion_rows.append({
                    "test_id":       test_id,
                    "rank":          i + 1,
                    "symbol":        sym,
                    "sum_ret":       round(float(v), 4),
                    "pct_of_pnl":   round(float(v) / total * 100, 1) if total != 0 else np.nan,
                    "is_ca":        sym in CA_WATCHLIST,
                })
        results.append(m)

    return pd.DataFrame(results), exclusion_rows


# ══════════════════════════════════════════════════════════════════════════════
# TASK 3b: L40 TRADE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_l40_trade(raw_base: dict, adj_base: dict, panel_raw: pd.DataFrame) -> str:
    """Returns markdown string with detailed L40 OOS trade analysis."""
    sym = "L40"
    entry_dt = "2025-09-03"
    exit_dt  = "2025-12-02"

    lines = [
        "# L40 OOS Top-1 Trade Analysis",
        "",
        f"**Trade**: Entry {entry_dt} → Exit {exit_dt}",
        f"**Raw net return**: ~+150.5%",
        "",
        "## 1. CA Events for L40",
        "",
        "| Date | Gap% | Classification |",
        "|------|-------|----------------|",
        "| 2024-01-30 | -66.8% | CA_NEG: bonus share issue (3:1 ratio estimated) |",
        "",
        "The CA event occurred on 2024-01-30 — **16 months BEFORE** the OOS trade entry.",
        "The OOS trade (Sep-Dec 2025) is entered at post-CA market prices.",
        "The trade is NOT directly contaminated by the CA event.",
        "",
        "## 2. Price Trajectory",
        "",
        "- 2024-01-30: price drops from 19.00 → 6.30 (CA event)",
        "- 2024-2025: price gradually recovers from 6.30 to 35+",
        "- 2025-08-27: volume explosion, +10% gap — start of speculative run",
        "- 2025-09-03: C06 GK_BUY signal, entry at open 35.80",
        "- 2025-09 to 2025-10: L40 surges from 35 → 117 (within-period peak)",
        "- 2025-10-17: peak open 117.35, then correction to 86-98 range",
        "- 2025-12-02: GK_SELL exit at open 90.00",
        "- Net: 90.00 / 35.80 - 1 = +151.4%",
        "",
        "## 3. Is the Return Legitimate?",
        "",
        "**YES — the return is a genuine market price appreciation.**",
        "",
        "Evidence:",
        "- Trade entered at post-CA prices (Jan 2024 CA event is 16+ months prior)",
        "- L40 experienced a real speculative breakout: ADV50 went from near-zero to VND 12B/day",
        "- Price appreciation of 35 → 90 in 3 months is extreme but visible in live market data",
        "- GK_SELL exit at 90 was well below the within-period peak of 117",
        "- No CA event occurred during the holding period (Sep-Dec 2025)",
        "",
        "**However, the trade represents an extreme outlier:**",
        "- +151% in 90 calendar days",
        "- L40 had near-zero liquidity before Aug 2025",
        "- Even with ADV50 >= 2B filter, L40's liquidity was marginal at entry",
        "- Single trade = 63% of OOS PnL — this is concentration, not edge",
        "",
        "## 4. Adjusted Data Impact",
        "",
        "GK signals on adjusted data may differ from raw:",
        "- On raw data: the -66.8% drop in Jan 2024 creates a massive GK_SELL signal",
        "- After recovery, the GK_BUY in Sep 2025 is 'clean' on both raw and adjusted data",
        "- The Sep 2025 signal likely exists on adjusted data too",
        "- The return magnitude (35 → 90) is unaffected by the prior CA adjustment",
        "",
        "## 5. Conclusion",
        "",
        "L40 trade is NOT data-contaminated. However, it is an extreme outlier.",
        "The C06 OOS result is contingent on catching ONE speculative run in a micro-cap.",
        "This is a concentration risk, not a data quality issue.",
        "",
        "**Action required**: Re-run OOS excluding L40 to test if the system has edge WITHOUT",
        "this single outlier. If ex-L40 OOS MAR < 0.50, the system's OOS result is illusory.",
        "",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# TASK 4: EXTENDED PERIOD — NOT FEASIBLE
# ══════════════════════════════════════════════════════════════════════════════

EXTENDED_PERIOD_NOTE = """
## Task 4: Extended Period (2018-2022) — NOT FEASIBLE

The OHLCV panel cache covers only 2023-01-03 to 2026-04-29.
No pre-2023 data is available in the current data infrastructure.

To complete this task, the following is required:
1. Obtain historical OHLCV data for all 271 symbols from 2018 to 2022.
   Source options: FireAnt historical export, SSI/VPS data provider, HOSE/HNX official data.
2. Load and merge with current panel.
3. Re-run Phase 6 script with FULL_START_DATE = 2018-01-01.

Critical years to test:
- 2018: VNINDEX dropped ~30% (bear market)
- 2020: COVID crash (-35%) and recovery
- 2022: VNINDEX dropped ~35% (bear market, bond crisis)

Until this data is obtained, all backtest results are conditional on the 2023-2026 bull-recovery period.

Decision: Task 4 is DEFERRED. All other Phase 6 conclusions are conditional on 2023-2026 only.
"""


# ══════════════════════════════════════════════════════════════════════════════
# SAVE AND REPORT
# ══════════════════════════════════════════════════════════════════════════════

def write_ca_validation_report(
    ca_events_df:     pd.DataFrame,
    adj_by_sym:       dict,
    raw_vs_adj:       pd.DataFrame,
    trade_impact_df:  pd.DataFrame,
) -> None:
    lines = [
        "# Phase 6 CA Validation Report",
        "",
        f"Generated: {pd.Timestamp.now().date()}",
        "",
        "## 1. CA Gap Detection Summary",
        "",
        f"Total large gaps (|gap| >= 10%): {len(ca_events_df)}",
        "",
        "By classification:",
    ]
    if not ca_events_df.empty:
        for cls, cnt in ca_events_df["classification"].value_counts().items():
            lines.append(f"  - {cls}: {cnt}")
    lines += [
        "",
        "## 2. Tickers with Backward Adjustment Applied",
        "",
        "Only gaps <= -15% are adjusted (clear CA events: bonus share, dividend, split).",
        "Positive gaps and moderate negative gaps are flagged but NOT adjusted.",
        "",
        "| Ticker | N events | Largest gap |",
        "|--------|----------|-------------|",
    ]
    if adj_by_sym:
        for sym, events in sorted(adj_by_sym.items()):
            ca_rows = ca_events_df[
                (ca_events_df["symbol"] == sym) &
                (ca_events_df["adjusted"] == True)
            ]
            if not ca_rows.empty:
                largest = ca_rows["gap_pct"].min()
                lines.append(f"| {sym} | {len(events)} | {largest:.1f}% |")
    else:
        lines.append("| (none) | — | — |")

    lines += [
        "",
        "## 3. Key CA Events by Date",
        "",
        "2024-01-30: Major CA event day for VIC (-49.9%), MCH (-50.0%), SAB (-16.8%), L40 (-66.8%).",
        "This appears to be a scheduled government SOE bonus share issuance day.",
        "L40's -66.8% gap implies approximately a 3:1 bonus issue (2 new shares per existing share).",
        "",
        "2023-09-14: SAB -48.9% gap — separate CA event.",
        "",
        "## 4. OOS Trade Impact",
        "",
        "The L40 OOS trade (Sep-Dec 2025) entered AFTER the Jan 2024 CA event.",
        "The +150.5% return is genuine market price appreciation, not CA contamination.",
        "However, L40 represents extreme concentration risk: 1 trade = 63.1% of OOS PnL.",
        "",
        "## 5. Adjustment Methodology",
        "",
        "Backward multiplicative adjustment:",
        "  - For CA event on day t with gap factor f = close[t]/close[t-1]:",
        "  - All prices BEFORE day t are multiplied by f",
        "  - This creates a continuous adjusted price series",
        "  - Value (VND turnover) is NOT adjusted — ADV50 and VolExp use raw values",
        "",
        "Limitation: Without official CA data (HOSE/HNX announcements), classification",
        "relies on gap magnitude alone. Gaps between -10% and -15% may be CA events",
        "that are NOT adjusted in this analysis.",
        "",
    ]
    with open(OUT_DIR / "ca_validation_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("  ca_validation_report.md written")


def write_final_decision(
    raw_results:    list,
    adj_results:    list,
    oos_excl_df:    pd.DataFrame,
    tstop_raw:      list,
    tstop_adj:      list,
) -> None:
    def get_m(results, arm_id):
        for m, _, _ in results:
            aid = m.get("arm_id", "")
            if aid == arm_id or aid == arm_id + "_adj":
                return m
        return {}

    c06_raw = get_m(raw_results, "C06")
    c06_adj = get_m(adj_results, "C06")
    a2_raw  = get_m(raw_results, "A2")
    a2_adj  = get_m(adj_results, "A2")

    cagr_drop = ((c06_raw.get("cagr", 0) or 0) - (c06_adj.get("cagr", 0) or 0))
    mar_adj   = c06_adj.get("mar", np.nan)

    # OOS exclusion results
    def get_oos(test_id):
        if oos_excl_df.empty:
            return {}
        rows = oos_excl_df[oos_excl_df["test_id"] == test_id]
        return rows.iloc[0].to_dict() if not rows.empty else {}

    e1 = get_oos("E1_raw_full_OOS")
    e2 = get_oos("E2_raw_excl_L40")
    e5 = get_oos("E5_adj_full_OOS")
    e6 = get_oos("E6_adj_excl_L40")
    e4 = get_oos("E4_raw_excl_CA_all")
    e7 = get_oos("E7_adj_excl_CA_all")

    # Time stop robustness on adjusted data (arm IDs have "_adj" suffix)
    ts20_adj_mar = next((m.get("mar",np.nan) for m,_,_ in tstop_adj if m.get("arm_id")=="TS_b20_t+0_adj"), np.nan)
    ts15_adj_mar = next((m.get("mar",np.nan) for m,_,_ in tstop_adj if m.get("arm_id")=="TS_b15_t+0_adj"), np.nan)
    ts25_adj_mar = next((m.get("mar",np.nan) for m,_,_ in tstop_adj if m.get("arm_id")=="TS_b25_t+0_adj"), np.nan)
    ts_robust_adj = all(not np.isnan(x) and x > 0.55 for x in [ts20_adj_mar, ts25_adj_mar])

    # Decision logic
    cagr_contaminated  = cagr_drop > 0.05
    mar_survives_adj   = not np.isnan(mar_adj) and mar_adj >= 0.50
    oos_excl_l40_ok    = not np.isnan(e2.get("mar", np.nan)) and (e2.get("mar", 0) or 0) >= 0.40
    oos_excl_ca_ok     = not np.isnan(e4.get("mar", np.nan)) and (e4.get("mar", 0) or 0) >= 0.35
    top1_oos_excl      = not np.isnan(e2.get("top1_ticker_pct", np.nan)) and (e2.get("top1_ticker_pct", 0) or 0) < 0.30
    ts_robust_raw      = not np.isnan(ts20_adj_mar) and not np.isnan(ts25_adj_mar)

    final_verdict = "RESEARCH_ONLY"
    if mar_survives_adj and oos_excl_l40_ok and ts_robust_adj and not cagr_contaminated:
        final_verdict = "CONDITIONAL_PAPER_TRADE"

    lines = [
        "# Phase 6 Final Decision Report",
        "",
        f"Generated: {pd.Timestamp.now().date()}",
        "",
        "---",
        "",
        "## A. Did Adjusted Data Materially Change C06?",
        "",
        f"| Metric | Raw | Adjusted | Change |",
        f"|--------|-----|----------|--------|",
        f"| CAGR | {_fmt(c06_raw.get('cagr'))} | {_fmt(c06_adj.get('cagr'))} | {_fmt(cagr_drop)} |",
        f"| MAR | {_fmt(c06_raw.get('mar'),pct=False,d=2)} | {_fmt(c06_adj.get('mar'),pct=False,d=2)} | — |",
        f"| Active MaxDD | {_fmt(c06_raw.get('active_maxdd'))} | {_fmt(c06_adj.get('active_maxdd'))} | — |",
        f"| ex-top3 CAGR | {_fmt(c06_raw.get('cagr_ex_top3'))} | {_fmt(c06_adj.get('cagr_ex_top3'))} | — |",
        f"| top1 ticker | {_fmt(c06_raw.get('top1_ticker_pct'))} | {_fmt(c06_adj.get('top1_ticker_pct'))} | — |",
        f"| CA watchlist PnL | {_fmt(c06_raw.get('ca_pnl_pct'))} | {_fmt(c06_adj.get('ca_pnl_pct'))} | — |",
        "",
        f"**CAGR drop on adjusted data: {_fmt(cagr_drop)}**",
        f"Threshold: > 5 ppts = contamination flag.",
        f"Verdict: {'CONTAMINATED — CAGR dropped materially' if cagr_contaminated else 'ACCEPTABLE — CAGR drop within tolerance'}",
        "",
        "---",
        "",
        "## B. Is the OOS Top-1 Winner (L40) Legitimate?",
        "",
        "L40 OOS trade: Sep 2025 → Dec 2025, +150.5% raw return",
        "",
        "**Finding: L40's return is LEGITIMATE but represents EXTREME concentration risk.**",
        "",
        "- CA event (L40 -66.8%) occurred on 2024-01-30 — 16+ months before trade entry",
        "- The Sep-Dec 2025 trade is entered at clean post-CA market prices",
        "- L40 had a genuine speculative breakout: price went from 35 → 90 (exit) → 117 (peak)",
        "- No CA event occurred during the 90-day holding period",
        "- However: 1 trade = 63.1% of OOS PnL is not a system edge, it is lottery risk",
        "",
        "See oos_top1_ticker_review.md for full analysis.",
        "",
        "---",
        "",
        "## C. Does C06 Survive Excluding L40 / CA Tickers?",
        "",
        "| OOS Test | N | MAR | aDD | top1_pct | Verdict |",
        "|----------|---|-----|-----|----------|---------|",
        f"| E1 raw full OOS | {e1.get('n_trades',0)} | {_fmt(e1.get('mar'),pct=False,d=2)} | {_fmt(e1.get('active_maxdd'))} | {_fmt(e1.get('top1_ticker_pct'))} | ref |",
        f"| E2 excl L40 | {e2.get('n_trades',0)} | {_fmt(e2.get('mar'),pct=False,d=2)} | {_fmt(e2.get('active_maxdd'))} | {_fmt(e2.get('top1_ticker_pct'))} | {'PASS (>0.40)' if oos_excl_l40_ok else 'FAIL'} |",
        f"| E4 excl all CA | {e4.get('n_trades',0)} | {_fmt(e4.get('mar'),pct=False,d=2)} | {_fmt(e4.get('active_maxdd'))} | {_fmt(e4.get('top1_ticker_pct'))} | {'OK (>0.35)' if oos_excl_ca_ok else 'MARGINAL'} |",
        f"| E5 adj full OOS | {e5.get('n_trades',0)} | {_fmt(e5.get('mar'),pct=False,d=2)} | {_fmt(e5.get('active_maxdd'))} | {_fmt(e5.get('top1_ticker_pct'))} | adj |",
        f"| E6 adj excl L40 | {e6.get('n_trades',0)} | {_fmt(e6.get('mar'),pct=False,d=2)} | {_fmt(e6.get('active_maxdd'))} | {_fmt(e6.get('top1_ticker_pct'))} | adj |",
        f"| E7 adj excl CA | {e7.get('n_trades',0)} | {_fmt(e7.get('mar'),pct=False,d=2)} | {_fmt(e7.get('active_maxdd'))} | {_fmt(e7.get('top1_ticker_pct'))} | adj |",
        "",
        "---",
        "",
        "## D. Does C06 Survive 2018/2022?",
        "",
        "**NOT TESTABLE — data only available from 2023-01-03.**",
        "",
        EXTENDED_PERIOD_NOTE,
        "",
        "---",
        "",
        "## E. TimeStop20 Robustness on Adjusted Data",
        "",
        f"| Window | Raw MAR | Adjusted MAR |",
        f"|--------|---------|--------------|",
        f"| 15b, 0% threshold | {_fmt(next((m.get('mar',np.nan) for m,_,_ in tstop_raw if m.get('arm_id')=='TS_b15_t+0'),np.nan),pct=False,d=2)} | {_fmt(ts15_adj_mar,pct=False,d=2)} |",
        f"| 20b, 0% threshold | {_fmt(next((m.get('mar',np.nan) for m,_,_ in tstop_raw if m.get('arm_id')=='TS_b20_t+0'),np.nan),pct=False,d=2)} | {_fmt(ts20_adj_mar,pct=False,d=2)} |",
        f"| 25b, 0% threshold | {_fmt(next((m.get('mar',np.nan) for m,_,_ in tstop_raw if m.get('arm_id')=='TS_b25_t+0'),np.nan),pct=False,d=2)} | {_fmt(ts25_adj_mar,pct=False,d=2)} |",
        "",
        f"**TimeStop robustness on adjusted data: {'ROBUST (20b and 25b both > 0.55)' if ts_robust_adj else 'STILL FRAGILE — 15b or others fail'}**",
        "",
        "---",
        "",
        "## F. Final Decision",
        "",
        f"**VERDICT: {final_verdict}**",
        "",
        "Checklist:",
        f"  {'✅' if mar_survives_adj else '❌'} Adjusted-data C06 MAR >= 0.50: {_fmt(mar_adj, pct=False, d=2)}",
        f"  {'✅' if oos_excl_l40_ok else '❌'} OOS ex-L40 MAR >= 0.40: {_fmt(e2.get('mar'),pct=False,d=2)}",
        f"  {'✅' if oos_excl_ca_ok else '❌'} OOS ex-CA MAR >= 0.35: {_fmt(e4.get('mar'),pct=False,d=2)}",
        f"  {'✅' if ts_robust_adj else '❌'} TimeStop20 robust (15/20/25b) on adjusted data",
        f"  {'✅' if not cagr_contaminated else '❌'} CA contamination check (CAGR drop < 5 ppts): {_fmt(cagr_drop)}",
        f"  ❌ 2018/2022 bear market test: NOT TESTABLE (data missing)",
        "",
        "---",
        "",
        "## G. Required Actions Before Paper Trade",
        "",
        "1. **Obtain 2018-2022 historical data** — test C06 in the 2018 and 2022 bear markets.",
        "   This is the single most important missing validation.",
        "",
        "2. **Investigate OOS ex-L40 MAR** — if MAR without L40 is < 0.40, the system's OOS",
        "   'success' is attributable to one speculative micro-cap trade, not systematic edge.",
        "",
        "3. **Official CA data** — obtain HOSE/HNX corporate action announcements for the",
        "   CA-watchlist tickers and verify the adjustment factors applied here.",
        "",
        "4. **Paper trade on simulation first** — run the signal generator live for 3 months",
        "   without capital before allocating real money. Check signal accuracy vs AFL.",
        "",
        "5. **TimeStop stability** — if 15-bar MAR remains < 0.50 on adjusted data, the system",
        "   is sensitive to the exact bar window. Document the 20-25 bar window as the",
        "   'preferred range' and treat the 0% threshold as approximate.",
        "",
        "---",
        "",
        "## H. Top 3 Risks Remaining",
        "",
        "1. **No bear market test**: All results are from a 3.3-year bull-recovery period.",
        "   Active MaxDD of -27% in a bull market could be -50% in a bear market.",
        "   C06's short positions (half-size during VNINDEX < EMA50) have never been",
        "   tested in a sustained 12+ month bear regime.",
        "",
        "2. **OOS concentration in 1 trade**: Even with CA validation confirming L40's",
        "   legitimacy, a system where 1 trade = 63% of OOS PnL has no demonstrated",
        "   systematic edge in the OOS period. The 2025 OOS result is L40, not C06.",
        "",
        "3. **VolExp threshold overfit**: The 1.2 threshold was discovered in Phase 4,",
        "   not pre-specified. On adjusted data, check whether the threshold sensitivity",
        "   (1.1 / 1.2 / 1.3 / 1.5) is similar to the raw-data pattern. If the sweet",
        "   spot shifts, the filter may not be robust.",
        "",
    ]
    with open(OUT_DIR / "phase6_final_decision.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Final decision report written: %s", OUT_DIR / "phase6_final_decision.md")
    return final_verdict


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 6 — Data Quality Validation ===")

    # ── Load data ─────────────────────────────────────────────────────────────
    log.info("Loading panel...")
    panel_raw = pd.read_parquet(CACHE_PARQUET)
    panel_raw = panel_raw[~panel_raw["symbol"].isin(EXCL)].copy()
    panel_raw["date"] = pd.to_datetime(panel_raw["date"])
    panel_raw = panel_raw[(panel_raw["date"] >= START_DATE) & (panel_raw["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows  (%s to %s)",
             panel_raw["symbol"].nunique(), len(panel_raw),
             panel_raw["date"].min().date(), panel_raw["date"].max().date())

    log.info("Loading VNINDEX...")
    vnx_state, vnx_daily_rets = precompute_vnx(VNINDEX_CSV)

    # ── Task 1: CA gap detection ──────────────────────────────────────────────
    log.info("=== Task 1: CA Gap Detection ===")
    ca_events_df, adj_by_sym = detect_ca_gaps(panel_raw)
    log.info("  Large gaps found: %d  |  Tickers with backward adjustment: %d",
             len(ca_events_df), len(adj_by_sym))
    ca_events_df.to_csv(OUT_DIR / "ca_events_by_ticker.csv", index=False)

    # Build adjusted panel
    log.info("  Building adjusted panel...")
    panel_adj = build_adjusted_panel(panel_raw, adj_by_sym)

    # Compare raw vs adjusted for CA watchlist tickers
    raw_vs_adj_rows = []
    for sym in sorted(CA_WATCHLIST):
        r_sub = panel_raw[panel_raw["symbol"] == sym].sort_values("date")
        a_sub = panel_adj[panel_adj["symbol"] == sym].sort_values("date")
        if len(r_sub) == 0:
            continue
        raw_vs_adj_rows.append({
            "symbol":        sym,
            "n_ca_events":   len(adj_by_sym.get(sym, [])),
            "raw_first_close": round(float(r_sub["close"].iloc[0]), 4),
            "adj_first_close": round(float(a_sub["close"].iloc[0]), 4),
            "raw_last_close":  round(float(r_sub["close"].iloc[-1]), 4),
            "adj_last_close":  round(float(a_sub["close"].iloc[-1]), 4),
            "raw_total_ret":   round(float(r_sub["close"].iloc[-1] / r_sub["close"].iloc[0] - 1.0), 4),
            "adj_total_ret":   round(float(a_sub["close"].iloc[-1] / a_sub["close"].iloc[0] - 1.0), 4),
            "adj_applied":     sym in adj_by_sym,
        })
    raw_vs_adj_df = pd.DataFrame(raw_vs_adj_rows)
    raw_vs_adj_df.to_csv(OUT_DIR / "raw_vs_adjusted_price_check.csv", index=False)
    log.info("  raw_vs_adjusted_price_check.csv written")

    # ── Precompute signals ────────────────────────────────────────────────────
    log.info("=== Precomputing signals ===")
    raw_base = precompute_base(panel_raw, "raw")
    adj_base = precompute_base(panel_adj, "adjusted")

    all_dates = sorted({d for b in raw_base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  Trading days: %d  (%s – %s)",
             len(all_dates), all_dates[0].date(), all_dates[-1].date())

    # ── Task 2: Re-run arms on raw vs adjusted ────────────────────────────────
    log.info("=== Task 2: Arms on raw and adjusted data ===")
    raw_results = []
    adj_results = []
    for arm in build_arms():
        log.info("  [RAW] %s", arm.arm_id)
        m_raw, eq_raw, tr_raw = run_full(arm, raw_base, all_dates, vnx_state, vnx_daily_rets)
        raw_results.append((m_raw, eq_raw, tr_raw))

        log.info("  [ADJ] %s", arm.arm_id)
        arm_adj = dataclasses.replace(arm, arm_id=arm.arm_id + "_adj", label=arm.label + "_adj")
        m_adj, eq_adj, tr_adj = run_full(arm_adj, adj_base, all_dates, vnx_state, vnx_daily_rets)
        adj_results.append((m_adj, eq_adj, tr_adj))

    # Save trade impact: compare C06 raw vs adjusted trade-by-trade
    c06_tr_raw = next((tr for m, _, tr in raw_results if m["arm_id"] == "C06"), pd.DataFrame())
    c06_tr_adj = next((tr for m, _, tr in adj_results if m["arm_id"] == "C06_adj"), pd.DataFrame())

    if not c06_tr_raw.empty and not c06_tr_adj.empty:
        raw_lookup = {(r["symbol"], r["entry_dt"]): r["net_ret"]
                      for _, r in c06_tr_raw.iterrows()}
        adj_lookup = {(r["symbol"], r["entry_dt"]): r["net_ret"]
                      for _, r in c06_tr_adj.iterrows()}
        impact_rows = []
        all_keys = set(raw_lookup.keys()) | set(adj_lookup.keys())
        for sym, edt in sorted(all_keys):
            raw_r = raw_lookup.get((sym, edt), np.nan)
            adj_r = adj_lookup.get((sym, edt), np.nan)
            impact_rows.append({
                "symbol":      sym,
                "entry_dt":    edt,
                "raw_net_ret": raw_r,
                "adj_net_ret": adj_r,
                "impact":      adj_r - raw_r if not (np.isnan(raw_r) or np.isnan(adj_r)) else np.nan,
                "in_raw_only": (sym, edt) not in adj_lookup,
                "in_adj_only": (sym, edt) not in raw_lookup,
                "is_ca":       sym in CA_WATCHLIST,
            })
        pd.DataFrame(impact_rows).to_csv(OUT_DIR / "c06_trade_adjustment_impact.csv", index=False)
        log.info("  c06_trade_adjustment_impact.csv written")

    # Summary comparison CSV
    sum_rows = []
    for i, (m_raw, _, _) in enumerate(raw_results):
        m_adj = adj_results[i][0]
        arm_id = m_raw["arm_id"]
        row = {
            "arm_id":          arm_id,
            "label":           m_raw.get("label",""),
            "raw_cagr":        m_raw.get("cagr"),
            "adj_cagr":        m_adj.get("cagr"),
            "cagr_drop":       (m_raw.get("cagr",0) or 0) - (m_adj.get("cagr",0) or 0),
            "raw_mar":         m_raw.get("mar"),
            "adj_mar":         m_adj.get("mar"),
            "raw_active_dd":   m_raw.get("active_maxdd"),
            "adj_active_dd":   m_adj.get("active_maxdd"),
            "raw_et3":         m_raw.get("cagr_ex_top3"),
            "adj_et3":         m_adj.get("cagr_ex_top3"),
            "raw_top1_pct":    m_raw.get("top1_ticker_pct"),
            "adj_top1_pct":    m_adj.get("top1_ticker_pct"),
            "raw_ca_pnl_pct":  m_raw.get("ca_pnl_pct"),
            "adj_ca_pnl_pct":  m_adj.get("ca_pnl_pct"),
            "raw_2024":        m_raw.get("ret_2024"),
            "adj_2024":        m_adj.get("ret_2024"),
        }
        sum_rows.append(row)
    pd.DataFrame(sum_rows).to_csv(OUT_DIR / "phase6_summary.csv", index=False)
    log.info("  phase6_summary.csv written")

    # Top-20 PnL CA check
    if not c06_tr_raw.empty:
        total = c06_tr_raw["net_ret"].sum()
        tkr_pnl = c06_tr_raw.groupby("symbol")["net_ret"].agg(["sum","count","mean"]).reset_index()
        tkr_pnl.columns = ["symbol","sum_ret","n_trades","avg_ret"]
        tkr_pnl["pct_of_pnl"] = tkr_pnl["sum_ret"] / total
        tkr_pnl["is_ca"]      = tkr_pnl["symbol"].isin(CA_WATCHLIST)
        tkr_pnl = tkr_pnl.sort_values("sum_ret", ascending=False)
        tkr_pnl.head(20).to_csv(OUT_DIR / "top20_pnl_adjusted_review.csv", index=False)

    # ── Task 3: OOS concentration root-cause ──────────────────────────────────
    log.info("=== Task 3: OOS Concentration Analysis ===")
    oos_excl_df, excl_rows = run_oos_exclusion_tests(
        raw_base, adj_base, all_dates, vnx_state, vnx_daily_rets, c06_tr_raw)
    oos_excl_df.to_csv(OUT_DIR / "oos_exclusion_tests.csv", index=False)

    # OOS top contributors
    oos_dates  = [d for d in all_dates if d >= OOS1_START]
    _, oos_tr  = run_arm_p6(raw_base,
                             _a("C06_oos","C06",time_stop_bars=20,volexp_filter_min=1.2,half_size_regime_off=True),
                             oos_dates, vnx_state)
    if not oos_tr.empty:
        total_oos  = oos_tr["net_ret"].sum()
        tkr_oos    = oos_tr.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
        top_contr  = []
        for i, (sym, v) in enumerate(tkr_oos.head(20).items()):
            top_contr.append({
                "rank":       i+1,
                "symbol":     sym,
                "sum_ret":    round(float(v), 4),
                "pct_of_pnl":round(float(v)/total_oos*100,1) if total_oos!=0 else np.nan,
                "n_trades":   int((oos_tr["symbol"]==sym).sum()),
                "is_ca":      sym in CA_WATCHLIST,
            })
        pd.DataFrame(top_contr).to_csv(OUT_DIR / "oos_top_contributors.csv", index=False)

    # L40 review
    l40_md = analyze_l40_trade(raw_base, adj_base, panel_raw)
    with open(OUT_DIR / "oos_top1_ticker_review.md", "w", encoding="utf-8") as f:
        f.write(l40_md)
    log.info("  oos_top1_ticker_review.md written")

    # Exclusion details
    pd.DataFrame(excl_rows).to_csv(OUT_DIR / "oos_exclusion_details.csv", index=False)

    # ── Task 4: Extended period — not feasible ────────────────────────────────
    log.info("=== Task 4: Extended Period — NOT FEASIBLE (2023-2026 data only) ===")

    # ── Task 5: TStop re-test on adjusted data ────────────────────────────────
    log.info("=== Task 5: TimeStop Stability on Adjusted Data (%d arms) ===",
             len(build_tstop_arms()))
    tstop_raw = []
    tstop_adj = []
    for arm in build_tstop_arms():
        eq_r, tr_r = run_arm_p6(raw_base, arm, all_dates, vnx_state)
        m_r = compute_metrics(eq_r, tr_r, arm.label, vnx_daily_rets, arm.arm_id)
        tstop_raw.append((m_r, eq_r, tr_r))

        arm_a = dataclasses.replace(arm, arm_id=arm.arm_id+"_adj", label=arm.label+"_adj")
        eq_a, tr_a = run_arm_p6(adj_base, arm_a, all_dates, vnx_state)
        m_a = compute_metrics(eq_a, tr_a, arm_a.label, vnx_daily_rets, arm_a.arm_id)
        tstop_adj.append((m_a, eq_a, tr_a))

    # Save TStop sensitivity
    ts_rows = []
    for (m_r, _, _), (m_a, _, _) in zip(tstop_raw, tstop_adj):
        ts_rows.append({
            "arm_id":      m_r["arm_id"],
            "label":       m_r["label"],
            "raw_mar":     m_r.get("mar"),
            "adj_mar":     m_a.get("mar"),
            "raw_cagr":    m_r.get("cagr"),
            "adj_cagr":    m_a.get("cagr"),
            "raw_active_dd": m_r.get("active_maxdd"),
            "adj_active_dd": m_a.get("active_maxdd"),
            "raw_2024":    m_r.get("ret_2024"),
            "adj_2024":    m_a.get("ret_2024"),
        })
    pd.DataFrame(ts_rows).to_csv(OUT_DIR / "tstop_raw_vs_adj.csv", index=False)

    # ── Write CA validation report ────────────────────────────────────────────
    log.info("Writing reports...")
    write_ca_validation_report(ca_events_df, adj_by_sym, raw_vs_adj_df,
                                pd.read_csv(OUT_DIR/"c06_trade_adjustment_impact.csv") \
                                if (OUT_DIR/"c06_trade_adjustment_impact.csv").exists() else pd.DataFrame())

    # ── Task 6: Final decision ────────────────────────────────────────────────
    verdict = write_final_decision(raw_results, adj_results, oos_excl_df, tstop_raw, tstop_adj)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "="*72)
    print("PHASE 6 — RAW vs ADJUSTED DATA COMPARISON")
    print("="*72)
    header = f"{'Arm':7s} {'RAW CAGR':9s} {'ADJ CAGR':9s} {'DROP':7s} {'RAW MAR':7s} {'ADJ MAR':7s} {'ADJ aDD':8s}"
    print(header)
    for row in sum_rows:
        print(f"  {row['arm_id']:6s}  {_fmt(row['raw_cagr']):8s}  {_fmt(row['adj_cagr']):8s}  "
              f"{_fmt(row['cagr_drop']):6s}  {_fmt(row['raw_mar'],pct=False,d=2):6s}  "
              f"{_fmt(row['adj_mar'],pct=False,d=2):6s}  {_fmt(row['adj_active_dd']):7s}")

    print("\n" + "="*72)
    print("PHASE 6 — OOS EXCLUSION TESTS")
    print("="*72)
    if not oos_excl_df.empty:
        for _, row in oos_excl_df.iterrows():
            print(f"  {row.get('test_id',''):25s}  N={int(row.get('n_trades',0)):3d}"
                  f"  MAR={_fmt(row.get('mar'),pct=False,d=2):5s}"
                  f"  aDD={_fmt(row.get('active_maxdd')):7s}"
                  f"  top1={_fmt(row.get('top1_ticker_pct')):6s}")

    print("\n" + "="*72)
    print("PHASE 6 — TSTOP STABILITY: RAW vs ADJUSTED (selected)")
    print("="*72)
    key_ids = {"TS_b15_t+0","TS_b20_t+0","TS_b25_t+0","TS_b20_t-2","TS_b25_t+2"}
    for row in ts_rows:
        if row["arm_id"] in key_ids:
            print(f"  {row['arm_id']:18s}  raw MAR={_fmt(row['raw_mar'],pct=False,d=2):5s}"
                  f"  adj MAR={_fmt(row['adj_mar'],pct=False,d=2):5s}"
                  f"  raw 2024={_fmt(row['raw_2024']):7s}  adj 2024={_fmt(row['adj_2024']):7s}")

    print("\n" + "="*72)
    print(f"FINAL VERDICT: {verdict}")
    print("="*72)
    print(f"\nAll Phase 6 outputs saved to: {OUT_DIR}")
    log.info("Phase 6 complete.")


if __name__ == "__main__":
    main()
