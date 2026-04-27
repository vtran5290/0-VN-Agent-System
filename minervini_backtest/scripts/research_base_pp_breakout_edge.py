"""
Historical edge study: base setups × pocket-pivot count × volume-confirmed breakout.

For walk-forward event study, base_id segmentation, and OOS robustness summaries, use
`minervini_backtest/scripts/research_base_pp_breakout_robust.py` (does not replace this script).

FACTS-only outputs (no claim of live profitability):
- For each bar that passes configurable "base" filters, records:
  - pp_count_in_base: number of pocket_pivot True in last `base_days` bars
  - Simulated entries:
    (A) k-th pocket pivot: next-open entry after the bar where cumulative PP in base first reaches k
    (B) Breakout: first bar in next `breakout_lookforward` days with
        close > pivot*(1+entry_buffer) AND volume >= breakout_vol_mult * vol_sma50
       entry next open (same semantics as prebreakout research)

Forward horizons: 5, 10, 20 trading days (close / entry_open - 1).

Source: local minervini_backtest/data/raw CSVs + VNINDEX regime trim.
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

import importlib.util

_rp = Path(__file__).resolve().parent / "run_prebreakout_research.py"
_spec = importlib.util.spec_from_file_location("run_prebreakout_research", _rp)
_rb = importlib.util.module_from_spec(_spec)
sys.modules["run_prebreakout_research"] = _rb
assert _spec.loader is not None
_spec.loader.exec_module(_rb)
_add_core_features = _rb._add_core_features

_scan = Path(__file__).resolve().parent / "scan_accumulation_bases.py"
_s2 = importlib.util.spec_from_file_location("scan_accumulation_bases", _scan)
_sm = importlib.util.module_from_spec(_s2)
sys.modules["scan_accumulation_bases"] = _sm
_s2.loader.exec_module(_sm)
_pick_analysis_regime = _sm._pick_analysis_regime
_row_metrics = _sm._row_metrics
_trend_series = _sm._trend_series
_discover = _sm._discover_symbols_all_raw


def _forward_ret_from_entry_open(
    close: np.ndarray, open_: np.ndarray, entry_i: int, horizons: tuple[int, ...]
) -> dict[str, float]:
    """entry_i = index of entry bar (fill at open[entry_i])."""
    eo = float(open_[entry_i])
    out: dict[str, float] = {}
    if not np.isfinite(eo) or eo <= 0:
        for h in horizons:
            out[f"ret_{h}d"] = np.nan
        return out
    n = len(close)
    for h in horizons:
        j = entry_i + h
        if j >= n:
            out[f"ret_{h}d"] = np.nan
        else:
            out[f"ret_{h}d"] = float(close[j] / eo - 1.0)
    return out


def _base_ok_row(
    m: dict,
    min_base_pos: float,
    max_dist: float,
    max_depth: float,
    min_depth: float,
) -> bool:
    bd = m["base_depth"]
    bp = m["base_pos_in_base"]
    dist = m["dist_to_pivot"]
    if not (min_depth <= bd <= max_depth):
        return False
    if bp < min_base_pos:
        return False
    if not np.isfinite(dist) or dist < -0.02 or dist > max_dist:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=2018)
    ap.add_argument("--base-days", type=int, default=80)
    ap.add_argument("--min-adv20", type=float, default=2e9)
    ap.add_argument("--trend", default="relaxed", choices=["medium", "relaxed", "none"])
    ap.add_argument("--min-base-pos", type=float, default=0.35)
    ap.add_argument("--max-dist-pivot", type=float, default=0.22)
    ap.add_argument("--max-base-depth", type=float, default=0.40)
    ap.add_argument("--min-base-depth", type=float, default=0.08)
    ap.add_argument("--anti-drift", action="store_true", help="Require close > close 20d ago at signal bar.")
    ap.add_argument("--entry-buffer", type=float, default=0.0015)
    ap.add_argument("--breakout-vol-mult", type=float, default=1.25)
    ap.add_argument("--breakout-lookforward", type=int, default=15)
    ap.add_argument("--pp-rungs", default="1,2,3", help="Which cumulative PP counts to tag for PP entries.")
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all raw symbols.")
    ap.add_argument(
        "--scoring",
        choices=["legacy", "edge"],
        default="legacy",
        help="Passed to scan _row_metrics (base geometry unchanged; edge adds PP/drift into composite only).",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/accumulation_scan/base_pp_breakout_research",
    )
    args = ap.parse_args()

    syms = _discover()
    if args.max_symbols and args.max_symbols > 0:
        syms = syms[: args.max_symbols]
    data = load_curated_data(syms + ["VNINDEX", "VN30"])
    bench = "VNINDEX" if "VNINDEX" in data else "VN30"
    if bench not in data:
        print("[ERROR] benchmark missing")
        return 1
    bench_df = _pick_analysis_regime(data[bench].sort_values("date"))
    bench_ret = bench_df.set_index("date")["close"].pct_change(63)
    start = pd.Timestamp(f"{args.start_year}-01-01")
    horizons = (5, 10, 20)

    pp_allowed = {int(x.strip()) for x in args.pp_rungs.split(",") if x.strip()}

    rows_pp: list[dict] = []
    rows_br: list[dict] = []

    for sym in syms:
        if sym not in data:
            continue
        d0 = data[sym].sort_values("date")
        d0 = d0[d0["date"] >= start]
        d0 = _pick_analysis_regime(d0)
        if len(d0) < 400:
            continue
        ed = _add_core_features(d0, bench_ret).reset_index(drop=True)
        n = len(ed)
        bd = int(args.base_days)
        # numpy arrays for speed
        close = ed["close"].to_numpy(dtype=float)
        open_ = ed["open"].to_numpy(dtype=float)
        vol = ed["volume"].to_numpy(dtype=float)
        vs50 = ed["vol_sma50"].to_numpy(dtype=float)
        pp = ed["pocket_pivot"].to_numpy()
        adv = ed["adv20"].to_numpy(dtype=float)
        dates = ed["date"].to_numpy()

        base_high = ed["high"].rolling(bd, min_periods=bd).max()
        pivot = base_high.shift(1)

        # cumulative PP in rolling base window: sum of pp in (i-bd+1 .. i)
        pp_roll = pd.Series(pp.astype(int)).rolling(bd, min_periods=1).sum()
        pp_cum_in_base = pp_roll.to_numpy()

        lf = int(args.breakout_lookforward)

        for i in range(bd + 5, n - max(horizons) - 3):
            if adv[i] < args.min_adv20:
                continue
            if not bool(_trend_series(args.trend, ed).iloc[i]):
                continue
            if args.anti_drift and i >= 20:
                if not (close[i] > close[i - 20]):
                    continue
            m = _row_metrics(ed, i, bd, scoring=args.scoring)
            if not m:
                continue
            if not _base_ok_row(
                m,
                args.min_base_pos,
                args.max_dist_pivot,
                args.max_base_depth,
                args.min_base_depth,
            ):
                continue

            piv = float(pivot.iloc[i]) if pd.notna(pivot.iloc[i]) else np.nan
            if not np.isfinite(piv) or piv <= 0:
                continue

            # --- Breakout path: first trigger in (i+1 .. i+LF] ---
            br_idx = None
            for j in range(i + 1, min(i + 1 + lf, n)):
                if not np.isfinite(vs50[j]) or vs50[j] <= 0:
                    continue
                if vol[j] >= args.breakout_vol_mult * vs50[j] and close[j] > piv * (1.0 + args.entry_buffer):
                    br_idx = j
                    break
            if br_idx is not None and br_idx + 1 < n:
                ent = br_idx + 1
                r = _forward_ret_from_entry_open(close, open_, ent, horizons)
                rows_br.append(
                    {
                        "symbol": sym,
                        "signal_i": i,
                        "signal_date": pd.Timestamp(dates[i]),
                        "breakout_i": br_idx,
                        "entry_i": ent,
                        "pp_in_base_at_signal": int(pp_cum_in_base[i]),
                        "base_depth": m["base_depth"],
                        "dist_to_pivot": m["dist_to_pivot"],
                        **{k: r[k] for k in r},
                    }
                )

        # --- PP path: on each PP day, if base_ok and cumulative PP count in {1,2,3} ---
        for t in range(bd + 5, n - max(horizons) - 2):
            if not pp[t]:
                continue
            if adv[t] < args.min_adv20:
                continue
            if not bool(_trend_series(args.trend, ed).iloc[t]):
                continue
            if args.anti_drift and t >= 20:
                if not (close[t] > close[t - 20]):
                    continue
            m2 = _row_metrics(ed, t, bd, scoring=args.scoring)
            if not m2 or not _base_ok_row(
                m2,
                args.min_base_pos,
                args.max_dist_pivot,
                args.max_base_depth,
                args.min_base_depth,
            ):
                continue
            c = int(pp_cum_in_base[t])
            if c not in pp_allowed:
                continue
            ent = t + 1
            if ent >= n - max(horizons):
                continue
            r = _forward_ret_from_entry_open(close, open_, ent, horizons)
            rows_pp.append(
                {
                    "symbol": sym,
                    "signal_i": t,
                    "signal_date": pd.Timestamp(dates[t]),
                    "pp_rung": c,
                    "pp_in_base_at_signal": c,
                    "base_depth": m2["base_depth"],
                    "dist_to_pivot": m2["dist_to_pivot"],
                    **{x: r[x] for x in r},
                }
            )

    out_root = REPO / args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    br_df = pd.DataFrame(rows_br)
    pp_df = pd.DataFrame(rows_pp)
    br_df.to_csv(out_root / "events_breakout_vol.csv", index=False)
    pp_df.to_csv(out_root / "events_pp_rungs.csv", index=False)

    # Aggregate summaries
    summ = []
    if not br_df.empty:
        br_df["pp_bucket"] = br_df["pp_in_base_at_signal"].clip(0, 5)
        for key, sub in br_df.groupby("pp_bucket"):
            summ.append(
                {
                    "path": "breakout_vol",
                    "bucket": f"pp_in_base_{int(key)}",
                    "n": len(sub),
                    "win5": float((sub["ret_5d"] > 0).mean()),
                    "win10": float((sub["ret_10d"] > 0).mean()),
                    "win20": float((sub["ret_20d"] > 0).mean()),
                    "median_ret10": float(sub["ret_10d"].median()),
                    "mean_ret10": float(sub["ret_10d"].mean()),
                }
            )
    if not pp_df.empty:
        for key, sub in pp_df.groupby("pp_rung"):
            summ.append(
                {
                    "path": "pp_rung_entry",
                    "bucket": f"pp_rung_{int(key)}",
                    "n": len(sub),
                    "win5": float((sub["ret_5d"] > 0).mean()),
                    "win10": float((sub["ret_10d"] > 0).mean()),
                    "win20": float((sub["ret_20d"] > 0).mean()),
                    "median_ret10": float(sub["ret_10d"].median()),
                    "mean_ret10": float(sub["ret_10d"].mean()),
                }
            )

    summ_df = pd.DataFrame(summ)
    summ_df.to_csv(out_root / "summary_edge_by_bucket.csv", index=False)

    note = [
        "# Base / PP / breakout edge (research)",
        "",
        "## Parameters",
        f"- trend: {args.trend}",
        f"- scoring: {args.scoring}",
        f"- base_days: {args.base_days}",
        f"- min_base_pos: {args.min_base_pos}, max_dist_pivot: {args.max_dist_pivot}, max_base_depth: {args.max_base_depth}",
        f"- breakout: close > pivot*(1+{args.entry_buffer}) AND vol >= {args.breakout_vol_mult} * vol_sma50, entry next open",
        f"- anti_drift: {args.anti_drift}",
        "",
        "## Interpretation",
        "- Higher win% / mean_ret on **out-of-sample** would require walk-forward; this is **in-sample** descriptive stats.",
        "- Survivorship / scale-break in local CSVs still apply.",
        "",
        f"- Breakout events: {len(br_df)}, PP rung events: {len(pp_df)}",
    ]
    (out_root / "README.md").write_text("\n".join(note), encoding="utf-8")

    print(summ_df.to_string(index=False))
    print(f"Wrote {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
