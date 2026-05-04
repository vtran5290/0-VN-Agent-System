#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GK Trend Ribbon Backtest -- Phase 1 (signal validation) + Phase 2 (optimization)

Source of truth: AFL section 02_GK_TREND_RIBBON from SMC Chart.
Signal logic reproduced exactly from the prompt specification.

Phase 1: reproduce GK signals exactly, validate on 5 tickers.
Phase 2: parameter grid + entry-filter / exit-rule / regime comparisons.

Key invariants enforced throughout:
  - No future bars: all lookbacks use only past data.
  - ADV50 lagged: eligibility on day t uses data through t-1 only.
  - Entry/exit execute at next trading day open (t+1 open).
  - PREPARE signal is excluded entirely from historical backtest.
  - Zero-volume / zero-open bars are treated as non-tradable.
  - Costs deducted both entry and exit.
"""
from __future__ import annotations

import io
import logging
import sys
from itertools import product
from pathlib import Path

# Force UTF-8 output on Windows consoles
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

# -- Paths ---------------------------------------------------------------------
CACHE_PARQUET = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_cache.parquet"
VNINDEX_CSV   = REPO / "data" / "fireant_exports" / "index_ohlcv" / "market" / "VNINDEX.csv"
OUT_DIR       = REPO / "data" / "research" / "gk_trend_ribbon"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -- Global constants ----------------------------------------------------------
START_DATE   = pd.Timestamp("2023-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
ADV50_MIN_BN = 2.0      # billion VND
FEE_BPS      = 25.0     # basis points per side
SLIP_BPS     = 10.0     # basis points per side
MAX_POS      = 10

PHASE1_TICKERS = ["FPT", "HPG", "VHM", "TCH", "NVL"]
YEARS          = [2023, 2024, 2025, 2026]

EXCL_SYMBOLS = {"VPL"}   # excluded per project convention


# ==============================================================================
# MATH PRIMITIVES
# ==============================================================================

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    """Standard EMA, alpha=2/(span+1). Matches AFL EMA() and existing codebase."""
    alpha = 2.0 / (span + 1)
    out = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = arr[i]
        if np.isnan(v):
            continue
        prev = out[i - 1] if i > 0 and not np.isnan(out[i - 1]) else np.nan
        out[i] = v if np.isnan(prev) else alpha * v + (1.0 - alpha) * prev
    return out


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """
    Wilder ATR matching AFL ATR(), alpha=1/n.
    Seeds with simple mean of first n true-range values.
    """
    # True range: first bar uses H-L only (no previous close)
    tr = np.empty(len(close))
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i]  - close[i - 1]),
        )
    alpha = 1.0 / n
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1] = float(np.mean(tr[:n]))
        for i in range(n, len(tr)):
            out[i] = alpha * tr[i] + (1.0 - alpha) * out[i - 1]
    return out


def _adv50_lagged(value: np.ndarray) -> np.ndarray:
    """
    ADV50 lagged by 1 bar.
    adv50_lagged[t] = mean(value[t-50 : t]) / 1e9
    Uses 50 bars strictly BEFORE bar t — no leakage on eligibility.
    First valid at t=50.
    """
    out = np.full(len(value), np.nan)
    for i in range(50, len(value)):
        out[i] = float(np.mean(value[i - 50: i])) / 1e9
    return out


# ==============================================================================
# GK SIGNAL COMPUTATION  (exact AFL replication)
# ==============================================================================

class GKParams:
    __slots__ = ("gk_len", "gk_mult", "gk_atr_len", "gk_conf")

    def __init__(self, gk_len=200, gk_mult=2.0, gk_atr_len=21, gk_conf=2):
        self.gk_len     = int(gk_len)
        self.gk_mult    = float(gk_mult)
        self.gk_atr_len = int(gk_atr_len)
        self.gk_conf    = int(gk_conf)

    def key(self) -> str:
        return f"L{self.gk_len}_M{self.gk_mult}_A{self.gk_atr_len}_C{self.gk_conf}"

    def __repr__(self):
        return (f"GKParams(len={self.gk_len}, mult={self.gk_mult}, "
                f"atr={self.gk_atr_len}, conf={self.gk_conf})")


def compute_gk_signals(
    close: np.ndarray,
    high:  np.ndarray,
    low:   np.ndarray,
    p: GKParams,
) -> dict:
    """
    Reproduce AFL 02_GK_TREND_RIBBON signal logic exactly.

    AFL equivalents:
      GK_Lag      = Floor((GK_Len - 1) / 2)
      GK_PastClose = Ref(C, -GK_Lag)  [filled with C where Null]
      GK_ZLInput  = C + (C - GK_PastClose)  if GK_Lag > 0 else C
      GK_ZL       = EMA(GK_ZLInput, GK_Len)
      GK_ATR      = ATR(GK_ATRLen)   [Wilder]
      GK_Upper    = GK_ZL + GK_ATR * GK_Mult
      GK_Lower    = GK_ZL - GK_ATR * GK_Mult
      GK_ConfBack = GK_Conf - 1
      GK_Bull     = C>Upper AND C[-1]>Upper[-1] AND C[-CB]>Upper[-CB] AND ZL>ZL[-1]
      GK_Bear     = C<Lower AND C[-1]<Lower[-1] AND C[-CB]<Lower[-CB] AND ZL<ZL[-1]
      GK_Trend    = stateful 1/-1/0, forward pass
      GK_Buy      = confirmed flip to 1 (GK_RawFlip AND GK_Trend==1)
      GK_Sell     = confirmed flip to -1

    No future bars are used:
      - ZLEMA: close[t] + (close[t] - close[t-lag]) uses only t and earlier
      - ATR: Wilder smoothing from historical TR values
      - Bull/Bear: Ref(x,-k) = x[t-k], purely past
      - Trend: forward pass reads only gk_trend[t-1]
    """
    n   = len(close)
    lag = max(int((p.gk_len - 1) // 2), 0)

    # ZLEMA input: AFL fills IsNull with C (i.e. for early bars where t-lag < 0)
    past_close = np.empty(n)
    for i in range(n):
        j = i - lag
        past_close[i] = close[j] if j >= 0 else close[i]

    zl_input = close + (close - past_close) if lag > 0 else close.copy()
    gk_zl    = _ema(zl_input, p.gk_len)
    gk_atr   = _wilder_atr(high, low, close, p.gk_atr_len)
    gk_upper = gk_zl + gk_atr * p.gk_mult
    gk_lower = gk_zl - gk_atr * p.gk_mult

    # Bull / Bear — vectorised shifts
    cb = p.gk_conf - 1   # GK_ConfBack

    above = close > gk_upper   # shape (n,)
    below = close < gk_lower

    # Ref(x, -1) = x shifted right by 1
    above1 = np.concatenate([[False], above[:-1]])
    below1 = np.concatenate([[False], below[:-1]])

    # Ref(x, -cb)
    if cb <= 0:
        above_cb = above.copy()
        below_cb = below.copy()
    else:
        above_cb = np.concatenate([np.full(cb, False), above[:-cb]])
        below_cb = np.concatenate([np.full(cb, False), below[:-cb]])

    # ZL rising / falling (Ref(ZL,-1) = ZL shifted right by 1)
    zl_prev   = np.concatenate([[np.nan], gk_zl[:-1]])
    zl_rising = gk_zl > zl_prev    # NaN comparison -> False [x]
    zl_falling = gk_zl < zl_prev

    gk_bull = above   & above1  & above_cb & zl_rising
    gk_bear = below   & below1  & below_cb & zl_falling

    # Handle NaN upper/lower: if upper/lower is NaN, suppress the signal
    valid = ~np.isnan(gk_upper) & ~np.isnan(gk_lower)
    gk_bull = gk_bull & valid
    gk_bear = gk_bear & valid

    # Trend state: forward pass
    # raw = 1 where bull, -1 where bear, NaN otherwise -> forward-fill -> fill remaining with 0
    raw = np.where(gk_bull, 1.0, np.where(gk_bear, -1.0, np.nan))
    s   = pd.Series(raw).ffill().fillna(0.0).astype(int)
    gk_trend = s.values  # shape (n,)

    # AFL: GK_PrevTrend = Nz(Ref(GK_Trend, -1), 0)
    gk_prev_trend = np.zeros(n, dtype=int)
    gk_prev_trend[1:] = gk_trend[:-1]

    # Confirmed flip — historical only (PREPARE excluded by design)
    raw_flip = (gk_trend != gk_prev_trend) & (gk_trend != 0)
    gk_buy   = raw_flip & (gk_trend == 1)
    gk_sell  = raw_flip & (gk_trend == -1)

    return {
        "gk_zl":    gk_zl,
        "gk_upper": gk_upper,
        "gk_lower": gk_lower,
        "gk_bull":  gk_bull,
        "gk_bear":  gk_bear,
        "gk_trend": gk_trend,
        "gk_buy":   gk_buy,
        "gk_sell":  gk_sell,
    }


# ==============================================================================
# PHASE 1 — SIGNAL VALIDATION
# ==============================================================================

def phase1_validate(panel: pd.DataFrame, params: GKParams) -> None:
    print("\n" + "=" * 80)
    print("PHASE 1 — GK TREND RIBBON: SIGNAL VALIDATION")
    print(f"  {params}")
    print("=" * 80)
    print()
    print("VERIFICATION CHECKLIST:")
    print("  [x] No future bars: ZLEMA uses close[t-lag..t], ATR uses TR[0..t]")
    print("  [x] Bull/Bear: numpy shifts — Ref(x,-k) = x[t-k], strictly past")
    print("  [x] Trend state: pandas ffill of {bull->1, bear->-1, else hold}")
    print("  [x] ADV50 lagged: mean(value[t-50:t])/1e9 — excludes bar t")
    print("  [x] Entry: executed at open of bar t+1 after GK_BUY on bar t")
    print("  [x] Exit:  executed at open of bar t+1 after GK_SELL on bar t")
    print("  [x] PREPARE signal: not computed; not used in historical backtest")
    print("  [x] Zero-open bars: skipped as non-tradable (open <= 0)")
    print()

    lines_out = []

    for sym in PHASE1_TICKERS:
        df = panel[panel["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if df.empty:
            print(f"  {sym}: NOT IN PANEL — skip\n")
            continue

        close  = df["close"].values.astype(float)
        high   = df["high"].values.astype(float)
        low    = df["low"].values.astype(float)
        open_  = df["open"].values.astype(float)
        volume = df["volume"].values.astype(float)
        value  = df["value"].values.astype(float)
        dates  = pd.to_datetime(df["date"].values)
        n      = len(df)

        sigs     = compute_gk_signals(close, high, low, params)
        adv50_l  = _adv50_lagged(value)

        buy_idx  = set(np.where(sigs["gk_buy"])[0])
        sell_idx = set(np.where(sigs["gk_sell"])[0])
        sig_idx  = buy_idx | sell_idx

        if not sig_idx:
            print(f"  {sym}: No GK signals detected in date range\n")
            continue

        # Collect ±3 context bars around each signal
        show = set()
        for t in sig_idx:
            for k in range(max(0, t - 3), min(n, t + 4)):
                show.add(k)
        show = sorted(show)

        header = f"\n{'-'*10} {sym} ({'GK signals with ±3-bar context'}) {'-'*10}"
        print(header)
        lines_out.append(header)

        rows = []
        for i in show:
            sig_type  = "GK_BUY" if i in buy_idx else ("GK_SELL" if i in sell_idx else "")
            entry_dt  = str(dates[i + 1].date()) if i in buy_idx  and i + 1 < n else ""
            exit_dt   = str(dates[i + 1].date()) if i in sell_idx and i + 1 < n else ""
            entry_px  = round(float(open_[i + 1]), 2) if i in buy_idx  and i + 1 < n and open_[i+1] > 0 else ""
            exit_px   = round(float(open_[i + 1]), 2) if i in sell_idx and i + 1 < n and open_[i+1] > 0 else ""

            rows.append({
                "date":      str(dates[i].date()),
                "open":      round(open_[i], 2),
                "high":      round(high[i], 2),
                "low":       round(low[i], 2),
                "close":     round(close[i], 2),
                "vol_k":     int(volume[i] / 1000),
                "val_bn":    round(value[i] / 1e9, 3),
                "adv50_lag": round(adv50_l[i], 3) if not np.isnan(adv50_l[i]) else "",
                "gk_zl":    round(sigs["gk_zl"][i], 3)    if not np.isnan(sigs["gk_zl"][i]) else "",
                "gk_upper": round(sigs["gk_upper"][i], 3)  if not np.isnan(sigs["gk_upper"][i]) else "",
                "gk_lower": round(sigs["gk_lower"][i], 3)  if not np.isnan(sigs["gk_lower"][i]) else "",
                "bull": int(sigs["gk_bull"][i]),
                "bear": int(sigs["gk_bear"][i]),
                "trend": int(sigs["gk_trend"][i]),
                "signal":    sig_type,
                "entry_dt":  entry_dt,
                "entry_px":  entry_px,
                "exit_dt":   exit_dt,
                "exit_px":   exit_px,
            })

        tbl = pd.DataFrame(rows).to_string(index=False)
        print(tbl)
        lines_out.append(tbl)
        print()

    # Universe-wide signal count
    print("\n-- Universe-wide signal count (default params, ADV50 >= 2bn) --")
    total_buy = total_sell = 0
    for sym, grp in panel.groupby("symbol"):
        df = grp.sort_values("date").reset_index(drop=True)
        c  = df["close"].values.astype(float)
        h  = df["high"].values.astype(float)
        l  = df["low"].values.astype(float)
        v  = df["value"].values.astype(float)
        adv = _adv50_lagged(v)
        s   = compute_gk_signals(c, h, l, params)
        for t in np.where(s["gk_buy"])[0]:
            if not np.isnan(adv[t]) and adv[t] >= ADV50_MIN_BN:
                total_buy += 1
        total_sell += int(s["gk_sell"].sum())

    msg = (f"  GK_BUY  (ADV50-eligible): {total_buy}\n"
           f"  GK_SELL (all):            {total_sell}")
    print(msg)

    # Save Phase 1 log
    phase1_path = OUT_DIR / "gk_phase1_validation.txt"
    with open(phase1_path, "w", encoding="utf-8") as f:
        f.write(f"GK Trend Ribbon — Phase 1 Validation\n{params}\n\n")
        f.write("\n".join(lines_out))
        f.write(f"\n\n{msg}\n")
    log.info("Phase 1 log saved: %s", phase1_path)


# ==============================================================================
# PRE-COMPUTE BASE DATA (once per symbol, reused across all grid combos)
# ==============================================================================

def precompute_base(panel: pd.DataFrame) -> dict[str, dict]:
    """
    Returns dict: sym -> {dates, open, high, low, close, volume, value,
                          adv50_lag, ema10, ema20, ema50, ema100, ema150,
                          date_to_idx}
    """
    base: dict[str, dict] = {}
    for sym, grp in panel.groupby("symbol"):
        df = grp.sort_values("date").reset_index(drop=True)
        c  = df["close"].values.astype(float)
        h  = df["high"].values.astype(float)
        l  = df["low"].values.astype(float)
        o  = df["open"].values.astype(float)
        v  = df["volume"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)

        base[sym] = {
            "dates":     dts,
            "open":      o,
            "high":      h,
            "low":       l,
            "close":     c,
            "volume":    v,
            "value":     val,
            "adv50_lag": _adv50_lagged(val),
            "ema10":     _ema(c, 10),
            "ema20":     _ema(c, 20),
            "ema50":     _ema(c, 50),
            "ema100":    _ema(c, 100),
            "ema150":    _ema(c, 150),
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


# ==============================================================================
# PORTFOLIO ENGINE
# ==============================================================================

def run_portfolio(
    base:       dict[str, dict],
    vnx_by_date: pd.DataFrame,
    params:     GKParams,
    *,
    fee_bps:      float = FEE_BPS,
    slip_bps:     float = SLIP_BPS,
    max_pos:      int   = MAX_POS,
    adv50_min_bn: float = ADV50_MIN_BN,
    entry_filter: str   = "none",     # none|ema_cloud|close_ema50|close_ema100|close_ema150
    exit_rule:    str   = "gk_sell",  # gk_sell|gk_sell_or_ema10|gk_sell_or_ema20
    stop_pct:     float = 0.0,        # 0 = no hard stop
    min_hold:     int   = 0,
    regime_filter: str  = "none",     # none|vnx_ema50|vnx_ema100|vnx_both
    rank_by:      str   = "adv50",    # adv50|rs3m
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Equal-weight portfolio simulation across the pre-computed symbol universe.

    Returns
    -------
    equity_df : daily equity curve with columns [date, portfolio_value, n_pos]
    trades_df : trade log
    """
    cost_e = 1.0 + (fee_bps + slip_bps) / 10_000
    cost_x = 1.0 - (fee_bps + slip_bps) / 10_000

    # Pre-compute GK signals for all symbols
    gk: dict[str, dict] = {}
    for sym, b in base.items():
        s = compute_gk_signals(b["close"], b["high"], b["low"], params)
        gk[sym] = s

    # Build master date index
    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    date_str_set = {str(d.date()) for d in all_dates}

    # Portfoliio state
    positions: dict[str, dict] = {}   # sym -> position record
    trades:    list[dict]       = []
    eq_curve:  list[dict]       = []
    portfolio_value = 1.0

    def _regime_ok(trade_date: pd.Timestamp) -> bool:
        if regime_filter == "none":
            return True
        ts = trade_date
        if ts not in vnx_by_date.index:
            return True
        row = vnx_by_date.loc[ts]
        c, e50, e100, e150 = float(row.close), float(row.ema50), float(row.ema100), float(row.ema150)
        if regime_filter == "vnx_ema50":
            return c > e50
        if regime_filter == "vnx_ema100":
            return c > e100
        if regime_filter == "vnx_both":
            return c > e50 and c > e150
        return True

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())

        # -- 1. Scan for exits ------------------------------------------------
        exits_today: list[tuple[str, int, str]] = []   # (sym, bar_t, reason)

        for sym, pos in positions.items():
            b = base[sym]
            idx = b["date_to_idx"]
            if day_str not in idx:
                continue
            t = idx[day_str]
            if t + 1 >= len(b["close"]):
                continue

            bars_held = day_i - pos["entry_day_i"]
            if bars_held < min_hold:
                continue  # minimum hold not reached

            c_now = float(b["close"][t])
            triggered, reason = False, ""

            # GK SELL
            if bool(gk[sym]["gk_sell"][t]):
                triggered, reason = True, "GK_SELL"

            # EMA10 confirmed exit (2 consecutive closes < EMA10)
            if not triggered and exit_rule in ("gk_sell_or_ema10",) and t >= 1:
                if (c_now < float(b["ema10"][t]) and
                        float(b["close"][t - 1]) < float(b["ema10"][t - 1])):
                    triggered, reason = True, "EMA10_EXIT"

            # EMA20 confirmed exit
            if not triggered and exit_rule in ("gk_sell_or_ema20",) and t >= 1:
                if (c_now < float(b["ema20"][t]) and
                        float(b["close"][t - 1]) < float(b["ema20"][t - 1])):
                    triggered, reason = True, "EMA20_EXIT"

            # Hard stop loss (from raw entry open, before cost)
            if not triggered and stop_pct > 0:
                gross = c_now / pos["entry_open_raw"] - 1.0
                if gross <= -stop_pct:
                    triggered, reason = True, f"STOP_{stop_pct*100:.0f}"

            if triggered:
                exits_today.append((sym, t, reason))

        # -- 2. Execute exits -------------------------------------------------
        for sym, t, reason in exits_today:
            b = base[sym]
            next_o = float(b["open"][t + 1]) if t + 1 < len(b["open"]) else 0.0
            if next_o <= 0:
                next_o = float(b["close"][t])  # fallback to close
            pos = positions[sym]
            exit_px = next_o * cost_x
            ret     = exit_px / pos["entry_px"] - 1.0
            exit_dt = b["dates"][t + 1] if t + 1 < len(b["dates"]) else b["dates"][t]

            trades.append({
                "symbol":            sym,
                "entry_date":        pos["entry_date"],
                "entry_px":          round(pos["entry_px"], 4),
                "entry_open_raw":    round(pos["entry_open_raw"], 4),
                "exit_date":         exit_dt,
                "exit_px":           round(exit_px, 4),
                "exit_reason":       reason,
                "hold_days":         (exit_dt - pos["entry_date"]).days,
                "hold_bars":         day_i - pos["entry_day_i"],
                "ret":               round(ret, 6),
                "adv50_entry":       round(pos["adv50_entry"], 3),
                "regime_entry":      pos["regime_entry"],
                "ema_cloud_entry":   pos["ema_cloud_entry"],
                "gk_trend_entry":    pos["gk_trend_entry"],
            })
            del positions[sym]

        # -- 3. Scan for new entries ------------------------------------------
        n_free = max_pos - len(positions)
        reg_ok = _regime_ok(trade_date)

        if n_free > 0 and reg_ok:
            candidates: list[dict] = []
            for sym, b in base.items():
                if sym in positions:
                    continue
                idx = b["date_to_idx"]
                if day_str not in idx:
                    continue
                t = idx[day_str]
                if t + 1 >= len(b["close"]):
                    continue
                if not bool(gk[sym]["gk_buy"][t]):
                    continue

                # ADV50 eligibility — lagged
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < adv50_min_bn:
                    continue

                # Next open must be tradable
                next_o = float(b["open"][t + 1])
                if next_o <= 0:
                    continue

                c   = float(b["close"][t])
                e10 = float(b["ema10"][t])
                e50 = float(b["ema50"][t])
                e100 = float(b["ema100"][t])
                e150 = float(b["ema150"][t])

                if entry_filter == "ema_cloud"    and not (e10 > e50):   continue
                if entry_filter == "close_ema50"  and not (c  > e50):   continue
                if entry_filter == "close_ema100" and not (c  > e100):  continue
                if entry_filter == "close_ema150" and not (c  > e150):  continue

                rs3m = np.nan
                if rank_by == "rs3m":
                    t3m = max(0, t - 63)
                    rs3m = (c / float(b["close"][t3m]) - 1.0) if b["close"][t3m] > 0 else np.nan

                candidates.append({
                    "sym": sym, "t": t, "adv": adv, "next_o": next_o,
                    "rs3m": rs3m, "ema_cloud": e10 > e50,
                    "gk_trend": int(gk[sym]["gk_trend"][t]),
                })

            # Rank
            if rank_by == "rs3m":
                candidates.sort(key=lambda x: (not np.isnan(x["rs3m"]), x["rs3m"] if not np.isnan(x["rs3m"]) else 0), reverse=True)
            else:
                candidates.sort(key=lambda x: x["adv"], reverse=True)

            for cand in candidates[:n_free]:
                sym, t = cand["sym"], cand["t"]
                b = base[sym]
                entry_o_raw = cand["next_o"]
                entry_px    = entry_o_raw * cost_e
                entry_dt    = b["dates"][t + 1]
                positions[sym] = {
                    "entry_date":     entry_dt,
                    "entry_px":       entry_px,
                    "entry_open_raw": entry_o_raw,
                    "entry_day_i":    day_i,
                    "adv50_entry":    cand["adv"],
                    "regime_entry":   reg_ok,
                    "ema_cloud_entry": cand["ema_cloud"],
                    "gk_trend_entry": cand["gk_trend"],
                }

        # -- 4. Daily mark-to-market equity (cost-inclusive) ----------------
        # entry_day_i is the SIGNAL day; position executes at open of day_i+1.
        # Skip positions where entry_day_i >= day_i (not yet executed).
        # Use entry_px (cost-inclusive) for the first execution day.
        if positions:
            pos_rets = []
            for sym, pos in positions.items():
                b = base[sym]
                idx = b["date_to_idx"]
                if day_str not in idx:
                    continue
                t = idx[day_str]
                if pos["entry_day_i"] >= day_i:
                    # Signal day or same day: position not yet executed -- skip
                    continue
                # Determine if this is the first execution day
                # entry_date is the actual execution day (day after signal)
                # We detect it by comparing dates
                entry_dt = pos["entry_date"]
                if hasattr(entry_dt, "date"):
                    is_entry_bar = (str(entry_dt.date()) == day_str)
                else:
                    is_entry_bar = False
                if is_entry_bar:
                    # First bar: return from cost-inclusive entry price to today's close
                    ep = pos["entry_px"]   # = entry_open_raw * cost_e
                    cc = float(b["close"][t])
                    if ep > 0:
                        pos_rets.append(cc / ep - 1.0)
                elif t >= 1:
                    cp = float(b["close"][t - 1])
                    cc = float(b["close"][t])
                    if cp > 0:
                        pos_rets.append(cc / cp - 1.0)
            if pos_rets:
                daily_ret = sum(pos_rets) / max_pos
                portfolio_value *= (1.0 + daily_ret)

        eq_curve.append({
            "date":            trade_date,
            "portfolio_value": round(portfolio_value, 6),
            "n_pos":           len(positions),
        })

    # -- Force-close remaining open positions at last bar close ----------------
    last_day_i = len(all_dates) - 1
    for sym, pos in list(positions.items()):
        b = base[sym]
        lr = b["close"][-1]
        exit_px = lr * cost_x
        ret     = exit_px / pos["entry_px"] - 1.0
        exit_dt = b["dates"][-1]
        trades.append({
            "symbol":         sym,
            "entry_date":     pos["entry_date"],
            "entry_px":       round(pos["entry_px"], 4),
            "entry_open_raw": round(pos["entry_open_raw"], 4),
            "exit_date":      exit_dt,
            "exit_px":        round(exit_px, 4),
            "exit_reason":    "EOD_FORCE",
            "hold_days":      (exit_dt - pos["entry_date"]).days,
            "hold_bars":      last_day_i - pos["entry_day_i"],
            "ret":            round(ret, 6),
            "adv50_entry":    round(pos["adv50_entry"], 3),
            "regime_entry":   pos["regime_entry"],
            "ema_cloud_entry": pos["ema_cloud_entry"],
            "gk_trend_entry": pos["gk_trend_entry"],
        })

    return pd.DataFrame(eq_curve), pd.DataFrame(trades)


