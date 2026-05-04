#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Donchian entries with GK-style exit — isolate GK entry signal edge.

Experimental arms (exit held constant where noted):
  Arm A: GK entry          + GK_SELL exit              (baseline, no EMA filter)
  Arm B: GK entry          + EMA cloud + GK_SELL exit   (GK conditioned to match DC)
  Arm C: DC entry          + GK_SELL exit               (same exit, DC breakout entry)
  Arm D: DC entry          + GK_Lower band stop         (tighter vol-adjusted stop)
  Arm E: DC entry          + GK_SELL + 7% hard stop     (best stop from prior research)

Interpretation:
  B vs C  => marginal edge of GK entry signal vs DC entry (holding exit constant, same filter)
  A vs C  => GK entry (no filter) vs DC entry (inherent cloud filter)
  C vs D  => band stop vs signal-based exit for DC entries
  C vs E  => hard stop vs signal-based exit for DC entries

DC entry definition (from DAILY_DONCHIAN_EMA_CLOUD_OPS.md):
  Close > max(high[t-20 : t]) * 1.003
  AND EMA10 > EMA50                (bull cloud)
  AND Close > max(EMA10, EMA50)    (above cloud)
  ADV50 >= 2bn (lagged, same as GK universe)
  Entry executes at open of t+1

GK exit / stop definitions:
  GK_SELL:       confirmed trend flip to -1 (existing GK logic)
  GK_Lower stop: close < gk_lower (band violation, 1-bar, no confirmation)
  7% hard stop:  (close / entry_open_raw - 1) <= -0.07

