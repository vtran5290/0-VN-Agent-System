#!/usr/bin/env python3
"""Quick combined-variant tests: T5+T6, T3+T5, T3+T5+T6 and year-by-year."""
from __future__ import annotations
import sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from pp_backtest.portfolio_optimization_phase1 import (
    _build_signal_cache, _exit_tp_trail, load_panel, load_vnindex,
    get_universe, compute_gk, portfolio_metrics, DEFAULT_COST,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _build_adv50_map, _tag_adv50, _build_equity_adv_capped_v2, _annual_return,
)

PORTFOLIO_VND = 5e9; MAX_SLOTS = 20; PARTICIPATION = 0.10; COST = DEFAULT_COST


def regime_100(vnx):
    w = vnx.sort_values("date").reset_index(drop=True)
    c = w["close"].astype(float)
    e20  = c.ewm(span=20,  adjust=False).mean()
    e100 = c.ewm(span=100, adjust=False).mean()
    return pd.Series((e20 > e100).values, index=pd.to_datetime(w["date"]).dt.normalize())


def build_trades(cache, exit_cfg, gate, adv50_map):
    rows = []
    for sym, data in cache.items():
        c = data["close"]; h = data["high"]; a = data["atr"]
        d = data["dates"]; n = len(c)
        for si in data["sig_idxs"]:
            ei = si + 1
            if ei >= n:
                continue
            sd = pd.Timestamp(d[si]).normalize()
            ed = pd.Timestamp(d[ei]).normalize()
            if not bool(gate.get(sd, True)):
                continue
            ep = c[ei]
            if ep <= 0:
                continue
            hb, gross, reason = _exit_tp_trail(c, h, a, ei, ep, exit_cfg)
            xi  = min(ei + hb, n - 1)
            xd  = pd.Timestamp(d[xi]).normalize()
            adv = 0.0
            s   = adv50_map.get(sym)
            if s is not None:
                v = s[s.index <= ed].dropna()
                if not v.empty:
                    adv = float(v.iloc[-1])
            rows.append({
                "symbol": sym, "signal_date": sd, "entry_date": ed, "exit_date": xd,
                "gross_return": gross, "net_return": gross - COST, "hold_bars": hb,
                "exit_reason": reason, "adv50_value": adv, "has_gk": False,
                "ema_dist_at_entry": (ep - data["slow"][ei]) / max(data["slow"][ei], 1e-9),
                "mom20_at_entry": data["mom20"][ei], "t1_frac": 0.5, "total_frac": 1.0,
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ("entry_date", "exit_date", "signal_date"):
            df[col] = pd.to_datetime(df[col])
    return df


def metrics(df, adv50_map):
    if df.empty:
        return {}
    eq, _ = _build_equity_adv_capped_v2(
        df, MAX_SLOTS, PORTFOLIO_VND, PARTICIPATION, rank_col="ema_dist_at_entry"
    )
    if eq.empty:
        return {}
    m = portfolio_metrics(eq, df[df["net_return"].notna()])
    for yr in range(2014, 2027):
        m[f"yr_{yr}"] = _annual_return(eq, yr)
    return m


def report(label, df, adv50_map):
    m = metrics(df, adv50_map)
    print(f"  {label}: n={len(df)} "
          f"MAR={m.get('mar', float('nan')):.4f} "
          f"CAGR={m.get('cagr', float('nan')):.2%} "
          f"MaxDD={m.get('max_dd', float('nan')):.2%} "
          f"hit={m.get('hit_rate', float('nan')):.1%}", flush=True)
    return m


def main():
    print("Loading data...", flush=True)
    panel = load_panel()
    vnx   = load_vnindex()
    regime = regime_100(vnx)
    adv50_map = _build_adv50_map(panel)

    print("Building S3 signal cache...", flush=True)
    s3_cache = _build_signal_cache(panel, "S3")

    print("Building GK cache (S3 universe)...", flush=True)
    s3_univ = get_universe(panel, "full")
    gk_c = {}
    for sym, sdf in panel[panel["symbol"].isin(s3_univ)].groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        if len(sdf) < 150:
            continue
        c  = sdf["close"].astype(float)
        h  = sdf["high"].astype(float)
        lo = sdf.get("low", c).astype(float)
        gk = compute_gk(c, h, lo)
        bd = set(pd.to_datetime(sdf.loc[gk["gk_buy"], "date"]).dt.normalize())
        if bd:
            gk_c[sym] = bd

    # Build max_hold=60 base trades
    print("Building max_hold=60 trades...", flush=True)
    cfg60 = {"tp_pct": 0.18, "tp_frac": 0.50, "trail_mult": 3.5, "max_hold": 60}
    df60  = build_trades(s3_cache, cfg60, regime, adv50_map)
    print(f"  max_hold=60: {len(df60)} trades", flush=True)

    # Top-100 ADV symbol set
    sym_adv  = df60.groupby("symbol")["adv50_value"].median().sort_values(ascending=False)
    top50    = set(sym_adv.head(50).index)
    top100   = set(sym_adv.head(100).index)

    # GK within 5 bars filter
    def tag_gk(df, window=5):
        mask = df.apply(
            lambda r: any(abs((r["signal_date"] - gd).days) <= window
                          for gd in gk_c.get(r["symbol"], set())), axis=1
        )
        return df[mask]

    print("\n=== Combined variants ===", flush=True)
    report("T5: max_hold=60",          df60,                                adv50_map)
    report("T5+T6_top50: max60+top50", df60[df60["symbol"].isin(top50)],    adv50_map)
    report("T5+T6_top100:max60+top100",df60[df60["symbol"].isin(top100)],   adv50_map)

    df60_gk = tag_gk(df60, 5)
    report("T3+T5: GK5+max60",         df60_gk,                             adv50_map)
    report("T3+T5+T6top50: GK5+max60+top50",
           df60_gk[df60_gk["symbol"].isin(top50)], adv50_map)
    report("T3+T5+T6top100: GK5+max60+top100",
           df60_gk[df60_gk["symbol"].isin(top100)], adv50_map)

    # Year-by-year for the three most important variants
    print("\n=== Year-by-year stability ===", flush=True)
    for label, df in [("max_hold=60", df60),
                      ("max60+top100", df60[df60["symbol"].isin(top100)]),
                      ("GK5+max60",    df60_gk)]:
        m = metrics(df, adv50_map)
        yr_vals = [(yr, m.get(f"yr_{yr}", float("nan"))) for yr in range(2015, 2027)]
        yr_str  = "  ".join(f"{yr}:{v:.1%}" for yr, v in yr_vals
                            if not (isinstance(v, float) and v != v))
        print(f"  {label}: {yr_str}", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