# ==============================================================================
# METRICS
# ==============================================================================

def compute_metrics(eq_df: pd.DataFrame, trades_df: pd.DataFrame, label: str = "") -> dict:
    m: dict = {"label": label, "n_trades": 0}
    if trades_df.empty:
        return m

    rets   = trades_df["ret"].values.astype(float)
    wins   = rets[rets > 0]
    losses = rets[rets <= 0]

    m["n_trades"]     = int(len(rets))
    m["win_rate"]     = round(float((rets > 0).mean()), 4)
    m["avg_ret"]      = round(float(rets.mean()), 4)
    m["avg_win"]      = round(float(wins.mean()),   4) if len(wins)   else float("nan")
    m["avg_loss"]     = round(float(losses.mean()), 4) if len(losses) else float("nan")
    m["profit_factor"] = round(float(wins.sum() / (-losses.sum())), 3) \
                         if len(losses) and losses.sum() < 0 else float("nan")
    m["best_trade"]   = round(float(rets.max()), 4)
    m["worst_trade"]  = round(float(rets.min()), 4)
    m["median_ret"]   = round(float(np.median(rets)), 4)

    if "hold_days" in trades_df.columns:
        hd = trades_df["hold_days"].dropna().values.astype(float)
        m["avg_hold_days"]    = round(float(hd.mean()),   1) if len(hd) else float("nan")
        m["median_hold_days"] = round(float(np.median(hd)), 1) if len(hd) else float("nan")

    # Portfolio-level metrics from equity curve (cost-inclusive since we use entry_px)
    if not eq_df.empty and "portfolio_value" in eq_df.columns:
        pv = eq_df["portfolio_value"].values.astype(float)
        if len(pv) >= 2 and pv[0] > 0:
            total_ret = pv[-1] / pv[0] - 1.0
            days = (eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days
            years = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0

            peak   = np.maximum.accumulate(pv)
            dd     = pv / peak - 1.0
            max_dd = float(dd.min())

            m["total_ret"]  = round(total_ret, 4)
            m["cagr"]       = round(cagr, 4)
            m["max_dd"]     = round(max_dd, 4)
            m["mar"]        = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else float("nan")

            # Annualised volatility from daily portfolio returns
            daily_rets = np.diff(pv) / pv[:-1]
            m["ann_vol"] = round(float(np.std(daily_rets) * np.sqrt(252)), 4)
            m["sharpe"]  = round(cagr / m["ann_vol"], 3) if m["ann_vol"] > 0 else float("nan")

            # Exposure %
            m["exposure_pct"] = round(float(eq_df["n_pos"].mean() / MAX_POS), 4)

    # Trade-log CAGR: cost-aware approximation (1/MAX_POS weight per trade, sequential)
    # This correctly shows cost sensitivity even when equity curve is approximate.
    if len(rets) > 0 and "entry_date" in trades_df.columns and "exit_date" in trades_df.columns:
        start_dt = pd.to_datetime(trades_df["entry_date"].min())
        end_dt   = pd.to_datetime(trades_df["exit_date"].max())
        trade_years = max((end_dt - start_dt).days / 365.25, 0.01)
        scaled_rets = rets / MAX_POS   # each trade uses 1/MAX_POS of capital
        trade_pv    = float(np.prod(1.0 + scaled_rets))
        m["trade_cagr"] = round(trade_pv ** (1.0 / trade_years) - 1.0, 4)

    # Yearly breakdown
    yearly: dict[int, dict] = {}
    if "entry_date" in trades_df.columns:
        for yr in YEARS:
            sub = trades_df[pd.to_datetime(trades_df["entry_date"]).dt.year == yr]
            if sub.empty:
                yearly[yr] = {}
                continue
            r = sub["ret"].values.astype(float)
            yearly[yr] = {
                "n": int(len(r)),
                "win_rate": round(float((r > 0).mean()), 3),
                "mean_ret": round(float(r.mean()), 4),
                "total_ret": round(float(np.prod(1 + r) - 1), 4),
            }
    m["yearly"] = yearly
    return m


def _fmt(v, pct=True, decimals=1) -> str:
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "n/a"
    if pct:
        return f"{v*100:.{decimals}f}%"
    return f"{v:.{decimals}f}"


def print_metrics(m: dict) -> None:
    print(f"\n  {'-'*60}")
    print(f"  {m['label']}")
    print(f"  {'-'*60}")
    print(f"  Trades:        {m.get('n_trades', 0):<6}  "
          f"Win rate:    {_fmt(m.get('win_rate',float('nan')))}")
    print(f"  CAGR (equity): {_fmt(m.get('cagr',float('nan'))):<8}  "
          f"Max DD:      {_fmt(m.get('max_dd',float('nan')))}")
    print(f"  CAGR (trades): {_fmt(m.get('trade_cagr',float('nan'))):<8}  "
          f"Total ret:   {_fmt(m.get('total_ret',float('nan')))}")
    print(f"  MAR:           {_fmt(m.get('mar',float('nan')), pct=False, decimals=2):<8}  "
          f"Profit factor: {_fmt(m.get('profit_factor',float('nan')), pct=False, decimals=2)}")
    print(f"  Sharpe:        {_fmt(m.get('sharpe',float('nan')), pct=False, decimals=2):<8}  "
          f"Ann vol:     {_fmt(m.get('ann_vol',float('nan')))}")
    print(f"  Avg ret/trade: {_fmt(m.get('avg_ret',float('nan'))):<8}  "
          f"Median ret:  {_fmt(m.get('median_ret',float('nan')))}")
    print(f"  Avg win:       {_fmt(m.get('avg_win',float('nan'))):<8}  "
          f"Avg loss:    {_fmt(m.get('avg_loss',float('nan')))}")
    print(f"  Avg hold days: {_fmt(m.get('avg_hold_days',float('nan')), pct=False, decimals=1):<8}  "
          f"Median hold: {_fmt(m.get('median_hold_days',float('nan')), pct=False, decimals=1)}")
    print(f"  Exposure:      {_fmt(m.get('exposure_pct',float('nan'))):<8}  "
          f"Ann vol:     {_fmt(m.get('ann_vol',float('nan')))}")
    print(f"  Best trade:    {_fmt(m.get('best_trade',float('nan'))):<8}  "
          f"Worst trade: {_fmt(m.get('worst_trade',float('nan')))}")

    yearly = m.get("yearly", {})
    if yearly:
        parts = []
        for yr in YEARS:
            yd = yearly.get(yr, {})
            if not yd:
                parts.append(f"  {yr}: no trades")
            else:
                parts.append(
                    f"  {yr}: n={yd['n']:3d}  wr={yd['win_rate']:.1%}  "
                    f"mean={yd['mean_ret']:+.2%}  tot={yd['total_ret']:+.2%}"
                )
        print("\n  Yearly breakdown:")
        for p in parts:
            print(p)


# ==============================================================================
# VNINDEX BENCHMARK
# ==============================================================================

def vnindex_bah(vnindex: pd.DataFrame) -> dict:
    v = vnindex.copy()
    v["date"] = pd.to_datetime(v["date"])
    v = v[(v["date"] >= START_DATE) & (v["date"] <= END_DATE)].sort_values("date")
    if len(v) < 2:
        return {"label": "VNINDEX B&H"}
    c     = v["close"].values.astype(float)
    days  = (v["date"].iloc[-1] - v["date"].iloc[0]).days
    years = max(days / 365.25, 0.01)
    cagr  = (c[-1] / c[0]) ** (1.0 / years) - 1.0
    peak  = np.maximum.accumulate(c)
    max_dd = float((c / peak - 1.0).min())
    yearly = {}
    for yr, grp in v.groupby(v["date"].dt.year):
        cc = grp["close"].values.astype(float)
        yearly[int(yr)] = {"ret": round(float(cc[-1] / cc[0] - 1.0), 4)}
    return {
        "label":     "VNINDEX B&H",
        "total_ret": round(float(c[-1] / c[0] - 1.0), 4),
        "cagr":      round(cagr, 4),
        "max_dd":    round(max_dd, 4),
        "mar":       round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else float("nan"),
        "yearly":    yearly,
    }


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    log.info("Loading panel data from %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL_SYMBOLS)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows, %s – %s",
             panel["symbol"].nunique(), len(panel),
             panel["date"].min().date(), panel["date"].max().date())

    log.info("Loading VNINDEX from %s", VNINDEX_CSV)
    vnindex_raw = pd.read_csv(VNINDEX_CSV)
    vnindex_raw["date"] = pd.to_datetime(vnindex_raw["date"])

    # Pre-compute VNINDEX EMAs (for regime filter)
    vnx = vnindex_raw.copy().sort_values("date").reset_index(drop=True)
    vc  = vnx["close"].values.astype(float)
    vnx["ema50"]  = _ema(vc, 50)
    vnx["ema100"] = _ema(vc, 100)
    vnx["ema150"] = _ema(vc, 150)
    vnx_by_date   = vnx.set_index("date")

    # Default params
    default_p = GKParams(gk_len=200, gk_mult=2.0, gk_atr_len=21, gk_conf=2)

    # ==========================================================================
    # PHASE 1
    # ==========================================================================
    phase1_validate(panel, default_p)

    input("\n  Phase 1 complete. Press Enter to continue to Phase 2 -> ")

    # ==========================================================================
    # PHASE 2 — pre-compute base data once
    # ==========================================================================
    log.info("Phase 2: Pre-computing per-symbol base data...")
    base = precompute_base(panel)
    log.info("  %d symbols pre-computed", len(base))

    vnx_bah = vnindex_bah(vnindex_raw)
    print(f"\n  VNINDEX B&H:  cagr={vnx_bah['cagr']:.1%}  "
          f"max_dd={vnx_bah['max_dd']:.1%}  MAR={_fmt(vnx_bah.get('mar',float('nan')), pct=False, decimals=2)}")
    for yr in YEARS:
        yd = vnx_bah["yearly"].get(yr, {})
        if yd:
            print(f"    {yr}: {yd['ret']:+.1%}")

    # -- Variant A: default params, no filter ---------------------------------
    print("\n" + "=" * 70)
    print("VARIANT A — Pure GK long-only (default params, no filter)")
    print("=" * 70)
    eq_a, tr_a = run_portfolio(base, vnx_by_date, default_p)
    tr_a.to_csv(OUT_DIR / "gk_default_trades.csv", index=False)
    eq_a.to_csv(OUT_DIR / "gk_default_equity.csv", index=False)
    m_a = compute_metrics(eq_a, tr_a, "Variant A: GK pure long-only")
    print_metrics(m_a)

    # -- Variant B: GK + EMA cloud entry filter --------------------------------
    print("\n" + "-" * 70)
    print("VARIANT B — GK + EMA cloud filter (EMA10 > EMA50)")
    print("-" * 70)
    eq_b, tr_b = run_portfolio(base, vnx_by_date, default_p, entry_filter="ema_cloud")
    tr_b.to_csv(OUT_DIR / "gk_variantB_trades.csv", index=False)
    m_b = compute_metrics(eq_b, tr_b, "Variant B: GK + EMA cloud")
    print_metrics(m_b)

    print("\n  Variant B2: GK + EMA cloud + EMA10 confirmed exit")
    eq_b2, tr_b2 = run_portfolio(base, vnx_by_date, default_p,
                                  entry_filter="ema_cloud", exit_rule="gk_sell_or_ema10")
    m_b2 = compute_metrics(eq_b2, tr_b2, "Variant B2: GK + EMA cloud + EMA10 exit")
    print_metrics(m_b2)

    print("\n  Variant B3: GK + EMA cloud + EMA20 confirmed exit")
    eq_b3, tr_b3 = run_portfolio(base, vnx_by_date, default_p,
                                  entry_filter="ema_cloud", exit_rule="gk_sell_or_ema20")
    m_b3 = compute_metrics(eq_b3, tr_b3, "Variant B3: GK + EMA cloud + EMA20 exit")
    print_metrics(m_b3)

    # -- Variant C: GK + VNINDEX regime ---------------------------------------
    print("\n" + "-" * 70)
    print("VARIANT C — GK + VNINDEX regime filters")
    print("-" * 70)
    regime_opts = [
        ("vnx_ema50",  "VNINDEX > EMA50"),
        ("vnx_ema100", "VNINDEX > EMA100"),
        ("vnx_both",   "VNINDEX > EMA50 & EMA150"),
    ]
    regime_results = []
    for r_key, r_label in regime_opts:
        eq_c, tr_c = run_portfolio(base, vnx_by_date, default_p, regime_filter=r_key)
        m_c = compute_metrics(eq_c, tr_c, f"Variant C: {r_label}")
        regime_results.append(m_c)
        print_metrics(m_c)

    # -- Entry filter sweep ----------------------------------------------------
    print("\n" + "-" * 70)
    print("ENTRY FILTER COMPARISON (default params, GK SELL exit)")
    print("-" * 70)
    filter_opts = [
        ("none",         "No filter"),
        ("ema_cloud",    "EMA10 > EMA50"),
        ("close_ema50",  "Close > EMA50"),
        ("close_ema100", "Close > EMA100"),
        ("close_ema150", "Close > EMA150"),
    ]
    filter_results = []
    for f_key, f_label in filter_opts:
        eq_f, tr_f = run_portfolio(base, vnx_by_date, default_p, entry_filter=f_key)
        m_f = compute_metrics(eq_f, tr_f, f_label)
        filter_results.append({**{k: v for k, v in m_f.items() if k != "yearly"},
                                "filter": f_key})
        print(f"\n  {f_label}: n={m_f['n_trades']}  "
              f"cagr={_fmt(m_f.get('cagr',float('nan')))}  "
              f"max_dd={_fmt(m_f.get('max_dd',float('nan')))}  "
              f"MAR={_fmt(m_f.get('mar',float('nan')), pct=False, decimals=2)}  "
              f"pf={_fmt(m_f.get('profit_factor',float('nan')), pct=False, decimals=2)}")
    pd.DataFrame(filter_results).to_csv(OUT_DIR / "gk_entry_filter_comparison.csv", index=False)

    # -- Stop loss comparison --------------------------------------------------
    print("\n" + "-" * 70)
    print("STOP LOSS COMPARISON")
    print("-" * 70)
    stop_results = []
    for stop_pct, stop_label in [(0.0, "No stop"), (0.07, "7% stop"), (0.08, "8% stop"), (0.10, "10% stop")]:
        eq_s, tr_s = run_portfolio(base, vnx_by_date, default_p, stop_pct=stop_pct)
        m_s = compute_metrics(eq_s, tr_s, stop_label)
        stop_results.append({**{k: v for k, v in m_s.items() if k != "yearly"},
                              "stop_pct": stop_pct})
        print(f"\n  {stop_label}: n={m_s['n_trades']}  "
              f"wr={_fmt(m_s.get('win_rate',float('nan')))}  "
              f"cagr={_fmt(m_s.get('cagr',float('nan')))}  "
              f"max_dd={_fmt(m_s.get('max_dd',float('nan')))}  "
              f"MAR={_fmt(m_s.get('mar',float('nan')), pct=False, decimals=2)}")
    pd.DataFrame(stop_results).to_csv(OUT_DIR / "gk_stop_loss_comparison.csv", index=False)

    # -- Cost / slippage sensitivity -------------------------------------------
    print("\n" + "-" * 70)
    print("COST / SLIPPAGE SENSITIVITY")
    print("-" * 70)
    cost_results = []
    for fee, slip, label in [(15, 0, "fee=15 slip=0"), (25, 10, "fee=25 slip=10"),
                              (35, 20, "fee=35 slip=20")]:
        eq_cs, tr_cs = run_portfolio(base, vnx_by_date, default_p, fee_bps=fee, slip_bps=slip)
        m_cs = compute_metrics(eq_cs, tr_cs, label)
        cost_results.append({**{k: v for k, v in m_cs.items() if k != "yearly"},
                              "fee_bps": fee, "slip_bps": slip})
        print(f"\n  {label}: n={m_cs['n_trades']}  "
              f"trade_cagr={_fmt(m_cs.get('trade_cagr',float('nan')))}  "
              f"eq_cagr={_fmt(m_cs.get('cagr',float('nan')))}  "
              f"avg_ret={_fmt(m_cs.get('avg_ret',float('nan')))}  "
              f"pf={_fmt(m_cs.get('profit_factor',float('nan')), pct=False, decimals=2)}")
    pd.DataFrame(cost_results).to_csv(OUT_DIR / "gk_cost_sensitivity.csv", index=False)

    # -- Max positions comparison ----------------------------------------------
    print("\n" + "-" * 70)
    print("MAX POSITIONS COMPARISON")
    print("-" * 70)
    maxpos_results = []
    for mp in [5, 10, 15, 20]:
        eq_mp, tr_mp = run_portfolio(base, vnx_by_date, default_p, max_pos=mp)
        m_mp = compute_metrics(eq_mp, tr_mp, f"max_pos={mp}")
        maxpos_results.append({**{k: v for k, v in m_mp.items() if k != "yearly"}, "max_pos": mp})
        print(f"\n  max_pos={mp}: n={m_mp['n_trades']}  "
              f"cagr={_fmt(m_mp.get('cagr',float('nan')))}  "
              f"max_dd={_fmt(m_mp.get('max_dd',float('nan')))}  "
              f"MAR={_fmt(m_mp.get('mar',float('nan')), pct=False, decimals=2)}")
    pd.DataFrame(maxpos_results).to_csv(OUT_DIR / "gk_maxpos_comparison.csv", index=False)

    # ==========================================================================
    # PARAMETER GRID SWEEP
    # ==========================================================================
    print("\n" + "=" * 70)
    print("PARAMETER GRID SWEEP")
    print("=" * 70)

    len_grid  = [80, 100, 120, 150, 180, 200]
    mult_grid = [1.6, 1.8, 2.0, 2.2, 2.5]
    atr_grid  = [14, 21]
    conf_grid = [2, 3]

    total = len(len_grid) * len(mult_grid) * len(atr_grid) * len(conf_grid)
    log.info("Grid: %d combos", total)

    grid_rows = []
    for i, (gl, gm, ga, gc) in enumerate(product(len_grid, mult_grid, atr_grid, conf_grid)):
        p = GKParams(gk_len=gl, gk_mult=gm, gk_atr_len=ga, gk_conf=gc)
        eq_g, tr_g = run_portfolio(base, vnx_by_date, p)
        m_g = compute_metrics(eq_g, tr_g, p.key())

        row: dict = {
            "gk_len": gl, "gk_mult": gm, "gk_atr_len": ga, "gk_conf": gc,
            "n_trades":       m_g.get("n_trades", 0),
            "win_rate":       m_g.get("win_rate", float("nan")),
            "cagr":           m_g.get("cagr", float("nan")),
            "max_dd":         m_g.get("max_dd", float("nan")),
            "mar":            m_g.get("mar", float("nan")),
            "profit_factor":  m_g.get("profit_factor", float("nan")),
            "avg_ret":        m_g.get("avg_ret", float("nan")),
            "avg_hold_days":  m_g.get("avg_hold_days", float("nan")),
            "sharpe":         m_g.get("sharpe", float("nan")),
            "exposure_pct":   m_g.get("exposure_pct", float("nan")),
        }
        for yr in YEARS:
            yd = m_g.get("yearly", {}).get(yr, {})
            row[f"n_{yr}"]   = yd.get("n", 0)
            row[f"wr_{yr}"]  = yd.get("win_rate", float("nan"))
            row[f"ret_{yr}"] = yd.get("total_ret", float("nan"))
        grid_rows.append(row)

        if (i + 1) % 30 == 0:
            log.info("  Grid progress: %d/%d", i + 1, total)

    grid_df = pd.DataFrame(grid_rows)
    grid_df.to_csv(OUT_DIR / "gk_parameter_grid.csv", index=False)
    log.info("Saved parameter grid: %s", OUT_DIR / "gk_parameter_grid.csv")

    print("\nTop 10 by MAR (min 10 trades):")
    g_valid = grid_df[grid_df["n_trades"] >= 10].copy()
    top_mar = g_valid.nlargest(10, "mar")
    print(top_mar[["gk_len","gk_mult","gk_atr_len","gk_conf",
                   "n_trades","win_rate","cagr","max_dd","mar","profit_factor"]].to_string(index=False))

    print("\nTop 10 by CAGR (min 10 trades):")
    top_cagr = g_valid.nlargest(10, "cagr")
    print(top_cagr[["gk_len","gk_mult","gk_atr_len","gk_conf",
                    "n_trades","win_rate","cagr","max_dd","mar","profit_factor"]].to_string(index=False))

    print("\nLowest max drawdown (min 10 trades):")
    g_valid["abs_dd"] = g_valid["max_dd"].abs()
    top_dd = g_valid.nsmallest(10, "abs_dd")
    print(top_dd[["gk_len","gk_mult","gk_atr_len","gk_conf",
                  "n_trades","win_rate","cagr","max_dd","mar"]].to_string(index=False))

    # Most robust: penalise year with negative total return
    g_valid["n_negative_years"] = sum(
        (g_valid[f"ret_{yr}"] < 0).fillna(True).astype(int) for yr in YEARS
    )
    top_robust = g_valid.nsmallest(10, "n_negative_years").nlargest(10, "mar")
    print("\nMost robust (fewest losing years, ranked by MAR):")
    print(top_robust[["gk_len","gk_mult","gk_atr_len","gk_conf",
                       "n_trades","cagr","max_dd","mar",
                       "n_negative_years"] + [f"ret_{yr}" for yr in YEARS]].to_string(index=False))

    # -- Master summary table --------------------------------------------------
    print("\n" + "=" * 70)
    print("MASTER SUMMARY — ALL VARIANTS vs VNINDEX B&H")
    print("=" * 70)

    all_metrics = [m_a, m_b, m_b2, m_b3] + \
                  [compute_metrics(*run_portfolio(base, vnx_by_date, default_p, regime_filter=rk),
                                   f"C: {rl}") for rk, rl in regime_opts]

    summary = []
    for m in all_metrics:
        summary.append({
            "variant":    m.get("label", ""),
            "n_trades":   m.get("n_trades", 0),
            "win_rate":   m.get("win_rate", float("nan")),
            "cagr":       m.get("cagr", float("nan")),
            "max_dd":     m.get("max_dd", float("nan")),
            "mar":        m.get("mar", float("nan")),
            "profit_factor": m.get("profit_factor", float("nan")),
            "sharpe":     m.get("sharpe", float("nan")),
            "avg_ret":    m.get("avg_ret", float("nan")),
            "exposure":   m.get("exposure_pct", float("nan")),
        })
    sum_df = pd.DataFrame(summary)
    sum_df.to_csv(OUT_DIR / "gk_summary.csv", index=False)
    print(sum_df.to_string(index=False))

    print(f"\n\nAll outputs saved to: {OUT_DIR}")
    log.info("Done.")


if __name__ == "__main__":
    main()
