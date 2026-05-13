"""
Walk-Forward OOS Validation Engine (v2)
========================================
No lookahead. For each test month, factor signs/weights are derived ONLY from
past data.  Tests three window types:
  - expanding  : all history before test date
  - rolling_36 : most recent 36 months before test date
  - rolling_60 : most recent 60 months before test date

For each test month × window × horizon:
  1. Select top factors from training data (|IC|, p < 0.10)
  2. Freeze sign map from training IC
  3. Z-score composite score at test month
  4. Compute OOS IC = Spearman(composite, forward_return)
  5. Simulate portfolios: top-10, top-20, top-quintile
  6. Apply transaction costs: 0.3%, 0.5%, 0.8% round-trip

Outputs:
  data/research/walkforward_ic.csv
  data/research/walkforward_portfolio_returns.csv
  data/research/walkforward_summary.md
"""
from __future__ import annotations
import sys, io, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from tabulate import tabulate

ROOT  = Path(__file__).resolve().parents[2]
SNAP  = ROOT / "data/research/indicator_snapshots.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
SMAP  = ROOT / "data/master/sector_map.csv"
OUT   = ROOT / "data/research"

HORIZONS  = [25, 50, 100, 150, 200, 250]
FWD_COLS  = {h: f"fwd{h}" for h in HORIZONS}

INDICS = [
    "r5", "r20", "r60", "r120", "r252",
    "rs20", "rs60",
    "stage2", "ma_align", "dist_hi52",
    "rsi14", "cmf20", "obv_slope", "atr_ratio",
    "vol_ratio", "dist_days", "bb_width",
]

WINDOWS      = ["expanding", "rolling_36", "rolling_60"]
TX_COSTS     = [0.003, 0.005, 0.008]   # round-trip
TOP_N_LIST   = [10, 20]                # portfolio sizes
TOP_QUANTILE = 0.20                    # quintile

TOP_K_FACTORS  = 5     # top K factors by training |IC|
MIN_TRAIN_OBS  = 30    # minimum stock-date observations in training set
FACTOR_P_THRESH = 0.10 # p-value threshold for factor inclusion in training


# ── Regime helper ─────────────────────────────────────────────────────────────

def add_regime(df: pd.DataFrame, vni: pd.DataFrame) -> pd.DataFrame:
    v = vni.sort_values("date").set_index("date")["close"]
    ma50  = v.rolling(50,  min_periods=30).mean()
    ma200 = v.rolling(200, min_periods=100).mean()
    regime = pd.Series("Unknown", index=v.index)
    regime[(v > ma50) & (ma50 > ma200)]  = "Expansion"
    regime[(v > ma50) & (ma50 <= ma200)] = "Accumulation"
    regime[(v <= ma50) & (ma50 > ma200)] = "Warning"
    regime[(v <= ma50) & (ma50 <= ma200)] = "Contraction"

    df = df.copy()
    df["regime"] = df["date"].map(
        lambda d: regime[regime.index <= d].iloc[-1] if len(regime[regime.index <= d]) else "Unknown"
    )
    return df


# ── Training: select factors and sign map ─────────────────────────────────────

def train_factor_model(train: pd.DataFrame, horizon: int,
                       top_k: int = TOP_K_FACTORS) -> dict | None:
    """Return dict with {indicator: sign} for top_k factors, or None if insufficient data."""
    fwd_col = FWD_COLS[horizon]
    if fwd_col not in train.columns:
        return None

    ic_scores = {}
    for ind in INDICS:
        if ind not in train.columns:
            continue
        sub = train[[ind, fwd_col]].dropna()
        if len(sub) < MIN_TRAIN_OBS:
            continue
        ic, pv = stats.spearmanr(sub[ind].values, sub[fwd_col].values)
        if pv < FACTOR_P_THRESH:
            ic_scores[ind] = (ic, pv, len(sub))

    if not ic_scores:
        return None

    # Select top_k by |IC|
    top = sorted(ic_scores.items(), key=lambda x: abs(x[1][0]), reverse=True)[:top_k]
    sign_map = {ind: int(np.sign(ic)) for ind, (ic, _, _) in top}
    ic_map   = {ind: ic for ind, (ic, _, _) in top}
    return {"signs": sign_map, "ics": ic_map}


# ── Scoring: Z-score composite ────────────────────────────────────────────────

