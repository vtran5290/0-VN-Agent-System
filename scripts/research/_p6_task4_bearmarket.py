"""
Phase 6 Task 4 — C06 on 2018-2026 full period (bear market test).

Now feasible: ohlcv_panel_full.parquet covers 2018-01-02 to 2026-04-29.

Tests:
  A. C06 full backtest 2018-2026 — yearly returns, CAGR, MAR, MaxDD
  B. Walk-forward: IS=2018-2022, OOS=2023-2026
  C. Bear market focus: 2018 and 2022 VNINDEX drawdown periods

Key question: does C06's -27% active MaxDD stay controlled in bear markets?
"""
import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

FULL_PARQUET = REPO / "data/research/ema_cloud/ohlcv_panel_full.parquet"
VNIDX        = REPO / "data/fireant_exports/index_ohlcv/market/VNINDEX.csv"
OUT_DIR      = REPO / "data/research/gk_audit/phase6_data_quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

START  = pd.Timestamp("2018-01-01")
END    = pd.Timestamp("2026-04-30")
OOS_START = pd.Timestamp("2023-01-01")   # IS=2018-2022, OOS=2023+

EXCL         = {"VPL"}
ADV50_MIN_BN = 2.0
MAX_POS      = 10
FEE          = 35 / 10000   # 25 bps fee + 10 bps slip
INITIAL_CAP  = 1.0

# C06 params
GK_LEN  = 100
GK_MULT = 2.0
GK_ATR  = 14
GK_CONF = 2
TS_BARS = 20
TS_THR  = 0.0
VEXP_MIN = 1.2

