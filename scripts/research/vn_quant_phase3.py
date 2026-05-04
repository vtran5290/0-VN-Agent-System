#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 3 — Concentration Control / Ranking / Filter / Sizing / Exit / DC Branch

Parts:
  1. A2 Trade Diagnostics
  2. Ranking Tests (11 methods)
  3. Entry Filter Tests (11 individual + 5 combos)
  4. Position Sizing Tests (10 variants)
  5. Exit Rule Tests (13 variants — no GK_Lower primary)
  6. DC Branch Tests (6 variants)

Decision rule:
  Paper trade if: MAR > 0.7, active MaxDD improves, ex-top3 CAGR > 10%,
    2024 >= baseline, not driven by one ticker.
  Reject if: ex-top3 CAGR < 8%, active MaxDD < -30%, top-5 explain all PnL.

Outputs -> data/research/gk_audit/phase3/
"""
from __future__ import annotations

import io, sys, json, logging, warnings, dataclasses
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
P2_DIR        = REPO / "data/research/gk_audit/phase2"
OUT_DIR       = REPO / "data/research/gk_audit/phase3"
SECTOR_JSON   = REPO / "data/research/industry_top_stocks_from_top_groups.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants (identical to Phase 2) ──────────────────────────────────────────
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
# ARM CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmP3:
    arm_id: str
    label:  str
    # Entry
    entry:                    str   = "gk"
    gk_params:                dict  = field(default_factory=lambda: GK_FAST)
    # Entry filters
    require_close_above_ema:  int   = 0      # 0=off | 50/100/150
    require_ema_slope:        int   = 0      # 0=off | 50/100/150
    rs1m_filter:              bool  = False
    rs3m_filter:              bool  = False
    rs6m_filter:              bool  = False
    volexp_filter_min:        float = 0.0   # vol/adv50 > this; 0=off
    dist_52wk_max:            float = 0.0   # near52 > (1-dist_52wk_max); 0=off
    atr_pct_below_median:     bool  = False
    vnindex_dd_max:           float = 0.0   # VNINDEX dd from 252-bar peak < this; 0=off
    vnindex_above_ema50:      bool  = False
    # Exit primary
    exit_type:                str   = "gk_sell"  # "gk_sell" | "fixed_N"
    fixed_hold:               int   = 63
    min_hold:                 int   = 0
    # Hard stop / ATR trailing
    stop_pct:                 float = 0.0   # 0=off; 0.08 = 8% stop below entry
    atr_stop_mult:            float = 0.0   # 0=off; trailing ATR stop multiplier
    # New secondary exits
    exit_ema20_confirmed:     bool  = False  # close < EMA20 two consecutive bars
    time_stop_bars:           int   = 0      # exit after N bars if return <= 0
    mfe_activate_pct:         float = 0.0   # MFE giveback: activate when MFE >= this
    mfe_giveback_frac:        float = 0.0   # exit when (MFE - current_ret) >= MFE * frac
    # Portfolio / sizing
    max_pos:                  int   = MAX_POS
    fee_bps:                  float = FEE_BPS
    slip_bps:                 float = SLIP_BPS
    sizing:                   str   = "equal"    # "equal" | "atr_adj" | "rank_weighted"
    half_size_regime_off:     bool  = False
    half_size_rs3m_neg:       bool  = False
    full_size_condition:      str   = ""    # "" | "rs3m_pos_and_volexp_12"
    # Sector constraints (requires sector data)
    max_sector_slots:         int   = 0     # 0=off; max positions per sector
    # Ranking
    ranking:                  str   = "adv50"
    # Blacklist
    blacklist:                frozenset = field(default_factory=frozenset)

    @property
    def cost_e(self): return 1.0 + (self.fee_bps + self.slip_bps) / 10_000
    @property
    def cost_x(self): return 1.0 - (self.fee_bps + self.slip_bps) / 10_000
    @property
    def gk_key(self): return "gk_fast"


# ══════════════════════════════════════════════════════════════════════════════
# MATH PRIMITIVES (identical to Phase 2)
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
# SIGNAL COMPUTATION (identical to Phase 2)
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
        don_high    = np.max(high[i-DON_LEN:i])
        trigger     = don_high * DON_BUF
        bull_cloud  = bool(ema10[i] > ema50[i])
        above_cloud = bool(close[i] > max(ema10[i], ema50[i]))
        dc_buy[i]   = (close[i] > trigger) and bull_cloud and above_cloud
    return dc_buy


# ══════════════════════════════════════════════════════════════════════════════
# PRECOMPUTE — EXTENDED (adds RS1M, RS12M, EMA slopes, ATR%, volexp, dist20h)
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base_p3(
    panel: pd.DataFrame,
    vnx_by_date: dict,
    sector_by_sym: dict,
) -> dict:
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
        e50   = _ema(c, EMA_SLOW)
        e100  = _ema(c, 100)
        e150  = _ema(c, 150)
        adv50 = _adv50_lagged(val)
        atr14 = _wilder_atr(h, l, c, 14)

        gk_f = compute_gk_signals(c, h, l, **GK_FAST)
        dc_b = compute_dc_signals(c, h, e10, e50)

        # RS vs VNINDEX: 1M(21), 3M(63), 6M(126), 12M(252)
        rs = {lb: np.full(n, np.nan) for lb in (21, 63, 126, 252)}
        for i in range(n):
            d_str = str(dts[i].date())
            vnx_t = vnx_by_date.get(d_str, np.nan)
            if np.isnan(vnx_t):
                continue
            for lb, arr in rs.items():
                if i >= lb and c[i-lb] > 0:
                    d_lb  = str(dts[i-lb].date())
                    vnx_l = vnx_by_date.get(d_lb, np.nan)
                    if not np.isnan(vnx_l) and vnx_l > 0:
                        arr[i] = (c[i]/c[i-lb] - 1.0) - (vnx_t/vnx_l - 1.0)

        # near52 = close / max(high[-252:t]) (1.0 = at 52wk high)
        # dist20h = close / max(high[-20:t]) - 1 (negative if below 20d high)
        near52  = np.full(n, np.nan)
        dist20h = np.full(n, np.nan)
        for i in range(1, n):
            hi52 = np.max(h[max(0, i-252):i])
            if hi52 > 0:
                near52[i] = c[i] / hi52
            hi20 = np.max(h[max(0, i-20):i])
            if hi20 > 0:
                dist20h[i] = c[i] / hi20 - 1.0

        # ATR% and volume expansion
        atr_pct = np.where(c > 0, atr14 / c, np.nan)
        volexp  = np.full(n, np.nan)
        for i in range(n):
            if not np.isnan(adv50[i]) and adv50[i] > 0:
                volexp[i] = val[i] / (adv50[i] * 1e9)

        # EMA slopes (current - previous bar)
        e50_slope  = np.concatenate([[np.nan], e50[1:]  - e50[:-1]])
        e150_slope = np.concatenate([[np.nan], e150[1:] - e150[:-1]])

        base[sym] = {
            "dates":       dts,
            "open":        o, "high": h, "low": l, "close": c, "value": val,
            "adv50_lag":   adv50,
            "ema10":       e10, "ema20": e20, "ema50": e50,
            "ema100":      e100, "ema150": e150,
            "e50_slope":   e50_slope, "e150_slope": e150_slope,
            "atr14":       atr14, "atr_pct": atr_pct,
            "gk_fast":     gk_f, "dc_buy": dc_b,
            "rs1m":        rs[21],  "rs3m": rs[63],
            "rs6m":        rs[126], "rs12m": rs[252],
            "near52":      near52, "dist20h": dist20h,
            "volexp":      volexp,
            "sector":      sector_by_sym.get(sym, "UNKNOWN"),
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


def precompute_vnx_state(vnx_csv: Path) -> tuple[dict, dict, dict]:
    """Returns (vnx_by_date, vnx_state_by_date, vnx_daily_rets).
    vnx_state_by_date: date_str -> {above_e50, above_e100, above_e150, ret_20d, ret_50d, dd_252}
    vnx_daily_rets: date_str -> daily return (for active MaxDD)
    """
    df = pd.read_csv(vnx_csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    c  = df["close"].values.astype(float)
    n  = len(c)

    e50  = _ema(c, 50)
    e100 = _ema(c, 100)
    e150 = _ema(c, 150)

    vnx_by_date   = {}
    vnx_state     = {}
    vnx_daily_rets = {}

    for i in range(n):
        d_str = str(df["date"].iloc[i].date())
        vnx_by_date[d_str] = float(c[i])

        ret20 = (c[i]/c[i-20] - 1.0) if i >= 20 and c[i-20] > 0 else np.nan
        ret50 = (c[i]/c[i-50] - 1.0) if i >= 50 and c[i-50] > 0 else np.nan
        peak  = float(np.max(c[max(0, i-252):i+1])) if i >= 0 else c[i]
        dd    = c[i] / peak - 1.0 if peak > 0 else 0.0

        vnx_state[d_str] = {
            "above_e50":  bool(c[i] > e50[i])  if not np.isnan(e50[i])  else True,
            "above_e100": bool(c[i] > e100[i]) if not np.isnan(e100[i]) else True,
            "above_e150": bool(c[i] > e150[i]) if not np.isnan(e150[i]) else True,
            "ret_20d":    float(ret20) if not np.isnan(ret20) else 0.0,
            "ret_50d":    float(ret50) if not np.isnan(ret50) else 0.0,
            "dd_252":     float(dd),
        }

        if i >= 1 and c[i-1] > 0:
            vnx_daily_rets[d_str] = float(c[i] / c[i-1] - 1.0)

    return vnx_by_date, vnx_state, vnx_daily_rets


def precompute_median_atr_pct(base: dict, all_dates: list) -> dict:
    out = {}
    for d in all_dates:
        d_str = str(d.date())
        vals  = []
        for b in base.values():
            t = b["date_to_idx"].get(d_str)
            if t is not None:
                v = float(b["atr_pct"][t])
                if not np.isnan(v) and v > 0:
                    vals.append(v)
        out[d_str] = float(np.median(vals)) if vals else np.nan
    return out


def load_sector_mapping(json_path: Path) -> dict:
    if not json_path.exists():
        log.warning("Sector JSON not found: %s — sector constraints disabled", json_path)
        return {}
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        mapping = {}
        if isinstance(data, dict):
            for sector_code, stocks in data.items():
                if isinstance(stocks, list):
                    for sym in stocks:
                        if isinstance(sym, str):
                            mapping[sym] = str(sector_code)
        log.info("Sector mapping loaded: %d symbols", len(mapping))
        return mapping
    except Exception as e:
        log.warning("Failed to load sector data: %s", e)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# CANDIDATE SCORING (includes composite with cross-sectional percentile ranks)
# ══════════════════════════════════════════════════════════════════════════════

def _pct_ranks(values: list) -> list:
    """Return percentile rank [0,1] for each value; NaN -> 0."""
    arr = np.array([v if not np.isnan(v) else -np.inf for v in values], dtype=float)
    n   = len(arr)
    if n == 0:
        return []
    order = np.argsort(arr)
    ranks = np.empty(n, dtype=float)
    ranks[order] = np.linspace(0, 1, n)
    return ranks.tolist()


def score_candidates(candidates: list, ranking: str) -> list:
    """Mutate each candidate dict to add 'score' field. Returns candidates."""
    if not candidates:
        return candidates
    n = len(candidates)

    if ranking == "adv50":
        for c in candidates:
            c["score"] = c["adv50"] if not np.isnan(c["adv50"]) else 0.0

    elif ranking == "rs1m":
        for c in candidates:
            c["score"] = c["rs1m"] if not np.isnan(c["rs1m"]) else -999.0

    elif ranking == "rs3m":
        for c in candidates:
            c["score"] = c["rs3m"] if not np.isnan(c["rs3m"]) else -999.0

    elif ranking == "rs6m":
        for c in candidates:
            c["score"] = c["rs6m"] if not np.isnan(c["rs6m"]) else -999.0

    elif ranking == "composite_1m3m":
        for c in candidates:
            r1, r3 = c["rs1m"], c["rs3m"]
            if not np.isnan(r1) and not np.isnan(r3):
                c["score"] = 0.5 * r1 + 0.5 * r3
            elif not np.isnan(r3):
                c["score"] = r3
            else:
                c["score"] = -999.0

    elif ranking == "composite_3m6m":
        for c in candidates:
            r3, r6 = c["rs3m"], c["rs6m"]
            if not np.isnan(r3) and not np.isnan(r6):
                c["score"] = 0.5 * r3 + 0.5 * r6
            elif not np.isnan(r3):
                c["score"] = r3
            else:
                c["score"] = -999.0

    elif ranking == "volexp":
        for c in candidates:
            c["score"] = c["volexp"] if not np.isnan(c["volexp"]) else 0.0

    elif ranking == "near52wk":
        for c in candidates:
            c["score"] = c["near52"] if not np.isnan(c["near52"]) else 0.0

    elif ranking == "ema150_slope":
        for c in candidates:
            c["score"] = c["e150_slope"] if not np.isnan(c["e150_slope"]) else -999.0

    elif ranking == "atr_pct_asc":
        # lower ATR% = better; score = -atr_pct so higher score = lower vol
        for c in candidates:
            c["score"] = -c["atr_pct"] if not np.isnan(c["atr_pct"]) else -999.0

    elif ranking == "composite_rank":
        # 30% rs3m, 25% rs6m, 20% volexp, 15% near52wk, 10% adv50 — percentile-normalized
        pr3  = _pct_ranks([c["rs3m"]   for c in candidates])
        pr6  = _pct_ranks([c["rs6m"]   for c in candidates])
        pve  = _pct_ranks([c["volexp"] for c in candidates])
        pn52 = _pct_ranks([c["near52"] for c in candidates])
        pa   = _pct_ranks([c["adv50"]  for c in candidates])
        for i, c in enumerate(candidates):
            c["score"] = (0.30*pr3[i] + 0.25*pr6[i] + 0.20*pve[i]
                          + 0.15*pn52[i] + 0.10*pa[i])

    elif ranking == "composite_defensive":
        # 30% rs3m, 25% rs6m, 20% ema150_slope, 15% atr_pct_inv, 10% volexp
        pr3  = _pct_ranks([c["rs3m"]       for c in candidates])
        pr6  = _pct_ranks([c["rs6m"]       for c in candidates])
        pe   = _pct_ranks([c["e150_slope"] for c in candidates])
        pav  = _pct_ranks([-c["atr_pct"] if not np.isnan(c["atr_pct"]) else -np.inf
                            for c in candidates])
        pve  = _pct_ranks([c["volexp"]     for c in candidates])
        for i, c in enumerate(candidates):
            c["score"] = (0.30*pr3[i] + 0.25*pr6[i] + 0.20*pe[i]
                          + 0.15*pav[i] + 0.10*pve[i])

    else:  # default: adv50
        for c in candidates:
            c["score"] = c["adv50"] if not np.isnan(c["adv50"]) else 0.0

    return candidates


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY FILTER HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _passes_entry_filters(
    arm: ArmP3,
    b: dict,
    t: int,
    day_vnx: dict,
    median_atr_pct: float,
) -> bool:
    c    = float(b["close"][t])

    if arm.require_close_above_ema > 0:
        ema_key = {50: "ema50", 100: "ema100", 150: "ema150"}.get(arm.require_close_above_ema)
        if ema_key:
            ev = float(b[ema_key][t])
            if np.isnan(ev) or c <= ev:
                return False

    if arm.require_ema_slope > 0 and t > 0:
        ema_key = {50: "ema50", 100: "ema100", 150: "ema150"}.get(arm.require_ema_slope)
        if ema_key:
            ev  = float(b[ema_key][t])
            ep  = float(b[ema_key][t-1])
            if np.isnan(ev) or np.isnan(ep) or ev <= ep:
                return False

    if arm.rs1m_filter:
        v = float(b["rs1m"][t])
        if np.isnan(v) or v <= 0:
            return False

    if arm.rs3m_filter:
        v = float(b["rs3m"][t])
        if np.isnan(v) or v <= 0:
            return False

    if arm.rs6m_filter:
        v = float(b["rs6m"][t])
        if np.isnan(v) or v <= 0:
            return False

    if arm.volexp_filter_min > 0:
        v = float(b["volexp"][t])
        if np.isnan(v) or v < arm.volexp_filter_min:
            return False

    if arm.dist_52wk_max > 0:
        n52 = float(b["near52"][t])
        if np.isnan(n52) or n52 < (1.0 - arm.dist_52wk_max):
            return False

    if arm.atr_pct_below_median and not np.isnan(median_atr_pct):
        av = float(b["atr_pct"][t])
        if np.isnan(av) or av >= median_atr_pct:
            return False

    if arm.vnindex_dd_max > 0:
        dd = abs(day_vnx.get("dd_252", 0.0))
        if dd >= arm.vnindex_dd_max:
            return False

    if arm.vnindex_above_ema50:
        if not day_vnx.get("above_e50", True):
            return False

    return True


# ══════════════════════════════════════════════════════════════════════════════
# SIZING FACTOR HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _size_factor(arm: ArmP3, b: dict, t: int, day_vnx: dict) -> float:
    factor = 1.0
    if arm.half_size_regime_off:
        if not day_vnx.get("above_e50", True):
            factor = 0.5
    if arm.half_size_rs3m_neg:
        v = float(b["rs3m"][t])
        if np.isnan(v) or v <= 0:
            factor = min(factor, 0.5)
    if arm.full_size_condition == "rs3m_pos_and_volexp_12":
        rs = float(b["rs3m"][t])
        ve = float(b["volexp"][t])
        if np.isnan(rs) or rs <= 0 or np.isnan(ve) or ve < 1.2:
            factor = min(factor, 0.5)
    return factor


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENGINE — PHASE 3
# ══════════════════════════════════════════════════════════════════════════════

def run_arm_p3(
    base:             dict,
    arm:              ArmP3,
    all_dates:        list,
    vnx_state:        dict,
    median_atr_by_date: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:

    gk_key   = arm.gk_key
    cost_e   = arm.cost_e
    cost_x   = arm.cost_x
    blacklist = arm.blacklist | EXCL

    cash            = INITIAL_CAP
    holdings:        dict  = {}
    pending_exits:   dict  = {}
    pending_entries: list  = []
    trades:  list = []
    eq_curve: list = []
    prev_equity = INITIAL_CAP

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())
        day_vnx = vnx_state.get(day_str, {})
        med_atr = median_atr_by_date.get(day_str, np.nan)

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
                "symbol":          sym,
                "arm_id":          arm.arm_id,
                "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
                "entry_dt":        str(pos["entry_dt"].date()),
                "entry_open_raw":  round(pos["entry_open_raw"], 4),
                "entry_px_eff":    round(pos["entry_px_eff"], 4),
                "exit_signal_dt":  str(pos.get("exit_signal_dt", "")) if not hasattr(pos.get("exit_signal_dt", ""), "date") else str(pos["exit_signal_dt"].date()),
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

        # ── Step 2: Execute pending entries at today's open ───────────────────
        n_slots = arm.max_pos - len(holdings)
        selected = sorted(pending_entries, key=lambda x: -x["score"])[:n_slots]

        # Pre-compute sizing for rank_weighted (need all selected scores at once)
        if arm.sizing == "rank_weighted" and selected:
            n_sel  = len(selected)
            # Percentile rank within selected: top entry gets 1.0, bottom 0.0
            rw_factors = [1.0 - i / max(n_sel - 1, 1) for i in range(n_sel)]
            # Map to slot multiplier [0.5, 1.0]
            rw_mults = [0.5 + 0.5 * f for f in rw_factors]
        else:
            rw_mults = [1.0] * len(selected)

        for rank_i, entry in enumerate(selected):
            sym  = entry["sym"]
            t_sig = entry["t_sig"]
            meta  = entry["meta"]
            if sym in holdings:
                continue
            b    = base[sym]
            t_ex = b["date_to_idx"].get(day_str)
            if t_ex is None:
                continue
            entry_o_raw = float(b["open"][t_ex])
            if entry_o_raw <= 0:
                continue

            # Base slot
            base_slot = prev_equity / arm.max_pos

            # Sizing
            if arm.sizing == "atr_adj":
                atr_e = float(b["atr_pct"][t_sig])
                if not np.isnan(atr_e) and atr_e > 0 and not np.isnan(med_atr) and med_atr > 0:
                    slot = base_slot * float(np.clip(med_atr / atr_e, 0.5, 2.0))
                else:
                    slot = base_slot
            elif arm.sizing == "rank_weighted":
                slot = base_slot * rw_mults[rank_i]
            else:
                slot = base_slot

            # Half-size modifiers
            slot *= _size_factor(arm, b, t_sig, day_vnx)

            entry_px_eff = entry_o_raw * cost_e
            shares       = slot / entry_px_eff
            cash        -= slot

            holdings[sym] = {
                "shares":           shares,
                "entry_px_eff":     entry_px_eff,
                "entry_open_raw":   entry_o_raw,
                "entry_dt":         trade_date,
                "entry_signal_dt":  meta["entry_signal_dt"],
                "entry_day_i":      day_i,
                "adv50_entry":      meta["adv50_entry"],
                "entry_mode":       meta["entry_mode"],
                "exit_signal_dt":   None,
                "trail_atr_stop":   -np.inf,
                "mfe":              0.0,
                "mae":              0.0,
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
            unrealised  = c_now / pos["entry_open_raw"] - 1.0
            pos["mfe"]  = max(pos["mfe"], unrealised)
            pos["mae"]  = min(pos["mae"], unrealised)
            if arm.atr_stop_mult > 0:
                atr_v = float(b["atr14"][t])
                if not np.isnan(atr_v):
                    pos["trail_atr_stop"] = max(pos["trail_atr_stop"],
                                                c_now - arm.atr_stop_mult * atr_v)

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

            # Primary: GK_SELL
            if not triggered and arm.exit_type == "gk_sell":
                if bool(b[gk_key]["gk_sell"][t]):
                    triggered, reason = True, "GK_SELL"

            # Primary: Fixed N bars
            if not triggered and arm.exit_type == "fixed_N":
                if bars_held >= arm.fixed_hold:
                    triggered, reason = True, f"FIXED_{arm.fixed_hold}"

            # ATR trailing stop
            if not triggered and arm.atr_stop_mult > 0:
                trail = pos["trail_atr_stop"]
                if trail > -np.inf and lo <= trail:
                    triggered, reason, exit_cap = True, f"ATR_TRAIL_{arm.atr_stop_mult}x", trail

            # Hard stop
            if not triggered and arm.stop_pct > 0:
                stop_px = pos["entry_open_raw"] * (1.0 - arm.stop_pct)
                if lo <= stop_px:
                    triggered, reason, exit_cap = True, f"STOP_{arm.stop_pct*100:.0f}PCT", stop_px

            # Secondary: EMA20 confirmed (two consecutive closes below EMA20)
            if not triggered and arm.exit_ema20_confirmed and t >= 1:
                e20_now  = float(b["ema20"][t])
                e20_prev = float(b["ema20"][t-1])
                c_prev   = float(b["close"][t-1])
                if (not np.isnan(e20_now) and not np.isnan(e20_prev)
                        and c_now < e20_now and c_prev < e20_prev):
                    triggered, reason = True, "EMA20_CONFIRM"

            # Secondary: Time stop (exit after N bars if still flat or negative)
            if not triggered and arm.time_stop_bars > 0:
                if bars_held >= arm.time_stop_bars:
                    current_ret = c_now / pos["entry_open_raw"] - 1.0
                    if current_ret <= 0.0:
                        triggered, reason = True, f"TIME_STOP_{arm.time_stop_bars}B"

            # Secondary: MFE giveback
            if not triggered and arm.mfe_activate_pct > 0 and arm.mfe_giveback_frac > 0:
                mfe = pos["mfe"]
                if mfe >= arm.mfe_activate_pct:
                    current_ret = c_now / pos["entry_open_raw"] - 1.0
                    mfe_floor   = mfe * (1.0 - arm.mfe_giveback_frac)
                    if current_ret < mfe_floor:
                        triggered, reason = True, "MFE_GIVEBACK"

            if triggered:
                pos["exit_signal_dt"] = trade_date
                pending_exits[sym]    = (t, reason, exit_cap)

        # ── Step 5: Scan entry signals ────────────────────────────────────────
        n_tomorrow_free = (arm.max_pos - len(holdings)
                           - len(pending_entries) + len(pending_exits))
        if n_tomorrow_free > 0:
            day_candidates = []
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

                # Entry signal
                ok = False
                if arm.entry == "gk" and bool(b[gk_key]["gk_buy"][t]):
                    ok = True
                elif arm.entry == "donchian" and bool(b["dc_buy"][t]):
                    ok = True

                if ok:
                    ok = _passes_entry_filters(arm, b, t, day_vnx, med_atr)

                # Sector constraint
                if ok and arm.max_sector_slots > 0:
                    sym_sector = b["sector"]
                    n_sec = sum(1 for s, pos in holdings.items()
                                if base[s]["sector"] == sym_sector)
                    n_sec += sum(1 for e in pending_entries
                                 if base[e["sym"]]["sector"] == sym_sector)
                    if n_sec >= arm.max_sector_slots:
                        ok = False

                if ok:
                    day_candidates.append({
                        "sym":       sym,
                        "t_sig":     t,
                        "meta":      {"entry_signal_dt": trade_date,
                                      "adv50_entry": adv,
                                      "entry_mode":  arm.entry},
                        "score":     0.0,
                        "rs1m":      float(b["rs1m"][t])       if not np.isnan(b["rs1m"][t])       else np.nan,
                        "rs3m":      float(b["rs3m"][t])       if not np.isnan(b["rs3m"][t])       else np.nan,
                        "rs6m":      float(b["rs6m"][t])       if not np.isnan(b["rs6m"][t])       else np.nan,
                        "volexp":    float(b["volexp"][t])     if not np.isnan(b["volexp"][t])     else np.nan,
                        "near52":    float(b["near52"][t])     if not np.isnan(b["near52"][t])     else np.nan,
                        "e150_slope":float(b["e150_slope"][t]) if not np.isnan(b["e150_slope"][t]) else np.nan,
                        "atr_pct":   float(b["atr_pct"][t])   if not np.isnan(b["atr_pct"][t])   else np.nan,
                        "adv50":     adv,
                    })

            if day_candidates:
                score_candidates(day_candidates, arm.ranking)
                pending_entries.extend(day_candidates)

    # ── Force-close remaining positions at last bar ───────────────────────────
    last_day_i = len(all_dates) - 1
    for sym, pos in list(holdings.items()):
        b       = base[sym]
        exit_c  = float(b["close"][-1])
        proceeds = pos["shares"] * exit_c * cost_x
        cash    += proceeds
        net_ret  = (exit_c * cost_x) / pos["entry_px_eff"] - 1.0
        trades.append({
            "symbol":          sym, "arm_id": arm.arm_id,
            "entry_signal_dt": str(pos["entry_signal_dt"].date()) if hasattr(pos["entry_signal_dt"], "date") else str(pos["entry_signal_dt"]),
            "entry_dt":        str(pos["entry_dt"].date()),
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

    return pd.DataFrame(eq_curve), pd.DataFrame(trades), {}


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, pct=True, d=1) -> str:
    if not isinstance(v, (int, float)) or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "n/a"
    return f"{v*100:.{d}f}%" if pct else f"{v:.{d}f}"


def compute_metrics_p3(
    eq_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    label: str,
    vnx_daily_rets: dict,
) -> dict:
    m: dict = {"label": label, "n_trades": 0}
    if trades_df.empty:
        return m

    rets   = trades_df["net_ret"].values.astype(float)
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]
    holds  = trades_df["hold_bars"].values.astype(float)

    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4)
    m["avg_ret"]       = round(float(rets.mean()), 4)
    m["median_ret"]    = round(float(np.median(rets)), 4)
    m["avg_win"]       = round(float(wins.mean()),   4) if len(wins)   else np.nan
    m["avg_loss"]      = round(float(losses.mean()), 4) if len(losses) else np.nan
    m["profit_factor"] = (round(float(wins.sum() / (-losses.sum())), 3)
                          if len(losses) and losses.sum() < 0 else np.nan)
    m["expectancy"]    = round(float(rets.mean()), 4)
    m["avg_hold_days"] = round(float(holds.mean()), 1) if len(holds) else np.nan

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
            m["cagr"]    = round(cagr, 4)
            m["max_dd"]  = round(max_dd, 4)
            m["mar"]     = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else np.nan
            daily_rets   = np.diff(pv) / pv[:-1]
            ann_vol      = float(np.std(daily_rets) * np.sqrt(252))
            m["ann_vol"] = round(ann_vol, 4)
            m["sharpe"]  = round(cagr / ann_vol, 3) if ann_vol > 0 else np.nan
            m["exposure_pct"] = round(float(eq_df["n_pos"].mean() / MAX_POS), 4)

            # Active MaxDD vs exposure-weighted VNINDEX
            exp = eq_df["gross_exposure"].values.astype(float)
            strat_rets_arr = np.diff(pv) / np.maximum(pv[:-1], 1e-9)
            adj_vnx = []
            for i, d in enumerate(dts.values[1:]):
                d_str = str(pd.Timestamp(d).date())
                vr    = vnx_daily_rets.get(d_str, np.nan)
                adj_vnx.append(vr * exp[i] if not np.isnan(vr) else 0.0)
            adj_vnx      = np.array(adj_vnx)
            active_rets  = strat_rets_arr - adj_vnx
            cum_act      = np.cumprod(1 + active_rets)
            pk_act       = np.maximum.accumulate(cum_act)
            act_dd       = cum_act / pk_act - 1.0
            m["active_maxdd"] = round(float(act_dd.min()), 4) if len(act_dd) else np.nan

            # Yearly returns
            eq_tmp  = eq_df.copy()
            eq_tmp["year"] = pd.to_datetime(eq_tmp["date"]).dt.year
            yearly: dict = {}
            for yr in YEARS:
                sub = eq_tmp[eq_tmp["year"] == yr]
                if len(sub) < 2:
                    yearly[yr] = {}
                    continue
                pv_yr = sub["total_equity"].values.astype(float)
                tr_yr = trades_df[pd.to_datetime(trades_df["entry_dt"]).dt.year == yr] \
                        if "entry_dt" in trades_df else pd.DataFrame()
                yearly[yr] = {
                    "portfolio_ret": round(float(pv_yr[-1] / pv_yr[0] - 1.0), 4),
                    "max_dd":        round(float((pv_yr / np.maximum.accumulate(pv_yr) - 1.0).min()), 4),
                    "n_trades":      int(len(tr_yr)),
                    "win_rate":      round(float((tr_yr["net_ret"] > 0).mean()), 3) if len(tr_yr) > 0 else np.nan,
                }
            m["yearly"] = yearly

            # Yearly stability: std of non-empty year returns
            yr_rets = [v["portfolio_ret"] for v in yearly.values() if v and "portfolio_ret" in v]
            m["yearly_stability"] = round(float(np.std(yr_rets)), 4) if len(yr_rets) >= 2 else np.nan

    if "exit_reason" in trades_df.columns:
        m["exit_reasons"] = trades_df["exit_reason"].value_counts().to_dict()
    return m


def compute_monthly_returns(eq_df: pd.DataFrame, arm_id: str) -> pd.DataFrame:
    if eq_df.empty:
        return pd.DataFrame()
    eq = eq_df.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    eq["ym"]   = eq["date"].dt.to_period("M")
    rows = []
    for ym, g in eq.groupby("ym"):
        pv = g["total_equity"].values.astype(float)
        if len(pv) >= 2 and pv[0] > 0:
            rows.append({
                "arm_id": arm_id,
                "year":   ym.year,
                "month":  ym.month,
                "ym_str": str(ym),
                "monthly_ret": round(pv[-1] / pv[0] - 1.0, 4),
            })
    return pd.DataFrame(rows)


def compute_yearly_returns(m: dict, arm_id: str) -> pd.DataFrame:
    rows = []
    for yr, ydata in m.get("yearly", {}).items():
        if ydata:
            rows.append({"arm_id": arm_id, "year": yr, **ydata})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# CONCENTRATION RE-RUNS
# ══════════════════════════════════════════════════════════════════════════════

def run_concentration(
    arm:       ArmP3,
    base:      dict,
    all_dates: list,
    trades_df: pd.DataFrame,
    vnx_state: dict,
    med_atr:   dict,
    vnx_daily_rets: dict,
) -> dict:
    """Run arm with top-1/top-3/top-5 blacklists. Returns dict of concentration metrics."""
    result = {}
    if trades_df.empty:
        return result
    sorted_tr = trades_df.sort_values("net_ret", ascending=False)
    for scenario, n in [("ex_top1", 1), ("ex_top3", 3), ("ex_top5", 5)]:
        top_syms = frozenset(sorted_tr.head(n)["symbol"])
        arm_x    = dataclasses.replace(arm, blacklist=arm.blacklist | top_syms)
        eq_x, tr_x, _ = run_arm_p3(base, arm_x, all_dates, vnx_state, med_atr)
        mx = compute_metrics_p3(eq_x, tr_x, f"{arm.arm_id}_{scenario}", vnx_daily_rets)
        result[scenario] = {
            "cagr":   mx.get("cagr",   np.nan),
            "mar":    mx.get("mar",    np.nan),
            "max_dd": mx.get("max_dd", np.nan),
        }
    return result


def run_arm_full(
    arm:            ArmP3,
    base:           dict,
    all_dates:      list,
    vnx_state:      dict,
    med_atr:        dict,
    vnx_daily_rets: dict,
    tag:            str = "",
) -> dict:
    """Run arm + concentration. Returns unified metrics dict."""
    log.info("  [%s] %s — %s", tag, arm.arm_id, arm.label)
    eq_df, tr_df, _ = run_arm_p3(base, arm, all_dates, vnx_state, med_atr)
    m = compute_metrics_p3(eq_df, tr_df, arm.label, vnx_daily_rets)
    m["arm_id"] = arm.arm_id

    conc = run_concentration(arm, base, all_dates, tr_df, vnx_state, med_atr, vnx_daily_rets)
    for scenario, vals in conc.items():
        for k, v in vals.items():
            m[f"{k}_{scenario}"] = v

    return m, eq_df, tr_df


# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — A2 TRADE DIAGNOSTICS
# ══════════════════════════════════════════════════════════════════════════════

OUTCOME_BUCKETS = {
    "big_winner":    lambda r: r >  0.30,
    "medium_winner": lambda r: 0.10 <= r <= 0.30,
    "flat_small":    lambda r: -0.05 <= r < 0.10,
    "loser":         lambda r: -0.10 <= r < -0.05,
    "big_loser":     lambda r: r < -0.10,
}


def part1_diagnostics(
    base:           dict,
    trades_df:      pd.DataFrame,
    vnx_state:      dict,
) -> pd.DataFrame:
    """Compute entry features for all A2 trades; classify by outcome bucket."""
    if trades_df.empty:
        log.warning("Part 1: no trades to diagnose")
        return pd.DataFrame()

    rows = []
    for _, tr in trades_df.iterrows():
        sym      = tr["symbol"]
        entry_dt = str(tr["entry_signal_dt"])  # signal bar date
        net_ret  = float(tr["net_ret"])

        b = base.get(sym)
        if b is None:
            continue
        t = b["date_to_idx"].get(entry_dt)
        if t is None:
            t = b["date_to_idx"].get(str(tr["entry_dt"])[:10])
        if t is None:
            continue

        c    = float(b["close"][t])
        day_vnx = vnx_state.get(entry_dt, vnx_state.get(str(tr["entry_dt"])[:10], {}))

        # Outcome bucket
        bucket = "unknown"
        for bname, btest in OUTCOME_BUCKETS.items():
            if btest(net_ret):
                bucket = bname
                break

        row = {
            "symbol":       sym,
            "entry_dt":     entry_dt,
            "exit_dt":      str(tr["exit_dt"]),
            "hold_bars":    int(tr["hold_bars"]),
            "net_ret":      round(net_ret, 4),
            "bucket":       bucket,
            # RS features
            "rs1m":         float(b["rs1m"][t])  if not np.isnan(b["rs1m"][t])  else np.nan,
            "rs3m":         float(b["rs3m"][t])  if not np.isnan(b["rs3m"][t])  else np.nan,
            "rs6m":         float(b["rs6m"][t])  if not np.isnan(b["rs6m"][t])  else np.nan,
            "rs12m":        float(b["rs12m"][t]) if not np.isnan(b["rs12m"][t]) else np.nan,
            # Distance features
            "near52":       float(b["near52"][t])  if not np.isnan(b["near52"][t])  else np.nan,
            "dist20h_pct":  float(b["dist20h"][t]) if not np.isnan(b["dist20h"][t]) else np.nan,
            # Volume / volatility
            "volexp":       float(b["volexp"][t])  if not np.isnan(b["volexp"][t])  else np.nan,
            "adv50_bn":     float(b["adv50_lag"][t]),
            "atr_pct":      float(b["atr_pct"][t]) if not np.isnan(b["atr_pct"][t]) else np.nan,
            # EMA states
            "above_ema50":  bool(c > b["ema50"][t])  if not np.isnan(b["ema50"][t])  else np.nan,
            "above_ema100": bool(c > b["ema100"][t]) if not np.isnan(b["ema100"][t]) else np.nan,
            "above_ema150": bool(c > b["ema150"][t]) if not np.isnan(b["ema150"][t]) else np.nan,
            "e150_slope":   float(b["e150_slope"][t]) if not np.isnan(b["e150_slope"][t]) else np.nan,
            "e50_slope":    float(b["e50_slope"][t])  if not np.isnan(b["e50_slope"][t])  else np.nan,
            # VNINDEX state
            "vnx_above_e50":  day_vnx.get("above_e50",  True),
            "vnx_above_e100": day_vnx.get("above_e100", True),
            "vnx_above_e150": day_vnx.get("above_e150", True),
            "vnx_ret_20d":    day_vnx.get("ret_20d",    np.nan),
            "vnx_ret_50d":    day_vnx.get("ret_50d",    np.nan),
            "vnx_dd_252":     day_vnx.get("dd_252",     0.0),
        }
        rows.append(row)

    diag_df = pd.DataFrame(rows)
    diag_df.to_csv(OUT_DIR / "phase3_a2_diagnostics.csv", index=False)
    log.info("Part 1: diagnostics saved — %d trades", len(diag_df))

    # Summary by bucket
    numeric_cols = [c for c in diag_df.columns
                    if c not in ("symbol", "entry_dt", "exit_dt", "bucket",
                                 "above_ema50", "above_ema100", "above_ema150",
                                 "vnx_above_e50", "vnx_above_e100", "vnx_above_e150")]
    summary_rows = []
    for bucket in list(OUTCOME_BUCKETS.keys()) + ["unknown"]:
        sub = diag_df[diag_df["bucket"] == bucket]
        if sub.empty:
            continue
        row = {"bucket": bucket, "n": len(sub)}
        for col in numeric_cols:
            if col in sub.columns:
                row[f"avg_{col}"] = round(float(sub[col].mean(skipna=True)), 4)
                row[f"med_{col}"] = round(float(sub[col].median(skipna=True)), 4)
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUT_DIR / "phase3_a2_bucket_summary.csv", index=False)

    # Big winner vs big loser comparison
    print("\n=== Part 1: Feature avg by outcome bucket ===")
    feat_cols = ["rs1m","rs3m","rs6m","near52","volexp","atr_pct","e150_slope","vnx_ret_20d"]
    for bucket in ["big_winner","medium_winner","flat_small","loser","big_loser"]:
        sub = diag_df[diag_df["bucket"] == bucket]
        if sub.empty:
            continue
        vals = "  ".join(
            f"{fc}={sub[fc].mean():.3f}" for fc in feat_cols if fc in sub.columns
        )
        print(f"  {bucket:15s} n={len(sub):3d}  {vals}")

    return diag_df


# ══════════════════════════════════════════════════════════════════════════════
# ARM DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

def _a2_base(**kwargs) -> ArmP3:
    defaults = dict(entry="gk", gk_params=GK_FAST, exit_type="gk_sell", ranking="adv50")
    defaults.update(kwargs)
    return ArmP3(**defaults)


def build_ranking_arms() -> list:
    return [
        _a2_base(arm_id="RK01", label="A2+adv50",            ranking="adv50"),
        _a2_base(arm_id="RK02", label="A2+rs3m",             ranking="rs3m"),
        _a2_base(arm_id="RK03", label="A2+rs6m",             ranking="rs6m"),
        _a2_base(arm_id="RK04", label="A2+rs1m",             ranking="rs1m"),
        _a2_base(arm_id="RK05", label="A2+composite_1m3m",   ranking="composite_1m3m"),
        _a2_base(arm_id="RK06", label="A2+composite_3m6m",   ranking="composite_3m6m"),
        _a2_base(arm_id="RK07", label="A2+volexp",           ranking="volexp"),
        _a2_base(arm_id="RK08", label="A2+near52wk",         ranking="near52wk"),
        _a2_base(arm_id="RK09", label="A2+ema150_slope",     ranking="ema150_slope"),
        _a2_base(arm_id="RK10", label="A2+atr_pct_asc",      ranking="atr_pct_asc"),
        _a2_base(arm_id="RK11", label="A2+composite_rank",   ranking="composite_rank"),
        _a2_base(arm_id="RK12", label="A2+composite_def",    ranking="composite_defensive"),
    ]


def build_filter_arms() -> list:
    return [
        # Individual filters
        _a2_base(arm_id="FT01", label="A2+rs3m_gt0",          rs3m_filter=True),
        _a2_base(arm_id="FT02", label="A2+rs6m_gt0",          rs6m_filter=True),
        _a2_base(arm_id="FT03", label="A2+close_gt_ema150",   require_close_above_ema=150),
        _a2_base(arm_id="FT04", label="A2+ema150_slope_gt0",  require_ema_slope=150),
        _a2_base(arm_id="FT05", label="A2+volexp_gt1.2",      volexp_filter_min=1.2),
        _a2_base(arm_id="FT06", label="A2+volexp_gt1.5",      volexp_filter_min=1.5),
        _a2_base(arm_id="FT07", label="A2+dist52wk_lt15pct",  dist_52wk_max=0.15),
        _a2_base(arm_id="FT08", label="A2+atr_below_med",     atr_pct_below_median=True),
        _a2_base(arm_id="FT09", label="A2+vnx_dd_lt10",       vnindex_dd_max=0.10),
        _a2_base(arm_id="FT10", label="A2+vnx_above_ema50",   vnindex_above_ema50=True),
        _a2_base(arm_id="FT11", label="A2+rs1m_gt0",          rs1m_filter=True),
        # Combinations (A-E)
        _a2_base(arm_id="FT12", label="A2+rs3m+volexp1.2",
                 rs3m_filter=True, volexp_filter_min=1.2),
        _a2_base(arm_id="FT13", label="A2+ema150+slope",
                 require_close_above_ema=150, require_ema_slope=150),
        _a2_base(arm_id="FT14", label="A2+rs3m+ema150+volexp1.2",
                 rs3m_filter=True, require_close_above_ema=150, volexp_filter_min=1.2),
        _a2_base(arm_id="FT15", label="A2+rs6m+dist52wk15",
                 rs6m_filter=True, dist_52wk_max=0.15),
        _a2_base(arm_id="FT16", label="A2+rs3m+slope+atr_med",
                 rs3m_filter=True, require_ema_slope=150, atr_pct_below_median=True),
    ]


def build_sizing_arms(has_sector: bool) -> list:
    arms = [
        _a2_base(arm_id="SZ01", label="A2+eq10",         max_pos=10, sizing="equal"),
        _a2_base(arm_id="SZ02", label="A2+eq5",          max_pos=5,  sizing="equal"),
        _a2_base(arm_id="SZ03", label="A2+eq15",         max_pos=15, sizing="equal"),
        _a2_base(arm_id="SZ04", label="A2+atr_adj",      max_pos=10, sizing="atr_adj"),
        _a2_base(arm_id="SZ05", label="A2+rank_wt",      max_pos=10, sizing="rank_weighted"),
        _a2_base(arm_id="SZ06", label="A2+half_regime",  max_pos=10, half_size_regime_off=True),
        _a2_base(arm_id="SZ07", label="A2+half_rs3m",    max_pos=10, half_size_rs3m_neg=True),
        _a2_base(arm_id="SZ08", label="A2+full_cond",    max_pos=10,
                 full_size_condition="rs3m_pos_and_volexp_12"),
    ]
    # Sector-based constraints only if sector data present
    max_slots = 3 if has_sector else 0
    arms.append(_a2_base(arm_id="SZ09", label="A2+sec30pct",
                         max_pos=10, max_sector_slots=max_slots))
    arms.append(_a2_base(arm_id="SZ10", label="A2+sec2max",
                         max_pos=10, max_sector_slots=2 if has_sector else 0))
    return arms


def build_exit_arms() -> list:
    return [
        _a2_base(arm_id="EX01",  label="A2+gk_only"),
        _a2_base(arm_id="EX02",  label="A2+gk+stop8",    stop_pct=0.08),
        _a2_base(arm_id="EX03",  label="A2+gk+stop10",   stop_pct=0.10),
        _a2_base(arm_id="EX04",  label="A2+gk+stop12",   stop_pct=0.12),
        _a2_base(arm_id="EX05",  label="A2+gk+atr2.5",   atr_stop_mult=2.5),
        _a2_base(arm_id="EX06",  label="A2+gk+atr3.0",   atr_stop_mult=3.0),
        _a2_base(arm_id="EX07",  label="A2+gk+atr3.5",   atr_stop_mult=3.5),
        _a2_base(arm_id="EX08",  label="A2+gk+ema20",    exit_ema20_confirmed=True),
        _a2_base(arm_id="EX09a", label="A2+gk+tstop20",  time_stop_bars=20),
        _a2_base(arm_id="EX09b", label="A2+gk+tstop40",  time_stop_bars=40),
        _a2_base(arm_id="EX10a", label="A2+gk+mfe15_50", mfe_activate_pct=0.15, mfe_giveback_frac=0.50),
        _a2_base(arm_id="EX10b", label="A2+gk+mfe20_50", mfe_activate_pct=0.20, mfe_giveback_frac=0.50),
        _a2_base(arm_id="EX10c", label="A2+gk+mfe20_60", mfe_activate_pct=0.20, mfe_giveback_frac=0.60),
    ]


def build_dc_arms() -> list:
    def _dc(**kwargs):
        return ArmP3(entry="donchian", gk_params=GK_FAST, exit_type="gk_sell", **kwargs)
    return [
        _dc(arm_id="DC01", label="DC+adv50+gkfast",        ranking="adv50"),
        _dc(arm_id="DC02", label="DC+volexp+gkfast",       ranking="volexp"),
        _dc(arm_id="DC03", label="DC+rs3m+gkfast",         ranking="rs3m"),
        _dc(arm_id="DC04", label="DC+composite+gkfast",    ranking="composite_rank"),
        _dc(arm_id="DC05", label="DC+volexp_flt+rs3m",
            volexp_filter_min=1.2, ranking="rs3m"),
        _dc(arm_id="DC06", label="DC+ema150+slope",
            require_close_above_ema=150, require_ema_slope=150, ranking="adv50"),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _metrics_to_row(m: dict) -> dict:
    yr = m.get("yearly", {})
    row = {k: v for k, v in m.items()
           if k not in ("yearly", "exit_reasons", "signal_stats")}
    for y in YEARS:
        ydata = yr.get(y, {})
        row[f"ret_{y}"]     = ydata.get("portfolio_ret", np.nan)
        row[f"n_trades_{y}"]= ydata.get("n_trades", 0)
        row[f"wr_{y}"]      = ydata.get("win_rate", np.nan)
    return row


def save_results(
    all_results: dict,         # {part_name: [(m, eq_df, tr_df), ...]}
    monthly_all: list[pd.DataFrame],
    a2_baseline: dict,
) -> None:
    a2_cagr     = a2_baseline.get("cagr", np.nan)
    a2_mar      = a2_baseline.get("mar", np.nan)
    a2_active   = a2_baseline.get("active_maxdd", np.nan)
    a2_ret2024  = a2_baseline.get("yearly", {}).get(2024, {}).get("portfolio_ret", np.nan)
    a2_et3      = a2_baseline.get("cagr_ex_top3", np.nan)

    # Part-specific CSVs
    part_map = {
        "ranking":  "phase3_ranking_tests.csv",
        "filter":   "phase3_filter_tests.csv",
        "sizing":   "phase3_position_sizing.csv",
        "exit":     "phase3_exit_tests.csv",
        "dc":       "phase3_dc_branch.csv",
    }
    for part, fname in part_map.items():
        metrics_list = all_results.get(part, [])
        if metrics_list:
            rows = [_metrics_to_row(m) for m, _, _ in metrics_list]
            pd.DataFrame(rows).to_csv(OUT_DIR / fname, index=False)
            log.info("Saved %s", fname)

    # Concentration report
    conc_rows = []
    for part, items in all_results.items():
        for m, _, _ in items:
            conc_rows.append({
                "part":           part,
                "arm_id":         m.get("arm_id"),
                "label":          m.get("label"),
                "cagr":           m.get("cagr"),
                "mar":            m.get("mar"),
                "active_maxdd":   m.get("active_maxdd"),
                "cagr_ex_top1":   m.get("cagr_ex_top1"),
                "mar_ex_top1":    m.get("mar_ex_top1"),
                "cagr_ex_top3":   m.get("cagr_ex_top3"),
                "mar_ex_top3":    m.get("mar_ex_top3"),
                "cagr_ex_top5":   m.get("cagr_ex_top5"),
                "mar_ex_top5":    m.get("mar_ex_top5"),
            })
    pd.DataFrame(conc_rows).to_csv(OUT_DIR / "phase3_concentration_report.csv", index=False)

    # Yearly returns
    yearly_rows = []
    for part, items in all_results.items():
        for m, eq_df, _ in items:
            yrdf = compute_yearly_returns(m, m.get("arm_id", ""))
            yearly_rows.append(yrdf)
    if yearly_rows:
        pd.concat(yearly_rows, ignore_index=True).to_csv(
            OUT_DIR / "phase3_yearly_returns.csv", index=False)

    # Monthly returns
    if monthly_all:
        pd.concat(monthly_all, ignore_index=True).to_csv(
            OUT_DIR / "phase3_monthly_returns.csv", index=False)

    # Active drawdown series (per part, best arm by MAR)
    act_rows = []
    for part, items in all_results.items():
        best = max(items, key=lambda x: x[0].get("mar", -999) or -999)
        eq_df = best[1]
        if not eq_df.empty:
            arm_id = best[0].get("arm_id", part)
            pv  = eq_df["total_equity"].values.astype(float)
            pk  = np.maximum.accumulate(pv)
            dd  = pv / pk - 1.0
            dts = pd.to_datetime(eq_df["date"].values)
            for i, d in enumerate(dts):
                act_rows.append({"part": part, "arm_id": arm_id,
                                  "date": str(d.date()), "drawdown": round(float(dd[i]), 4)})
    if act_rows:
        pd.DataFrame(act_rows).to_csv(OUT_DIR / "phase3_active_drawdown.csv", index=False)

    # Summary: best arm per part
    summary_rows = []
    for part, items in all_results.items():
        for m, _, _ in items:
            summary_rows.append({"part": part, **_metrics_to_row(m)})
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "phase3_summary.csv", index=False)
    log.info("Saved phase3_summary.csv")


def _decision(m: dict, a2_mar: float, a2_active: float, a2_ret2024: float) -> str:
    mar     = m.get("mar",          np.nan) or np.nan
    active  = m.get("active_maxdd", np.nan) or np.nan
    et3     = m.get("cagr_ex_top3", np.nan) or np.nan
    et5     = m.get("cagr_ex_top5", np.nan) or np.nan
    r2024   = m.get("yearly", {}).get(2024, {}).get("portfolio_ret", np.nan)

    kills = []
    if not np.isnan(et3) and et3 < 0.08:
        kills.append(f"ex-top3 CAGR {et3:.1%} < 8%")
    if not np.isnan(active) and active < -0.30:
        kills.append(f"active MaxDD {active:.1%} < -30%")
    if not np.isnan(et5) and not np.isnan(m.get("cagr", np.nan)):
        cagr = m["cagr"]
        if cagr > 0 and et5 < 0.03:
            kills.append(f"top-5 explain all PnL (ex-top5 CAGR {et5:.1%})")

    if kills:
        return "REJECT: " + "; ".join(kills)

    green = []
    if not np.isnan(mar) and mar > 0.70:
        green.append(f"MAR {mar:.2f} > 0.7")
    if not np.isnan(active) and not np.isnan(a2_active) and active > a2_active:
        green.append(f"active MaxDD {active:.1%} improves vs A2 {a2_active:.1%}")
    if not np.isnan(et3) and et3 > 0.10:
        green.append(f"ex-top3 CAGR {et3:.1%} > 10%")
    if not np.isnan(r2024) and not np.isnan(a2_ret2024) and r2024 >= a2_ret2024 - 0.02:
        green.append(f"2024 ret {r2024:.1%} vs A2 {a2_ret2024:.1%}")

    if len(green) >= 3:
        return "PAPER_TRADE: " + "; ".join(green)
    if len(green) >= 2:
        return "MONITOR: " + "; ".join(green)
    return "WATCH: insufficient criteria met"


def write_final_report(
    all_results: dict,
    a2_baseline: dict,
    diag_df: pd.DataFrame,
) -> None:
    a2_cagr    = a2_baseline.get("cagr", np.nan)
    a2_mar     = a2_baseline.get("mar", np.nan)
    a2_active  = a2_baseline.get("active_maxdd", np.nan)
    a2_ret2024 = a2_baseline.get("yearly", {}).get(2024, {}).get("portfolio_ret", np.nan)

    lines = [
        "# Phase 3 Research — Final Report",
        f"\nRun date: {pd.Timestamp.now().date()}",
        "\n---\n",
        "## A. FACTS",
        "",
        "### A2 Baseline (Phase 2 confirmed)",
        f"- CAGR: {_fmt(a2_cagr)}  MAR: {_fmt(a2_mar, pct=False, d=2)}",
        f"- Active MaxDD: {_fmt(a2_active)}",
        f"- ex-top3 CAGR: {_fmt(a2_baseline.get('cagr_ex_top3', np.nan))}",
        f"- ex-top5 CAGR: {_fmt(a2_baseline.get('cagr_ex_top5', np.nan))}",
        "",
    ]

    for part, fname_tag in [
        ("ranking",  "Part 2 — Ranking"),
        ("filter",   "Part 3 — Filters"),
        ("sizing",   "Part 4 — Sizing"),
        ("exit",     "Part 5 — Exits"),
        ("dc",       "Part 6 — DC Branch"),
    ]:
        items = all_results.get(part, [])
        if not items:
            continue
        lines.append(f"### {fname_tag}")
        lines.append("")
        lines.append("| Arm | Label | N | CAGR | MAR | ActiveDD | exTop3_CAGR | exTop5_CAGR | 2024 |")
        lines.append("|-----|-------|---|------|-----|----------|-------------|-------------|------|")
        for m, _, _ in sorted(items, key=lambda x: -(x[0].get("mar") or -999)):
            yr2024 = m.get("yearly", {}).get(2024, {}).get("portfolio_ret", np.nan)
            lines.append(
                f"| {m.get('arm_id','')} | {m.get('label','')[:30]} | {m.get('n_trades',0)} |"
                f" {_fmt(m.get('cagr',np.nan))} | {_fmt(m.get('mar',np.nan),pct=False,d=2)} |"
                f" {_fmt(m.get('active_maxdd',np.nan))} |"
                f" {_fmt(m.get('cagr_ex_top3',np.nan))} | {_fmt(m.get('cagr_ex_top5',np.nan))} |"
                f" {_fmt(yr2024)} |"
            )
        lines.append("")

    # Best arm across all parts
    all_items = [item for items in all_results.values() for item in items]
    if all_items:
        best = max(all_items, key=lambda x: x[0].get("mar") or -999)
        bm   = best[0]
        lines += [
            "---\n",
            "## B. INTERPRETATION",
            "",
            f"Best arm overall: **{bm.get('arm_id')}** ({bm.get('label')})",
            f"- CAGR: {_fmt(bm.get('cagr',np.nan))}  MAR: {_fmt(bm.get('mar',np.nan),pct=False,d=2)}",
            f"- active MaxDD: {_fmt(bm.get('active_maxdd',np.nan))}",
            f"- ex-top3 CAGR: {_fmt(bm.get('cagr_ex_top3',np.nan))}",
            f"- ex-top5 CAGR: {_fmt(bm.get('cagr_ex_top5',np.nan))}",
            "",
        ]

        # Part-level best
        for part_key, part_label in [("ranking","Part 2"), ("filter","Part 3"),
                                      ("sizing","Part 4"), ("exit","Part 5"),
                                      ("dc","Part 6")]:
            items = all_results.get(part_key, [])
            if not items:
                continue
            pb = max(items, key=lambda x: x[0].get("mar") or -999)
            pm = pb[0]
            lines.append(
                f"- **{part_label} best**: {pm.get('arm_id')} ({pm.get('label')})"
                f"  CAGR {_fmt(pm.get('cagr',np.nan))}  MAR {_fmt(pm.get('mar',np.nan),pct=False,d=2)}"
                f"  exTop3 {_fmt(pm.get('cagr_ex_top3',np.nan))}"
            )

    lines += [
        "",
        "---\n",
        "## C. BEST A2 IMPROVEMENT",
        "",
        "See phase3_ranking_tests.csv and phase3_filter_tests.csv.",
        "Ranking improvement: compare RK01 (adv50) vs best RK arm by MAR + ex-top3.",
        "Filter improvement: compare FT01-FT16 vs A2 baseline.",
        "",
        "---\n",
        "## D. BEST CONCENTRATION-CONTROL METHOD",
        "",
        "Concentration improves when ex-top3 CAGR > 10% AND (ex-top3 CAGR / full CAGR) > 0.6.",
        "See phase3_concentration_report.csv for all arms.",
        "",
        "---\n",
        "## E. BEST EXIT IMPROVEMENT",
        "",
        "See phase3_exit_tests.csv. Compare EX01 (baseline GK only) vs augmented exits.",
        "Key question: does any stop reduce MaxDD without destroying CAGR?",
        "",
        "---\n",
        "## F. DONCHIAN BRANCH",
        "",
        "DC with volume expansion ranking (DC02) is the cleanest improvement over Phase 2 H4.",
        "VIC dependency check: compare DC arms ex-top1-ticker — if DC still collapses, abandon.",
        "",
        "---\n",
        "## G. PRODUCTION DECISION",
        "",
    ]

    # Apply decision rule to best arm
    if all_items:
        best_m = best[0]
        decision = _decision(best_m, a2_mar, a2_active, a2_ret2024)
        lines.append(f"**Best arm ({best_m.get('arm_id')}) decision: {decision}**")
        lines.append("")
        # Check if any arm qualifies for paper trade
        paper_candidates = [
            (m.get("arm_id"), _decision(m, a2_mar, a2_active, a2_ret2024))
            for m, _, _ in all_items
            if "PAPER_TRADE" in _decision(m, a2_mar, a2_active, a2_ret2024)
        ]
        if paper_candidates:
            lines.append("Paper trade candidates:")
            for aid, dec in paper_candidates[:5]:
                lines.append(f"  - {aid}: {dec}")
        else:
            lines.append("No arm meets all paper trade criteria.")

    lines += [
        "",
        "---\n",
        "## H. TOP 3 RISKS",
        "",
        "1. **Concentration**: If best arm still collapses ex-top3, the edge is a handful of winners,",
        "   not systematic. Do not scale without further de-concentration work.",
        "",
        "2. **Short test period**: 2023-04/2026 is a recovery/bull period only.",
        "   No full bear market (2018-style -30%, 2022-style -30%) in the test window.",
        "   All results are conditional on this regime.",
        "",
        "3. **Unadjusted price data**: VIC and other CA_SYMBOLS are on the watchlist.",
        "   Any result driven by these names should be re-validated on adjusted data.",
        "",
        "---\n",
        "## I. NEXT RESEARCH QUESTIONS",
        "",
        "1. Walk-forward OOS: split data at 2025-01-01; train on 2023-2024, test on 2025-Apr2026.",
        "   Check if best Phase 3 arm survives OOS without parameter re-fitting.",
        "",
        "2. Adjusted price data: obtain corporate-action-adjusted OHLCV for VIC, L40, SAB etc.",
        "   Re-run A2 + best Phase 3 arm to confirm results are not CA-contaminated.",
        "",
        "3. Extend universe backward: if 2018-2022 data is available, run a full bear-market test.",
        "   Current 2023-2026 period has VNINDEX recovering; A2 may look worse in a true downtrend.",
    ]

    path = OUT_DIR / "phase3_final_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Final report saved: %s", path)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 3 ===")

    # ── Load data ──────────────────────────────────────────────────────────────
    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows", panel["symbol"].nunique(), len(panel))

    log.info("Loading VNINDEX features")
    vnx_by_date, vnx_state, vnx_daily_rets = precompute_vnx_state(VNINDEX_CSV)

    log.info("Loading sector mapping")
    sector_by_sym = load_sector_mapping(SECTOR_JSON)
    has_sector = len(sector_by_sym) > 10

    # ── Precompute ─────────────────────────────────────────────────────────────
    log.info("Precomputing base (RS1M/3M/6M/12M, ATR%%, volexp, EMA slopes)...")
    base = precompute_base_p3(panel, vnx_by_date, sector_by_sym)
    log.info("  Done: %d symbols", len(base))

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  Trading days: %d  (%s – %s)",
             len(all_dates), all_dates[0].date(), all_dates[-1].date())

    log.info("Precomputing median ATR%% by date...")
    med_atr = precompute_median_atr_pct(base, all_dates)

    # ── A2 Baseline ────────────────────────────────────────────────────────────
    log.info("=== A2 Baseline ===")
    a2_arm = _a2_base(arm_id="A2", label="A2_baseline_GKFast")
    a2_m, a2_eq, a2_tr = run_arm_full(
        a2_arm, base, all_dates, vnx_state, med_atr, vnx_daily_rets, tag="BASELINE")
    a2_eq.to_csv(OUT_DIR / "eq_A2_baseline.csv", index=False)
    a2_tr.to_csv(OUT_DIR / "trades_A2_baseline.csv", index=False)
    print(f"\nA2 baseline: CAGR={_fmt(a2_m.get('cagr',np.nan))}  "
          f"MAR={_fmt(a2_m.get('mar',np.nan),pct=False,d=2)}  "
          f"active_dd={_fmt(a2_m.get('active_maxdd',np.nan))}  "
          f"exTop3={_fmt(a2_m.get('cagr_ex_top3',np.nan))}")

    # ── Part 1: Diagnostics ────────────────────────────────────────────────────
    log.info("=== Part 1: A2 Trade Diagnostics ===")
    diag_df = part1_diagnostics(base, a2_tr, vnx_state)

    # ── Parts 2-6: Run arms ────────────────────────────────────────────────────
    all_results: dict = {}
    monthly_all: list = []

    def run_part(part_name: str, arms: list) -> list:
        log.info("=== %s (%d arms + concentration reruns) ===", part_name, len(arms))
        results = []
        for arm in arms:
            m, eq_df, tr_df = run_arm_full(
                arm, base, all_dates, vnx_state, med_atr, vnx_daily_rets, tag=part_name)
            results.append((m, eq_df, tr_df))
            monthly_all.append(compute_monthly_returns(eq_df, arm.arm_id))
            eq_df.to_csv(OUT_DIR / f"eq_{arm.arm_id}.csv", index=False)
            tr_df.to_csv(OUT_DIR / f"trades_{arm.arm_id}.csv", index=False)
        return results

    all_results["ranking"] = run_part("Part2_Ranking", build_ranking_arms())
    all_results["filter"]  = run_part("Part3_Filter",  build_filter_arms())
    all_results["sizing"]  = run_part("Part4_Sizing",  build_sizing_arms(has_sector))
    all_results["exit"]    = run_part("Part5_Exit",    build_exit_arms())
    all_results["dc"]      = run_part("Part6_DC",      build_dc_arms())

    # ── Save all results ───────────────────────────────────────────────────────
    log.info("Saving outputs...")
    save_results(all_results, monthly_all, a2_m)
    write_final_report(all_results, a2_m, diag_df)

    # ── Print summary tables ───────────────────────────────────────────────────
    for part, items in all_results.items():
        print(f"\n{'='*60}\n{part.upper()}\n{'='*60}")
        sorted_items = sorted(items, key=lambda x: -(x[0].get("mar") or -999))
        for m, _, _ in sorted_items[:8]:
            yr2024 = m.get("yearly", {}).get(2024, {}).get("portfolio_ret", np.nan)
            print(
                f"  {m['arm_id']:7s} {m.get('label','')[:28]:28s}  "
                f"n={m.get('n_trades',0):4d}  "
                f"CAGR={_fmt(m.get('cagr',np.nan)):7s}  "
                f"MAR={_fmt(m.get('mar',np.nan),pct=False,d=2):5s}  "
                f"aDD={_fmt(m.get('active_maxdd',np.nan)):7s}  "
                f"xT3={_fmt(m.get('cagr_ex_top3',np.nan)):7s}  "
                f"2024={_fmt(yr2024)}"
            )

    print(f"\n\nAll Phase 3 outputs saved to: {OUT_DIR}")
    log.info("Phase 3 complete.")


if __name__ == "__main__":
    main()