def score_stocks(test_df: pd.DataFrame, model: dict) -> pd.Series | None:
    signs = model["signs"]
    if not signs:
        return None

    z_scores = []
    for ind, sign in signs.items():
        if ind not in test_df.columns:
            continue
        v = test_df[ind].values.astype(float)
        std = np.nanstd(v)
        mn  = np.nanmean(v)
        if std > 0:
            z = (v - mn) / std * sign
        else:
            z = np.zeros(len(v))
        z_scores.append(z)

    if not z_scores:
        return None

    composite = np.nanmean(np.stack(z_scores, axis=1), axis=1)
    return pd.Series(composite, index=test_df.index, name="composite")


# ── Portfolio simulation ──────────────────────────────────────────────────────

def portfolio_returns(test_df: pd.DataFrame, composite: pd.Series,
                      horizon: int) -> dict:
    fwd_col = FWD_COLS[horizon]
    if fwd_col not in test_df.columns:
        return {}

    df = test_df.copy()
    df["composite"] = composite
    df = df.dropna(subset=["composite", fwd_col])

    if len(df) < 5:
        return {}

    n = len(df)
    df = df.sort_values("composite", ascending=False)

    results = {}
    for top_n in TOP_N_LIST:
        if top_n > n:
            continue
        fwd_mean = float(df[fwd_col].iloc[:top_n].mean())
        for tc in TX_COSTS:
            net = fwd_mean - tc * 100  # tc is fraction, fwd is in %
            key = f"top{top_n}_tc{int(tc*1000)}bp"
            results[key] = round(net, 4)

    # Quintile
    q_size = max(1, int(n * TOP_QUANTILE))
    fwd_top_q = float(df[fwd_col].iloc[:q_size].mean())
    fwd_bot_q = float(df[fwd_col].iloc[-q_size:].mean())
    results["quintile_spread"] = round(fwd_top_q - fwd_bot_q, 4)
    for tc in TX_COSTS:
        net = fwd_top_q - tc * 100
        results[f"quintile_tc{int(tc*1000)}bp"] = round(net, 4)

    results["universe_mean"] = round(float(df[fwd_col].mean()), 4)
    results["n_stocks"] = n
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading snapshots...", flush=True)
    snap = pd.read_parquet(SNAP)
    snap["date"] = pd.to_datetime(snap["date"])
    snap = snap.sort_values("date").reset_index(drop=True)

    print("Loading VNINDEX + regime...", flush=True)
    vni = pd.read_parquet(VNIDX)
    vni["date"] = pd.to_datetime(vni["date"])

    print("Loading sector map...", flush=True)
    smap = pd.read_csv(SMAP)
    snap = snap.merge(smap[["symbol", "primary_sector"]].rename(
        columns={"primary_sector": "sector"}), on="symbol", how="left")
    snap["sector"] = snap["sector"].fillna("Other")

    # Attach regime
    vni_close = vni.sort_values("date").set_index("date")["close"]
    ma50  = vni_close.rolling(50,  min_periods=30).mean()
    ma200 = vni_close.rolling(200, min_periods=100).mean()
    regime_map = pd.Series("Unknown", index=vni_close.index)
    regime_map[(vni_close > ma50) & (ma50 > ma200)]  = "Expansion"
    regime_map[(vni_close > ma50) & (ma50 <= ma200)] = "Accumulation"
    regime_map[(vni_close <= ma50) & (ma50 > ma200)] = "Warning"
    regime_map[(vni_close <= ma50) & (ma50 <= ma200)] = "Contraction"

    dates = sorted(snap["date"].unique())
    print(f"  {len(dates)} snapshot dates, {snap['symbol'].nunique()} tickers")

    ic_records   = []
    port_records = []

    for window in WINDOWS:
        min_train_months = 36 if window == "rolling_36" else (60 if window == "rolling_60" else 12)
        print(f"\nWindow: {window}  (min train months: {min_train_months})", flush=True)

        for ti, test_date in enumerate(dates):
            # Determine training window
            if window == "expanding":
                train_mask = snap["date"] < test_date
            elif window == "rolling_36":
                cutoff = test_date - pd.DateOffset(months=36)
                train_mask = (snap["date"] < test_date) & (snap["date"] >= cutoff)
            else:  # rolling_60
                cutoff = test_date - pd.DateOffset(months=60)
                train_mask = (snap["date"] < test_date) & (snap["date"] >= cutoff)

            train = snap[train_mask]
            test  = snap[snap["date"] == test_date].reset_index(drop=True)

            n_train_months = train["date"].nunique()
            if n_train_months < min_train_months:
                continue

            if len(test) < 5:
                continue

            # Regime at test date
            reg_before = regime_map[regime_map.index <= test_date]
            regime_label = str(reg_before.iloc[-1]) if len(reg_before) else "Unknown"

            for h in HORIZONS:
                fwd_col = FWD_COLS[h]

                # Train model
                model = train_factor_model(train, h)
                if model is None:
                    continue

                # Score test stocks
                composite = score_stocks(test, model)
                if composite is None:
                    continue

                # OOS IC
                fwd_vals = test[fwd_col].values.astype(float)
                oos_ic, oos_pv, n_oos = _spearman(composite.values, fwd_vals)

                # Selected factors summary
                factors_used = ";".join(model["signs"].keys())
                ic_records.append({
                    "window":        window,
                    "test_date":     test_date,
                    "horizon":       h,
                    "regime":        regime_label,
                    "n_train_months": n_train_months,
                    "n_test_stocks": len(test),
                    "factors_used":  factors_used,
                    "oos_ic":        round(oos_ic, 5) if not np.isnan(oos_ic) else None,
                    "oos_pv":        round(oos_pv, 5) if not np.isnan(oos_pv) else None,
                })

                # Portfolio simulation
                port = portfolio_returns(test, composite, h)
                if port:
                    base = {
                        "window": window, "test_date": test_date,
                        "horizon": h, "regime": regime_label,
                    }
                    base.update(port)
                    port_records.append(base)

        print(f"  done  ({len(ic_records):,} IC records so far)", flush=True)

    ic_df   = pd.DataFrame(ic_records)
    port_df = pd.DataFrame(port_records)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  WALK-FORWARD OOS IC SUMMARY")
    print("="*80)

    summary_rows = []
    for (window, horizon), g in ic_df.groupby(["window", "horizon"]):
        v = g["oos_ic"].dropna()
        if len(v) < 3:
            continue
        mn   = float(v.mean())
        std  = float(v.std(ddof=1))
        icir = mn / std if std > 0 else np.nan
        tstat = mn / (std / np.sqrt(len(v))) if std > 0 else np.nan
        summary_rows.append({
            "window": window, "horizon": horizon, "n_months": len(v),
            "oos_ic_mean": round(mn, 4),
            "oos_ic_std":  round(std, 4),
            "oos_icir":    round(icir, 3),
            "oos_tstat":   round(tstat, 3),
            "pct_pos":     round(float((v > 0).mean() * 100), 1),
        })
    sum_df = pd.DataFrame(summary_rows)

    for window in WINDOWS:
        sub = sum_df[sum_df["window"] == window].copy()
        if sub.empty:
            continue
        rows = sub[["horizon","n_months","oos_ic_mean","oos_ic_std",
                    "oos_icir","oos_tstat","pct_pos"]].values.tolist()
        rows = [[int(r[0]), int(r[1]), f"{r[2]:+.4f}", f"{r[3]:.4f}",
                 f"{r[4]:+.3f}", f"{r[5]:+.3f}", f"{r[6]:.0f}%"] for r in rows]
        print(f"\n  Window: {window}")
        print(tabulate(rows, headers=["Horizon","N_months","OOS_IC_mean","OOS_IC_std",
                                       "ICIR","t-stat","%pos"],
                       tablefmt="simple"))

    # Portfolio net returns
    print("\n" + "="*80)
    print("  PORTFOLIO NET RETURNS  (25d horizon, expanding window)")
    print("="*80)
    if not port_df.empty:
        p_sub = port_df[(port_df["window"] == "expanding") &
                         (port_df["horizon"] == 25)].copy()
        if not p_sub.empty:
            for col in ["top10_tc3bp","top10_tc5bp","top10_tc8bp",
                        "quintile_tc3bp","quintile_tc5bp","quintile_spread",
                        "universe_mean"]:
                if col in p_sub.columns:
                    print(f"  {col:<25} mean={p_sub[col].mean():+.2f}%  "
                          f"median={p_sub[col].median():+.2f}%  "
                          f">0: {(p_sub[col]>0).mean()*100:.0f}%")

    # Regime-conditional OOS IC
    print("\n" + "="*80)
    print("  OOS IC BY REGIME  (expanding window)")
    print("="*80)
    if "regime" in ic_df.columns:
        reg_sub = ic_df[ic_df["window"] == "expanding"].copy()
        for h in [50, 100, 200]:
            hg = reg_sub[reg_sub["horizon"] == h]
            pivot = hg.groupby("regime")["oos_ic"].agg(
                mean=lambda x: x.mean(), n=len).reset_index()
            print(f"\n  Horizon {h}d:")
            print(tabulate(pivot.values.tolist(),
                           headers=["Regime","OOS_IC_mean","N_months"],
                           tablefmt="simple", floatfmt=".4f"))

    # ── Save ──────────────────────────────────────────────────────────────────
    ic_out   = OUT / "walkforward_ic.csv"
    port_out = OUT / "walkforward_portfolio_returns.csv"
    sum_out  = OUT / "walkforward_ic_summary.csv"

    ic_df.to_csv(ic_out, index=False)
    port_df.to_csv(port_out, index=False)
    sum_df.to_csv(sum_out, index=False)

    print(f"\nSaved: {ic_out}  ({len(ic_df):,} rows)")
    print(f"Saved: {port_out}  ({len(port_df):,} rows)")
    print(f"Saved: {sum_out}  ({len(sum_df)} rows)")

    # Generate markdown summary
    _write_summary(sum_df, port_df, ic_df)
    print("Done.")