Outputs: data/research/donchian_gk_exit/
"""
from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

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
OUT_DIR       = REPO / "data" / "research" / "donchian_gk_exit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -- Global constants ----------------------------------------------------------
START_DATE   = pd.Timestamp("2023-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
ADV50_MIN_BN = 2.0
FEE_BPS      = 25.0
SLIP_BPS     = 10.0
MAX_POS      = 10
YEARS        = [2023, 2024, 2025, 2026]
EXCL_SYMBOLS = {"VPL"}

# Donchian parameters
DON_LEN    = 20
DON_BUF    = 1.003   # 0.30% buffer above prior high
EMA_FAST   = 10
EMA_SLOW   = 50
DC_WARMUP  = max(EMA_SLOW + 10, DON_LEN + 1)  # 61 bars

# GK default parameters
GK_LEN     = 200
GK_MULT    = 2.0
GK_ATR_LEN = 21
GK_CONF    = 2


# ==============================================================================
# MATH PRIMITIVES  (identical to gk_trend_ribbon_backtest.py)
# ==============================================================================

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out   = np.full(len(arr), np.nan)
    for i in range(len(arr)):
        v = arr[i]
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
    out = np.full(len(value), np.nan)
    for i in range(50, len(value)):
        out[i] = float(np.mean(value[i - 50: i])) / 1e9
    return out


# ==============================================================================
# SIGNAL COMPUTATION
# ==============================================================================

def compute_gk_signals(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> dict:
    """
    GK Trend Ribbon signal — exact AFL replication (default params).
    Returns: gk_buy, gk_sell, gk_lower, gk_upper, gk_trend arrays.
    """
    n   = len(close)
    lag = max(int((GK_LEN - 1) // 2), 0)

    past_close = np.empty(n)
    for i in range(n):
        j = i - lag
        past_close[i] = close[j] if j >= 0 else close[i]

    zl_input = close + (close - past_close) if lag > 0 else close.copy()
    gk_zl    = _ema(zl_input, GK_LEN)
    gk_atr   = _wilder_atr(high, low, close, GK_ATR_LEN)
    gk_upper = gk_zl + gk_atr * GK_MULT
    gk_lower = gk_zl - gk_atr * GK_MULT

    cb       = GK_CONF - 1
    above    = close > gk_upper
    below    = close < gk_lower
    above1   = np.concatenate([[False], above[:-1]])
    below1   = np.concatenate([[False], below[:-1]])
    above_cb = np.concatenate([np.full(cb, False), above[:-cb]]) if cb > 0 else above.copy()
    below_cb = np.concatenate([np.full(cb, False), below[:-cb]]) if cb > 0 else below.copy()

    zl_prev    = np.concatenate([[np.nan], gk_zl[:-1]])
    zl_rising  = gk_zl > zl_prev
    zl_falling = gk_zl < zl_prev

    valid    = ~np.isnan(gk_upper) & ~np.isnan(gk_lower)
    gk_bull  = above & above1 & above_cb & zl_rising  & valid
    gk_bear  = below & below1 & below_cb & zl_falling & valid

    raw      = np.where(gk_bull, 1.0, np.where(gk_bear, -1.0, np.nan))
    s        = pd.Series(raw).ffill().fillna(0.0).astype(int)
    gk_trend = s.values

    gk_prev       = np.zeros(n, dtype=int)
    gk_prev[1:]   = gk_trend[:-1]
    raw_flip      = (gk_trend != gk_prev) & (gk_trend != 0)

    return {
        "gk_buy":   raw_flip & (gk_trend == 1),
        "gk_sell":  raw_flip & (gk_trend == -1),
        "gk_lower": gk_lower,
        "gk_upper": gk_upper,
        "gk_trend": gk_trend,
    }


def compute_donchian_signals(
    close: np.ndarray,
    high:  np.ndarray,
    ema10: np.ndarray,
    ema50: np.ndarray,
) -> np.ndarray:
    """
    Donchian breakout entry signal.

    Entry bar t:
      Close[t] > max(high[t-DON_LEN : t]) * DON_BUF   (prior DON_LEN bars, excludes t)
      AND EMA10[t] > EMA50[t]                           (bull cloud)
      AND Close[t] > max(EMA10[t], EMA50[t])            (above cloud)

    Returns boolean array; valid from bar DC_WARMUP onward.
    """
    n      = len(close)
    dc_buy = np.zeros(n, dtype=bool)
    for i in range(DON_LEN, n):
        if np.isnan(ema10[i]) or np.isnan(ema50[i]):
            continue
        don_high = np.max(high[i - DON_LEN: i])  # excludes bar i
        trigger  = don_high * DON_BUF
        bull_cloud = ema10[i] > ema50[i]
        above_cloud = close[i] > max(ema10[i], ema50[i])
        dc_buy[i] = (close[i] > trigger) and bull_cloud and above_cloud
    return dc_buy


# ==============================================================================
# PRE-COMPUTE BASE DATA
# ==============================================================================

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

        base[sym] = {
            "dates":      dts,
            "open":       o,
            "high":       h,
            "low":        l,
            "close":      c,
            "value":      val,
            "adv50_lag":  _adv50_lagged(val),
            "ema10":      e10,
            "ema50":      e50,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
            # pre-compute both signal types
            "gk":  compute_gk_signals(c, h, l),
            "dc_buy": compute_donchian_signals(c, h, e10, e50),
        }
    return base


# ==============================================================================
# PORTFOLIO ENGINE
# ==============================================================================

def run_portfolio(
    base:          dict[str, dict],
    *,
    entry_mode:    str   = "gk",       # "gk" | "donchian"
    entry_filter:  str   = "none",     # "none" | "ema_cloud"  (only for gk entry)
    exit_mode:     str   = "gk_sell",  # "gk_sell" | "gk_lower_stop"
    stop_pct:      float = 0.0,        # additional hard % stop (0 = off)
    fee_bps:       float = FEE_BPS,
    slip_bps:      float = SLIP_BPS,
    max_pos:       int   = MAX_POS,
    adv50_min_bn:  float = ADV50_MIN_BN,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cost_e = 1.0 + (fee_bps + slip_bps) / 10_000
    cost_x = 1.0 - (fee_bps + slip_bps) / 10_000

    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]

    positions: dict[str, dict] = {}
    trades:    list[dict]      = []
    eq_curve:  list[dict]      = []
    portfolio_value = 1.0

    for day_i, trade_date in enumerate(all_dates):
        day_str = str(trade_date.date())

        # -- 1. Scan exits -------------------------------------------------------
        exits_today: list[tuple[str, int, str]] = []

        for sym, pos in positions.items():
            b   = base[sym]
            idx = b["date_to_idx"]
            if day_str not in idx:
                continue
            t = idx[day_str]
            if t + 1 >= len(b["close"]):
                continue

            c_now      = float(b["close"][t])
            triggered  = False
            reason     = ""

            # GK_SELL signal
            if exit_mode in ("gk_sell",) or stop_pct > 0:
                if bool(b["gk"]["gk_sell"][t]):
                    triggered, reason = True, "GK_SELL"

            # GK_Lower band stop: exit immediately on band violation (1-bar, no confirmation)
            if not triggered and exit_mode == "gk_lower_stop":
                gk_lo = float(b["gk"]["gk_lower"][t])
                if not np.isnan(gk_lo) and c_now < gk_lo:
                    triggered, reason = True, "GK_LOWER_STOP"

            # Hard % stop (applied on top of whatever exit_mode is used)
            if not triggered and stop_pct > 0:
                gross = c_now / pos["entry_open_raw"] - 1.0
                if gross <= -stop_pct:
                    triggered, reason = True, f"STOP_{stop_pct*100:.0f}PCT"

            if triggered:
                exits_today.append((sym, t, reason))

        # -- 2. Execute exits ----------------------------------------------------
        for sym, t, reason in exits_today:
            b      = base[sym]
            next_o = float(b["open"][t + 1]) if t + 1 < len(b["open"]) else 0.0
            if next_o <= 0:
                next_o = float(b["close"][t])
            pos     = positions[sym]
            exit_px = next_o * cost_x
            ret     = exit_px / pos["entry_px"] - 1.0
            exit_dt = b["dates"][t + 1] if t + 1 < len(b["dates"]) else b["dates"][t]
            trades.append({
                "symbol":         sym,
                "entry_mode":     entry_mode,
                "entry_date":     pos["entry_date"],
                "entry_px":       round(pos["entry_px"], 4),
                "entry_open_raw": round(pos["entry_open_raw"], 4),
                "exit_date":      exit_dt,
                "exit_px":        round(exit_px, 4),
                "exit_reason":    reason,
                "hold_days":      (exit_dt - pos["entry_date"]).days,
                "hold_bars":      day_i - pos["entry_day_i"],
                "ret":            round(ret, 6),
                "adv50_entry":    round(pos["adv50_entry"], 3),
                "ema_cloud_entry": pos["ema_cloud_entry"],
                "gk_trend_entry": pos["gk_trend_entry"],
            })
            del positions[sym]

        # -- 3. Scan entries -----------------------------------------------------
        n_free = max_pos - len(positions)

        if n_free > 0:
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

                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < adv50_min_bn:
                    continue
                next_o = float(b["open"][t + 1])
                if next_o <= 0:
                    continue

                e10 = float(b["ema10"][t])
                e50 = float(b["ema50"][t])

                if entry_mode == "gk":
                    if not bool(b["gk"]["gk_buy"][t]):
                        continue
                    if entry_filter == "ema_cloud" and not (e10 > e50):
                        continue
                elif entry_mode == "donchian":
                    if not bool(b["dc_buy"][t]):
                        continue
                else:
                    raise ValueError(f"Unknown entry_mode: {entry_mode}")

                candidates.append({
                    "sym": sym, "t": t, "adv": adv, "next_o": next_o,
                    "ema_cloud": e10 > e50,
                    "gk_trend":  int(b["gk"]["gk_trend"][t]),
                })

            candidates.sort(key=lambda x: x["adv"], reverse=True)

            for cand in candidates[:n_free]:
                sym, t = cand["sym"], cand["t"]
                b = base[sym]
                entry_o_raw = cand["next_o"]
                entry_px    = entry_o_raw * cost_e
                entry_dt    = b["dates"][t + 1]
                positions[sym] = {
                    "entry_date":      entry_dt,
                    "entry_px":        entry_px,
                    "entry_open_raw":  entry_o_raw,
                    "entry_day_i":     day_i,
                    "adv50_entry":     cand["adv"],
                    "ema_cloud_entry": cand["ema_cloud"],
                    "gk_trend_entry":  cand["gk_trend"],
                }

        # -- 4. Daily MTM equity -------------------------------------------------
        if positions:
            pos_rets = []
            for sym, pos in positions.items():
                b = base[sym]
                idx = b["date_to_idx"]
                if day_str not in idx:
                    continue
                t = idx[day_str]
                if pos["entry_day_i"] >= day_i:
                    continue
                entry_dt = pos["entry_date"]
                is_entry_bar = (hasattr(entry_dt, "date") and
                                str(entry_dt.date()) == day_str)
                if is_entry_bar:
                    ep = pos["entry_px"]
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

    # Force-close open positions at last bar
    last_day_i = len(all_dates) - 1
    for sym, pos in list(positions.items()):
        b       = base[sym]
        lr      = float(b["close"][-1])
        exit_px = lr * cost_x
        ret     = exit_px / pos["entry_px"] - 1.0
        exit_dt = b["dates"][-1]
        trades.append({
            "symbol":         sym,
            "entry_mode":     entry_mode,
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

    m["n_trades"]      = int(len(rets))
    m["win_rate"]      = round(float((rets > 0).mean()), 4)
    m["avg_ret"]       = round(float(rets.mean()), 4)
    m["avg_win"]       = round(float(wins.mean()),   4) if len(wins)   else float("nan")
    m["avg_loss"]      = round(float(losses.mean()), 4) if len(losses) else float("nan")
    m["profit_factor"] = round(float(wins.sum() / (-losses.sum())), 3) \
                         if len(losses) and losses.sum() < 0 else float("nan")
    m["best_trade"]    = round(float(rets.max()), 4)
    m["worst_trade"]   = round(float(rets.min()), 4)
    m["median_ret"]    = round(float(np.median(rets)), 4)

    hd = trades_df["hold_days"].dropna().values.astype(float) if "hold_days" in trades_df else np.array([])
    m["avg_hold_days"]    = round(float(hd.mean()),   1) if len(hd) else float("nan")
    m["median_hold_days"] = round(float(np.median(hd)), 1) if len(hd) else float("nan")

    if not eq_df.empty and "portfolio_value" in eq_df.columns:
        pv    = eq_df["portfolio_value"].values.astype(float)
        if len(pv) >= 2 and pv[0] > 0:
            total_ret = pv[-1] / pv[0] - 1.0
            days  = (eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days
            years = max(days / 365.25, 0.01)
            cagr  = (pv[-1] / pv[0]) ** (1.0 / years) - 1.0
            peak  = np.maximum.accumulate(pv)
            dd    = pv / peak - 1.0
            max_dd = float(dd.min())

            m["total_ret"]  = round(total_ret, 4)
            m["cagr"]       = round(cagr, 4)
            m["max_dd"]     = round(max_dd, 4)
            m["mar"]        = round(abs(cagr / max_dd), 3) if max_dd < -1e-6 else float("nan")

            daily_rets = np.diff(pv) / pv[:-1]
            m["ann_vol"] = round(float(np.std(daily_rets) * np.sqrt(252)), 4)
            m["sharpe"]  = round(cagr / m["ann_vol"], 3) if m["ann_vol"] > 0 else float("nan")
            m["exposure_pct"] = round(float(eq_df["n_pos"].mean() / MAX_POS), 4)

    if len(rets) > 0 and "entry_date" in trades_df.columns:
        start_dt    = pd.to_datetime(trades_df["entry_date"].min())
        end_dt      = pd.to_datetime(trades_df["exit_date"].max())
        trade_years = max((end_dt - start_dt).days / 365.25, 0.01)
        scaled_rets = rets / MAX_POS
        trade_pv    = float(np.prod(1.0 + scaled_rets))
        m["trade_cagr"] = round(trade_pv ** (1.0 / trade_years) - 1.0, 4)

    yearly: dict[int, dict] = {}
    if "entry_date" in trades_df.columns:
        for yr in YEARS:
            sub = trades_df[pd.to_datetime(trades_df["entry_date"]).dt.year == yr]
            if sub.empty:
                yearly[yr] = {}
                continue
            r = sub["ret"].values.astype(float)
            yearly[yr] = {
                "n":         int(len(r)),
                "win_rate":  round(float((r > 0).mean()), 3),
                "mean_ret":  round(float(r.mean()), 4),
                "total_ret": round(float(np.prod(1 + r) - 1), 4),
            }
    m["yearly"] = yearly

    # Exit reason breakdown
    if "exit_reason" in trades_df.columns:
        m["exit_reasons"] = trades_df["exit_reason"].value_counts().to_dict()

    return m


def _fmt(v, pct=True, decimals=1) -> str:
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "n/a"
    if pct:
        return f"{v*100:.{decimals}f}%"
    return f"{v:.{decimals}f}"


def print_metrics(m: dict) -> None:
    print(f"\n  {'='*64}")
    print(f"  {m['label']}")
    print(f"  {'='*64}")
    print(f"  Trades:        {m.get('n_trades', 0):<6}  "
          f"Win rate:      {_fmt(m.get('win_rate', float('nan')))}")
    print(f"  CAGR (equity): {_fmt(m.get('cagr', float('nan'))):<8}  "
          f"Max DD:        {_fmt(m.get('max_dd', float('nan')))}")
    print(f"  MAR:           {_fmt(m.get('mar', float('nan')), pct=False, decimals=2):<8}  "
          f"Profit factor: {_fmt(m.get('profit_factor', float('nan')), pct=False, decimals=2)}")
    print(f"  Sharpe:        {_fmt(m.get('sharpe', float('nan')), pct=False, decimals=2):<8}  "
          f"Ann vol:       {_fmt(m.get('ann_vol', float('nan')))}")
    print(f"  Avg ret/trade: {_fmt(m.get('avg_ret', float('nan'))):<8}  "
          f"Median ret:    {_fmt(m.get('median_ret', float('nan')))}")
    print(f"  Avg win:       {_fmt(m.get('avg_win', float('nan'))):<8}  "
          f"Avg loss:      {_fmt(m.get('avg_loss', float('nan')))}")
    print(f"  Avg hold days: {_fmt(m.get('avg_hold_days', float('nan')), pct=False, decimals=1):<8}  "
          f"Median hold:   {_fmt(m.get('median_hold_days', float('nan')), pct=False, decimals=1)}")
    print(f"  Exposure:      {_fmt(m.get('exposure_pct', float('nan')))}")

    er = m.get("exit_reasons", {})
    if er:
        parts = "  |  ".join(f"{k}: {v}" for k, v in sorted(er.items(), key=lambda x: -x[1]))
        print(f"  Exits:         {parts}")

    yearly = m.get("yearly", {})
    if yearly:
        print("  Yearly breakdown:")
        for yr in YEARS:
            yd = yearly.get(yr, {})
            if not yd:
                print(f"    {yr}: no trades")
            else:
                print(f"    {yr}: n={yd['n']:3d}  wr={yd['win_rate']:.1%}  "
                      f"mean={yd['mean_ret']:+.2%}  tot={yd['total_ret']:+.2%}")


def _row(m: dict, arm: str) -> dict:
    r = {"arm": arm, "label": m.get("label", "")}
    for k in ("n_trades", "win_rate", "cagr", "max_dd", "mar", "profit_factor",
              "sharpe", "avg_ret", "median_ret", "avg_win", "avg_loss",
              "avg_hold_days", "exposure_pct", "trade_cagr", "ann_vol"):
        r[k] = m.get(k, float("nan"))
    for yr in YEARS:
        yd = m.get("yearly", {}).get(yr, {})
        r[f"n_{yr}"]   = yd.get("n",         0)
        r[f"wr_{yr}"]  = yd.get("win_rate",   float("nan"))
        r[f"ret_{yr}"] = yd.get("total_ret",  float("nan"))
    return r


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    log.info("Loading panel: %s", CACHE_PARQUET)
    panel = pd.read_parquet(CACHE_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL_SYMBOLS)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows, %s – %s",
             panel["symbol"].nunique(), len(panel),
             panel["date"].min().date(), panel["date"].max().date())

    log.info("Pre-computing per-symbol base data (GK + DC signals)...")
    base = precompute_base(panel)
    log.info("  Done: %d symbols", len(base))

    # Report signal counts so we can sanity-check warmup
    total_gk_buy = sum(int(b["gk"]["gk_buy"].sum()) for b in base.values())
    total_dc_buy = sum(int(b["dc_buy"].sum()) for b in base.values())
    log.info("  GK_BUY signals (all): %d  |  DC_BUY signals (all): %d",
             total_gk_buy, total_dc_buy)

    arms = [
        # (label,            entry_mode,   entry_filter,  exit_mode,        stop_pct)
        ("A: GK+GK_SELL",        "gk",        "none",     "gk_sell",         0.00),
        ("B: GK+cloud+GK_SELL",  "gk",        "ema_cloud", "gk_sell",        0.00),
        ("C: DC+GK_SELL",        "donchian",  "none",     "gk_sell",         0.00),
        ("D: DC+GK_Lower stop",  "donchian",  "none",     "gk_lower_stop",   0.00),
        ("E: DC+GK_SELL+7%stop", "donchian",  "none",     "gk_sell",         0.07),
    ]

    results = []
    all_trades = []

    print("\n" + "=" * 70)
    print("DONCHIAN vs GK ENTRY — GK-STYLE EXIT COMPARISON")
    print("=" * 70)
    print(f"\nUniverse: {len(base)} symbols  |  ADV50 >= {ADV50_MIN_BN}bn  "
          f"|  Costs: {FEE_BPS}+{SLIP_BPS} bps/side  |  Max pos: {MAX_POS}")
    print(f"Period: {START_DATE.date()} – {END_DATE.date()}")

    for arm_label, entry_mode, entry_filter, exit_mode, stop_pct in arms:
        log.info("Running arm: %s", arm_label)
        eq, tr = run_portfolio(
            base,
            entry_mode=entry_mode,
            entry_filter=entry_filter,
            exit_mode=exit_mode,
            stop_pct=stop_pct,
        )
        m = compute_metrics(eq, tr, arm_label)
        print_metrics(m)
        results.append(_row(m, arm_label.split(":")[0].strip()))
        if not tr.empty:
            tr["arm"] = arm_label
            all_trades.append(tr)

    # -- Summary table ----------------------------------------------------------
    summary_df = pd.DataFrame(results)
    summary_path = OUT_DIR / "donchian_gk_exit_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    log.info("Summary saved: %s", summary_path)

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if not trades_df.empty:
        trades_path = OUT_DIR / "donchian_gk_exit_trades.csv"
        trades_df.to_csv(trades_path, index=False)
        log.info("Trades saved: %s", trades_path)

    # -- Interpretation guidance ------------------------------------------------
    print("\n" + "=" * 70)
    print("INTERPRETATION GUIDE")
    print("=" * 70)
    print()
    print("  Key comparisons:")
    print("  A vs C  : Does GK entry (no filter) add edge over DC entry (with cloud filter)?")
    print("  B vs C  : Fair comparison — both have EMA cloud condition. Pure entry signal edge.")
    print("  C vs D  : GK_SELL signal exit vs GK_Lower band stop on DC entries.")
    print("  C vs E  : GK_SELL vs GK_SELL + 7% hard stop on DC entries.")
    print()
    print("  If B ≈ C  → GK entry signal adds no marginal edge; DC breakout is equivalent.")
    print("  If B >> C → GK entry timing is superior (worth the added complexity).")
    print("  If C >> B → DC breakout is a better entry filter than GK trend flip.")
    print()
    print(f"  Full results: {OUT_DIR}")


if __name__ == "__main__":
    main()
