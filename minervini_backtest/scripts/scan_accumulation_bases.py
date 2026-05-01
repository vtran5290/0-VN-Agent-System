"""
Rank VN stocks by accumulation/base quality at latest bar (research-style heuristics).

Maps loosely to Minervini / Morales / O'Neil themes:
- Tightness: low ATR ratio, narrow range, low close dispersion
- Quiet base: volume dry-up vs longer MA
- Constructive price action: higher share of up-days
- Right-side interest: recent volume lift vs base quiet zone
- Shakeout/spring proxy: undercut of a recent pivot zone then reclaim

This is NOT the strict prebreakout preset grid; it is a broader "base quality" scan.
Outputs CSV + prints top table. Source: local curated OHLCV (same as prebreakout).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from run import load_curated_data

# Load sibling module without package import path issues
import importlib.util

_rp = Path(__file__).resolve().parent / "run_prebreakout_research.py"
_spec = importlib.util.spec_from_file_location("run_prebreakout_research", _rp)
_rb = importlib.util.module_from_spec(_spec)
sys.modules["run_prebreakout_research"] = _rb
assert _spec.loader is not None
_spec.loader.exec_module(_rb)
_add_core_features = _rb._add_core_features
_read_symbols = _rb._read_symbols

_RAW_DIR = ROOT / "data" / "raw"
_BENCH = {"VNINDEX", "VN30"}


def _discover_symbols_all_raw() -> list[str]:
    """All tickers that have a CSV in minervini_backtest/data/raw (ex benchmarks)."""
    if not _RAW_DIR.is_dir():
        return []
    out: list[str] = []
    for fp in _RAW_DIR.glob("*.csv"):
        stem = fp.stem.upper()
        if stem in _BENCH:
            continue
        out.append(stem)
    return sorted(out)


def _trend_mask_medium(d: pd.DataFrame) -> pd.Series:
    ma50_slope = (d["ma50"] - d["ma50"].shift(20)) / d["ma50"].shift(20).replace(0, np.nan)
    ma150_slope = (d["ma150"] - d["ma150"].shift(20)) / d["ma150"].shift(20).replace(0, np.nan)
    return (
        (d["close"] > d["ma50"])
        & (d["ma50"] > d["ma150"])
        & (d["ma150"] > d["ma200"])
        & (ma50_slope > 0)
        & (ma150_slope > 0)
    ).fillna(False)


def _trend_mask_relaxed(d: pd.DataFrame) -> pd.Series:
    """Minervini relaxed: price above rising MA50, MA50 above MA200 (matches prebreakout relaxed tier)."""
    ma50_slope = (d["ma50"] - d["ma50"].shift(20)) / d["ma50"].shift(20).replace(0, np.nan)
    return ((d["close"] > d["ma50"]) & (d["ma50"] > d["ma200"]) & (ma50_slope > 0)).fillna(False)


def _trend_series(mode: str, d: pd.DataFrame) -> pd.Series:
    if mode == "medium":
        return _trend_mask_medium(d)
    if mode == "relaxed":
        return _trend_mask_relaxed(d)
    # none: all True (base scan only; no stage-2 gate)
    return pd.Series(True, index=d.index)


def _split_price_regimes(df: pd.DataFrame, col: str = "close") -> list[tuple[int, int]]:
    """Return list of (start_idx, end_idx exclusive) segments split on >20x price jumps."""
    if df.empty or col not in df.columns:
        return []
    c = df[col].astype(float).values
    cuts = [0]
    for i in range(1, len(c)):
        a, b = c[i - 1], c[i]
        if not np.isfinite(a) or not np.isfinite(b) or a <= 0:
            continue
        r = b / a
        if r > 20.0 or r < (1.0 / 20.0):
            cuts.append(i)
    cuts.append(len(c))
    return [(cuts[j], cuts[j + 1]) for j in range(len(cuts) - 1)]


def _pick_analysis_regime(df: pd.DataFrame, col: str = "close", min_bars: int = 280) -> pd.DataFrame:
    """
    Choose a single price regime for long-horizon TA.

    If the newest merged segment is very short (common after a bad unit/join at file tail),
    use the previous long segment so MA150/200 and base windows stay meaningful.
    """
    if df.empty:
        return df
    segs = _split_price_regimes(df, col)
    if not segs:
        return df.reset_index(drop=True)
    # Prefer last segment if long enough; else longest segment ending at or before last date
    last_start, last_end = segs[-1]
    if last_end - last_start >= min_bars:
        out = df.iloc[last_start:last_end]
        return out.reset_index(drop=True)
    # Short tail: drop it and use longest prior segment
    best = max(segs[:-1], key=lambda x: x[1] - x[0], default=segs[0])
    s, e = best
    out = df.iloc[s:e]
    return out.reset_index(drop=True)


def _norm01(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    v = (x - lo) / (hi - lo)
    return float(np.clip(v, 0.0, 1.0))


def _pp_count_in_base(ed: pd.DataFrame, i: int, base_days: int) -> int:
    """Number of pocket-pivot days in the rolling base window ending at i."""
    lo = i - base_days + 1
    if lo < 0:
        return 0
    seg = ed.iloc[lo : i + 1]
    if "pocket_pivot" not in seg.columns:
        return 0
    return int(seg["pocket_pivot"].fillna(False).sum())


def _anti_drift_ok(ed: pd.DataFrame, i: int, lookback: int = 20) -> bool:
    """Close above close N days ago (reduces pure down-drifting 'bases')."""
    if i < lookback:
        return False
    c = float(ed["close"].iloc[i])
    c0 = float(ed["close"].iloc[i - lookback])
    return bool(np.isfinite(c) and np.isfinite(c0) and c0 > 0 and c > c0)


def _row_metrics(ed: pd.DataFrame, i: int, base_days: int, scoring: str = "legacy") -> dict:
    """Point-in-time metrics at bar index i (end-of-day)."""
    row = ed.iloc[i]
    if i < base_days + 5:
        return {}

    base_high = ed["high"].rolling(base_days, min_periods=base_days).max()
    base_low = ed["low"].rolling(base_days, min_periods=base_days).min()
    bh = float(base_high.iloc[i])
    bl = float(base_low.iloc[i])
    if bh <= 0 or bh <= bl:
        return {}
    base_depth = (bh - bl) / bh
    base_pos = (float(row["close"]) - bl) / (bh - bl)
    pivot = float(base_high.shift(1).iloc[i])
    dist_to_pivot = (pivot - float(row["close"])) / pivot if pivot > 0 else np.nan

    # Green / constructive days (last 10)
    sub10 = ed.iloc[i - 9 : i + 1]
    up = (sub10["close"] > sub10["close"].shift(1)).fillna(False)
    green_ratio_10 = float(up.mean())

    sub20 = ed.iloc[i - 19 : i + 1]
    up20 = (sub20["close"] > sub20["close"].shift(1)).fillna(False)
    green_ratio_20 = float(up20.mean())

    # Volume: quiet middle of base vs recent
    volr = ed["volume"] / ed["vol_sma50"].replace(0, np.nan)
    if i >= 40:
        quiet_zone = volr.iloc[i - 35 : i - 5]
        quiet_med = float(quiet_zone.median()) if len(quiet_zone) else np.nan
    else:
        quiet_med = np.nan
    recent5 = volr.iloc[i - 4 : i + 1]
    max_volr_5 = float(recent5.max())

    # Shakeout / spring proxy: in last 20 bars, price undercuts prior 30-bar low (excl last 10) then last close holds above that low
    if i >= 40:
        prior_low = float(ed["low"].iloc[i - 40 : i - 10].min())
        last20 = ed.iloc[i - 19 : i + 1]
        undercut = (last20["low"] < prior_low * 0.995).any()
        reclaim = float(row["close"]) > prior_low
        shakeout_score = 1.0 if (undercut and reclaim) else 0.0
    else:
        shakeout_score = 0.0

    # Tightness components (already in features)
    atr_r = float(row["atr_ratio_10_50"]) if pd.notna(row["atr_ratio_10_50"]) else np.nan
    rng10 = float(row["range_10"]) if pd.notna(row["range_10"]) else np.nan
    disp = float(row["disp_10"]) if pd.notna(row["disp_10"]) else np.nan
    vr = float(row["vol_ratio_10_50"]) if pd.notna(row["vol_ratio_10_50"]) else np.nan

    # Scores 0..1 (higher = better)
    tight = (
        0.34 * (1.0 - _norm01(atr_r, 0.55, 1.25))
        + 0.33 * (1.0 - _norm01(rng10, 0.03, 0.16))
        + 0.33 * (1.0 - _norm01(disp, 0.01, 0.06))
    )
    dry = 1.0 - _norm01(vr, 0.55, 1.05)
    constructive = _norm01(green_ratio_10, 0.35, 0.75)

    # Right-side volume: want some lift vs very quiet base, but not climax-only
    thrust = 0.0
    if np.isfinite(quiet_med) and quiet_med > 0:
        thrust = _norm01(max_volr_5 / quiet_med, 1.0, 2.2)

    composite = (
        0.28 * tight
        + 0.22 * dry
        + 0.18 * constructive
        + 0.12 * thrust
        + 0.12 * float(shakeout_score)
        + 0.08 * _norm01(float(row.get("rs_63", np.nan)), -0.05, 0.25)
    )

    pp_n = _pp_count_in_base(ed, i, base_days)
    pp_norm = min(float(pp_n) / 3.0, 1.0)  # cap at 3 PPs in window
    drift_ok = _anti_drift_ok(ed, i, 20)

    # "edge" scoring: emphasize PP ladder + structural drift, slightly less pure dry-up
    if scoring == "edge":
        composite = (
            0.22 * tight
            + 0.16 * dry
            + 0.14 * constructive
            + 0.10 * thrust
            + 0.10 * float(shakeout_score)
            + 0.10 * _norm01(float(row.get("rs_63", np.nan)), -0.05, 0.25)
            + 0.12 * pp_norm
            + 0.06 * (1.0 if drift_ok else 0.0)
        )

    return {
        "base_depth": base_depth,
        "base_pos_in_base": base_pos,
        "dist_to_pivot": dist_to_pivot,
        "green_ratio_10": green_ratio_10,
        "green_ratio_20": green_ratio_20,
        "atr_ratio_10_50": atr_r,
        "range_10": rng10,
        "disp_10": disp,
        "vol_ratio_10_50": vr,
        "max_vol_vs50_5d": max_volr_5,
        "quiet_median_vol_ratio_30d": quiet_med,
        "shakeout_spring_proxy": shakeout_score,
        "score_tightness": tight,
        "score_dry_volume": dry,
        "score_constructive": constructive,
        "score_right_side_thrust": thrust,
        "pp_count_in_base": pp_n,
        "anti_drift_20d": drift_ok,
        "composite_base_score": composite,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank accumulation base quality at latest OHLCV date.")
    ap.add_argument("--base-days", type=int, default=80, help="Base window (~16 weeks if 5d/wk).")
    ap.add_argument(
        "--universe",
        choices=["watchlist", "all_raw"],
        default="all_raw",
        help="watchlist=config/universe_186|watchlist_80|watchlist; all_raw=all CSV tickers under minervini_backtest/data/raw.",
    )
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all universe symbols.")
    ap.add_argument(
        "--min-adv20",
        type=float,
        default=2e9,
        help="Min ADV20 = rolling 20D avg turnover (close*volume) in VND (default: 2e9 = 2B/phiên).",
    )
    ap.add_argument("--out-csv", default="minervini_backtest/outputs/accumulation_scan/accumulation_bases_ranked.csv")
    ap.add_argument(
        "--trend",
        choices=["medium", "relaxed", "none"],
        default="medium",
        help="Stage-2 trend gate: medium=MA50>MA150>MA200+slope; relaxed=MA50>MA200+MA50 slope; none=off.",
    )
    ap.add_argument(
        "--min-base-pos",
        type=float,
        default=0.45,
        help="Min price location in 80d base range (0=base low, 1=high). Default 0.45=upper half. Use 0 to allow full range (e.g. late-stage washout).",
    )
    ap.add_argument(
        "--max-dist-pivot",
        type=float,
        default=0.14,
        help="Max (pivot-close)/pivot to pivot (default 14%%). Widen to include names farther below pivot.",
    )
    ap.add_argument(
        "--max-base-depth",
        type=float,
        default=0.38,
        help="Max base depth over base window (default 0.38).",
    )
    ap.add_argument(
        "--scoring",
        choices=["legacy", "edge"],
        default="edge",
        help="legacy=tight+dry heuristic; edge=adds PP-in-base + anti-drift for follow-through proxy.",
    )
    ap.add_argument(
        "--require-anti-drift",
        action="store_true",
        help="Require close > close 20d ago (filters down-drifting bases).",
    )
    ap.add_argument("--min-pp-in-base", type=int, default=0, help="Minimum pocket pivots counted in base window (0=off).")
    args = ap.parse_args()

    if args.universe == "all_raw":
        discovered = _discover_symbols_all_raw()
        if not discovered:
            print("[ERROR] No CSV symbols under data/raw.")
            return 1
        load_list = discovered + ["VNINDEX", "VN30"]
        data = load_curated_data(load_list)
        symbols = [s for s in discovered if s in data]
        print(
            f"[info] universe=all_raw n_csv={len(discovered)} loaded={len(symbols)} "
            f"trend={args.trend} min_adv20={args.min_adv20:,.0f} "
            f"min_base_pos={args.min_base_pos} max_dist_pivot={args.max_dist_pivot} "
            f"max_base_depth={args.max_base_depth} scoring={args.scoring}"
        )
    else:
        symbols = _read_symbols()
        load_list = list(symbols) if symbols else None
        if load_list is not None:
            load_list = load_list + ["VNINDEX", "VN30"]
        data = load_curated_data(load_list)
        if not data:
            print("[ERROR] No OHLCV data.")
            return 1
        all_syms = sorted(k for k in data.keys() if k not in _BENCH)
        if args.max_symbols and args.max_symbols > 0:
            symbols = (symbols or all_syms)[: args.max_symbols]
        else:
            symbols = symbols or all_syms
        symbols = [s for s in symbols if s in data and s not in _BENCH]
    if not data:
        print("[ERROR] No OHLCV data.")
        return 1
    bench = "VNINDEX" if "VNINDEX" in data else ("VN30" if "VN30" in data else None)
    if not bench:
        print("[ERROR] No benchmark.")
        return 1
    if args.max_symbols and args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]

    bench_df = data[bench].sort_values("date")
    bench_df = _pick_analysis_regime(bench_df)
    bench_ret_63 = bench_df.set_index("date")["close"].pct_change(63)
    asof = pd.Timestamp(bench_df["date"].max())

    rows: list[dict] = []
    base_days = int(args.base_days)

    for sym in symbols:
        d0 = data[sym].sort_values("date")
        d0 = d0[d0["date"] <= asof]
        d0 = _pick_analysis_regime(d0)
        if len(d0) < 350:
            continue
        ed = _add_core_features(d0, bench_ret_63)
        ed = ed.reset_index(drop=True)
        i = len(ed) - 1
        row0 = ed.iloc[i]
        if float(row0.get("adv20", 0) or 0) < args.min_adv20:
            continue
        if not bool(_trend_series(args.trend, ed).iloc[i]):
            continue

        m = _row_metrics(ed, i, base_days, scoring=args.scoring)
        if not m:
            continue
        if args.require_anti_drift and not m.get("anti_drift_20d"):
            continue
        if int(m.get("pp_count_in_base", 0) or 0) < int(args.min_pp_in_base):
            continue

        bd = m["base_depth"]
        bp = m["base_pos_in_base"]
        dist = m["dist_to_pivot"]
        # Broad "valid base" filter (not as tight as prebreakout preset)
        if not (0.08 <= bd <= float(args.max_base_depth)):
            continue
        if bp < float(args.min_base_pos):
            continue
        max_dp = float(args.max_dist_pivot)
        if not np.isfinite(dist) or dist < -0.02 or dist > max_dp:
            continue

        last_dt = pd.Timestamp(row0["date"])
        rows.append(
            {
                "symbol": sym,
                "benchmark_last_date": str(asof.date()),
                "last_bar_date": str(last_dt.date()),
                "close": float(row0["close"]),
                "adv20_vnd": float(row0.get("adv20", 0) or 0),
                **m,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        print("[WARN] No rows after filters. Relax filters or check data.")
        return 0

    out = out.sort_values("composite_base_score", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)

    out_path = REPO / args.out_csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path} rows={len(out)} asof={asof.date()}")
    cols = [
        "rank",
        "symbol",
        "composite_base_score",
        "pp_count_in_base",
        "anti_drift_20d",
        "score_tightness",
        "score_dry_volume",
        "score_constructive",
        "score_right_side_thrust",
        "shakeout_spring_proxy",
        "dist_to_pivot",
        "base_depth",
        "green_ratio_10",
        "vol_ratio_10_50",
    ]
    cols = [c for c in cols if c in out.columns]
    print(out[cols].head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