def _spearman(x, y):
    mask = (~np.isnan(x)) & (~np.isnan(y))
    n = int(mask.sum())
    if n < 5:
        return np.nan, np.nan, n
    ic, pv = stats.spearmanr(x[mask], y[mask])
    return float(ic), float(pv), n


def _write_summary(sum_df, port_df, ic_df):
    out = ROOT / "data/research" / "walkforward_summary.md"
    lines = ["# Walk-Forward Validation Summary", f"\n**Date:** {pd.Timestamp.now().date()}"]

    lines.append("\n## OOS IC by Window × Horizon")
    for window in WINDOWS:
        sub = sum_df[sum_df["window"] == window]
        if sub.empty:
            continue
        lines.append(f"\n### {window}")
        rows = sub[["horizon","n_months","oos_ic_mean","oos_icir","oos_tstat","pct_pos"]].values.tolist()
        rows = [[int(r[0]), int(r[1]), f"{r[2]:+.4f}", f"{r[3]:+.3f}", f"{r[4]:+.3f}", f"{r[5]:.0f}%"]
                for r in rows]
        lines.append(tabulate(rows, headers=["Horizon","N","OOS_IC","ICIR","t-stat","%pos"],
                               tablefmt="github"))

    lines.append("\n## Portfolio Returns (expanding, net of tx costs)")
    for h in [25, 50, 100]:
        p_sub = port_df[(port_df["window"] == "expanding") & (port_df["horizon"] == h)]
        if p_sub.empty:
            continue
        lines.append(f"\n### Horizon {h}d")
        cols = [c for c in ["top10_tc3bp","top10_tc5bp","top10_tc8bp",
                             "quintile_tc3bp","quintile_spread","universe_mean"]
                if c in p_sub.columns]
        tbl = [[c,
                f"{p_sub[c].mean():+.2f}%",
                f"{p_sub[c].median():+.2f}%",
                f"{(p_sub[c]>0).mean()*100:.0f}%",
                str(len(p_sub))] for c in cols]
        lines.append(tabulate(tbl, headers=["Metric","Mean","Median","Hit%","N"],
                               tablefmt="github"))

    lines.append("\n## Regime-Conditional OOS IC (expanding)")
    reg_sub = ic_df[ic_df["window"] == "expanding"] if "window" in ic_df else ic_df
    if "regime" in reg_sub.columns:
        pivot = reg_sub[reg_sub["horizon"] == 100].groupby("regime")["oos_ic"].agg(
            Mean="mean", Std="std", N="count").reset_index()
        lines.append("\n### Horizon 100d")
        lines.append(tabulate(pivot.values.tolist(),
                               headers=["Regime","OOS_IC_mean","std","N"],
                               tablefmt="github", floatfmt=".4f"))

    lines.append("\n## Go/No-Go Criteria")
    lines.append("""
A factor family is considered **deployable** only if ALL of the following hold:

| Criterion | Threshold |
|-----------|-----------|
| OOS ICIR (expanding) | >= 0.30 |
| OOS IC t-stat | >= 1.5  |
| % positive IC months | >= 55%  |
| Works in Expansion AND Accumulation regimes | IC > 0 in both |
| Sector-neutral IC not much weaker than raw | SN_IC / IC > 0.5 |
| Net of 50bp cost still positive | > 0% mean |

**Current status: CANDIDATE_RESEARCH** — requires further validation before deployment.
""")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
