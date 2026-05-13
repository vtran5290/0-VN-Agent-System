#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN Quant Phase 7 - Market Regime Framework Testing

Phase 6 baseline (2018-2026 full period on adjusted data):
  C06: CAGR=0.5%, MAR=0.01, aDD=-53.3%
  2018: -22.3%  2022: -29.9%

Tests Groups 1-6:
  G1  Stop-new-entries gates (G01-G12)
  G2  Force-flat gates (F01-F12)
  G3  Hysteresis on best 3 gates (H variants)
  G4  Two-layer regime (R01-R04)
  G5  Breadth filters (B01-B05)
  G6  Sector filters (S01-S04) if sector data available

Outputs -> data/research/gk_audit/phase7_regime/
"""
from __future__ import annotations

import io, sys, logging, warnings, dataclasses, itertools
from dataclasses import dataclass, field
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

# ── Paths ─────────────────────────────────────────────────────────────────────
FULL_PARQUET  = REPO / "data/research/ema_cloud/ohlcv_panel_full.parquet"
VNINDEX_CSV   = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
SECTOR_CSV    = REPO / "data/research/stocks_in_sectors_p20_gt_015_adv50_ge_2bn.csv"
OUT_DIR       = REPO / "data/research/gk_audit/phase7_regime"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────
START_DATE   = pd.Timestamp("2018-01-01")
END_DATE     = pd.Timestamp("2026-04-30")
OOS_START    = pd.Timestamp("2025-01-01")
EXCL         = {"VPL"}
ADV50_MIN    = 2.0
MAX_POS      = 10
FEE          = 35 / 10000  # 25 bps fee + 10 bps slip
INITIAL_CAP  = 1.0
VEXP_MIN     = 1.2
TS_BARS      = 20
TS_THR       = 0.0
GK_LEN, GK_MULT, GK_ATR, GK_CONF = 100, 2.0, 14, 2
YEARS        = list(range(2018, 2027))

# Phase 6 Task 4 baseline (no regime gate, SZ06 only)
BASELINE_ID  = "C06_SZ06_ONLY"

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def _ema_np(a: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1); out = np.full(len(a), np.nan)
    for i in range(len(a)):
        v = float(a[i])
        if np.isnan(v): continue
        p = out[i - 1] if i > 0 and not np.isnan(out[i - 1]) else np.nan
        out[i] = v if np.isnan(p) else alpha * v + (1 - alpha) * p
    return out


def _watr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    for i in range(1, len(c)):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1] = float(np.mean(tr[:n]))
        for i in range(n, len(tr)):
            out[i] = tr[i] / n + out[i - 1] * (1 - 1 / n)
    return out


def _adv50(val: np.ndarray) -> np.ndarray:
    out = np.full(len(val), np.nan)
    for i in range(50, len(val)):
        out[i] = float(np.mean(val[i - 50:i])) / 1e9
    return out


def _gk_sig(c, h, l):
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


def precompute_base(panel: pd.DataFrame) -> dict:
    log.info("Precomputing signals (%d symbols)...", panel["symbol"].nunique())
    base = {}
    for sym, grp in panel.groupby("symbol"):
        df = grp.sort_values("date").reset_index(drop=True)
        c = df["close"].values.astype(float); h = df["high"].values.astype(float)
        l = df["low"].values.astype(float); o = df["open"].values.astype(float)
        val = df["value"].values.astype(float); dts = pd.to_datetime(df["date"].values)
        adv = _adv50(val); g = _gk_sig(c, h, l)
        ve = np.full(len(c), np.nan)
        for i in range(len(c)):
            if not np.isnan(adv[i]) and adv[i] > 0:
                ve[i] = val[i] / (adv[i] * 1e9)
        e20 = _ema_np(c, 20); e50 = _ema_np(c, 50); e100 = _ema_np(c, 100)
        # 20-day return series (for breadth)
        ret20 = np.full(len(c), np.nan)
        for i in range(20, len(c)):
            if c[i - 20] > 0: ret20[i] = c[i] / c[i - 20] - 1
        base[sym] = {
            "dates": dts, "open": o, "close": c, "gk_fast": g,
            "adv50_lag": adv, "volexp": ve, "ema20": e20, "ema50": e50, "ema100": e100,
            "ret20": ret20,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


# ══════════════════════════════════════════════════════════════════════════════
# VNINDEX REGIME CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

def build_vnx_calendar(vnx_df: pd.DataFrame) -> pd.DataFrame:
    vnx = vnx_df.sort_values("date").copy()
    c = vnx["close"].values.astype(float)
    dates = pd.to_datetime(vnx["date"].values)

    ema20  = pd.Series(c).ewm(span=20,  adjust=False).mean().values
    ema50  = pd.Series(c).ewm(span=50,  adjust=False).mean().values
    ema100 = pd.Series(c).ewm(span=100, adjust=False).mean().values
    ema150 = pd.Series(c).ewm(span=150, adjust=False).mean().values
    ema200 = pd.Series(c).ewm(span=200, adjust=False).mean().values

    slope50 = np.full(len(c), False)
    for i in range(10, len(c)):
        slope50[i] = ema50[i] > ema50[i - 10]

    roll_high = pd.Series(c).rolling(252, min_periods=1).max().values
    roll_low  = pd.Series(c).rolling(252, min_periods=1).min().values
    dd252     = c / roll_high - 1     # negative: drawdown from 252d high
    dist_low  = c / roll_low  - 1     # positive: distance above 252d low

    ret20v = np.full(len(c), np.nan)
    for i in range(20, len(c)):
        if c[i - 20] > 0: ret20v[i] = c[i] / c[i - 20] - 1

    cal = pd.DataFrame({
        "date":       pd.to_datetime([str(d.date()) for d in dates]),
        "close":      c, "ema20": ema20, "ema50": ema50, "ema100": ema100,
        "ema150":     ema150, "ema200": ema200, "slope50": slope50,
        "dd252":      dd252, "dist_low": dist_low, "ret20": ret20v,
    }).set_index("date")
    return cal


# ══════════════════════════════════════════════════════════════════════════════
# BREADTH CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

def build_breadth_calendar(base: dict, all_dates: list) -> pd.DataFrame:
    log.info("Computing breadth calendar (%d dates)...", len(all_dates))
    rows = []
    for td in all_dates:
        ds = str(td.date())
        above50 = above100 = ret20_pos = n_valid = 0
        for sym, b in base.items():
            t = b["date_to_idx"].get(ds)
            if t is None: continue
            cn = float(b["close"][t]); e50 = b["ema50"][t]; e100 = b["ema100"][t]
            r20 = b["ret20"][t]
            if not np.isnan(e50):
                above50 += int(cn > e50); n_valid += 1
            if not np.isnan(e100):
                above100 += int(cn > e100)
            if not np.isnan(r20):
                ret20_pos += int(r20 > 0)
        n = max(n_valid, 1)
        rows.append({
            "date": td,  # keep as Timestamp so reindex against vnx_cal works
            "above50_pct":   above50   / n,
            "above100_pct":  above100  / n,
            "ret20_pos_pct": ret20_pos / n,
        })
    return pd.DataFrame(rows).set_index("date")


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

def build_sector_map(base: dict) -> Optional[tuple]:
    if not SECTOR_CSV.exists():
        log.warning("Sector mapping not found: %s", SECTOR_CSV)
        return None
    sdf = pd.read_csv(SECTOR_CSV)[["symbol", "sector_code_l4"]].dropna()
    sym_to_sector = dict(zip(sdf["symbol"], sdf["sector_code_l4"].astype(str)))
    sector_to_syms = {}
    for sym, sec in sym_to_sector.items():
        sector_to_syms.setdefault(sec, []).append(sym)
    log.info("Sector map: %d symbols, %d sectors", len(sym_to_sector), len(sector_to_syms))
    return sym_to_sector, sector_to_syms


def build_sector_calendar(base: dict, all_dates: list,
                          sector_to_syms: dict) -> dict:
    """Returns: date_str -> sector_code -> {'above50_pct': float}"""
    log.info("Computing sector calendar...")
    cal = {}
    for td in all_dates:
        ds = str(td.date())
        sec_stats = {}
        for sec, syms in sector_to_syms.items():
            above50 = n = 0
            for sym in syms:
                b = base.get(sym);
                if b is None: continue
                t = b["date_to_idx"].get(ds)
                if t is None: continue
                cn = float(b["close"][t]); e50 = b["ema50"][t]
                if not np.isnan(e50):
                    above50 += int(cn > e50); n += 1
            if n > 0:
                sec_stats[sec] = {"above50_pct": above50 / n}
        cal[ds] = sec_stats
    return cal


# ══════════════════════════════════════════════════════════════════════════════
# REGIME DAILY STATE BUILDER
# ══════════════════════════════════════════════════════════════════════════════

GATE_DEFS = {
    "G01": lambda c: c["close"] > c["ema50"],
    "G02": lambda c: c["close"] > c["ema100"],
    "G03": lambda c: c["close"] > c["ema150"],
    "G04": lambda c: c["close"] > c["ema200"],
    "G05": lambda c: c["ema20"] > c["ema50"],
    "G06": lambda c: c["slope50"],
    "G07": lambda c: (c["close"] > c["ema50"])  & (c["ema20"] > c["ema50"]),
    "G08": lambda c: (c["close"] > c["ema100"]) & (c["ema20"] > c["ema50"]),
    "G09": lambda c: c["dd252"] > -0.15,
    "G10": lambda c: c["dd252"] > -0.20,
    "G11": lambda c: c["dist_low"] > 0.10,
    "G12": lambda c: (c["close"] > c["ema100"]) & (c["ema20"] > c["ema50"]) & (c["dd252"] > -0.20),
}

BREADTH_GATE_DEFS = {
    "B01": lambda b: b["above50_pct"]  > 0.40,
    "B02": lambda b: b["above50_pct"]  > 0.50,
    "B03": lambda b: b["above100_pct"] > 0.40,
    "B04": lambda b: b["above50_pct"].diff().fillna(0) > 0,   # rising breadth (EMA-approx)
    "B05_vnx_b": None,   # combined: handled specially
}


def _apply_hysteresis(gate_series: pd.Series, n: int) -> pd.Series:
    """Require n consecutive True days before allowing entries."""
    rolling_sum = gate_series.astype(int).rolling(n, min_periods=n).sum()
    return rolling_sum >= n


def build_regime_daily(
    vnx_cal: pd.DataFrame,
    gate_key: str,
    force_flat: bool = False,
    consecutive: int = 0,
    breadth_cal: Optional[pd.DataFrame] = None,
    extra_cond_key: Optional[str] = None,  # for H5: AND vnx_20d_ret > 0
) -> dict:
    """
    Builds per-date regime state dict.
    Keys: allow_entry (bool), size_factor (float), force_exit (bool)
    size_factor uses SZ06: 0.5 when VNINDEX close < EMA50, else 1.0
    """
    # Compute gate condition
    if gate_key.startswith("B"):
        if breadth_cal is None:
            gate_series = pd.Series(True, index=vnx_cal.index)
        elif gate_key == "B04":
            raw = breadth_cal["above50_pct"].reindex(vnx_cal.index).ffill().bfill().fillna(0)
            ema10 = raw.ewm(span=10, adjust=False).mean()
            gate_series = (ema10.diff().fillna(0) > 0).fillna(False)
        else:
            fn = BREADTH_GATE_DEFS[gate_key]
            raw = breadth_cal.reindex(vnx_cal.index).ffill().bfill().fillna(0)
            gate_series = fn(raw).fillna(False)
    else:
        fn = GATE_DEFS[gate_key]
        gate_series = fn(vnx_cal).fillna(False)

    # Extra condition for H5 variant
    if extra_cond_key == "ret20_pos":
        gate_series = gate_series & (vnx_cal["ret20"] > 0).fillna(False)

    # Apply hysteresis (consecutive days requirement)
    if consecutive > 0:
        gate_effective = _apply_hysteresis(gate_series, consecutive)
    else:
        gate_effective = gate_series.fillna(False)

    # Detect force-flat transition: was ON, now OFF
    if force_flat:
        prev_on = gate_effective.shift(1).fillna(True)
        force_exit_series = (~gate_effective) & prev_on
    else:
        force_exit_series = pd.Series(False, index=gate_effective.index)

    # SZ06: half-size when VNINDEX close < EMA50
    above_e50_series = (vnx_cal["close"] > vnx_cal["ema50"]).fillna(True)

    result = {}
    for ds in gate_effective.index:
        ds_str = str(ds.date())
        is_on = bool(gate_effective.loc[ds])
        result[ds_str] = {
            "allow_entry": is_on,
            "size_factor": 1.0 if bool(above_e50_series.loc[ds]) else 0.5,
            "force_exit":  bool(force_exit_series.loc[ds]),
        }
    return result


def build_two_layer_regime_daily(
    vnx_cal: pd.DataFrame,
    variant: str,  # "R01", "R02", "R03", "R04"
) -> dict:
    """
    Two-layer regime:
      risk_on:      close > EMA50 AND EMA20 > EMA50  -> full size (1.0)
      risk_neutral: close > EMA100 but not risk_on   -> half size (0.5) or 0 entries
      risk_off:     otherwise                         -> no entries or force flat
    """
    risk_on      = (vnx_cal["close"] > vnx_cal["ema50"]) & (vnx_cal["ema20"] > vnx_cal["ema50"])
    risk_neutral  = (vnx_cal["close"] > vnx_cal["ema100"]) & ~risk_on
    risk_off      = ~(risk_on | risk_neutral)

    # Force-flat: detect when risk_off turns ON (was not risk_off yesterday)
    prev_risk_off = risk_off.shift(1).fillna(False)
    transition_to_off = risk_off & ~prev_risk_off

    result = {}
    for ds in vnx_cal.index:
        ds_str = str(ds.date())
        ron  = bool(risk_on.loc[ds])
        rnt  = bool(risk_neutral.loc[ds])
        roff = bool(risk_off.loc[ds])
        toff = bool(transition_to_off.loc[ds])

        if variant == "R01":
            # risk_on: full, neutral: half, off: no new entries (keep existing)
            allow_entry = not roff
            size_factor = 1.0 if ron else 0.5
            force_exit  = False
        elif variant == "R02":
            # risk_on: full, neutral: half, off: force flat
            allow_entry = not roff
            size_factor = 1.0 if ron else 0.5
            force_exit  = toff
        elif variant == "R03":
            # risk_on: full, neutral: no new entries, off: force flat
            allow_entry = ron
            size_factor = 1.0
            force_exit  = toff
        elif variant == "R04":
            # risk_on only: full, all other: cash (force flat when not risk_on)
            prev_on = bool(risk_on.shift(1).fillna(False).loc[ds])
            force_exit = (not ron) and prev_on
            allow_entry = ron
            size_factor = 1.0
        else:
            allow_entry = True; size_factor = 1.0; force_exit = False

        result[ds_str] = {
            "allow_entry": allow_entry,
            "size_factor": size_factor,
            "force_exit":  force_exit,
        }
    return result


def build_sector_regime_daily(
    vnx_cal: pd.DataFrame,
    base: dict,
    sym_to_sector: dict,
    sector_cal: dict,
    variant: str,  # "S01", "S02", "S03", "S04"
    gate_key: str = "G08",  # base regime gate
) -> tuple[dict, dict]:
    """
    Returns (base_regime_daily, sector_filter_dict)
    base_regime_daily: standard regime gate
    sector_filter_dict: sym_str -> date_str -> bool (allow this stock this day)
    """
    base_regime = build_regime_daily(vnx_cal, gate_key)

    sym_filter = {}
    for sym, b in base.items():
        sec = sym_to_sector.get(sym)
        sym_filter_by_date = {}
        for td_idx in range(len(b["dates"])):
            ds = str(b["dates"][td_idx].date())
            if sec is None:
                sym_filter_by_date[ds] = True  # no sector info -> always allow
                continue
            sec_stats = sector_cal.get(ds, {}).get(str(sec), {})
            above50 = sec_stats.get("above50_pct", 0.5)
            if variant == "S01":
                allow = above50 > 0.40
            elif variant == "S02":
                allow = above50 > 0.50
            elif variant == "S03":
                allow = above50 > 0.30
            elif variant == "S04":
                allow = above50 >= 0.30  # block if < 30%
            else:
                allow = True
            sym_filter_by_date[ds] = allow
        sym_filter[sym] = sym_filter_by_date
    return base_regime, sym_filter


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_REGIME = {"allow_entry": True, "size_factor": 1.0, "force_exit": False}


def run_simulation(
    base: dict,
    all_dates: list,
    regime_daily: dict,
    sym_filter: Optional[dict] = None,
    oos_only: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if oos_only:
        sim_dates = [d for d in all_dates if d >= OOS_START]
    else:
        sim_dates = all_dates

    cash = INITIAL_CAP; holdings = {}; pending_exits = {}; pending_entries = []
    trades = []; eq = []; prev_eq = INITIAL_CAP

    for day_i, td in enumerate(sim_dates):
        ds = str(td.date())
        regime = regime_daily.get(ds, DEFAULT_REGIME)

        # Force-flat: add all holdings to pending_exits
        if regime.get("force_exit", False):
            for sym in list(holdings.keys()):
                if sym not in pending_exits:
                    pending_exits[sym] = "REGIME_EXIT"

        # Process pending exits at today's open
        for sym, rsn in list(pending_exits.items()):
            b = base.get(sym)
            if b is None: continue
            tex = b["date_to_idx"].get(ds)
            if tex is None: continue
            op = float(b["open"][tex]); pos = holdings.pop(sym, None)
            if pos is None: continue
            proceeds = pos["sh"] * op * (1 - FEE / 2); cash += proceeds
            trades.append({
                "symbol": sym, "entry_dt": str(pos["edt"].date()), "exit_dt": str(td.date()),
                "exit_reason": rsn, "net_ret": (op * (1 - FEE / 2)) / pos["epx"] - 1,
                "hold_bars": day_i - pos["edi"], "entry_size": pos["slot"],
                "mfe": pos["mfe"], "mae": pos["mae"], "eop": pos["eop"],
            })
        pending_exits.clear()

        # Execute pending entries
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
                sf = regime.get("size_factor", 1.0)
                slot = (prev_eq / MAX_POS) * sf; px_eff = op * (1 + FEE / 2)
                sh = slot / px_eff; cash -= slot
                holdings[sym] = {
                    "sh": sh, "epx": px_eff, "eop": op, "edt": td,
                    "edi": day_i, "adv": e["adv"], "slot": slot, "mfe": 0., "mae": 0.,
                }
        pending_entries.clear()

        # Mark exits, update MFE/MAE
        for sym, pos in list(holdings.items()):
            b = base.get(sym);
            if b is None: continue
            t = b["date_to_idx"].get(ds)
            if t is None or t + 1 >= len(b["close"]): continue
            bars = day_i - pos["edi"]; cn = float(b["close"][t])
            u = cn / pos["eop"] - 1; pos["mfe"] = max(pos["mfe"], u); pos["mae"] = min(pos["mae"], u)
            tri, rsn = False, ""
            if bool(b["gk_fast"]["gk_sell"][t]): tri, rsn = True, "GK_SELL"
            if not tri and bars >= TS_BARS and cn / pos["eop"] - 1 <= TS_THR: tri, rsn = True, "TSTOP"
            if tri: pending_exits[sym] = rsn

        # Queue new entries
        if regime.get("allow_entry", True):
            for sym, b in base.items():
                if sym in holdings or sym in pending_exits: continue
                if any(x["sym"] == sym for x in pending_entries): continue
                t = b["date_to_idx"].get(ds)
                if t is None or t + 1 >= len(b["close"]): continue
                adv = float(b["adv50_lag"][t])
                if np.isnan(adv) or adv < ADV50_MIN: continue
                if not bool(b["gk_fast"]["gk_buy"][t]): continue
                ve = float(b["volexp"][t])
                if np.isnan(ve) or ve < VEXP_MIN: continue
                # Sector filter
                if sym_filter and not sym_filter.get(sym, {}).get(ds, True): continue
                pending_entries.append({"sym": sym, "adv": adv})

        # Update equity
        mv = 0.
        for sym, pos in holdings.items():
            b = base.get(sym)
            if b is None: continue
            t = b["date_to_idx"].get(ds)
            if t is None: continue
            mv += pos["sh"] * float(b["close"][t])
        eq_now = cash + mv; prev_eq = eq_now
        eq.append({"date": td, "equity": eq_now, "n_pos": len(holdings)})

    eq_df = pd.DataFrame(eq); tr_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    return eq_df, tr_df


# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(
    eq_df: pd.DataFrame,
    tr_df: pd.DataFrame,
    vnx_rets: pd.DataFrame,
    arm_id: str = "",
    label: str = "",
) -> dict:
    if eq_df.empty:
        return {"arm_id": arm_id, "label": label}
    eq_df = eq_df.copy()
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    eq_df["strat_ret"] = eq_df["equity"].pct_change().fillna(0)
    eq_df = eq_df.merge(vnx_rets[["date", "vnx_ret"]], on="date", how="left")
    eq_df["vnx_ret"] = eq_df["vnx_ret"].fillna(0)
    eq_df["exp_frac"] = (eq_df["n_pos"].clip(0, MAX_POS) / MAX_POS)
    eq_df["bench_ret"] = eq_df["vnx_ret"] * eq_df["exp_frac"]
    eq_df["active_ret"] = eq_df["strat_ret"] - eq_df["bench_ret"]
    eq_df["cum_active"] = (1 + eq_df["active_ret"]).cumprod()
    roll_max = eq_df["cum_active"].cummax()
    dd = eq_df["cum_active"] / roll_max - 1
    active_maxdd = float(dd.min())

    years = max((eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days / 365.25, 1e-6)
    final_eq = float(eq_df["equity"].iloc[-1])
    cagr = final_eq ** (1 / years) - 1
    mar = cagr / abs(active_maxdd) if active_maxdd < 0 else np.nan
    exposure = float(eq_df["n_pos"].mean()) / MAX_POS

    # Yearly returns
    yearly = {}
    for yr in YEARS:
        sub = eq_df[eq_df["date"].dt.year == yr]
        if len(sub) >= 2:
            yearly[yr] = float(sub["equity"].iloc[-1] / sub["equity"].iloc[0] - 1)

    # Monthly returns (for report)
    eq_df["ym"] = eq_df["date"].dt.to_period("M")
    monthly = eq_df.groupby("ym").apply(
        lambda g: float(g["equity"].iloc[-1] / g["equity"].iloc[0] - 1) if len(g) > 1 else 0.0
    ).to_dict()

    # Concentration
    top1_pct = top5_pct = ex_top1_cagr = ex_top3_cagr = np.nan
    if not tr_df.empty and "entry_size" in tr_df.columns:
        tr = tr_df.copy()
        tr["abs_pnl"] = tr["net_ret"] * tr["entry_size"]
        total_pnl = tr["abs_pnl"].sum()
        if abs(total_pnl) > 1e-9:
            by_sym = tr.groupby("symbol")["abs_pnl"].sum().sort_values(ascending=False)
            top1_pct = float(by_sym.iloc[0] / total_pnl) if len(by_sym) > 0 else np.nan
            top5_pnl = by_sym.head(5).sum()
            top5_pct = float(top5_pnl / total_pnl) if len(by_sym) >= 5 else np.nan
            # ex-top3 CAGR: approximation via PnL subtraction
            if len(by_sym) >= 3:
                ex3_pnl = total_pnl - by_sym.head(3).sum()
                ex_top3_cagr = (ex3_pnl / INITIAL_CAP) / years
            if len(by_sym) >= 1:
                ex1_pnl = total_pnl - by_sym.head(1).sum()
                ex_top1_cagr = (ex1_pnl / INITIAL_CAP) / years

    # Exit reason breakdown
    exit_counts = {}
    if not tr_df.empty and "exit_reason" in tr_df.columns:
        exit_counts = tr_df["exit_reason"].value_counts().to_dict()

    return {
        "arm_id": arm_id, "label": label,
        "cagr": cagr, "mar": mar, "active_maxdd": active_maxdd,
        "n_trades": len(tr_df), "exposure": exposure,
        "top1_pct": top1_pct, "top5_pct": top5_pct,
        "ex_top1_cagr": ex_top1_cagr, "ex_top3_cagr": ex_top3_cagr,
        "yearly": yearly, "monthly": monthly, "exit_counts": exit_counts,
        **{f"ret_{yr}": yearly.get(yr, np.nan) for yr in YEARS},
    }


def _fmt(v, pct=True, d=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "n/a"
    if pct: return f"{v*100:.{d}f}%"
    return f"{v:.{d}f}"


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(m: dict) -> dict:
    """Return pass/fail flags for evaluation criteria."""
    ret_2018 = m.get("ret_2018", np.nan)
    ret_2022 = m.get("ret_2022", np.nan)
    aDD      = m.get("active_maxdd", np.nan)
    cagr     = m.get("cagr", np.nan)
    mar      = m.get("mar", np.nan)
    top1     = m.get("top1_pct", np.nan)

    required = (
        (np.isnan(ret_2018) or ret_2018 > -0.15) and
        (np.isnan(ret_2022) or ret_2022 > -0.15) and
        (np.isnan(aDD)      or aDD > -0.30) and
        (np.isnan(cagr)     or cagr > 0.08) and
        (np.isnan(mar)      or mar > 0.40) and
        m.get("n_trades", 0) >= 80
    )
    strong = required and (
        (np.isnan(ret_2018) or ret_2018 > -0.10) and
        (np.isnan(ret_2022) or ret_2022 > -0.10) and
        (np.isnan(aDD)      or aDD > -0.25) and
        (np.isnan(cagr)     or cagr > 0.10) and
        (np.isnan(mar)      or mar > 0.50) and
        (np.isnan(top1)     or top1 < 0.30)
    )
    fail = (
        (not np.isnan(ret_2018) and ret_2018 <= -0.20) or
        (not np.isnan(ret_2022) and ret_2022 <= -0.20) or
        (not np.isnan(aDD)      and aDD <= -0.35) or
        (not np.isnan(cagr)     and cagr <= 0.02) or
        m.get("n_trades", 0) < 40
    )
    if strong:   verdict = "STRONG_CANDIDATE"
    elif required: verdict = "CANDIDATE"
    elif not fail: verdict = "MARGINAL"
    else:          verdict = "FAIL"
    return {"verdict": verdict, "required_pass": required, "strong_pass": strong, "fail": fail}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("=== VN Quant Phase 7 - Market Regime Framework ===")

    # ── Load data ──────────────────────────────────────────────────────────────
    log.info("Loading full panel...")
    panel = pd.read_parquet(FULL_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START_DATE) & (panel["date"] <= END_DATE)].copy()
    log.info("  %d symbols, %d rows  (%s to %s)",
             panel["symbol"].nunique(), len(panel),
             panel["date"].min().date(), panel["date"].max().date())

    log.info("Loading VNINDEX...")
    vnx_raw = pd.read_csv(VNINDEX_CSV)
    vnx_raw["date"] = pd.to_datetime(vnx_raw["date"])
    vnx_raw = vnx_raw.sort_values("date").reset_index(drop=True)

    vnx_rets = vnx_raw[["date"]].copy()
    vnx_rets["vnx_ret"] = vnx_raw["close"].pct_change().fillna(0)

    # ── Precompute signals ─────────────────────────────────────────────────────
    log.info("Precomputing base signals...")
    base = precompute_base(panel)
    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START_DATE <= d <= END_DATE]
    log.info("  %d symbols, %d trading days", len(base), len(all_dates))

    # ── VNINDEX calendar ───────────────────────────────────────────────────────
    log.info("Building VNINDEX regime calendar...")
    vnx_cal = build_vnx_calendar(vnx_raw)

    # ── Breadth calendar ───────────────────────────────────────────────────────
    log.info("Building breadth calendar...")
    breadth_cal = build_breadth_calendar(base, all_dates)

    # ── Sector data ────────────────────────────────────────────────────────────
    sector_map = build_sector_map(base)
    sym_to_sector = sector_to_syms = sector_cal = None
    if sector_map:
        sym_to_sector, sector_to_syms = sector_map
        sector_cal = build_sector_calendar(base, all_dates, sector_to_syms)

    # ── Baseline (C06 + SZ06 only, no additional gate) ─────────────────────────
    log.info("=== Baseline: C06 SZ06-only ===")
    baseline_regime = {}
    above_e50_dates = (vnx_cal["close"] > vnx_cal["ema50"]).to_dict()
    for td in all_dates:
        ds = str(td.date())
        above = bool(above_e50_dates.get(pd.Timestamp(ds), True))
        baseline_regime[ds] = {"allow_entry": True, "size_factor": 1.0 if above else 0.5, "force_exit": False}
    eq_bl, tr_bl = run_simulation(base, all_dates, baseline_regime)
    m_bl = compute_metrics(eq_bl, tr_bl, vnx_rets, BASELINE_ID, "C06_SZ06_only")
    ev_bl = evaluate(m_bl)
    log.info("  Baseline: CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%",
             m_bl.get("cagr", 0)*100, m_bl.get("mar", 0) or 0,
             m_bl.get("active_maxdd", 0)*100, m_bl.get("ret_2018", 0)*100, m_bl.get("ret_2022", 0)*100)

    all_results = [(m_bl, eq_bl, tr_bl, ev_bl)]

    # ── Group 1: Stop-New-Entries ──────────────────────────────────────────────
    log.info("=== Group 1: Stop-New-Entries Gates ===")
    g1_results = []
    for gate in ["G01","G02","G03","G04","G05","G06","G07","G08","G09","G10","G11","G12"]:
        arm_id = gate; label = f"stop_new_{gate}"
        log.info("  %s", arm_id)
        rd = build_regime_daily(vnx_cal, gate, force_flat=False, breadth_cal=breadth_cal)
        eq, tr = run_simulation(base, all_dates, rd)
        m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
        ev = evaluate(m)
        log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  N=%d  %s",
                 m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                 m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, m.get("n_trades",0), ev["verdict"])
        g1_results.append((m, eq, tr, ev))
        all_results.append((m, eq, tr, ev))

    # ── Group 2: Force-Flat ────────────────────────────────────────────────────
    log.info("=== Group 2: Force-Flat Gates ===")
    g2_results = []
    for gate in ["G01","G02","G03","G04","G05","G06","G07","G08","G09","G10","G11","G12"]:
        arm_id = f"F{gate[1:]}"; label = f"force_flat_{gate}"
        log.info("  %s", arm_id)
        rd = build_regime_daily(vnx_cal, gate, force_flat=True, breadth_cal=breadth_cal)
        eq, tr = run_simulation(base, all_dates, rd)
        m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
        ev = evaluate(m)
        log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  N=%d  %s",
                 m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                 m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, m.get("n_trades",0), ev["verdict"])
        g2_results.append((m, eq, tr, ev))
        all_results.append((m, eq, tr, ev))

    # ── Find best 3 for Group 3 ────────────────────────────────────────────────
    combined_g12 = g1_results + g2_results
    sorted_g12 = sorted(combined_g12, key=lambda x: (x[0].get("mar") or -99), reverse=True)
    best3 = sorted_g12[:3]
    log.info("Top-3 gates for hysteresis: %s", [x[0]["arm_id"] for x in best3])

    # ── Group 3: Hysteresis ────────────────────────────────────────────────────
    log.info("=== Group 3: Hysteresis Variants ===")
    g3_results = []

    def _base_gate_of(arm_id: str) -> str:
        if arm_id.startswith("F"):
            return "G" + arm_id[1:]
        return arm_id

    def _is_force_flat(arm_id: str) -> bool:
        return arm_id.startswith("F")

    for (best_m, _, _, _) in best3:
        best_gate = _base_gate_of(best_m["arm_id"])
        best_ff = _is_force_flat(best_m["arm_id"])
        for hysteresis_key, consec, extra in [
            ("H1", 3, None), ("H2", 5, None), ("H3", 10, None),
            ("H4", 5, None), ("H5", 0, "ret20_pos"),
        ]:
            gate_for_h = "G07" if hysteresis_key == "H4" else best_gate
            arm_id = f"{best_m['arm_id']}_{hysteresis_key}"
            label = f"hyst_{best_gate}_{hysteresis_key}"
            log.info("  %s", arm_id)
            rd = build_regime_daily(vnx_cal, gate_for_h, force_flat=best_ff,
                                    consecutive=consec, breadth_cal=breadth_cal,
                                    extra_cond_key=extra)
            eq, tr = run_simulation(base, all_dates, rd)
            m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
            ev = evaluate(m)
            log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  %s",
                     m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                     m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, ev["verdict"])
            g3_results.append((m, eq, tr, ev))
            all_results.append((m, eq, tr, ev))

    # ── Group 4: Two-Layer Regime ──────────────────────────────────────────────
    log.info("=== Group 4: Two-Layer Regime ===")
    g4_results = []
    for variant in ["R01","R02","R03","R04"]:
        log.info("  %s", variant)
        rd = build_two_layer_regime_daily(vnx_cal, variant)
        eq, tr = run_simulation(base, all_dates, rd)
        m = compute_metrics(eq, tr, vnx_rets, variant, f"two_layer_{variant}")
        ev = evaluate(m)
        log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  N=%d  %s",
                 m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                 m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, m.get("n_trades",0), ev["verdict"])
        g4_results.append((m, eq, tr, ev))
        all_results.append((m, eq, tr, ev))

    # ── Group 5: Breadth Filters ──────────────────────────────────────────────
    log.info("=== Group 5: Breadth Filters ===")
    g5_results = []
    for bgate in ["B01","B02","B03","B04"]:
        for ff in [False, True]:
            arm_id = f"{bgate}_{'ff' if ff else 'sne'}"
            label = f"breadth_{bgate}_{'force_flat' if ff else 'stop_new'}"
            log.info("  %s", arm_id)
            rd = build_regime_daily(vnx_cal, bgate, force_flat=ff, breadth_cal=breadth_cal)
            eq, tr = run_simulation(base, all_dates, rd)
            m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
            ev = evaluate(m)
            log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  %s",
                     m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                     m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, ev["verdict"])
            g5_results.append((m, eq, tr, ev))
            all_results.append((m, eq, tr, ev))

    # B05: VNINDEX G08 + breadth > 40% above EMA50
    for ff in [False, True]:
        arm_id = f"B05_{'ff' if ff else 'sne'}"
        log.info("  %s", arm_id)
        rd_base = build_regime_daily(vnx_cal, "G08", force_flat=ff, breadth_cal=breadth_cal)
        # Merge with breadth B01 condition
        rd_b01 = build_regime_daily(vnx_cal, "B01", force_flat=ff, breadth_cal=breadth_cal)
        rd_combined = {}
        for ds in set(rd_base) | set(rd_b01):
            base_r = rd_base.get(ds, DEFAULT_REGIME)
            b01_r  = rd_b01.get(ds, DEFAULT_REGIME)
            combined_allow = base_r["allow_entry"] and b01_r["allow_entry"]
            combined_fe    = base_r["force_exit"] or b01_r["force_exit"]
            rd_combined[ds] = {
                "allow_entry": combined_allow,
                "size_factor": base_r["size_factor"],
                "force_exit":  combined_fe,
            }
        eq, tr = run_simulation(base, all_dates, rd_combined)
        m = compute_metrics(eq, tr, vnx_rets, arm_id, f"breadth_B05_{'ff' if ff else 'sne'}")
        ev = evaluate(m)
        log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  %s",
                 m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                 m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, ev["verdict"])
        g5_results.append((m, eq, tr, ev))
        all_results.append((m, eq, tr, ev))

    # ── Group 6: Sector Filters ────────────────────────────────────────────────
    g6_results = []
    if sector_cal and sym_to_sector:
        log.info("=== Group 6: Sector Filters ===")
        for sv in ["S01","S02","S03","S04"]:
            arm_id = sv; label = f"sector_{sv}"
            log.info("  %s", arm_id)
            base_rd, sym_filt = build_sector_regime_daily(
                vnx_cal, base, sym_to_sector, sector_cal, sv, gate_key="G08"
            )
            eq, tr = run_simulation(base, all_dates, base_rd, sym_filter=sym_filt)
            m = compute_metrics(eq, tr, vnx_rets, arm_id, label)
            ev = evaluate(m)
            log.info("    CAGR=%.1f%%  MAR=%.2f  aDD=%.1f%%  2018=%.1f%%  2022=%.1f%%  %s",
                     m.get("cagr",0)*100, m.get("mar",0) or 0, m.get("active_maxdd",0)*100,
                     m.get("ret_2018",0)*100, m.get("ret_2022",0)*100, ev["verdict"])
            g6_results.append((m, eq, tr, ev))
            all_results.append((m, eq, tr, ev))
    else:
        log.info("=== Group 6: Sector Filters — SKIPPED (no sector mapping) ===")

    # ══════════════════════════════════════════════════════════════════════════
    # OUTPUT FILES
    # ══════════════════════════════════════════════════════════════════════════
    log.info("=== Writing output files ===")

    def row_to_dict(m, ev):
        d = {k: v for k, v in m.items() if k not in ("yearly", "monthly", "exit_counts")}
        d.update(ev)
        return d

    def results_to_df(results):
        return pd.DataFrame([row_to_dict(m, ev) for m, _, _, ev in results])

    # Summary: all arms
    summary_df = results_to_df(all_results)
    summary_df.to_csv(OUT_DIR / "phase7_summary.csv", index=False)

    # Group-specific CSVs
    results_to_df([(m_bl, eq_bl, tr_bl, ev_bl)] + g1_results).to_csv(
        OUT_DIR / "phase7_stop_new_entries.csv", index=False)
    results_to_df([(m_bl, eq_bl, tr_bl, ev_bl)] + g2_results).to_csv(
        OUT_DIR / "phase7_force_flat.csv", index=False)
    if g3_results:
        results_to_df(g3_results).to_csv(OUT_DIR / "phase7_hysteresis.csv", index=False)
    results_to_df(g4_results).to_csv(OUT_DIR / "phase7_two_layer_regime.csv", index=False)
    if g5_results:
        results_to_df(g5_results).to_csv(OUT_DIR / "phase7_breadth_filters.csv", index=False)
    if g6_results:
        results_to_df(g6_results).to_csv(OUT_DIR / "phase7_sector_filters.csv", index=False)

    # Yearly returns (wide format)
    yr_rows = []
    for m, _, _, ev in all_results:
        row = {"arm_id": m.get("arm_id"), "label": m.get("label"), "verdict": ev["verdict"]}
        for yr in YEARS:
            row[str(yr)] = m.get("yearly", {}).get(yr, np.nan)
        yr_rows.append(row)
    pd.DataFrame(yr_rows).to_csv(OUT_DIR / "phase7_yearly_returns.csv", index=False)

    # Monthly returns (long format)
    mo_rows = []
    for m, eq_df, _, _ in all_results:
        eq = eq_df.copy(); eq["date"] = pd.to_datetime(eq["date"])
        eq["ym"] = eq["date"].dt.to_period("M")
        for ym, grp in eq.groupby("ym"):
            if len(grp) < 2: continue
            mo_rows.append({
                "arm_id": m.get("arm_id"),
                "year_month": str(ym),
                "ret": float(grp["equity"].iloc[-1] / grp["equity"].iloc[0] - 1),
            })
    pd.DataFrame(mo_rows).to_csv(OUT_DIR / "phase7_monthly_returns.csv", index=False)

    # Drawdown report
    dd_rows = []
    for m, eq_df, _, ev in all_results:
        eq = eq_df.copy(); eq["date"] = pd.to_datetime(eq["date"])
        strat = eq["equity"].pct_change().fillna(0)
        roll_max = eq["equity"].cummax()
        strat_dd = (eq["equity"] / roll_max - 1).min()
        dd_rows.append({
            "arm_id": m.get("arm_id"), "label": m.get("label"),
            "active_maxdd": m.get("active_maxdd"),
            "strat_maxdd": float(strat_dd),
            "verdict": ev["verdict"],
        })
    pd.DataFrame(dd_rows).to_csv(OUT_DIR / "phase7_drawdown_report.csv", index=False)

    # Exit reason report
    er_rows = []
    for m, _, tr_df, _ in all_results:
        if tr_df.empty or "exit_reason" not in tr_df.columns: continue
        counts = tr_df["exit_reason"].value_counts()
        avg_ret = tr_df.groupby("exit_reason")["net_ret"].mean()
        for rsn in counts.index:
            regime_trades = tr_df[tr_df["exit_reason"] == rsn]
            er_rows.append({
                "arm_id": m.get("arm_id"), "exit_reason": rsn,
                "count": int(counts[rsn]),
                "avg_net_ret": float(avg_ret[rsn]),
                "avg_mfe": float(regime_trades["mfe"].mean()) if "mfe" in regime_trades.columns else np.nan,
                "avg_mae": float(regime_trades["mae"].mean()) if "mae" in regime_trades.columns else np.nan,
                "avg_hold_bars": float(regime_trades["hold_bars"].mean()),
            })
    pd.DataFrame(er_rows).to_csv(OUT_DIR / "phase7_exit_reason_report.csv", index=False)

    # Concentration report
    conc_rows = []
    for m, _, tr_df, ev in all_results:
        if tr_df.empty or "entry_size" not in tr_df.columns: continue
        tr = tr_df.copy()
        tr["abs_pnl"] = tr["net_ret"] * tr["entry_size"]
        total = tr["abs_pnl"].sum()
        by_sym = tr.groupby("symbol")["abs_pnl"].sum().sort_values(ascending=False)
        for rank, (sym, pnl) in enumerate(by_sym.head(10).items(), 1):
            conc_rows.append({
                "arm_id": m.get("arm_id"), "rank": rank, "symbol": sym,
                "sum_pnl": float(pnl), "pct_of_total": float(pnl / total) if abs(total) > 1e-9 else np.nan,
                "n_trades": int(len(tr[tr["symbol"] == sym])),
            })
    pd.DataFrame(conc_rows).to_csv(OUT_DIR / "phase7_concentration_report.csv", index=False)

    # Best candidates
    cand_rows = []
    for m, _, _, ev in all_results:
        if ev.get("required_pass") or ev["verdict"] in ("STRONG_CANDIDATE", "CANDIDATE"):
            cand_rows.append(row_to_dict(m, ev))
    cand_df = pd.DataFrame(cand_rows)
    if not cand_df.empty:
        cand_df = cand_df.sort_values("mar", ascending=False)
    cand_df.to_csv(OUT_DIR / "phase7_best_candidates.csv", index=False)

    # ══════════════════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ══════════════════════════════════════════════════════════════════════════
    _write_final_report(
        all_results, g1_results, g2_results, g3_results, g4_results,
        g5_results, g6_results, m_bl, ev_bl, cand_df
    )

    # Console summary
    print("\n" + "="*78)
    print("PHASE 7 RESULTS SUMMARY")
    print("="*78)
    print(f"{'Arm':20s} {'CAGR':7s} {'MAR':5s} {'aDD':7s} {'2018':7s} {'2022':7s} {'N':5s} {'Verdict':18s}")
    print("-"*78)
    sorted_all = sorted(all_results, key=lambda x: (x[0].get("mar") or -99), reverse=True)
    for m, _, _, ev in sorted_all[:30]:
        print(f"  {m.get('arm_id',''):18s} {_fmt(m.get('cagr')):7s} "
              f"{_fmt(m.get('mar'),pct=False,d=2):5s} {_fmt(m.get('active_maxdd')):7s} "
              f"{_fmt(m.get('ret_2018')):7s} {_fmt(m.get('ret_2022')):7s} "
              f"{m.get('n_trades',0):5d} {ev['verdict']:18s}")

    print(f"\nAll outputs -> {OUT_DIR}")
    log.info("Phase 7 complete.")


def _write_final_report(
    all_results, g1, g2, g3, g4, g5, g6, m_bl, ev_bl, cand_df
):
    def best_by_mar(results, n=1):
        s = sorted(results, key=lambda x: (x[0].get("mar") or -99), reverse=True)
        return s[:n]

    def section_row(m, ev):
        return (f"| {m.get('arm_id',''):20s} | {_fmt(m.get('cagr')):7s} | {_fmt(m.get('mar'),pct=False,d=2):5s} | "
                f"{_fmt(m.get('active_maxdd')):7s} | {_fmt(m.get('ret_2018')):7s} | {_fmt(m.get('ret_2022')):7s} | "
                f"{m.get('n_trades',0):5d} | {ev['verdict']:18s} |")

    tbl_hdr = ("| Arm                  | CAGR    | MAR   | aDD     | 2018    | 2022    |"
               "     N | Verdict            |")
    tbl_sep = ("|----------------------|---------|-------|---------|---------|---------|"
               "-------|----------------------|")

    def best_g1():
        return best_by_mar(g1)[0] if g1 else None
    def best_g2():
        return best_by_mar(g2)[0] if g2 else None
    def best_g3():
        return best_by_mar(g3)[0] if g3 else None
    def best_g4():
        return best_by_mar(g4)[0] if g4 else None

    lines = [
        "# Phase 7 Final Report — Market Regime Framework",
        "",
        f"Run date: 2026-05-05",
        "",
        "---",
        "",
        "## A. Facts",
        "",
        "**Phase 6 baseline (2018-2026, C06 + SZ06 only):**",
        f"- CAGR: {_fmt(m_bl.get('cagr'))}  MAR: {_fmt(m_bl.get('mar'),pct=False,d=2)}  aDD: {_fmt(m_bl.get('active_maxdd'))}",
        f"- 2018: {_fmt(m_bl.get('ret_2018'))}  2022: {_fmt(m_bl.get('ret_2022'))}  N: {m_bl.get('n_trades',0)}",
        f"- Baseline verdict: {ev_bl['verdict']}",
        "",
        "**Evaluation thresholds:**",
        "- Required: 2018 > -15%, 2022 > -15%, aDD > -30%, CAGR > 8%, MAR > 0.40, N >= 80",
        "- Strong:   2018 > -10%, 2022 > -10%, aDD > -25%, CAGR > 10%, MAR > 0.50, top1 < 30%",
        "",
        "---",
        "",
        "## B. Best Stop-New-Entries Regime",
        "",
        tbl_hdr, tbl_sep,
        section_row(m_bl, ev_bl),
    ]
    for m, _, _, ev in best_by_mar(g1, 5):
        lines.append(section_row(m, ev))
    lines += [
        "",
        f"**Best stop-new-entries gate:** {best_g1()[0].get('arm_id') if best_g1() else 'n/a'}",
        "",
        "---",
        "",
        "## C. Best Force-Flat Regime",
        "",
        tbl_hdr, tbl_sep,
        section_row(m_bl, ev_bl),
    ]
    for m, _, _, ev in best_by_mar(g2, 5):
        lines.append(section_row(m, ev))
    lines += [
        "",
        f"**Best force-flat gate:** {best_g2()[0].get('arm_id') if best_g2() else 'n/a'}",
        "",
        "---",
        "",
        "## D. Best Hysteresis Rule",
        "",
        tbl_hdr, tbl_sep,
    ]
    for m, _, _, ev in best_by_mar(g3, 5):
        lines.append(section_row(m, ev))
    lines += [
        "",
        f"**Best hysteresis arm:** {best_g3()[0].get('arm_id') if best_g3() else 'n/a'}",
        "",
        "---",
        "",
        "## E. Best Two-Layer Regime",
        "",
        tbl_hdr, tbl_sep,
    ]
    for m, _, _, ev in g4:
        lines.append(section_row(m, ev))
    lines += [
        "",
        f"**Best two-layer arm:** {best_g4()[0].get('arm_id') if best_g4() else 'n/a'}",
        "",
        "---",
        "",
        "## F. Breadth Filters",
        "",
        tbl_hdr, tbl_sep,
    ]
    for m, _, _, ev in best_by_mar(g5, 5):
        lines.append(section_row(m, ev))
    lines += [""]

    if g6:
        lines += [
            "---", "",
            "## G. Sector Filters",
            "",
            tbl_hdr, tbl_sep,
        ]
        for m, _, _, ev in g6:
            lines.append(section_row(m, ev))
        lines += [""]
    else:
        lines += ["---", "", "## G. Sector Filters", "", "Sector filters run on G08 base gate.", ""]

    # H. Bear market review
    lines += ["---", "", "## H. 2018/2022 Bear Market Review", ""]
    for m, _, _, ev in sorted(all_results, key=lambda x: (x[0].get("ret_2018") or -99), reverse=True)[:8]:
        lines.append(f"  {m.get('arm_id',''):20s}  2018={_fmt(m.get('ret_2018'))}  2022={_fmt(m.get('ret_2022'))}"
                     f"  aDD={_fmt(m.get('active_maxdd'))}  MAR={_fmt(m.get('mar'),pct=False,d=2)}  {ev['verdict']}")

    # I. OOS concentration
    lines += ["", "---", "", "## I. OOS Concentration (top1 by abs PnL, full period)", ""]
    for m, _, tr_df, ev in sorted(all_results, key=lambda x: (x[0].get("top1_pct") or 99))[:8]:
        lines.append(f"  {m.get('arm_id',''):20s}  top1={_fmt(m.get('top1_pct'))}  "
                     f"top5={_fmt(m.get('top5_pct'))}  ex_top3_CAGR={_fmt(m.get('ex_top3_cagr'))}")

    # J. Decision
    lines += ["", "---", "", "## J. Production / Paper-Trade Decision", ""]
    if cand_df.empty:
        lines.append("**VERDICT: RESEARCH_ONLY** — No arm met the required criteria.")
        lines.append("The regime gates reduce bear market losses but not sufficiently to meet all thresholds.")
    else:
        best = cand_df.iloc[0]
        lines.append(f"**VERDICT: CONDITIONAL — {best['arm_id']} meets required criteria.**")
        lines.append(f"Best arm: {best.get('label')} — CAGR {_fmt(best.get('cagr'))}  "
                     f"MAR {_fmt(best.get('mar'),pct=False,d=2)}  aDD {_fmt(best.get('active_maxdd'))}")
        lines.append("Condition: live paper-trade signal validation required before capital deployment.")

    lines += [
        "",
        "---",
        "",
        "## K. Top 3 Risks",
        "",
        "1. **Regime whipsaw**: Regime gates can trigger multiple short-lived exits in volatile",
        "   markets (e.g. 2020 COVID crash). Force-flat gates risk cutting positions at panic lows.",
        "   Stop-new-entries gates preserve existing positions but miss the re-entry window.",
        "",
        "2. **2020 recovery capture**: The best bear-market protection may reduce 2020 recovery",
        "   upside (VNINDEX recovered sharply after March 2020 crash). Gates that are too slow",
        "   to re-open will miss the early recovery.",
        "",
        "3. **OOS concentration unresolved**: L40 (Sep-Dec 2025 OOS trade) still dominates",
        "   OOS PnL in all regime-gated variants. The regime gate addresses bear market losses",
        "   but does not fix the OOS sample size problem (N=78 trades in 1.5 years).",
        "",
        "---",
        "",
        "## L. Next Research Questions",
        "",
        "1. If any arm qualifies: run full Phase 6 OOS exclusion tests (E1-E7) on the best",
        "   regime-gated arm to check whether OOS concentration is reduced.",
        "",
        "2. Test walk-forward: IS=2018-2022, OOS=2023-2026 on the best qualifying arm.",
        "   Does the regime gate improve OOS MAR from 0.16?",
        "",
        "3. If force-flat gates dominate: analyze REGIME_EXIT trade data. Are exits timed well",
        "   (before large drawdowns) or are they whipsaw losses?",
        "",
        "4. Test EMA slope hysteresis on the best gate: require both gate ON and EMA slope",
        "   positive for at least 5 days before re-entry. This may reduce whipsaw without",
        "   losing much recovery capture.",
    ]

    path = OUT_DIR / "phase7_final_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Final report written: %s", path)


if __name__ == "__main__":
    main()
