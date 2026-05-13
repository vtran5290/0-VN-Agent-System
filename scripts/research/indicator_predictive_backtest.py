"""
Indicator Predictive Power Backtest
====================================
Builds a panel of monthly snapshots (full panel history), computes 17 technical
indicators at each snapshot, then tests predictive power for forward returns at
horizons 25 / 50 / 100 / 150 / 200 / 250 trading days.

Outputs:
  1. Spearman IC (Information Coefficient) per indicator x horizon
  2. Q5-Q1 quintile spread (top vs bottom 20% average return)
  3. Hit rate (% positive return in top quintile)
  4. Mutual Information vs each horizon
  5. Multi-factor pairs + triples optimization

Filter: ADV50 >= 2B VND at snapshot date, >= 60 bars history before snapshot.

Usage:
  python scripts/research/indicator_predictive_backtest.py [--adv 2] [--sample-every N]
"""
from __future__ import annotations
import sys, io, warnings, itertools, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats
from sklearn.feature_selection import mutual_info_regression

try:
    from tabulate import tabulate as _tab
    TABULATE = True
except ImportError:
    TABULATE = False

ROOT  = Path(__file__).resolve().parents[2]
PANEL = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
OUT   = ROOT / "data/research"

HORIZONS    = [25, 50, 100, 150, 200, 250]
ADV_MIN_B   = 2.0   # Billion VND
MIN_BARS    = 60
TOP_K_MULTI = 8     # top indicators fed into multi-factor search

INDICS = [
    "r5", "r20", "r60", "r120", "r252",
    "rs20", "rs60",
    "stage2", "ma_align", "dist_hi52",
    "rsi14", "cmf20", "obv_slope", "atr_ratio",
    "vol_ratio", "dist_days", "bb_width",
]


# ─── Data Loading ──────────────────────────────────────────────────────────────

def load_data():
    print("Loading OHLCV panel...", flush=True)
    panel = pd.read_parquet(PANEL)
    panel["date"] = pd.to_datetime(panel["date"])

    med_c = panel.groupby("symbol")["close"].median().median()
    if med_c < 500:
        for col in ["open", "high", "low", "close"]:
            panel[col] = panel[col] * 1000
        print("  Prices scaled x1000 (raw panel in thousand VND)", flush=True)

    if panel["value"].median() < 1e8:
        panel["value"] = panel["value"] * 1000

    print(f"  {len(panel):,} rows | {panel['symbol'].nunique()} tickers "
          f"| {panel['date'].min().date()} -> {panel['date'].max().date()}", flush=True)

    print("Loading VNINDEX...", flush=True)
    vni = pd.read_parquet(VNIDX)
    vni["date"] = pd.to_datetime(vni["date"])
    vni = vni.sort_values("date").set_index("date")["close"]
    print(f"  VNINDEX: {len(vni)} bars, last {vni.index[-1].date()}", flush=True)

    return panel, vni


# ─── Per-ticker Indicator Computation ─────────────────────────────────────────