BEAR_PERIODS = [
    ("2018_bear", pd.Timestamp("2018-01-01"), pd.Timestamp("2019-12-31")),
    ("2020_covid", pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31")),
    ("2022_bear", pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31")),
]


def _ema(a, span):
    alpha = 2.0 / (span + 1); out = np.full(len(a), np.nan)
    for i in range(len(a)):
        v = float(a[i])
        if np.isnan(v): continue
        p = out[i - 1] if i > 0 and not np.isnan(out[i - 1]) else np.nan
        out[i] = v if np.isnan(p) else alpha * v + (1 - alpha) * p
    return out


def _watr(h, l, c, n):
    tr = np.empty(len(c)); tr[0] = h[0] - l[0]
    for i in range(1, len(c)):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1] = float(np.mean(tr[:n]))
        for i in range(n, len(tr)):
            out[i] = tr[i] / n + out[i - 1] * (1 - 1 / n)
    return out


def _adv50(val):
    out = np.full(len(val), np.nan)
    for i in range(50, len(val)):
        out[i] = float(np.mean(val[i - 50:i])) / 1e9
    return out


def gk_sig(c, h, l):
    n = len(c); lag = max(int((GK_LEN - 1) // 2), 0)
    pc = np.empty(n)
    for i in range(n): j = i - lag; pc[i] = c[j] if j >= 0 else c[i]
    zl = _ema(c + (c - pc), GK_LEN); atr = _watr(h, l, c, GK_ATR)
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


def precompute(panel, label):
    print(f"Precomputing signals ({label}, {panel['symbol'].nunique()} symbols)...")
    base = {}
    for sym, grp in panel.groupby("symbol"):
        df = grp.sort_values("date").reset_index(drop=True)
        c = df["close"].values.astype(float); h = df["high"].values.astype(float)
        l = df["low"].values.astype(float); o = df["open"].values.astype(float)
        val = df["value"].values.astype(float); dts = pd.to_datetime(df["date"].values)
        adv = _adv50(val)
        g = gk_sig(c, h, l)
        ve = np.full(len(c), np.nan)
        for i in range(len(c)):
            if not np.isnan(adv[i]) and adv[i] > 0:
                ve[i] = val[i] / (adv[i] * 1e9)
        base[sym] = {
            "dates": dts, "open": o, "close": c,
            "gk_fast": g, "adv50_lag": adv, "volexp": ve,
            "date_to_idx": {str(d.date()): i for i, d in enumerate(dts)},
        }
    return base


def run_c06(base, all_dates, vnx_state, fold_dates=None):
    if fold_dates is None:
        fold_dates = set(str(d.date()) for d in all_dates)
    else:
        fold_dates = set(str(d.date()) for d in fold_dates)

    cash = INITIAL_CAP; holdings = {}; pending_exits = {}; pending_entries = []
    trades = []; eq = []; prev_eq = INITIAL_CAP

    sim_dates = [d for d in all_dates if str(d.date()) in fold_dates]

    for day_i, td in enumerate(sim_dates):
        ds = str(td.date()); vnx = vnx_state.get(ds, {})

        for sym, (t_sig, rsn) in list(pending_exits.items()):
            b = base[sym]; tex = b["date_to_idx"].get(ds)
            if tex is None: continue
            op = float(b["open"][tex]); pos = holdings.pop(sym)
            proceeds = pos["sh"] * op * (1 - FEE / 2); cash += proceeds
            trades.append({
                "symbol": sym, "entry_dt": str(pos["edt"].date()),
                "exit_dt": str(td.date()), "exit_reason": rsn,
                "net_ret": (op * (1 - FEE / 2)) / pos["epx"] - 1,
                "hold_bars": day_i - pos["edi"],
            })
        pending_exits.clear()

        slots = MAX_POS - len(holdings)
        sel = sorted(pending_entries, key=lambda x: -x["adv"])[:slots]
        for e in sel:
            sym = e["sym"]; b = base[sym]; tex = b["date_to_idx"].get(ds)
            if tex is None or sym in holdings: continue
            op = float(b["open"][tex])
            if op <= 0: continue
            sf = 0.5 if not vnx.get("above_e50", True) else 1.0
            slot = (prev_eq / MAX_POS) * sf; px_eff = op * (1 + FEE / 2)
            sh = slot / px_eff; cash -= slot
            holdings[sym] = {"sh": sh, "epx": px_eff, "eop": op, "edt": td,
                             "edi": day_i, "adv": e["adv"]}
        pending_entries.clear()

        mv = 0.
        for sym, pos in holdings.items():
            b = base[sym]; t = b["date_to_idx"].get(ds)
            if t is None: continue
            mv += pos["sh"] * float(b["close"][t])
        eq_now = cash + mv; prev_eq = eq_now
        eq.append({"date": td, "equity": eq_now, "n_pos": len(holdings)})

        for sym, pos in list(holdings.items()):
            b = base[sym]; t = b["date_to_idx"].get(ds)
            if t is None or t + 1 >= len(b["close"]): continue
            bars = day_i - pos["edi"]; cn = float(b["close"][t])
            tri, rsn = False, ""
            if bool(b["gk_fast"]["gk_sell"][t]): tri, rsn = True, "GK_SELL"
            if not tri and bars >= TS_BARS:
                if cn / pos["eop"] - 1 <= TS_THR: tri, rsn = True, "TSTOP"
            if tri: pending_exits[sym] = (t, rsn)

        for sym, b in base.items():
            if sym in holdings or sym in pending_exits or any(x["sym"] == sym for x in pending_entries): continue
            t = b["date_to_idx"].get(ds)
            if t is None or t + 1 >= len(b["close"]): continue
            adv = float(b["adv50_lag"][t])
            if np.isnan(adv) or adv < ADV50_MIN_BN: continue
            if not bool(b["gk_fast"]["gk_buy"][t]): continue
            ve = float(b["volexp"][t])
            if np.isnan(ve) or ve < VEXP_MIN: continue
            pending_entries.append({"sym": sym, "adv": adv})

    eq_df = pd.DataFrame(eq)
    tr_df = pd.DataFrame(trades)
    return eq_df, tr_df


def compute_metrics(eq_df, tr_df, vnx_rets):
    if eq_df.empty:
        return {}
    eq_df = eq_df.copy(); eq_df["date"] = pd.to_datetime(eq_df["date"])
    eq_df["strat_ret"] = eq_df["equity"].pct_change().fillna(0)

    # Active returns
    eq_df = eq_df.merge(vnx_rets[["date", "vnx_ret"]], on="date", how="left")
    eq_df["vnx_ret"] = eq_df["vnx_ret"].fillna(0)
    eq_df["n_pos"] = eq_df.get("n_pos", 0)
    eq_df["exp_frac"] = (eq_df["n_pos"] / MAX_POS).clip(0, 1)
    eq_df["bench_ret"] = eq_df["vnx_ret"] * eq_df["exp_frac"]
    eq_df["active_ret"] = eq_df["strat_ret"] - eq_df["bench_ret"]
    eq_df["cum_active"] = (1 + eq_df["active_ret"]).cumprod()
    roll_max = eq_df["cum_active"].cummax()
    dd = eq_df["cum_active"] / roll_max - 1
    active_maxdd = float(dd.min())

    start = eq_df["date"].iloc[0]; end = eq_df["date"].iloc[-1]
    years = max((end - start).days / 365.25, 1e-6)
    final_eq = float(eq_df["equity"].iloc[-1])
    cagr = final_eq ** (1 / years) - 1
    mar = cagr / abs(active_maxdd) if active_maxdd < 0 else np.nan

    # Yearly returns
    yearly = {}
    for yr in range(2018, 2027):
        sub = eq_df[eq_df["date"].dt.year == yr]
        if len(sub) >= 2:
            yearly[yr] = float(sub["equity"].iloc[-1] / sub["equity"].iloc[0] - 1)

    # Concentration
    top1_pct = np.nan
    if not tr_df.empty:
        total_ret = tr_df["net_ret"].sum()
        by_sym = tr_df.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
        if total_ret != 0:
            top1_pct = float(by_sym.iloc[0] / total_ret) if len(by_sym) > 0 else np.nan

    return {
        "cagr": cagr, "mar": mar, "active_maxdd": active_maxdd,
        "n_trades": len(tr_df), "top1_pct": top1_pct,
        "yearly": yearly,
    }


def main():
    print("=== Phase 6 Task 4 — Bear Market Test ===")

    # Load full panel
    print(f"\nLoading full panel: {FULL_PARQUET}")
    panel = pd.read_parquet(FULL_PARQUET)
    panel = panel[~panel["symbol"].isin(EXCL)].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel[(panel["date"] >= START) & (panel["date"] <= END)].copy()
    print(f"  {panel['symbol'].nunique()} symbols, {len(panel):,} rows  "
          f"({panel['date'].min().date()} to {panel['date'].max().date()})")

    # VNINDEX for regime + benchmark
    vnx = pd.read_csv(VNIDX); vnx["date"] = pd.to_datetime(vnx["date"])
    vnx = vnx.sort_values("date")
    vc = vnx["close"].values.astype(float); e50 = _ema(vc, 50)
    vnx_state = {}
    for i in range(len(vnx)):
        d = str(vnx["date"].iloc[i].date())
        vnx_state[d] = {"above_e50": bool(vc[i] > e50[i]) if not np.isnan(e50[i]) else True}

    vnx_rets = vnx[["date"]].copy()
    vnx_rets["vnx_ret"] = vnx["close"].pct_change().fillna(0)

    # Precompute
    base = precompute(panel, "full 2018-2026")
    all_dates = sorted({d for b in base.values() for d in b["dates"]})
    all_dates = [d for d in all_dates if START <= d <= END]
    print(f"  Trading days: {len(all_dates)}  ({all_dates[0].date()} to {all_dates[-1].date()})")

    # A. Full backtest 2018-2026
    print("\n--- A. C06 Full Backtest 2018-2026 ---")
    eq_full, tr_full = run_c06(base, all_dates, vnx_state)
    m_full = compute_metrics(eq_full, tr_full, vnx_rets)
    print(f"  N trades: {m_full['n_trades']}")
    print(f"  CAGR: {m_full['cagr']*100:.1f}%  MAR: {m_full['mar']:.2f}  aDD: {m_full['active_maxdd']*100:.1f}%")
    print(f"  top1 ticker: {m_full['top1_pct']*100:.1f}%" if not np.isnan(m_full.get('top1_pct', np.nan)) else "  top1: n/a")
    print("\n  Yearly returns:")
    for yr, ret in m_full["yearly"].items():
        flag = ""
        if yr in (2018, 2022): flag = " <-- BEAR YEAR"
        if yr == 2020: flag = " <-- COVID"
        print(f"    {yr}: {ret*100:+.1f}%{flag}")

    # B. Walk-forward: IS=2018-2022, OOS=2023-2026
    print("\n--- B. Walk-Forward: IS=2018-2022 -> OOS=2023-2026 ---")
    oos_dates = [d for d in all_dates if d >= OOS_START]
    eq_oos, tr_oos = run_c06(base, all_dates, vnx_state, fold_dates=oos_dates)
    m_oos = compute_metrics(eq_oos, tr_oos, vnx_rets)
    print(f"  OOS period: {oos_dates[0].date()} to {oos_dates[-1].date()}  ({len(oos_dates)} days)")
    print(f"  N trades: {m_oos['n_trades']}")
    print(f"  CAGR: {m_oos['cagr']*100:.1f}%  MAR: {m_oos['mar']:.2f}  aDD: {m_oos['active_maxdd']*100:.1f}%")
    if not np.isnan(m_oos.get('top1_pct', np.nan)):
        print(f"  top1 ticker: {m_oos['top1_pct']*100:.1f}%")

    if not tr_oos.empty:
        by_sym = tr_oos.groupby("symbol")["net_ret"].sum().sort_values(ascending=False)
        total = tr_oos["net_ret"].sum()
        print("  Top-5 OOS tickers:")
        for sym, v in by_sym.head(5).items():
            pct = v / total * 100 if total != 0 else 0
            n = len(tr_oos[tr_oos["symbol"] == sym])
            print(f"    {sym:6s}  sum_ret={v:.3f}  pct={pct:.1f}%  n={n}")

    # C. Bear period isolation
    print("\n--- C. Bear Period Isolation ---")
    for label, bear_start, bear_end in BEAR_PERIODS:
        bear_dates = [d for d in all_dates if bear_start <= d <= bear_end]
        if len(bear_dates) < 50:
            print(f"  {label}: insufficient days ({len(bear_dates)})")
            continue
        eq_b, tr_b = run_c06(base, all_dates, vnx_state, fold_dates=bear_dates)
        m_b = compute_metrics(eq_b, tr_b, vnx_rets)
        print(f"  {label} ({bear_start.year}): N={m_b['n_trades']}  "
              f"CAGR={m_b['cagr']*100:.1f}%  MAR={m_b['mar']:.2f}  aDD={m_b['active_maxdd']*100:.1f}%")

    # Save summary
    rows = [
        {"test": "full_2018_2026", **{k: v for k, v in m_full.items() if k != "yearly"}},
        {"test": "oos_2023_2026",  **{k: v for k, v in m_oos.items()  if k != "yearly"}},
    ]
    pd.DataFrame(rows).to_csv(OUT_DIR / "task4_bearmarket_summary.csv", index=False)

    # Yearly table
    yr_rows = [{"year": yr, "ret": ret} for yr, ret in m_full["yearly"].items()]
    pd.DataFrame(yr_rows).to_csv(OUT_DIR / "task4_yearly_returns.csv", index=False)
    print(f"\nSaved: task4_bearmarket_summary.csv, task4_yearly_returns.csv")

    # Final interpretation
    print("\n--- TASK 4 INTERPRETATION ---")
    yr_2018 = m_full["yearly"].get(2018, np.nan)
    yr_2022 = m_full["yearly"].get(2022, np.nan)
    aDD_full = m_full["active_maxdd"]

    if not np.isnan(yr_2018):
        status_2018 = "PASS" if yr_2018 > -0.20 else "FAIL"
        print(f"  2018 bear year: {yr_2018*100:+.1f}%  -> {status_2018} (threshold: > -20%)")
    if not np.isnan(yr_2022):
        status_2022 = "PASS" if yr_2022 > -0.20 else "FAIL"
        print(f"  2022 bear year: {yr_2022*100:+.1f}%  -> {status_2022} (threshold: > -20%)")
    print(f"  Full-period active MaxDD: {aDD_full*100:.1f}%  (previous 2023-2026: -27.3%)")
    oos_pass = (not np.isnan(m_oos.get('mar', np.nan))) and m_oos.get('mar', 0) > 0.50
    print(f"  New OOS (2023-2026) MAR: {m_oos.get('mar', np.nan):.2f}  -> {'PASS' if oos_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
