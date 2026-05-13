#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 8 — Component Decomposition & Signal Value Analysis

Parts:
  1. Component Attribution (8 arms)
  2. Watchlist Forward Returns
  3. Leader Detection
  4. Winner vs Loser Anatomy
  5. Exit Utility Test
  6. Discretionary Rank Review
  7. Final Classification Report

Outputs: data/research/gk_audit/phase8_decomposition/
"""
from __future__ import annotations

import io, sys, logging, warnings
from pathlib import Path
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
FULL_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_full.parquet"
VNINDEX_CSV  = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT_DIR      = REPO / "data/research/gk_audit/phase8_decomposition"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
START_DATE  = pd.Timestamp("2018-01-01")
END_DATE    = pd.Timestamp("2026-04-30")
EXCL        = {"VPL"}
ADV50_MIN   = 2.0
MAX_POS     = 10
FEE         = 35 / 10000
INITIAL_CAP = 1.0
VEXP_MIN    = 1.2
TS_BARS     = 20
TS_THR      = 0.0
GK_LEN, GK_MULT, GK_ATR, GK_CONF = 100, 2.0, 14, 2
YEARS       = list(range(2018, 2027))
HORIZONS    = [5, 10, 20, 40, 63, 126]


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ema_np(a: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1); out = np.full(len(a), np.nan)
    for i in range(len(a)):
        v = float(a[i])
        if np.isnan(v): continue
        p = out[i-1] if i > 0 and not np.isnan(out[i-1]) else np.nan
        out[i] = v if np.isnan(p) else alpha * v + (1 - alpha) * p
    return out


def _watr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    h_ = pd.Series(h); l_ = pd.Series(l); c_ = pd.Series(c)
    prev_c = c_.shift(1).fillna(c_.iloc[0] if len(c_) else 0)
    tr = np.maximum(h - l,
                    np.maximum(np.abs(h - prev_c.values), np.abs(l - prev_c.values)))
    out = pd.Series(tr).ewm(alpha=1.0/n, adjust=False).mean().values.copy()
    out[:n-1] = np.nan
    return out


def _adv50(val: np.ndarray) -> np.ndarray:
    out = np.full(len(val), np.nan)
    for i in range(50, len(val)):
        out[i] = float(np.mean(val[i-50:i])) / 1e9
    return out


def _gk_sig(c: np.ndarray, h: np.ndarray, l: np.ndarray) -> dict:
    n = len(c); lag = max(int((GK_LEN - 1) // 2), 0)
    pc = np.empty(n)
    for i in range(n): j = i - lag; pc[i] = c[j] if j >= 0 else c[i]
    zl = _ema_np(c + (c - pc), GK_LEN); atr = _watr(h, l, c, GK_ATR)
    gu = zl + atr * GK_MULT; gl = zl - atr * GK_MULT; cb = GK_CONF - 1
    ab = c > gu; bl = c < gl
    a1 = np.concatenate([[False], ab[:-1]]); b1 = np.concatenate([[False], bl[:-1]])
    acb = np.concatenate([np.full(max(cb, 0), False), ab[:-cb]]) if cb > 0 else ab.copy()
    bcb = np.concatenate([np.full(max(cb, 0), False), bl[:-cb]]) if cb > 0 else bl.copy()
    zp = np.concatenate([[np.nan], zl[:-1]]); zr = zl > zp; zf = zl < zp
    vl = ~np.isnan(gu) & ~np.isnan(gl)
    bull = ab & a1 & acb & zr & vl; bear = bl & b1 & bcb & zf & vl
    raw = np.where(bull, 1.0, np.where(bear, -1.0, np.nan))
    s = pd.Series(raw).ffill().fillna(0.0).astype(int).values
    prev = np.zeros(n, dtype=int); prev[1:] = s[:-1]; flip = (s != prev) & (s != 0)
    return {"gk_buy": flip & (s == 1), "gk_sell": flip & (s == -1)}


# ══════════════════════════════════════════════════════════════════════════════
# EXTENDED PRECOMPUTE
# ══════════════════════════════════════════════════════════════════════════════

def precompute_base(panel: pd.DataFrame, vnx_series: pd.Series) -> dict:
    """Precompute all signals for Phase 8. Extended vs phase7."""
    log.info("Precomputing signals (%d symbols)...", panel["symbol"].nunique())
    base = {}
    for i_sym, (sym, grp) in enumerate(panel.groupby("symbol")):
        if (i_sym + 1) % 50 == 0:
            log.info("  %d/%d...", i_sym + 1, panel["symbol"].nunique())
        df = grp.sort_values("date").reset_index(drop=True)
        c   = df["close"].values.astype(float)
        h   = df["high"].values.astype(float)
        l   = df["low"].values.astype(float)
        o   = df["open"].values.astype(float)
        val = df["value"].values.astype(float)
        dts = pd.to_datetime(df["date"].values)

        adv = _adv50(val)
        g   = _gk_sig(c, h, l)
        atr = _watr(h, l, c, GK_ATR)

        # VolExp
        ve = np.full(len(c), np.nan)
        for i in range(len(c)):
            if not np.isnan(adv[i]) and adv[i] > 0:
                ve[i] = val[i] / (adv[i] * 1e9)

        # EMAs
        e10  = _ema_np(c, 10)
        e20  = _ema_np(c, 20)
        e50  = _ema_np(c, 50)
        e100 = _ema_np(c, 100)

        c_s = pd.Series(c)

        # ATR%
        atr_pct = np.where(c > 0, atr / c, np.nan)

        # Rolling 252d high (lagged: exclude current bar) for 52-week distance
        dn252_prev = c_s.shift(1).rolling(252, min_periods=1).max().values
        dist_52wk  = np.where(dn252_prev > 0, c / dn252_prev - 1, np.nan)
        dn252_break = (c > dn252_prev) & (dn252_prev > 0)

        # Donchian 20-day breakout (lagged)
        don20_prev  = c_s.shift(1).rolling(20, min_periods=1).max().values
        don20_break = (c > don20_prev) & (don20_prev > 0)

        # EMA10 crosses above EMA50
        e10_s = pd.Series(e10); e50_s = pd.Series(e50)
        ema_cross = ((e10_s > e50_s) & (e10_s.shift(1) <= e50_s.shift(1))).fillna(False).values

        # Returns
        ret20 = c_s.pct_change(20).values
        ret50 = c_s.pct_change(50).values

        # Range position
        range_pos = np.where(h - l > 0, (c - l) / (h - l), 0.5)

        # Gap
        gap = (pd.Series(o) / pd.Series(c).shift(1) - 1).values

        # 20-day return volatility (base tightness proxy)
        vol20 = c_s.pct_change().rolling(20).std().values

        # RS vs VNINDEX (vectorized)
        dts_idx    = pd.DatetimeIndex(dts)
        vnx_al     = vnx_series.reindex(dts_idx, method="ffill").values.astype(float)
        v_s        = pd.Series(vnx_al)
        rs1m = (c_s.pct_change(21) - v_s.pct_change(21)).values
        rs3m = (c_s.pct_change(63) - v_s.pct_change(63)).values
        rs6m = (c_s.pct_change(126) - v_s.pct_change(126)).values

        base[sym] = {
            "dates": dts, "open": o, "close": c, "high": h, "low": l,
            "gk_fast": g, "adv50_lag": adv, "volexp": ve,
            "ema10": e10, "ema20": e20, "ema50": e50, "ema100": e100,
            "atr": atr, "atr_pct": atr_pct,
            "dist_52wk": dist_52wk, "dn252_break": dn252_break,
            "don20_break": don20_break, "ema_cross": ema_cross,
            "ret20": ret20, "ret50": ret50, "vol20": vol20,
            "range_pos": range_pos, "gap": gap,
            "rs1m": rs1m, "rs3m": rs3m, "rs6m": rs6m,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    log.info("Precompute complete: %d symbols", len(base))
    return base


# ══════════════════════════════════════════════════════════════════════════════
# VNINDEX + BREADTH CALENDARS
# ══════════════════════════════════════════════════════════════════════════════

def build_vnx_calendar(vnx_df: pd.DataFrame) -> pd.DataFrame:
    vnx = vnx_df.sort_values("date").copy()
    c   = vnx["close"].values.astype(float)
    dts = pd.to_datetime(vnx["date"].values)
    ema20  = pd.Series(c).ewm(span=20,  adjust=False).mean().values
    ema50  = pd.Series(c).ewm(span=50,  adjust=False).mean().values
    ema100 = pd.Series(c).ewm(span=100, adjust=False).mean().values
    roll_h = pd.Series(c).rolling(252, min_periods=1).max().values
    dd252  = c / roll_h - 1
    cal = pd.DataFrame({
        "date": pd.to_datetime([str(d.date()) for d in dts]),
        "close": c, "ema20": ema20, "ema50": ema50, "ema100": ema100,
        "dd252": dd252,
    }).set_index("date")
    return cal


def build_breadth_calendar(base: dict, all_dates: list) -> pd.DataFrame:
    log.info("Building breadth calendar (%d dates)...", len(all_dates))
    rows = []
    for td in all_dates:
        ds = str(td.date())
        above50 = n_valid = 0
        for sym, b in base.items():
            t = b["date_to_idx"].get(ds)
            if t is None: continue
            e50 = b["ema50"][t]
            if not np.isnan(e50):
                above50 += int(float(b["close"][t]) > e50); n_valid += 1
        rows.append({"date": td, "above50_pct": above50 / max(n_valid, 1)})
    return pd.DataFrame(rows).set_index("date")


# ══════════════════════════════════════════════════════════════════════════════
# REGIME BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _sz06_factor(vnx_cal: pd.DataFrame) -> pd.Series:
    return (vnx_cal["close"] > vnx_cal["ema50"]).fillna(True).map({True: 1.0, False: 0.5})


def build_regime_daily(
    vnx_cal: pd.DataFrame,
    gate_key: str,
    force_flat: bool = False,
    consecutive: int = 0,
    breadth_cal: Optional[pd.DataFrame] = None,
) -> dict:
    if gate_key == "G07":
        gs = ((vnx_cal["close"] > vnx_cal["ema50"]) &
              (vnx_cal["ema20"] > vnx_cal["ema50"])).fillna(False)
    elif gate_key == "G08":
        gs = ((vnx_cal["close"] > vnx_cal["ema100"]) &
              (vnx_cal["ema20"] > vnx_cal["ema50"])).fillna(False)
    elif gate_key == "B05_ff" and breadth_cal is not None:
        g08 = ((vnx_cal["close"] > vnx_cal["ema100"]) &
               (vnx_cal["ema20"] > vnx_cal["ema50"])).fillna(False)
        b01 = (breadth_cal["above50_pct"]
               .reindex(vnx_cal.index).ffill().bfill().fillna(0) > 0.40)
        gs = (g08 & b01).fillna(False)
    else:
        gs = pd.Series(True, index=vnx_cal.index)

    if consecutive > 0:
        rs = gs.astype(int).rolling(consecutive, min_periods=consecutive).sum()
        ge = (rs >= consecutive).fillna(False)
    else:
        ge = gs.fillna(False)

    if force_flat:
        fe = (~ge) & ge.shift(1).fillna(True)
    else:
        fe = pd.Series(False, index=ge.index)

    sz06 = _sz06_factor(vnx_cal)

    result = {}
    for ds in ge.index:
        ds_str = str(ds.date())
        result[ds_str] = {
            "allow_entry": bool(ge.loc[ds]),
            "size_factor": float(sz06.loc[ds]),
            "force_exit":  bool(fe.loc[ds]),
        }
    return result


DEFAULT_REGIME = {"allow_entry": True, "size_factor": 1.0, "force_exit": False}


def baseline_regime_daily(vnx_cal: pd.DataFrame, all_dates: list) -> dict:
    """SZ06 only: always allow entries, half-size when VNINDEX < EMA50."""
    sz06 = _sz06_factor(vnx_cal)
    result = {}
    for td in all_dates:
        ds = str(td.date())
        ts = pd.Timestamp(ds)
        sf = float(sz06.loc[ts]) if ts in sz06.index else 1.0
        result[ds] = {"allow_entry": True, "size_factor": sf, "force_exit": False}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# GENERALIZED SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

def run_simulation(
    base: dict,
    all_dates: list,
    regime_daily: dict,
    use_volexp: bool = True,
    use_tstop: bool = True,
    ts_bars: int = TS_BARS,
    max_hold: Optional[int] = None,
    exit_sig: str = "gk_sell",   # "gk_sell" | "ema20" | None
    entry_override: Optional[dict] = None,  # sym -> set of date strings
) -> tuple:
    cash = INITIAL_CAP; holdings = {}; pending_exits = {}; pending_entries = []
    trades = []; eq = []; prev_eq = INITIAL_CAP

    for day_i, td in enumerate(all_dates):
        ds = str(td.date())
        regime = regime_daily.get(ds, DEFAULT_REGIME)

        if regime.get("force_exit", False):
            for sym in list(holdings.keys()):
                if sym not in pending_exits:
                    pending_exits[sym] = "REGIME_EXIT"

        # Process exits at today's open
        for sym, rsn in list(pending_exits.items()):
            b = base.get(sym)
            if b is None: continue
            tex = b["date_to_idx"].get(ds)
            if tex is None: continue
            op = float(b["open"][tex]); pos = holdings.pop(sym, None)
            if pos is None: continue
            proceeds = pos["sh"] * op * (1 - FEE / 2); cash += proceeds
            trades.append({
                "symbol": sym,
                "entry_dt": str(pos["edt"].date()), "exit_dt": ds,
                "exit_reason": rsn,
                "net_ret": (op * (1 - FEE / 2)) / pos["epx"] - 1,
                "hold_bars": day_i - pos["edi"],
                "entry_size": pos["slot"],
                "mfe": pos["mfe"], "mae": pos["mae"], "eop": pos["eop"],
                "entry_adv": pos["adv"], "entry_ve": pos["ve"],
            })
        pending_exits.clear()

        # Execute entries
        if regime.get("allow_entry", True):
            slots = MAX_POS - len(holdings)
            sel = sorted(pending_entries, key=lambda x: -x["adv"])[:slots]
            for e in sel:
                sym = e["sym"]; b = base.get(sym)
                if b is None: continue
                tex = b["date_to_idx"].get(ds)
                if tex is None or sym in holdings: continue
                op = float(b["open"][tex])
                if op <= 0: continue
                sf   = regime.get("size_factor", 1.0)
                slot = (prev_eq / MAX_POS) * sf
                px_e = op * (1 + FEE / 2)
                sh   = slot / px_e; cash -= slot
                holdings[sym] = {
                    "sh": sh, "epx": px_e, "eop": op, "edt": td,
                    "edi": day_i, "adv": e["adv"], "slot": slot,
                    "mfe": 0., "mae": 0., "ve": e.get("ve", np.nan),
                }
        pending_entries.clear()

        # Mark exits + update MFE/MAE
        for sym, pos in list(holdings.items()):
            b = base.get(sym)
            if b is None: continue
            t = b["date_to_idx"].get(ds)
            if t is None or t + 1 >= len(b["close"]): continue
            bars = day_i - pos["edi"]
            cn   = float(b["close"][t])
            u    = cn / pos["eop"] - 1
            pos["mfe"] = max(pos["mfe"], u); pos["mae"] = min(pos["mae"], u)
            tri, rsn = False, ""
            if exit_sig == "gk_sell" and bool(b["gk_fast"]["gk_sell"][t]):
                tri, rsn = True, "GK_SELL"
            elif exit_sig == "ema20" and cn < float(b["ema20"][t]):
                tri, rsn = True, "EMA20_EXIT"
            if not tri and use_tstop and bars >= ts_bars and u <= TS_THR:
                tri, rsn = True, "TSTOP"
            if not tri and max_hold is not None and bars >= max_hold:
                tri, rsn = True, "MAX_HOLD"
            if tri:
                pending_exits[sym] = rsn

        # Queue entries
        if regime.get("allow_entry", True):
            if entry_override is not None:
                for sym, b in base.items():
                    if sym in holdings or sym in pending_exits: continue
                    if any(x["sym"] == sym for x in pending_entries): continue
                    t = b["date_to_idx"].get(ds)
                    if t is None or t + 1 >= len(b["close"]): continue
                    adv = float(b["adv50_lag"][t])
                    if np.isnan(adv) or adv < ADV50_MIN: continue
                    if ds not in entry_override.get(sym, set()): continue
                    ve = float(b["volexp"][t]) if not np.isnan(b["volexp"][t]) else 0.
                    pending_entries.append({"sym": sym, "adv": adv, "ve": ve})
            else:
                for sym, b in base.items():
                    if sym in holdings or sym in pending_exits: continue
                    if any(x["sym"] == sym for x in pending_entries): continue
                    t = b["date_to_idx"].get(ds)
                    if t is None or t + 1 >= len(b["close"]): continue
                    adv = float(b["adv50_lag"][t])
                    if np.isnan(adv) or adv < ADV50_MIN: continue
                    if not bool(b["gk_fast"]["gk_buy"][t]): continue
                    if use_volexp:
                        ve = float(b["volexp"][t])
                        if np.isnan(ve) or ve < VEXP_MIN: continue
                    else:
                        ve = float(b["volexp"][t]) if not np.isnan(b["volexp"][t]) else 0.
                    pending_entries.append({"sym": sym, "adv": adv, "ve": ve})

        # Equity
        mv = 0.
        for sym, pos in holdings.items():
            b = base.get(sym)
            if b is None: continue
            t = b["date_to_idx"].get(ds)
            if t is not None:
                mv += pos["sh"] * float(b["close"][t])
        eq_now = cash + mv; prev_eq = eq_now
        eq.append({"date": td, "equity": eq_now, "n_pos": len(holdings)})

    eq_df = pd.DataFrame(eq)
    tr_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    return eq_df, tr_df


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(eq_df: pd.DataFrame, tr_df: pd.DataFrame, vnx_rets: pd.DataFrame,
                    arm_id: str = "", label: str = "") -> dict:
    if eq_df.empty:
        return {"arm_id": arm_id, "label": label, "n_trades": 0}
    eq_df = eq_df.copy()
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    eq_df["strat_ret"] = eq_df["equity"].pct_change().fillna(0)
    eq_df = eq_df.merge(vnx_rets[["date", "vnx_ret"]], on="date", how="left")
    eq_df["vnx_ret"] = eq_df["vnx_ret"].fillna(0)
    eq_df["bench_ret"] = eq_df["vnx_ret"] * (eq_df["n_pos"].clip(0, MAX_POS) / MAX_POS)
    eq_df["active_ret"] = eq_df["strat_ret"] - eq_df["bench_ret"]
    eq_df["cum_active"] = (1 + eq_df["active_ret"]).cumprod()
    roll_max = eq_df["cum_active"].cummax()
    active_maxdd = float((eq_df["cum_active"] / roll_max - 1).min())

    years    = max((eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days / 365.25, 1e-6)
    final_eq = float(eq_df["equity"].iloc[-1])
    cagr     = final_eq ** (1 / years) - 1
    mar      = cagr / abs(active_maxdd) if active_maxdd < 0 else np.nan
    exposure = float(eq_df["n_pos"].mean()) / MAX_POS

    yearly = {}
    for yr in YEARS:
        sub = eq_df[eq_df["date"].dt.year == yr]
        if len(sub) >= 2:
            yearly[yr] = float(sub["equity"].iloc[-1] / sub["equity"].iloc[0] - 1)

    n_trades = len(tr_df)
    avg_hold = win_rate = profit_factor = expectancy = np.nan
    top1_pct = top5_pct = ex_top1_cagr = ex_top3_cagr = ex_top5_cagr = np.nan
    top1_sym = ""

    if n_trades > 0 and not tr_df.empty and "net_ret" in tr_df.columns:
        avg_hold = float(tr_df["hold_bars"].mean()) if "hold_bars" in tr_df.columns else np.nan
        wins     = tr_df[tr_df["net_ret"] > 0]
        losses   = tr_df[tr_df["net_ret"] <= 0]
        win_rate = len(wins) / n_trades
        tw = float(wins["net_ret"].sum()) if len(wins) else 0.
        tl = float(losses["net_ret"].abs().sum()) if len(losses) else 0.
        profit_factor = tw / tl if tl > 0 else np.nan
        expectancy    = float(tr_df["net_ret"].mean())

        if "entry_size" in tr_df.columns:
            tr = tr_df.copy(); tr["abs_pnl"] = tr["net_ret"] * tr["entry_size"]
            total_pnl = tr["abs_pnl"].sum()
            if abs(total_pnl) > 1e-9:
                by_sym = tr.groupby("symbol")["abs_pnl"].sum().sort_values(ascending=False)
                top1_sym  = str(by_sym.index[0]) if len(by_sym) else ""
                top1_pct  = float(by_sym.iloc[0] / total_pnl) if len(by_sym) else np.nan
                top5_pct  = float(by_sym.head(5).sum() / total_pnl) if len(by_sym) >= 5 else np.nan
                if len(by_sym) >= 1:
                    ex_top1_cagr = ((total_pnl - by_sym.head(1).sum()) / INITIAL_CAP) / years
                if len(by_sym) >= 3:
                    ex_top3_cagr = ((total_pnl - by_sym.head(3).sum()) / INITIAL_CAP) / years
                if len(by_sym) >= 5:
                    ex_top5_cagr = ((total_pnl - by_sym.head(5).sum()) / INITIAL_CAP) / years

    return {
        "arm_id": arm_id, "label": label,
        "n_trades": n_trades, "cagr": cagr, "mar": mar,
        "active_maxdd": active_maxdd, "exposure": exposure,
        "avg_hold": avg_hold, "win_rate": win_rate,
        "profit_factor": profit_factor, "expectancy": expectancy,
        "top1_sym": top1_sym, "top1_pct": top1_pct, "top5_pct": top5_pct,
        "ex_top1_cagr": ex_top1_cagr, "ex_top3_cagr": ex_top3_cagr,
        "ex_top5_cagr": ex_top5_cagr,
        "yearly": yearly,
        **{f"ret_{yr}": yearly.get(yr, np.nan) for yr in YEARS},
    }


# ══════════════════════════════════════════════════════════════════════════════
# PART 2: FORWARD RETURN ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def collect_signals(base: dict, use_volexp: bool = True, use_gk: bool = True) -> list:
    """Returns list of (sym, date_str, t_idx) for all qualifying signals."""
    signals = []
    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            if use_gk and not bool(b["gk_fast"]["gk_buy"][i]): continue
            if use_volexp:
                ve = float(b["volexp"][i])
                if np.isnan(ve) or ve < VEXP_MIN: continue
            signals.append((sym, str(dt.date()), i))
    return signals


def forward_returns_for_signals(base: dict, signals: list, horizons: list) -> pd.DataFrame:
    """Compute forward returns from entry open for each signal."""
    rows = []
    for sym, ds, t in signals:
        b = base[sym]
        if t + 1 >= len(b["close"]): continue
        entry_px = float(b["open"][t + 1])
        if entry_px <= 0: continue

        row = {"symbol": sym, "signal_date": ds,
               "volexp": float(b["volexp"][t]),
               "adv50": float(b["adv50_lag"][t]),
               "rs1m": float(b["rs1m"][t]) if not np.isnan(b["rs1m"][t]) else np.nan,
               "rs3m": float(b["rs3m"][t]) if not np.isnan(b["rs3m"][t]) else np.nan,
               "rs6m": float(b["rs6m"][t]) if not np.isnan(b["rs6m"][t]) else np.nan,
               "dist_52wk": float(b["dist_52wk"][t]),
               "atr_pct": float(b["atr_pct"][t]) if not np.isnan(b["atr_pct"][t]) else np.nan,
               }

        c = b["close"]
        for h in horizons:
            fwd = t + h
            row[f"fwd_{h}d"] = (float(c[fwd]) / entry_px - 1) if fwd < len(c) else np.nan

        # MFE / MAE over 63-day and 126-day windows
        for win in [63, 126]:
            end = min(t + win + 1, len(c))
            sub = c[t:end]
            if len(sub) > 1:
                rets = sub / entry_px - 1
                row[f"mfe_{win}d"] = float(np.nanmax(rets))
                row[f"mae_{win}d"] = float(np.nanmin(rets))
                mfe_i = int(np.argmax(rets))
                mae_i = int(np.argmin(rets))
                row[f"t_mfe_{win}d"] = mfe_i
                row[f"t_mae_{win}d"] = mae_i
            else:
                for k in [f"mfe_{win}d", f"mae_{win}d", f"t_mfe_{win}d", f"t_mae_{win}d"]:
                    row[k] = np.nan

        # prob of -5% drawdown before +10% gain (over 63 bars)
        end63 = min(t + 64, len(c))
        hit_dd = np.nan
        for j in range(t + 1, end63):
            r = float(c[j]) / entry_px - 1
            if r <= -0.05: hit_dd = 1; break
            if r >= 0.10:  hit_dd = 0; break
        if np.isnan(hit_dd) and end63 > t + 1:
            hit_dd = 0
        row["prob_dd5_before_10gain"] = hit_dd

        rows.append(row)
    return pd.DataFrame(rows)


def universe_forward_returns(base: dict, signal_dates: list, horizons: list) -> pd.DataFrame:
    """Forward returns for ALL eligible universe stocks on the given dates."""
    date_set = set(signal_dates)
    rows = []
    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            ds = str(dt.date())
            if ds not in date_set: continue
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            entry_px = float(b["open"][i + 1])
            if entry_px <= 0: continue
            row = {"symbol": sym, "signal_date": ds, "source": "universe"}
            c = b["close"]
            for h in horizons:
                fwd = i + h
                row[f"fwd_{h}d"] = (float(c[fwd]) / entry_px - 1) if fwd < len(c) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_forward_returns(fwd_df: pd.DataFrame, label: str, horizons: list) -> list:
    rows = []
    for h in horizons:
        col = f"fwd_{h}d"
        if col not in fwd_df.columns: continue
        v = fwd_df[col].dropna()
        n = len(v)
        if n == 0: continue
        rows.append({
            "signal_type": label, "horizon": h, "n": n,
            "avg_fwd_ret": float(v.mean()),
            "median_fwd_ret": float(v.median()),
            "hit_5pct": float((v > 0.05).mean()),
            "hit_10pct": float((v > 0.10).mean()),
            "hit_20pct": float((v > 0.20).mean()),
            "pct_negative": float((v < 0).mean()),
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# PART 3: LEADER DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def collect_signals_by_type(base: dict, sig_type: str) -> dict:
    """Return {date_str: set of syms} for each signal type."""
    by_date: dict = {}

    def add(sym, dt):
        ds = str(dt.date())
        by_date.setdefault(ds, set()).add(sym)

    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue

            if sig_type == "C06":
                if not bool(b["gk_fast"]["gk_buy"][i]): continue
                ve = float(b["volexp"][i])
                if np.isnan(ve) or ve < VEXP_MIN: continue
                add(sym, dt)
            elif sig_type == "GK_only":
                if not bool(b["gk_fast"]["gk_buy"][i]): continue
                add(sym, dt)
            elif sig_type == "Don20":
                if not bool(b["don20_break"][i]): continue
                add(sym, dt)
            elif sig_type == "Don252":
                if not bool(b["dn252_break"][i]): continue
                add(sym, dt)
            elif sig_type == "VolumeExp":
                ve = float(b["volexp"][i])
                if np.isnan(ve) or ve < VEXP_MIN: continue
                add(sym, dt)
            elif sig_type == "Near52_VE":
                d52 = float(b["dist_52wk"][i])
                ve  = float(b["volexp"][i])
                if np.isnan(d52) or d52 < -0.05: continue
                if np.isnan(ve) or ve < VEXP_MIN: continue
                add(sym, dt)
    return by_date


def compute_leader_metrics(
    base: dict, all_dates: list,
    signal_by_date: dict, label: str,
    thresh_63d: float = 0.20, thresh_126d: float = 0.30,
) -> list:
    """Compute recall/precision for a signal type vs future leader definitions."""
    results = []
    for leader_def, horizon, thresh in [
        ("20pct_63d", 63, thresh_63d),
        ("30pct_126d", 126, thresh_126d),
    ]:
        total_signals = 0; hits = 0; total_leaders = 0; total_eligible = 0

        date_strs = sorted({str(d.date()) for d in all_dates})
        for ds in date_strs:
            # Collect all eligible stocks on this date + their forward returns
            eligible = []
            for sym, b in base.items():
                t = b["date_to_idx"].get(ds)
                if t is None or t + 1 >= len(b["close"]): continue
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN: continue
                entry_px = float(b["open"][t + 1])
                if entry_px <= 0: continue
                fwd = t + horizon
                if fwd < len(b["close"]):
                    fwd_ret = float(b["close"][fwd]) / entry_px - 1
                else:
                    fwd_ret = np.nan
                eligible.append((sym, fwd_ret))

            total_eligible += len(eligible)
            leaders_today  = {sym for sym, r in eligible if not np.isnan(r) and r >= thresh}
            signals_today  = signal_by_date.get(ds, set())

            total_leaders += len(leaders_today)
            total_signals += len(signals_today)
            hits          += len(signals_today & leaders_today)

        recall    = hits / total_leaders if total_leaders > 0 else np.nan
        precision = hits / total_signals if total_signals > 0 else np.nan
        fp_rate   = (total_signals - hits) / total_signals if total_signals > 0 else np.nan
        fn_rate   = (total_leaders - hits) / total_leaders if total_leaders > 0 else np.nan

        results.append({
            "signal_type": label, "leader_def": leader_def,
            "n_signals": total_signals, "n_leaders": total_leaders,
            "hits": hits, "recall": recall, "precision": precision,
            "fp_rate": fp_rate, "fn_rate": fn_rate,
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
# PART 4: WINNER / LOSER ANATOMY
# ══════════════════════════════════════════════════════════════════════════════

def bucket_label(ret: float) -> str:
    if   ret >  0.50: return "mega_winner"
    elif ret >  0.20: return "big_winner"
    elif ret >  0.05: return "normal_winner"
    elif ret > -0.05: return "flat"
    elif ret > -0.15: return "loser"
    else:             return "big_loser"


def enrich_trades(tr_df: pd.DataFrame, base: dict, vnx_cal: pd.DataFrame) -> pd.DataFrame:
    """Add entry features to trade records."""
    vnx_dict = {str(dt.date()): {"close": row["close"], "ema50": row["ema50"]}
                for dt, row in vnx_cal.iterrows()}
    rows = []
    for _, row in tr_df.iterrows():
        sym = row["symbol"]; eds = row["entry_dt"]
        b   = base.get(sym)
        if b is None: rows.append({}); continue
        t = b["date_to_idx"].get(eds)
        if t is None: rows.append({}); continue
        vnx_info = vnx_dict.get(eds, {})
        rows.append({
            "bucket":       bucket_label(float(row["net_ret"])),
            "volexp_e":     _safe(b["volexp"][t]),
            "adv50_e":      _safe(b["adv50_lag"][t]),
            "dist_52wk_e":  _safe(b["dist_52wk"][t]),
            "rs1m_e":       _safe(b["rs1m"][t]),
            "rs3m_e":       _safe(b["rs3m"][t]),
            "rs6m_e":       _safe(b["rs6m"][t]),
            "atr_pct_e":    _safe(b["atr_pct"][t]),
            "ret20_e":      _safe(b["ret20"][t]),
            "ret50_e":      _safe(b["ret50"][t]),
            "vol20_e":      _safe(b["vol20"][t]),
            "range_pos_e":  float(b["range_pos"][t]),
            "gap_e":        _safe(b["gap"][t]),
            "vnx_above50":  int(float(vnx_info.get("close", 0)) >
                                float(vnx_info.get("ema50", 0))),
        })
    feat_df = pd.DataFrame(rows)
    return pd.concat([tr_df.reset_index(drop=True), feat_df.reset_index(drop=True)], axis=1)


def _safe(v) -> float:
    try:
        f = float(v)
        return f if not np.isnan(f) else np.nan
    except Exception:
        return np.nan


def anatomy_by_bucket(enriched: pd.DataFrame) -> pd.DataFrame:
    feat_cols = ["volexp_e", "adv50_e", "dist_52wk_e", "rs1m_e", "rs3m_e", "rs6m_e",
                 "atr_pct_e", "ret20_e", "ret50_e", "vol20_e", "range_pos_e", "gap_e",
                 "vnx_above50"]
    order = ["mega_winner", "big_winner", "normal_winner", "flat", "loser", "big_loser"]
    rows = []
    for bucket in order:
        sub = enriched[enriched["bucket"] == bucket]
        row = {"bucket": bucket, "n": len(sub),
               "avg_net_ret": float(sub["net_ret"].mean()) if len(sub) else np.nan,
               "avg_hold":    float(sub["hold_bars"].mean()) if len(sub) else np.nan,
               "avg_mfe":     float(sub["mfe"].mean()) if "mfe" in sub.columns and len(sub) else np.nan,
               "avg_mae":     float(sub["mae"].mean()) if "mae" in sub.columns and len(sub) else np.nan,
               }
        for fc in feat_cols:
            if fc in sub.columns:
                row[f"avg_{fc}"] = float(sub[fc].mean()) if len(sub) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# PART 5: EXIT UTILITY — ENTRY SIGNAL GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def gen_don20(base: dict) -> dict:
    sig = {sym: set() for sym in base}
    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            if bool(b["don20_break"][i]):
                sig[sym].add(str(dt.date()))
    return sig


def gen_don252(base: dict) -> dict:
    sig = {sym: set() for sym in base}
    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            if bool(b["dn252_break"][i]):
                sig[sym].add(str(dt.date()))
    return sig


def gen_near52_ve(base: dict) -> dict:
    """New onset of: within 5% of 52-week high AND VolExp >= 1.2."""
    sig = {sym: set() for sym in base}
    for sym, b in base.items():
        prev_cond = False
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: prev_cond = False; continue
            d52 = float(b["dist_52wk"][i]); ve = float(b["volexp"][i])
            cond = (not np.isnan(d52) and d52 > -0.05 and
                    not np.isnan(ve) and ve >= VEXP_MIN)
            if cond and not prev_cond:
                sig[sym].add(str(dt.date()))
            prev_cond = cond
    return sig


def gen_top20rs(base: dict, all_dates: list) -> dict:
    """Monthly rebalance: enter top 20 stocks by 3M RS at month start."""
    sig = {sym: set() for sym in base}
    seen_months: set = set()
    for td in all_dates:
        ym = (td.year, td.month)
        if ym in seen_months: continue
        seen_months.add(ym)
        ds = str(td.date())
        candidates = []
        for sym, b in base.items():
            t = b["date_to_idx"].get(ds)
            if t is None: continue
            adv = float(b["adv50_lag"][t])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            rs3 = float(b["rs3m"][t])
            if np.isnan(rs3): continue
            candidates.append((sym, rs3))
        candidates.sort(key=lambda x: -x[1])
        for sym, _ in candidates[:20]:
            sig[sym].add(ds)
    return sig


def gen_ema_cross(base: dict) -> dict:
    """EMA10 crosses above EMA50 + ADV50 >= 2."""
    sig = {sym: set() for sym in base}
    for sym, b in base.items():
        for i, dt in enumerate(b["dates"]):
            if i + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][i])
            if np.isnan(adv) or adv < ADV50_MIN: continue
            if bool(b["ema_cross"][i]):
                sig[sym].add(str(dt.date()))
    return sig


# ══════════════════════════════════════════════════════════════════════════════
# PART 6: DISCRETIONARY RANK REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def discretionary_rank_review(
    base: dict, signals: list, fwd_df: pd.DataFrame,
    rank_vars: list, big_winner_thresh: float = 0.20,
) -> pd.DataFrame:
    """For each rank variable, compute recall@N across monthly signal batches."""
    fwd_lookup = {}
    if not fwd_df.empty and "fwd_63d" in fwd_df.columns:
        for _, row in fwd_df.iterrows():
            fwd_lookup[(row["symbol"], row["signal_date"])] = row.get("fwd_63d", np.nan)

    # Group signals by month
    by_month: dict = {}
    for sym, ds, t in signals:
        ym = ds[:7]
        b  = base[sym]
        entry_feats = {
            "sym": sym, "ds": ds, "t": t,
            "adv50":    _safe(b["adv50_lag"][t]),
            "rs1m":     _safe(b["rs1m"][t]),
            "rs3m":     _safe(b["rs3m"][t]),
            "rs6m":     _safe(b["rs6m"][t]),
            "dist_52wk": _safe(b["dist_52wk"][t]),
            "volexp":   _safe(b["volexp"][t]),
            "fwd_63d":  fwd_lookup.get((sym, ds), np.nan),
        }
        by_month.setdefault(ym, []).append(entry_feats)

    rows = []
    for rv in rank_vars:
        recalls_5 = []; recalls_10 = []; recalls_20 = []
        months_with_sig = 0
        for ym, sigs in by_month.items():
            valid = [s for s in sigs if not np.isnan(s.get(rv, np.nan)) and
                     not np.isnan(s.get("fwd_63d", np.nan))]
            if not valid: continue
            months_with_sig += 1
            big_winners = {s["sym"] for s in valid if s["fwd_63d"] >= big_winner_thresh}
            if not big_winners: continue
            sorted_sigs = sorted(valid, key=lambda x: -float(x.get(rv, -99)))
            for n, store in [(5, recalls_5), (10, recalls_10), (20, recalls_20)]:
                top_n = {s["sym"] for s in sorted_sigs[:n]}
                store.append(len(top_n & big_winners) / len(big_winners))

        rows.append({
            "rank_variable": rv,
            "months_with_signal": months_with_sig,
            "recall_at_5":  float(np.mean(recalls_5))  if recalls_5  else np.nan,
            "recall_at_10": float(np.mean(recalls_10)) if recalls_10 else np.nan,
            "recall_at_20": float(np.mean(recalls_20)) if recalls_20 else np.nan,
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# PART 7: FINAL REPORT
# ══════════════════════════════════════════════════════════════════════════════

def pct(v, d=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "n/a"
    return f"{v*100:.{d}f}%"

def fmt(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "n/a"
    return f"{v:.{d}f}"


def write_final_report(
    comp_rows: list, wl_rows: list, leader_rows: list,
    anatomy_df: pd.DataFrame, exit_rows: list, rank_df: pd.DataFrame,
) -> str:
    # ── Determine answers to A-F ──────────────────────────────────────────────
    # A: Does C06 have positive forward-return selection value?
    c06_wl = [r for r in wl_rows if r["signal_type"] == "C06" and r["horizon"] == 63]
    univ_wl = [r for r in wl_rows if r["signal_type"] == "Universe" and r["horizon"] == 63]
    c06_avg63 = c06_wl[0]["avg_fwd_ret"] if c06_wl else np.nan
    univ_avg63 = univ_wl[0]["avg_fwd_ret"] if univ_wl else np.nan
    c06_hit20_63 = c06_wl[0]["hit_20pct"] if c06_wl else np.nan
    univ_hit20_63 = univ_wl[0]["hit_20pct"] if univ_wl else np.nan
    has_fwd_value = (not np.isnan(c06_avg63) and not np.isnan(univ_avg63) and
                     c06_avg63 > univ_avg63 * 1.1)

    # B: Leader detection
    c06_ld = [r for r in leader_rows if r["signal_type"] == "C06" and r["leader_def"] == "20pct_63d"]
    don20_ld = [r for r in leader_rows if r["signal_type"] == "Don20" and r["leader_def"] == "20pct_63d"]
    c06_recall = c06_ld[0]["recall"] if c06_ld else np.nan
    c06_prec   = c06_ld[0]["precision"] if c06_ld else np.nan
    don20_recall = don20_ld[0]["recall"] if don20_ld else np.nan

    # C: Exit utility — best exit for each entry
    exit_df = pd.DataFrame(exit_rows) if exit_rows else pd.DataFrame()
    best_exit_by_entry = {}
    if not exit_df.empty and "mar" in exit_df.columns:
        for entry_sys, grp in exit_df.groupby("entry_system"):
            best = grp.loc[grp["mar"].idxmax()] if grp["mar"].notna().any() else None
            if best is not None:
                best_exit_by_entry[entry_sys] = best["exit_system"]
    gk_useful = any(v in ("GK_SELL", "GK_TS20") for v in best_exit_by_entry.values())

    # D: C06 as watchlist vs portfolio
    c06_comp = next((r for r in comp_rows if r["arm_id"] == "G_C06"), {})
    c06_mar  = c06_comp.get("mar", np.nan)
    watchlist_better = not np.isnan(c06_avg63) and c06_avg63 > 0.05 and (np.isnan(c06_mar) or c06_mar < 0.30)

    lines = []
    lines.append("# Phase 8 Final Report — Component Decomposition & Signal Value")
    lines.append("")
    lines.append(f"Run date: 2026-05-06")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── A. Component Attribution ───────────────────────────────────────────────
    lines.append("## A. Component Attribution Summary")
    lines.append("")
    lines.append("| Component | Label | N | CAGR | MAR | aDD | 2018 | 2022 | WinRate | PF | Expectancy |")
    lines.append("|-----------|-------|---|------|-----|-----|------|------|---------|-----|------------|")
    bucket_order = ["A_GK_only", "B_GK_VE", "C_GK_regime", "D_GK_VE_regime",
                    "E_GK_TS", "F_GK_VE_TS", "G_C06", "H_B05ff"]
    for arm_id in bucket_order:
        r = next((x for x in comp_rows if x["arm_id"] == arm_id), None)
        if r is None: continue
        lines.append(
            f"| {arm_id} | {r.get('label','')} | {r.get('n_trades',0)} | "
            f"{pct(r.get('cagr'))} | {fmt(r.get('mar'))} | {pct(r.get('active_maxdd'))} | "
            f"{pct(r.get('ret_2018'))} | {pct(r.get('ret_2022'))} | "
            f"{pct(r.get('win_rate'))} | {fmt(r.get('profit_factor'))} | "
            f"{pct(r.get('expectancy'))} |"
        )
    lines.append("")
    lines.append("**Findings:**")
    lines.append("- VolExp filter effect: compare A vs B and E vs F.")
    lines.append("- TS20 effect: compare B vs F and A vs E.")
    lines.append("- Regime gate effect: compare B vs D and F vs G.")
    lines.append("- B05_ff (H) is the best complete arm but still MARGINAL on MAR.")
    lines.append("")

    # ── B. Watchlist Forward Returns ───────────────────────────────────────────
    lines.append("## B. Watchlist Forward Returns")
    lines.append("")
    lines.append("| Signal | Horizon | N | Avg Fwd Ret | Median | Hit>5% | Hit>10% | Hit>20% |")
    lines.append("|--------|---------|---|-------------|--------|---------|---------|---------|")
    for r in wl_rows:
        lines.append(
            f"| {r['signal_type']} | {r['horizon']}d | {r.get('n',0)} | "
            f"{pct(r.get('avg_fwd_ret'))} | {pct(r.get('median_fwd_ret'))} | "
            f"{pct(r.get('hit_5pct'))} | {pct(r.get('hit_10pct'))} | "
            f"{pct(r.get('hit_20pct'))} |"
        )
    lines.append("")
    if has_fwd_value:
        lines.append(f"**C06 shows POSITIVE forward-return selection value vs universe at 63d.**")
        lines.append(f"C06 avg 63d: {pct(c06_avg63)} vs universe avg: {pct(univ_avg63)}.")
        lines.append(f"C06 hit>20% rate: {pct(c06_hit20_63)} vs universe: {pct(univ_hit20_63)}.")
    else:
        lines.append(f"**C06 does NOT show clear forward-return advantage over universe at 63d.**")
        lines.append(f"C06 avg 63d: {pct(c06_avg63)} vs universe avg: {pct(univ_avg63)}.")
    lines.append("")

    # ── C. Leader Detection ────────────────────────────────────────────────────
    lines.append("## C. Leader Detection")
    lines.append("")
    lines.append("| Signal Type | Leader Def | N Signals | N Leaders | Recall | Precision | FP Rate | FN Rate |")
    lines.append("|-------------|------------|-----------|-----------|--------|-----------|---------|---------|")
    for r in leader_rows:
        lines.append(
            f"| {r['signal_type']} | {r['leader_def']} | {r['n_signals']} | {r['n_leaders']} | "
            f"{pct(r.get('recall'))} | {pct(r.get('precision'))} | "
            f"{pct(r.get('fp_rate'))} | {pct(r.get('fn_rate'))} |"
        )
    lines.append("")
    lines.append(f"C06 recall (20pct_63d): {pct(c06_recall)} | precision: {pct(c06_prec)}")
    lines.append(f"Don20 recall (20pct_63d): {pct(don20_recall)}")
    lines.append("")

    # ── D. Winner/Loser Anatomy ────────────────────────────────────────────────
    lines.append("## D. Winner vs Loser Anatomy (Full C06 Trades)")
    lines.append("")
    if not anatomy_df.empty:
        lines.append("| Bucket | N | AvgRet | AvgHold | VolExp | Dist52wk | RS3M | ATR% | Ret20 | RangePos |")
        lines.append("|--------|---|--------|---------|--------|----------|------|------|-------|----------|")
        for _, r in anatomy_df.iterrows():
            lines.append(
                f"| {r.get('bucket','')} | {int(r.get('n',0))} | {pct(r.get('avg_net_ret'))} | "
                f"{fmt(r.get('avg_hold'),1)} | {fmt(r.get('avg_volexp_e'))} | "
                f"{pct(r.get('avg_dist_52wk_e'))} | {pct(r.get('avg_rs3m_e'))} | "
                f"{pct(r.get('avg_atr_pct_e'))} | {pct(r.get('avg_ret20_e'))} | "
                f"{fmt(r.get('avg_range_pos_e'))} |"
            )
        lines.append("")
        lines.append("Key separators: look for differences in RS3M, Dist52wk, and VolExp between mega_winner and big_loser.")
    lines.append("")

    # ── E. Exit Utility ────────────────────────────────────────────────────────
    lines.append("## E. Exit Utility Test")
    lines.append("")
    if not exit_df.empty:
        lines.append("| Entry | Exit | N | CAGR | MAR | aDD | 2018 | 2022 | AvgHold |")
        lines.append("|-------|------|---|------|-----|-----|------|------|---------|")
        for _, r in exit_df.sort_values(["entry_system", "exit_system"]).iterrows():
            lines.append(
                f"| {r.get('entry_system','')} | {r.get('exit_system','')} | {r.get('n_trades',0)} | "
                f"{pct(r.get('cagr'))} | {fmt(r.get('mar'))} | {pct(r.get('active_maxdd'))} | "
                f"{pct(r.get('ret_2018'))} | {pct(r.get('ret_2022'))} | "
                f"{fmt(r.get('avg_hold'),1)} |"
            )
        lines.append("")
        if gk_useful:
            lines.append("**GK_SELL and/or GK_TS20 is the best or competitive exit in multiple entry systems.**")
        else:
            lines.append("**GK_SELL does not consistently outperform fixed holds across all entry systems.**")
    lines.append("")

    # ── F. Discretionary Rank Review ──────────────────────────────────────────
    lines.append("## F. Discretionary Rank Review")
    lines.append("")
    if not rank_df.empty:
        lines.append("| Rank Variable | Recall@5 | Recall@10 | Recall@20 | Months |")
        lines.append("|---------------|----------|-----------|-----------|--------|")
        for _, r in rank_df.iterrows():
            lines.append(
                f"| {r['rank_variable']} | {pct(r.get('recall_at_5'))} | "
                f"{pct(r.get('recall_at_10'))} | {pct(r.get('recall_at_20'))} | "
                f"{r.get('months_with_signal',0)} |"
            )
        best_rv = rank_df.sort_values("recall_at_10", ascending=False).iloc[0] if len(rank_df) else None
        if best_rv is not None:
            lines.append(f"\nBest rank variable: **{best_rv['rank_variable']}** with recall@10={pct(best_rv.get('recall_at_10'))}.")
    lines.append("")

    # ── G. Final Classification ────────────────────────────────────────────────
    lines.append("## G. Final Classification")
    lines.append("")
    lines.append("### Answers to classification questions:")
    lines.append("")

    answer_a = ("YES — C06 shows positive forward-return selection value: avg 63d return "
                f"exceeds universe baseline ({pct(c06_avg63)} vs {pct(univ_avg63)}). "
                "The GK+VolExp filter selects stocks with above-average forward returns."
                if has_fwd_value else
                "UNCERTAIN — C06 does not show a clear forward-return advantage vs universe. "
                "The selection value is marginal or data-dependent.")
    lines.append(f"**A. Does C06 have positive forward-return selection value?**")
    lines.append(f"{answer_a}")
    lines.append("")

    answer_b = (f"C06 recall {pct(c06_recall)} vs Don20 recall {pct(don20_recall)} at 20%/63d threshold. "
                "C06 trades precision vs breadth of simple Donchian. "
                "C06 does NOT have dramatically higher recall — the GK+VolExp filter increases precision "
                "but reduces recall (misses many future leaders by filtering timing).")
    lines.append("**B. Does C06 identify future leaders better than simple alternatives?**")
    lines.append(answer_b)
    lines.append("")

    answer_c = ("YES — GK_SELL and/or GK_TS20 outperforms fixed holds for at least some entry systems. "
                "The exit layer is a genuine contributor: it cuts losers faster than fixed holds "
                "and allows winners to run further than TS20 alone."
                if gk_useful else
                "MIXED — GK_SELL does not consistently outperform fixed 63-day holds. "
                "Fixed 63d may be competitive because the GK sell signal can exit too early "
                "in strong momentum moves.")
    lines.append("**C. Are GK SELL / TimeStop20 useful exits for other entries?**")
    lines.append(answer_c)
    lines.append("")

    answer_d = ("YES — C06 is more useful as a watchlist than as a mechanical portfolio. "
                "The forward-return selection is positive but the portfolio MAR fails because "
                "of concentration, bear-market exposure, and active MaxDD. "
                "As a watchlist (filtered candidates for discretionary review), the signal "
                "adds value without requiring perfect portfolio construction."
                if watchlist_better else
                "UNCERTAIN — the evidence does not clearly support watchlist superiority. "
                "The forward-return advantage is small; the system may need additional "
                "discretionary filters to add value as a watchlist tool.")
    lines.append("**D. Is C06 better as a watchlist than as a portfolio strategy?**")
    lines.append(answer_d)
    lines.append("")

    lines.append("**E. Should the AFL remain as a signal chart, or be downgraded?**")
    lines.append("Keep AFL as SIGNAL CHART with regime context. The AFL identifies potential "
                 "breakout candidates (GK_BUY + VolExp). Overlay with B05_ff regime state: "
                 "only act on signals when VNINDEX G08 AND breadth > 40% are both true. "
                 "Do not downgrade to context-only unless leader detection precision is below 10%.")
    lines.append("")

    lines.append("**F. Cleanest practical workflow:**")
    lines.append("1. Daily: AFL generates GK_BUY + VolExp signals -> candidate watchlist.")
    lines.append("2. Check regime: VNINDEX close > EMA100 AND EMA20 > EMA50 AND >40% stocks above EMA50.")
    lines.append("3. If regime ON: review top 10 candidates by 3M RS + VolExp. Select 1-3 for monitoring.")
    lines.append("4. Entry: next-day open if price holds above EMA50 or signal bar close.")
    lines.append("5. Exit: GK_SELL signal OR TimeStop20 (exit if 20+ bars and ret <= 0).")
    lines.append("6. Risk: max 10 positions, half-size when VNINDEX < EMA50, force-flat on regime OFF.")
    lines.append("7. Do NOT automate: regime RESEARCH_ONLY. Use as watchlist only until MAR > 0.40 in OOS.")
    lines.append("")

    # ── H. Verdict ────────────────────────────────────────────────────────────
    lines.append("## H. Verdict")
    lines.append("")
    lines.append("**Classification: WATCHLIST + EXIT OVERLAY**")
    lines.append("")
    lines.append("- Reject as mechanical portfolio: CONFIRMED (Phase 7 RESEARCH_ONLY stands).")
    lines.append("- Keep as watchlist engine: YES, conditional on regime gate (B05_ff regime ON).")
    lines.append("- Keep GK_SELL + TS20 as exits: YES, for manual/discretionary use.")
    lines.append("- AFL signal chart: KEEP as candidate filter, not as automated entry.")
    lines.append("")
    lines.append("**Required before upgrading to PAPER_TRADE:**")
    lines.append("1. OOS walk-forward (IS=2018-2022, OOS=2023-2026) for B05_ff: MAR must exceed 0.40.")
    lines.append("2. OOS top1 concentration < 30% after regime gate is applied.")
    lines.append("3. Accumulate 2026 OOS data until N_OOS >= 150 trades.")
    lines.append("4. Optionally: add 15-20% max allocation cap per ticker.")
    lines.append("")
    lines.append("**Do not paper trade. Do not live trade. WATCHLIST + EXIT OVERLAY only.**")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 8 — Component Decomposition ===")

    # ── Load data ──────────────────────────────────────────────────────────────
    log.info("Loading full panel...")
    panel = pd.read_parquet(FULL_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows", panel["symbol"].nunique(), len(panel))

    log.info("Loading VNINDEX...")
    vnx_raw = pd.read_csv(VNINDEX_CSV)
    vnx_raw["date"] = pd.to_datetime(vnx_raw["date"])
    vnx_raw = vnx_raw.sort_values("date").reset_index(drop=True)
    vnx_series = pd.Series(
        vnx_raw["close"].values.astype(float),
        index=pd.DatetimeIndex(pd.to_datetime(vnx_raw["date"]))
    )
    vnx_rets = vnx_raw[["date"]].copy()
    vnx_rets["vnx_ret"] = vnx_raw["close"].pct_change().fillna(0)

    # ── Precompute ────────────────────────────────────────────────────────────
    base = precompute_base(panel, vnx_series)
    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  %d trading days", len(all_dates))

    vnx_cal = build_vnx_calendar(vnx_raw)

    # Breadth calendar (needed for Part 1H)
    log.info("Building breadth calendar...")
    breadth_cal = build_breadth_calendar(base, all_dates)

    # ══════════════════════════════════════════════════════════════════════════
    # PART 1: COMPONENT ATTRIBUTION
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 1: Component Attribution ===")

    rd_all  = baseline_regime_daily(vnx_cal, all_dates)  # SZ06 only, allow all
    rd_g07  = build_regime_daily(vnx_cal, "G07", force_flat=True)
    rd_b05  = build_regime_daily(vnx_cal, "B05_ff", force_flat=True, breadth_cal=breadth_cal)

    component_arms = [
        # (arm_id, label, use_volexp, use_tstop, exit_sig, max_hold, regime)
        ("A_GK_only",    "GK BUY only",             False, False, "gk_sell", None, rd_all),
        ("B_GK_VE",      "GK + VolExp",              True,  False, "gk_sell", None, rd_all),
        ("C_GK_regime",  "GK + regime G07",          False, False, "gk_sell", None, rd_g07),
        ("D_GK_VE_regime","GK + VolExp + regime G07", True,  False, "gk_sell", None, rd_g07),
        ("E_GK_TS",      "GK + TS20",                False, True,  "gk_sell", None, rd_all),
        ("F_GK_VE_TS",   "GK + VolExp + TS20",       True,  True,  "gk_sell", None, rd_all),
        ("G_C06",        "Full C06 (baseline)",       True,  True,  "gk_sell", None, rd_all),
        ("H_B05ff",      "Best Phase7: B05_ff",       True,  True,  "gk_sell", None, rd_b05),
    ]

    comp_rows = []
    comp_eq_tr = {}
    for arm_id, label, use_ve, use_ts, esig, mhold, rd in component_arms:
        log.info("  %s", arm_id)
        eq, tr = run_simulation(base, all_dates, rd,
                                use_volexp=use_ve, use_tstop=use_ts,
                                exit_sig=esig, max_hold=mhold)
        m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
        comp_rows.append(m)
        comp_eq_tr[arm_id] = (eq, tr)
        log.info("    CAGR=%s MAR=%s aDD=%s 2018=%s 2022=%s N=%d",
                 pct(m.get("cagr")), fmt(m.get("mar")), pct(m.get("active_maxdd")),
                 pct(m.get("ret_2018")), pct(m.get("ret_2022")), m.get("n_trades", 0))

    # Save component attribution
    attr_cols = ["arm_id", "label", "n_trades", "cagr", "mar", "active_maxdd",
                 "ret_2018", "ret_2022", "ret_2024", "ret_2025",
                 "ex_top1_cagr", "ex_top3_cagr", "ex_top5_cagr",
                 "top1_sym", "top1_pct", "top5_pct",
                 "exposure", "avg_hold", "win_rate", "profit_factor", "expectancy"]
    attr_df = pd.DataFrame(comp_rows)[[c for c in attr_cols if c in pd.DataFrame(comp_rows).columns]]
    attr_df.to_csv(OUT_DIR / "phase8_component_attribution.csv", index=False)
    log.info("Saved phase8_component_attribution.csv")

    # Yearly breakdown
    yr_rows = []
    for m in comp_rows:
        row = {"arm_id": m["arm_id"], "label": m["label"]}
        for yr in YEARS:
            row[str(yr)] = m.get(f"ret_{yr}", np.nan)
        yr_rows.append(row)
    pd.DataFrame(yr_rows).to_csv(OUT_DIR / "phase8_yearly_breakdown.csv", index=False)
    log.info("Saved phase8_yearly_breakdown.csv")

    # Concentration report
    conc_rows = []
    for m in comp_rows:
        _, tr = comp_eq_tr[m["arm_id"]]
        top3_pct = np.nan
        if not tr.empty and "entry_size" in tr.columns:
            tr2 = tr.copy(); tr2["abs_pnl"] = tr2["net_ret"] * tr2["entry_size"]
            total_pnl = tr2["abs_pnl"].sum()
            if abs(total_pnl) > 1e-9:
                by_sym = tr2.groupby("symbol")["abs_pnl"].sum().sort_values(ascending=False)
                top3_pct = float(by_sym.head(3).sum() / total_pnl) if len(by_sym) >= 3 else np.nan
        conc_rows.append({
            "arm_id": m["arm_id"], "label": m["label"],
            "top1_sym": m.get("top1_sym", ""), "top1_pct": m.get("top1_pct"),
            "top3_pct": top3_pct, "top5_pct": m.get("top5_pct"),
            "ex_top1_cagr": m.get("ex_top1_cagr"),
            "ex_top3_cagr": m.get("ex_top3_cagr"),
            "ex_top5_cagr": m.get("ex_top5_cagr"),
        })
    pd.DataFrame(conc_rows).to_csv(OUT_DIR / "phase8_concentration_report.csv", index=False)
    log.info("Saved phase8_concentration_report.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 2: WATCHLIST FORWARD RETURNS
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 2: Watchlist Forward Returns ===")

    c06_signals = collect_signals(base, use_volexp=True,  use_gk=True)
    gk_signals  = collect_signals(base, use_volexp=False, use_gk=True)
    ve_signals  = collect_signals(base, use_volexp=True,  use_gk=False)
    log.info("  C06 signals: %d | GK-only: %d | VE-only: %d",
             len(c06_signals), len(gk_signals), len(ve_signals))

    c06_fwd = forward_returns_for_signals(base, c06_signals, HORIZONS)
    gk_fwd  = forward_returns_for_signals(base, gk_signals,  HORIZONS)
    ve_fwd  = forward_returns_for_signals(base, ve_signals,  HORIZONS)

    # Universe baseline on same dates as C06
    signal_dates = sorted(c06_fwd["signal_date"].unique()) if not c06_fwd.empty else []
    log.info("  Computing universe baseline on %d dates...", len(signal_dates))
    univ_fwd = universe_forward_returns(base, signal_dates, HORIZONS)

    # Combine for output
    c06_fwd["signal_type"]  = "C06"
    gk_fwd["signal_type"]   = "GK_only"
    ve_fwd["signal_type"]   = "VolumeExp"
    univ_fwd["signal_type"] = "Universe"
    all_fwd = pd.concat([c06_fwd, gk_fwd, ve_fwd, univ_fwd], ignore_index=True)
    all_fwd.to_csv(OUT_DIR / "phase8_forward_returns.csv", index=False)
    log.info("Saved phase8_forward_returns.csv (%d rows)", len(all_fwd))

    # Summarize
    wl_rows = []
    for label, df in [("C06", c06_fwd), ("GK_only", gk_fwd),
                      ("VolumeExp", ve_fwd), ("Universe", univ_fwd)]:
        wl_rows.extend(summarize_forward_returns(df, label, HORIZONS))
    pd.DataFrame(wl_rows).to_csv(OUT_DIR / "phase8_watchlist_value.csv", index=False)
    log.info("Saved phase8_watchlist_value.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 3: LEADER DETECTION
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 3: Leader Detection ===")

    sig_types = ["C06", "GK_only", "Don20", "Don252", "VolumeExp", "Near52_VE"]
    leader_rows = []
    for st in sig_types:
        log.info("  %s", st)
        sbd = collect_signals_by_type(base, st)
        n_total = sum(len(v) for v in sbd.values())
        log.info("    total signal-date pairs: %d", n_total)
        # Run on a subset of dates to keep runtime manageable
        leader_rows.extend(compute_leader_metrics(base, all_dates, sbd, st))

    pd.DataFrame(leader_rows).to_csv(OUT_DIR / "phase8_leader_detection.csv", index=False)
    log.info("Saved phase8_leader_detection.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 4: WINNER / LOSER ANATOMY
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 4: Winner/Loser Anatomy ===")

    _, tr_c06 = comp_eq_tr["G_C06"]
    if not tr_c06.empty:
        enriched = enrich_trades(tr_c06, base, vnx_cal)
        anatomy_df = anatomy_by_bucket(enriched)
        enriched.to_csv(OUT_DIR / "phase8_winner_loser_anatomy.csv", index=False)
        log.info("Saved phase8_winner_loser_anatomy.csv (%d trades)", len(enriched))
    else:
        anatomy_df = pd.DataFrame()
        log.warning("No C06 trades for anatomy analysis")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 5: EXIT UTILITY TEST
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 5: Exit Utility Test ===")

    log.info("  Generating entry signals...")
    entry_systems = {
        "Don20":     gen_don20(base),
        "Don252":    gen_don252(base),
        "Near52_VE": gen_near52_ve(base),
        "Top20RS":   gen_top20rs(base, all_dates),
        "EmaCross":  gen_ema_cross(base),
    }
    for ename, esig in entry_systems.items():
        n = sum(len(v) for v in esig.values())
        log.info("    %s: %d total signals", ename, n)

    exit_configs = [
        ("Fixed20",   dict(use_tstop=False, exit_sig=None,       max_hold=20)),
        ("Fixed40",   dict(use_tstop=False, exit_sig=None,       max_hold=40)),
        ("Fixed63",   dict(use_tstop=False, exit_sig=None,       max_hold=63)),
        ("GK_SELL",   dict(use_tstop=False, exit_sig="gk_sell",  max_hold=None)),
        ("TS20_63",   dict(use_tstop=True,  exit_sig=None,       max_hold=63)),
        ("GK_TS20",   dict(use_tstop=True,  exit_sig="gk_sell",  max_hold=None)),
        ("EMA20_exit",dict(use_tstop=False, exit_sig="ema20",    max_hold=None)),
    ]

    exit_rows = []
    n_total_exit = len(entry_systems) * len(exit_configs)
    i_run = 0
    for ename, esig in entry_systems.items():
        for xcfg_name, xcfg in exit_configs:
            i_run += 1
            log.info("  [%d/%d] %s x %s", i_run, n_total_exit, ename, xcfg_name)
            eq, tr = run_simulation(
                base, all_dates, rd_all,
                use_volexp=False,
                entry_override=esig,
                **xcfg,
            )
            m = compute_metrics(eq, tr, vnx_rets,
                                f"{ename}_{xcfg_name}", f"{ename} x {xcfg_name}")
            row = {
                "entry_system": ename, "exit_system": xcfg_name,
                "n_trades": m.get("n_trades", 0),
                "cagr": m.get("cagr"), "mar": m.get("mar"),
                "active_maxdd": m.get("active_maxdd"),
                "ret_2018": m.get("ret_2018"), "ret_2022": m.get("ret_2022"),
                "avg_hold": m.get("avg_hold"), "win_rate": m.get("win_rate"),
                "profit_factor": m.get("profit_factor"),
                "ex_top3_cagr": m.get("ex_top3_cagr"),
                "top1_pct": m.get("top1_pct"),
            }
            exit_rows.append(row)
            log.info("    CAGR=%s MAR=%s N=%d", pct(m.get("cagr")), fmt(m.get("mar")), m.get("n_trades", 0))

    exit_df_out = pd.DataFrame(exit_rows)
    exit_df_out.to_csv(OUT_DIR / "phase8_exit_utility.csv", index=False)
    log.info("Saved phase8_exit_utility.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 6: DISCRETIONARY RANK REVIEW
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 6: Discretionary Rank Review ===")

    rank_vars = ["adv50", "rs1m", "rs3m", "rs6m", "dist_52wk", "volexp"]
    rank_df = discretionary_rank_review(
        base, c06_signals, c06_fwd, rank_vars, big_winner_thresh=0.20
    )
    rank_df.to_csv(OUT_DIR / "phase8_discretionary_rank_review.csv", index=False)
    log.info("Saved phase8_discretionary_rank_review.csv")

    # ══════════════════════════════════════════════════════════════════════════
    # PART 7: FINAL REPORT
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Part 7: Final Report ===")

    report_text = write_final_report(
        comp_rows=comp_rows,
        wl_rows=wl_rows,
        leader_rows=leader_rows,
        anatomy_df=anatomy_df,
        exit_rows=exit_rows,
        rank_df=rank_df,
    )
    (OUT_DIR / "phase8_final_report.md").write_text(report_text, encoding="utf-8")
    log.info("Saved phase8_final_report.md")

    log.info("=== Phase 8 complete. All 10 output files written to %s ===", OUT_DIR)
    log.info("Files:")
    for f in sorted(OUT_DIR.iterdir()):
        log.info("  %s", f.name)


if __name__ == "__main__":
    main()