def process_ticker(sym: str, sdf: pd.DataFrame, vni: pd.Series,
                   sample_every: int = 1):
    sdf = sdf.sort_values("date").reset_index(drop=True)
    n = len(sdf)
    if n < MIN_BARS:
        return None

    close = sdf["close"].values.astype(float)
    high  = sdf["high"].values.astype(float)
    low   = sdf["low"].values.astype(float)
    vol   = sdf["volume"].values.astype(float)
    value = sdf["value"].values.astype(float)
    dates = sdf["date"].values  # datetime64[ns]

    # Align VNINDEX to ticker dates (ffill for holidays/gaps)
    vni_aligned = vni.reindex(pd.DatetimeIndex(dates), method="ffill").values.astype(float)

    c     = pd.Series(close)
    hi    = pd.Series(high)
    lo    = pd.Series(low)
    v     = pd.Series(vol)
    val_s = pd.Series(value)
    vni_s = pd.Series(vni_aligned)

    # ── Momentum ────────────────────────────────────────────────────────────────
    r5_s   = c.pct_change(5)   * 100
    r20_s  = c.pct_change(20)  * 100
    r60_s  = c.pct_change(60)  * 100
    r120_s = c.pct_change(120) * 100
    r252_s = c.pct_change(252) * 100

    # ── Relative Strength vs VNINDEX ────────────────────────────────────────────
    rs20_s = r20_s - vni_s.pct_change(20) * 100
    rs60_s = r60_s - vni_s.pct_change(60) * 100

    # ── Moving Averages ─────────────────────────────────────────────────────────
    ma50_s  = c.rolling(50,  min_periods=45).mean()
    ma150_s = c.rolling(150, min_periods=120).mean()
    ma200_s = c.rolling(200, min_periods=150).mean()
    ma50_6w = ma50_s.shift(30)   # MA50 six weeks ago (slope proxy)

    ma_align_s = (
        (c > ma50_s) & (c > ma150_s) & (c > ma200_s) &
        (ma50_s > ma150_s) & (ma150_s > ma200_s)
    ).astype(float)

    stage2_s = (
        (c > ma50_s).astype(float) +
        (c > ma150_s).astype(float) +
        (c > ma200_s).astype(float) +
        (ma50_s > ma150_s).astype(float) +
        (ma150_s > ma200_s).astype(float) +
        ((ma50_s > ma50_6w).fillna(False)).astype(float)
    ).clip(0, 5)

    # ── 52-week high distance ────────────────────────────────────────────────────
    hi52_s      = c.rolling(252, min_periods=40).max()
    dist_hi52_s = (c / hi52_s - 1) * 100   # <= 0; closer to 0 = near high

    # ── RSI 14 (EWM) ────────────────────────────────────────────────────────────
    delta    = c.diff()
    avg_gain = delta.clip(lower=0).ewm(span=14, min_periods=14, adjust=False).mean()
    avg_loss = (-delta).clip(lower=0).ewm(span=14, min_periods=14, adjust=False).mean()
    rsi14_s  = 100 - 100 / (1 + avg_gain / avg_loss.replace(0, np.nan))

    # ── CMF 20 ───────────────────────────────────────────────────────────────────
    hl  = hi - lo
    mfm = ((c - lo) - (hi - c)) / hl.replace(0, np.nan)
    mfv = mfm * v
    cmf20_s = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    # ── ATR ratio (14 / 50) ─────────────────────────────────────────────────────
    prev_c = c.shift(1)
    tr     = pd.concat([hi - lo, (hi - prev_c).abs(), (lo - prev_c).abs()], axis=1).max(axis=1)
    atr14_s    = tr.rolling(14, min_periods=10).mean()
    atr50_s    = tr.rolling(50, min_periods=40).mean()
    atr_ratio_s = atr14_s / atr50_s.replace(0, np.nan)

    # ── OBV normalized slope (20-bar) ────────────────────────────────────────────
    direction   = np.sign(c.diff()).fillna(0)
    obv         = (direction * v).cumsum()
    avg_v20     = v.rolling(20, min_periods=10).mean()
    obv_slope_s = obv.diff(20) / (avg_v20 * 20).replace(0, np.nan)

    # ── Volume ratio (5d / 50d) ─────────────────────────────────────────────────
    vol_ratio_s = v.rolling(5).mean() / v.rolling(50).mean().replace(0, np.nan)

    # ── Distribution days (25-bar window) ────────────────────────────────────────
    avg_v50   = v.rolling(50, min_periods=20).mean()
    is_dist   = ((c.pct_change() < -0.002) & (v > avg_v50)).astype(float)
    dist_days_s = is_dist.rolling(25, min_periods=10).sum()

    # ── Bollinger Band width (4*sigma / price * 100) ─────────────────────────────
    sd20_s     = c.rolling(20, min_periods=15).std(ddof=1)
    bb_width_s = 4 * sd20_s / c * 100

    # ── ADV50 in billions ────────────────────────────────────────────────────────
    adv50_s = val_s.rolling(50, min_periods=20).mean() / 1e9

    # ── Monthly snapshot positions ────────────────────────────────────────────────
    dates_idx = pd.DatetimeIndex(dates)
    periods   = pd.Series(dates_idx.to_period("M"))
    last_flag = (periods != periods.shift(-1)).fillna(True).values
    snap_pos  = np.where(last_flag)[0]

    if sample_every > 1:
        snap_pos = snap_pos[::sample_every]

    # ── Build rows ────────────────────────────────────────────────────────────────
    rows = []
    for i in snap_pos:
        if i < MIN_BARS - 1:
            continue
        adv = adv50_s.iloc[i]
        if pd.isna(adv) or adv < ADV_MIN_B:
            continue

        fwd = {}
        has_any = False
        for fh in HORIZONS:
            if i + fh < n:
                fwd[f"fwd{fh}"] = (close[i + fh] / close[i] - 1) * 100
                has_any = True
            else:
                fwd[f"fwd{fh}"] = np.nan

        if not has_any:
            continue

        rows.append({
            "symbol":    sym,
            "date":      dates[i],
            "r5":        r5_s.iloc[i],
            "r20":       r20_s.iloc[i],
            "r60":       r60_s.iloc[i],
            "r120":      r120_s.iloc[i],
            "r252":      r252_s.iloc[i],
            "rs20":      rs20_s.iloc[i],
            "rs60":      rs60_s.iloc[i],
            "stage2":    stage2_s.iloc[i],
            "ma_align":  ma_align_s.iloc[i],
            "dist_hi52": dist_hi52_s.iloc[i],
            "rsi14":     rsi14_s.iloc[i],
            "cmf20":     cmf20_s.iloc[i],
            "obv_slope": obv_slope_s.iloc[i],
            "atr_ratio": atr_ratio_s.iloc[i],
            "vol_ratio": vol_ratio_s.iloc[i],
            "dist_days": dist_days_s.iloc[i],
            "bb_width":  bb_width_s.iloc[i],
            **fwd,
        })

    return pd.DataFrame(rows) if rows else None


