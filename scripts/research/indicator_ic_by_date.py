"""
Cross-Sectional IC Engine (v2)
==============================
For each snapshot date × each indicator × each horizon:
  - Raw Spearman IC (indicator vs forward return)
  - VNINDEX-excess return IC (indicator vs fwd_excess_return)
  - Sector-neutral IC (demean both factor and return within sector before computing IC)

Also labels each snapshot date with VNINDEX regime:
  Expansion:    close > MA50 > MA200  (uptrend, MA aligned)
  Accumulation: close > MA50, MA50 <= MA200  (recovering, MAs not yet aligned)
  Warning:      close < MA50, MA50 > MA200  (price under MA50 but trend intact)
  Contraction:  close < MA50, MA50 < MA200  (downtrend)

Outputs:
  data/research/ic_by_date.csv                    — row per (date, indicator, horizon)
  data/research/ic_summary_by_factor_horizon.csv  — aggregated statistics
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

HORIZONS = [25, 50, 100, 150, 200, 250]
FWD_COLS = {h: f"fwd{h}" for h in HORIZONS}

INDICS = [
    "r5", "r20", "r60", "r120", "r252",
    "rs20", "rs60",
    "stage2", "ma_align", "dist_hi52",
    "rsi14", "cmf20", "obv_slope", "atr_ratio",
    "vol_ratio", "dist_days", "bb_width",
]

MIN_STOCKS_PER_DATE = 10  # skip dates with fewer stocks


# ── Regime labeling ───────────────────────────────────────────────────────────

def build_regime_series(vni: pd.DataFrame) -> pd.Series:
    """Return a date-indexed Series of regime labels."""
    v = vni.sort_values("date").set_index("date")["close"]
    ma50  = v.rolling(50,  min_periods=30).mean()
    ma200 = v.rolling(200, min_periods=100).mean()

    regime = pd.Series("Unknown", index=v.index, name="regime")
    regime[(v > ma50) & (ma50 > ma200)]              = "Expansion"
    regime[(v > ma50) & (ma50 <= ma200)]              = "Accumulation"
    regime[(v <= ma50) & (ma50 > ma200)]              = "Warning"
    regime[(v <= ma50) & (ma50 <= ma200)]             = "Contraction"
    return regime


# ── Cross-sectional IC helpers ────────────────────────────────────────────────

def spearman_ic(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """Return (IC, p_value, n) after dropping joint NaNs."""
    mask = (~np.isnan(x)) & (~np.isnan(y))
    n = int(mask.sum())
    if n < 5:
        return np.nan, np.nan, n
    ic, pv = stats.spearmanr(x[mask], y[mask])
    return float(ic), float(pv), n


def sector_neutral_demean(df: pd.DataFrame, col: str, sector_col: str = "sector") -> np.ndarray:
    """Subtract within-sector mean from `col`; return demeaned numpy array."""
    out = df[col].values.astype(float).copy()
    for s, idx in df.groupby(sector_col).groups.items():
        vals = df.loc[idx, col].values.astype(float)
        m    = np.nanmean(vals)
        out[df.index.get_indexer(idx)] -= m
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading snapshots...", flush=True)
    snap = pd.read_parquet(SNAP)
    snap["date"] = pd.to_datetime(snap["date"])
    print(f"  {len(snap):,} rows | {snap['symbol'].nunique()} tickers "
          f"| {snap['date'].min().date()} -> {snap['date'].max().date()}")

    print("Loading VNINDEX...", flush=True)
    vni = pd.read_parquet(VNIDX)
    vni["date"] = pd.to_datetime(vni["date"])
    regime_s = build_regime_series(vni)

    print("Loading sector map...", flush=True)
    smap = pd.read_csv(SMAP)
    snap = snap.merge(smap[["symbol", "primary_sector"]].rename(
        columns={"primary_sector": "sector"}), on="symbol", how="left")
    snap["sector"] = snap["sector"].fillna("Other")

    # Compute VNINDEX forward returns at each horizon for sector-adjusted excess return
    vni_close = vni.sort_values("date").set_index("date")["close"]
    for h in HORIZONS:
        vni_fwd = vni_close.pct_change(h).shift(-h) * 100
        snap = snap.merge(vni_fwd.rename(f"vni_fwd{h}").reset_index(),
                          on="date", how="left")

    # ── Per-date IC computation ────────────────────────────────────────────────
    dates = sorted(snap["date"].unique())
    print(f"\nComputing cross-sectional IC for {len(dates)} dates × "
          f"{len(INDICS)} indicators × {len(HORIZONS)} horizons...", flush=True)

    records = []
    for di, dt in enumerate(dates):
        dslice = snap[snap["date"] == dt].reset_index(drop=True)
        n_stocks = len(dslice)
        if n_stocks < MIN_STOCKS_PER_DATE:
            continue

        # Nearest regime date (ffill)
        regime_at_dt = "Unknown"
        earlier = regime_s.index[regime_s.index <= dt]
        if len(earlier):
            regime_at_dt = regime_s[earlier[-1]]

        for indicator in INDICS:
            if indicator not in dslice.columns:
                continue
            x_raw = dslice[indicator].values.astype(float)

            for h in HORIZONS:
                fwd_col = FWD_COLS[h]
                if fwd_col not in dslice.columns:
                    continue

                y_raw  = dslice[fwd_col].values.astype(float)

                # 1. Raw IC
                ic_raw, pv_raw, n = spearman_ic(x_raw, y_raw)

                # 2. Excess-return IC (stock fwd - VNINDEX fwd)
                vni_col = f"vni_fwd{h}"
                if vni_col in dslice.columns:
                    y_exc = y_raw - dslice[vni_col].values.astype(float)
                    ic_exc, pv_exc, _ = spearman_ic(x_raw, y_exc)
                else:
                    ic_exc, pv_exc = np.nan, np.nan

                # 3. Sector-neutral IC
                # Demean x within sector, demean y within sector
                x_sn = sector_neutral_demean(dslice, indicator)
                y_sn = sector_neutral_demean(dslice, fwd_col)
                ic_sn, pv_sn, _ = spearman_ic(x_sn, y_sn)

                records.append({
                    "date":        dt,
                    "indicator":   indicator,
                    "horizon":     h,
                    "n_stocks":    n_stocks,
                    "regime":      regime_at_dt,
                    "ic_raw":      round(ic_raw, 5)  if not np.isnan(ic_raw)  else None,
                    "pv_raw":      round(pv_raw, 5)  if not np.isnan(pv_raw)  else None,
                    "ic_excess":   round(ic_exc, 5)  if not np.isnan(ic_exc)  else None,
                    "pv_excess":   round(pv_exc, 5)  if not np.isnan(pv_exc)  else None,
                    "ic_sn":       round(ic_sn, 5)   if not np.isnan(ic_sn)   else None,
                    "pv_sn":       round(pv_sn, 5)   if not np.isnan(pv_sn)   else None,
                })

        if (di + 1) % 12 == 0:
            print(f"  {di+1}/{len(dates)}  records: {len(records):,}", flush=True)

    ic_df = pd.DataFrame(records)
    ic_df["date"] = pd.to_datetime(ic_df["date"])
    print(f"\nIC records: {len(ic_df):,}")

    # ── Summary statistics ────────────────────────────────────────────────────
    print("Computing summary statistics...", flush=True)

    def summary_stats(series: pd.Series, label: str) -> dict:
        v = series.dropna()
        if len(v) < 3:
            return {f"{label}_mean": None, f"{label}_median": None,
                    f"{label}_std": None, f"{label}_icir": None,
                    f"{label}_pct_pos": None, f"{label}_tstat": None,
                    f"{label}_n": 0}
        mean_ic = float(v.mean())
        std_ic  = float(v.std(ddof=1))
        icir    = mean_ic / std_ic if std_ic > 0 else np.nan
        tstat   = mean_ic / (std_ic / np.sqrt(len(v)))
        return {
            f"{label}_mean":    round(mean_ic, 5),
            f"{label}_median":  round(float(v.median()), 5),
            f"{label}_std":     round(std_ic, 5),
            f"{label}_icir":    round(icir, 3),
            f"{label}_pct_pos": round(float((v > 0).mean() * 100), 1),
            f"{label}_tstat":   round(tstat, 3),
            f"{label}_n":       len(v),
        }

    summary_rows = []
    for (indicator, horizon), g in ic_df.groupby(["indicator", "horizon"]):
        row = {"indicator": indicator, "horizon": horizon}
        row.update(summary_stats(g["ic_raw"],    "raw"))
        row.update(summary_stats(g["ic_excess"], "exc"))
        row.update(summary_stats(g["ic_sn"],     "sn"))
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows)

    # ── Regime-conditional IC ─────────────────────────────────────────────────
    regime_rows = []
    for (indicator, horizon, regime), g in ic_df.groupby(["indicator", "horizon", "regime"]):
        row = {"indicator": indicator, "horizon": horizon, "regime": regime,
               "n_months": len(g)}
        v = g["ic_raw"].dropna()
        if len(v) >= 3:
            row["ic_mean"] = round(float(v.mean()), 5)
            row["ic_std"]  = round(float(v.std(ddof=1)), 5)
            row["icir"]    = round(row["ic_mean"] / row["ic_std"], 3) if row["ic_std"] > 0 else None
        regime_rows.append(row)
    regime_df = pd.DataFrame(regime_rows)

    # ── Console output ────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("  CROSS-SECTIONAL IC SUMMARY  (mean IC ± std, ICIR, % months IC > 0)")
    print("="*80)

    for h in HORIZONS:
        sub = summary_df[summary_df["horizon"] == h].copy()
        sub = sub.sort_values("raw_mean", key=abs, ascending=False)
        rows = []
        for _, r in sub.iterrows():
            rows.append([
                r["indicator"],
                f"{r['raw_mean']:+.4f}" if r["raw_mean"] is not None else "—",
                f"{r['raw_std']:.4f}"   if r["raw_std"]  is not None else "—",
                f"{r['raw_icir']:+.2f}" if r["raw_icir"] is not None else "—",
                f"{r['raw_pct_pos']:.0f}%" if r["raw_pct_pos"] is not None else "—",
                f"{r['raw_tstat']:+.2f}" if r["raw_tstat"] is not None else "—",
                f"{r['sn_mean']:+.4f}"  if r["sn_mean"]  is not None else "—",
                f"{r['sn_icir']:+.2f}"  if r["sn_icir"]  is not None else "—",
            ])
        print(f"\n  Horizon {h}d")
        print(tabulate(rows,
                       headers=["Indicator","IC_mean","IC_std","ICIR","Pct+","t-stat","IC_SN","ICIR_SN"],
                       tablefmt="simple"))

    # Regime summary for the top factors
    print("\n" + "="*80)
    print("  REGIME-CONDITIONAL IC  (top indicators, raw IC mean by regime)")
    print("="*80)
    top_indicators = ["r252", "r120", "bb_width", "cmf20", "vol_ratio", "stage2", "r60"]
    for h in [50, 100, 200]:
        sub = regime_df[regime_df["horizon"] == h].copy()
        sub = sub[sub["indicator"].isin(top_indicators)]
        pivot = sub.pivot_table(index="indicator", columns="regime",
                                values="ic_mean", aggfunc="first")
        print(f"\n  Horizon {h}d:")
        print(tabulate(pivot.reset_index(), headers=["Indicator"] + list(pivot.columns),
                       tablefmt="simple", floatfmt="+.4f"))

    # ── Save ──────────────────────────────────────────────────────────────────
    ic_out   = OUT / "ic_by_date.csv"
    sum_out  = OUT / "ic_summary_by_factor_horizon.csv"
    reg_out  = OUT / "ic_by_regime.csv"

    ic_df.to_csv(ic_out, index=False)
    summary_df.to_csv(sum_out, index=False)
    regime_df.to_csv(reg_out, index=False)
    print(f"\nSaved: {ic_out}  ({len(ic_df):,} rows)")
    print(f"Saved: {sum_out}  ({len(summary_df)} rows)")
    print(f"Saved: {reg_out}  ({len(regime_df)} rows)")
    print("Done.")


if __name__ == "__main__":
    main()