# ─── Build Full Snapshot Panel ─────────────────────────────────────────────────

def build_snapshot_panel(panel: pd.DataFrame, vni: pd.Series,
                         sample_every: int = 1) -> pd.DataFrame:
    symbols = panel["symbol"].unique()
    print(f"\nBuilding snapshots for {len(symbols)} tickers "
          f"(sample_every={sample_every})...", flush=True)

    t0 = time.time()
    all_dfs = []
    for i, sym in enumerate(symbols, 1):
        sdf = panel[panel["symbol"] == sym]
        df  = process_ticker(sym, sdf, vni, sample_every)
        if df is not None and len(df) > 0:
            all_dfs.append(df)
        if i % 250 == 0:
            total = sum(len(d) for d in all_dfs)
            print(f"  [{i}/{len(symbols)}]  snapshots: {total:,}  "
                  f"({time.time()-t0:.0f}s)", flush=True)

    snap = pd.concat(all_dfs, ignore_index=True)
    snap = snap.replace([np.inf, -np.inf], np.nan)

    print(f"\nSnapshot panel: {len(snap):,} rows | {snap['symbol'].nunique()} tickers", flush=True)
    print(f"Date range: {pd.to_datetime(snap['date']).min().date()} -> "
          f"{pd.to_datetime(snap['date']).max().date()}", flush=True)
    for fh in HORIZONS:
        pct = snap[f"fwd{fh}"].notna().mean() * 100
        print(f"  fwd{fh:>3}d coverage: {pct:.0f}%  "
              f"(n={snap[f'fwd{fh}'].notna().sum():,})", flush=True)

    return snap


# ─── Statistical Tests ─────────────────────────────────────────────────────────

def spearman_ic(x: np.ndarray, y: np.ndarray):
    mask = np.isfinite(x) & np.isfinite(y)
    nn = int(mask.sum())
    if nn < 30:
        return np.nan, np.nan, nn
    corr, pval = stats.spearmanr(x[mask], y[mask])
    return float(corr), float(pval), nn


def quintile_stats(x: np.ndarray, y: np.ndarray):
    mask = np.isfinite(x) & np.isfinite(y)
    xm, ym = x[mask], y[mask]
    if len(xm) < 50:
        return np.nan, np.nan, np.nan, np.nan
    q20, q80 = np.percentile(xm, [20, 80])
    top = ym[xm >= q80]
    bot = ym[xm <= q20]
    top_mean = float(np.mean(top)) if len(top) > 0 else np.nan
    bot_mean = float(np.mean(bot)) if len(bot) > 0 else np.nan
    spread   = top_mean - bot_mean if not (np.isnan(top_mean) or np.isnan(bot_mean)) else np.nan
    hit_rate = float(np.mean(top > 0)) * 100 if len(top) > 0 else np.nan
    return top_mean, bot_mean, spread, hit_rate


def mi_score(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 30:
        return np.nan
    try:
        return float(mutual_info_regression(
            x[mask].reshape(-1, 1), y[mask], n_neighbors=3, random_state=42
        )[0])
    except Exception:
        return np.nan


# ─── Single Factor Analysis ────────────────────────────────────────────────────

def run_single_factor(snap: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 72, flush=True)
    print("  SINGLE-FACTOR IC ANALYSIS  (Spearman rank correlation)", flush=True)
    print("=" * 72, flush=True)

    records = []
    for ind in INDICS:
        x = snap[ind].values.astype(float)
        row: dict = {"indicator": ind}
        ics = []
        for fh in HORIZONS:
            y  = snap[f"fwd{fh}"].values.astype(float)
            ic, pv, nn = spearman_ic(x, y)
            row[f"IC_{fh}d"] = round(ic, 4) if np.isfinite(ic) else np.nan
            row[f"pv_{fh}d"] = round(pv, 4) if np.isfinite(pv) else np.nan
            row[f"n_{fh}d"]  = nn
            if np.isfinite(ic):
                ics.append(abs(ic))
        row["mean_abs_IC"] = round(float(np.mean(ics)), 4) if ics else np.nan
        records.append(row)

    sf = pd.DataFrame(records).sort_values("mean_abs_IC", ascending=False)

    # ── IC table ──────────────────────────────────────────────────────────────
    print("\n  IC per indicator x horizon  (* p<0.05, ** p<0.01):\n", flush=True)
    ic_rows = []
    for _, r in sf.iterrows():
        disp = {"Indicator": r["indicator"]}
        for fh in HORIZONS:
            ic = r.get(f"IC_{fh}d", np.nan)
            pv = r.get(f"pv_{fh}d", np.nan)
            if np.isnan(ic):
                disp[f"{fh}d"] = " --   "
            else:
                star = "**" if pv < 0.01 else ("*" if pv < 0.05 else "  ")
                disp[f"{fh}d"] = f"{ic:+.4f}{star}"
        disp["Mean|IC|"] = f"{r['mean_abs_IC']:.4f}" if not np.isnan(r["mean_abs_IC"]) else "--"
        ic_rows.append(disp)

    if TABULATE:
        print(_tab(ic_rows, headers="keys", tablefmt="simple"), flush=True)
    else:
        print(pd.DataFrame(ic_rows).to_string(index=False), flush=True)

    # ── Quintile spread table ─────────────────────────────────────────────────
    print("\n  Q5-Q1 spread  (top 20% avg return minus bottom 20%, %):\n", flush=True)
    q_rows = []
    for _, r in sf.iterrows():
        x = snap[r["indicator"]].values.astype(float)
        disp = {"Indicator": r["indicator"]}
        for fh in HORIZONS:
            y = snap[f"fwd{fh}"].values.astype(float)
            top_m, bot_m, spread, hit = quintile_stats(x, y)
            disp[f"{fh}d"] = f"{spread:+.1f}%" if not np.isnan(spread) else " -- "
        q_rows.append(disp)

    if TABULATE:
        print(_tab(q_rows, headers="keys", tablefmt="simple"), flush=True)
    else:
        print(pd.DataFrame(q_rows).to_string(index=False), flush=True)

    # ── Hit rate table ─────────────────────────────────────────────────────────
    print("\n  Hit rate: % of top-quintile snapshots with POSITIVE forward return:\n",
          flush=True)
    h_rows = []
    for _, r in sf.iterrows():
        x = snap[r["indicator"]].values.astype(float)
        disp = {"Indicator": r["indicator"]}
        for fh in HORIZONS:
            y = snap[f"fwd{fh}"].values.astype(float)
            _, _, _, hit = quintile_stats(x, y)
            disp[f"{fh}d"] = f"{hit:.0f}%" if not np.isnan(hit) else " -- "
        h_rows.append(disp)

    if TABULATE:
        print(_tab(h_rows, headers="keys", tablefmt="simple"), flush=True)
    else:
        print(pd.DataFrame(h_rows).to_string(index=False), flush=True)

    # ── Mutual Information ────────────────────────────────────────────────────
    print("\n  Mutual Information per indicator x horizon:\n", flush=True)
    mi_rows = []
    for _, r in sf.iterrows():
        x = snap[r["indicator"]].values.astype(float)
        disp = {"Indicator": r["indicator"]}
        mi_vals = []
        for fh in HORIZONS:
            y  = snap[f"fwd{fh}"].values.astype(float)
            mi = mi_score(x, y)
            disp[f"{fh}d"] = f"{mi:.5f}" if not np.isnan(mi) else "  --  "
            if not np.isnan(mi):
                mi_vals.append(mi)
        disp["MeanMI"] = f"{np.mean(mi_vals):.5f}" if mi_vals else "  -- "
        mi_rows.append(disp)

    mi_df = pd.DataFrame(mi_rows)
    mi_df["_s"] = mi_df["MeanMI"].apply(lambda x: float(x) if x.strip() not in ("--","") else -1)
    mi_df = mi_df.sort_values("_s", ascending=False).drop(columns="_s")
    if TABULATE:
        print(_tab(mi_df.to_dict("records"), headers="keys", tablefmt="simple"), flush=True)
    else:
        print(mi_df.to_string(index=False), flush=True)

    return sf


# ─── Multi-Factor Optimization ─────────────────────────────────────────────────

def run_multifactor(snap: pd.DataFrame, sf_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 72, flush=True)
    print("  MULTI-FACTOR OPTIMIZATION  (pairs + triples, Z-score composite)", flush=True)
    print("=" * 72, flush=True)

    top_ind = (sf_df.dropna(subset=["mean_abs_IC"])
               .sort_values("mean_abs_IC", ascending=False)
               .head(TOP_K_MULTI)["indicator"].tolist())
    print(f"\n  Compositing top {TOP_K_MULTI}: {top_ind}", flush=True)

    # Sign convention: flip so higher composite always means "more bullish"
    sign_map = {}
    for ind in top_ind:
        row = sf_df[sf_df["indicator"] == ind]
        ic50 = row["IC_50d"].values[0] if len(row) > 0 else 0
        sign_map[ind] = 1 if (not np.isnan(ic50) and ic50 >= 0) else -1
        if sign_map[ind] == -1:
            print(f"    {ind}: sign flipped (IC50={ic50:.4f})", flush=True)

    # Precompute signed z-scores (winsorize at 3 std)
    z = {}
    for ind in top_ind:
        x     = snap[ind].values.astype(float)
        valid = np.isfinite(x)
        z_arr = np.full(len(x), np.nan)
        if valid.sum() > 10:
            mu, sd = np.nanmean(x[valid]), np.nanstd(x[valid])
            if sd > 0:
                z_arr[valid] = np.clip((x[valid] - mu) / sd, -3, 3)
        z[ind] = z_arr * sign_map[ind]

    top6 = top_ind[:min(6, len(top_ind))]
    pairs   = list(itertools.combinations(top_ind, 2))
    triples = list(itertools.combinations(top6, 3))
    all_combos = [list(p) for p in pairs] + [list(t) for t in triples]
    print(f"\n  Testing {len(pairs)} pairs + {len(triples)} triples...", flush=True)

    records = []
    for combo in all_combos:
        zs        = np.stack([z[ind] for ind in combo], axis=1)
        n_valid   = np.sum(np.isfinite(zs), axis=1)
        composite = np.where(n_valid >= 2, np.nanmean(zs, axis=1), np.nan)

        row = {"combo": "+".join(combo), "n_factors": len(combo)}
        ics = []
        for fh in HORIZONS:
            y  = snap[f"fwd{fh}"].values.astype(float)
            ic, pv, nn = spearman_ic(composite, y)
            row[f"IC_{fh}d"] = round(ic, 4) if np.isfinite(ic) else np.nan
            row[f"pv_{fh}d"] = round(pv, 4) if np.isfinite(pv) else np.nan
            if np.isfinite(ic):
                ics.append(abs(ic))
        row["mean_abs_IC"] = round(float(np.mean(ics)), 4) if ics else np.nan
        records.append(row)

    mf = pd.DataFrame(records).sort_values("mean_abs_IC", ascending=False)

    print(f"\n  TOP 25 MULTI-FACTOR COMBINATIONS:\n", flush=True)
    disp_rows = []
    for _, r in mf.head(25).iterrows():
        d = {"Combo": r["combo"], "N": int(r["n_factors"])}
        for fh in HORIZONS:
            ic = r.get(f"IC_{fh}d", np.nan)
            pv = r.get(f"pv_{fh}d", np.nan)
            if np.isnan(ic):
                d[f"{fh}d"] = " --   "
            else:
                star = "**" if pv < 0.01 else ("*" if pv < 0.05 else "  ")
                d[f"{fh}d"] = f"{ic:+.4f}{star}"
        d["Mean|IC|"] = f"{r['mean_abs_IC']:.4f}" if not np.isnan(r["mean_abs_IC"]) else "--"
        disp_rows.append(d)

    if TABULATE:
        print(_tab(disp_rows, headers="keys", tablefmt="simple"), flush=True)
    else:
        print(pd.DataFrame(disp_rows).to_string(index=False), flush=True)

    return mf


# ─── Summary ───────────────────────────────────────────────────────────────────

def print_summary(sf_df: pd.DataFrame, mf_df: pd.DataFrame):
    print("\n" + "=" * 72, flush=True)
    print("  KEY FINDINGS SUMMARY", flush=True)
    print("=" * 72, flush=True)

    print("\n  Top 7 individual indicators (mean |IC| across all horizons):", flush=True)
    top7 = sf_df.dropna(subset=["mean_abs_IC"]).head(7)
    for i, (_, r) in enumerate(top7.iterrows(), 1):
        sig_h = [f"{fh}d" for fh in HORIZONS if r.get(f"pv_{fh}d", 1) < 0.01]
        ics_str = "  ".join(
            f"fwd{fh}d={r[f'IC_{fh}d']:+.4f}"
            for fh in HORIZONS if not np.isnan(r.get(f"IC_{fh}d", np.nan))
        )
        print(f"    {i}. {r['indicator']:<12} mean|IC|={r['mean_abs_IC']:.4f}  "
              f"sig(p<0.01): {', '.join(sig_h) if sig_h else 'none'}", flush=True)

    print("\n  Best multi-factor composite:", flush=True)
    best = mf_df.dropna(subset=["mean_abs_IC"]).iloc[0]
    print(f"    {best['combo']}", flush=True)
    print(f"    mean|IC|={best['mean_abs_IC']:.4f}", flush=True)
    for fh in HORIZONS:
        ic = best.get(f"IC_{fh}d", np.nan)
        pv = best.get(f"pv_{fh}d", np.nan)
        if not np.isnan(ic):
            sig = " **" if pv < 0.01 else (" *" if pv < 0.05 else "")
            print(f"    fwd{fh:>3}d: IC={ic:+.4f}  p={pv:.4f}{sig}", flush=True)

    print("\n  Benchmarks for IC interpretation:", flush=True)
    print("    |IC| > 0.02 — weak signal, worth monitoring", flush=True)
    print("    |IC| > 0.05 — meaningful signal in equity research", flush=True)
    print("    |IC| > 0.10 — strong predictive power", flush=True)
    print("  Note: All IC computed in-sample (no train/test split).", flush=True)
    print("  For out-of-sample validation use the walkforward scripts.", flush=True)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    global ADV_MIN_B
    ap = argparse.ArgumentParser()
    ap.add_argument("--adv", type=float, default=ADV_MIN_B,
                    help="Min ADV50 in Billion VND (default 2)")
    ap.add_argument("--sample-every", type=int, default=1,
                    help="Use every Nth monthly snapshot (default 1 = all)")
    args = ap.parse_args()

    ADV_MIN_B = args.adv

    t_start = time.time()
    panel, vni = load_data()
    snap = build_snapshot_panel(panel, vni, args.sample_every)

    snap_path = OUT / "indicator_snapshots.parquet"
    snap.to_parquet(snap_path, index=False)
    print(f"\nSnapshot saved: {snap_path}", flush=True)

    sf_df = run_single_factor(snap)
    mf_df = run_multifactor(snap, sf_df)
    print_summary(sf_df, mf_df)

    sf_out = OUT / "indicator_backtest_single_factor.csv"
    mf_out = OUT / "indicator_backtest_multifactor.csv"
    sf_df.to_csv(sf_out, index=False, encoding="utf-8-sig")
    mf_df.to_csv(mf_out, index=False, encoding="utf-8-sig")

    print(f"\n{'='*72}", flush=True)
    print(f"  Total runtime: {time.time()-t_start:.0f}s", flush=True)
    print(f"  Saved: {sf_out.name}, {mf_out.name}", flush=True)
    print("=" * 72, flush=True)


if __name__ == "__main__":
    main()
