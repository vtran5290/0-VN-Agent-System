"""
run_minervini_fa_score_backtest.py
==================================

E8 — FA scoring backtest (Mark-style Tier A) on U1.

Core idea:
- Use a minimal FA core gate (profit_positive + sales_yoy >= 15 + earnings_yoy >= 15).
- Build a 0–100 score per symbol at each as-of (month-end) using:
  earnings accel, sales strength, RS_6m percentile, margin_yoy, debt_to_equity.
- At each month-end, pick Top-N symbols by score (N in [10,20,30] by default),
  then compute forward returns and alpha vs VNINDEX for 126/252 trading days.

This does NOT change Tier S or existing timing logic; it's a separate experiment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minervini_candidates.utils import (  # type: ignore
    load_fa_latest_per_symbol_asof,
    load_price_data,
    get_month_end_trading_dates,
    compute_rs_6m,
    rs_percentile_in_universe,
    forward_return_at_asof,
    fa_core_gate_e8,
    fa_score_e8,
    price_features_at_asof,
)


def _load_universe(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="E8 FA scoring backtest (monthly, Top-N by score, forward 6m/12m alpha)"
    )
    ap.add_argument("--fa-csv", default="data/fa_minervini.csv", help="FA CSV with report_date history")
    ap.add_argument(
        "--price-dir",
        default="minervini_backtest/data/raw",
        help="Directory of OHLCV CSVs (default: minervini_backtest/data/raw)",
    )
    ap.add_argument(
        "--universe",
        default="config/universe_186.txt",
        help="Universe file (one symbol per line). Use U1 by default.",
    )
    ap.add_argument("--bench", default="VNINDEX", help="Benchmark symbol (for alpha)")
    ap.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    ap.add_argument("--end", default="2026-12-31", help="End date YYYY-MM-DD")
    ap.add_argument(
        "--forward-days",
        nargs="+",
        type=int,
        default=[126, 252],
        help="Forward horizons in trading days (e.g. 126 252)",
    )
    ap.add_argument(
        "--topN",
        nargs="+",
        type=int,
        default=[10, 20, 30],
        help="Top N by score per asof to evaluate (default: 10 20 30)",
    )
    ap.add_argument(
        "--rs-min",
        type=float,
        default=0.0,
        help="Minimum RS_6m percentile (0-100) gate before scoring (default: 0 = no RS gate)",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/minervini_fa_score_U1",
        help="Output directory for trades & summary",
    )
    ap.add_argument(
        "--gate-not-extended",
        action="store_true",
        help="If set, require price to be not extended vs MA10/MA20 at asof (simple Mark-style setup gate).",
    )
    ap.add_argument(
        "--gate-accel-purity",
        action="store_true",
        help="If set, require high-confidence 2-step earnings acceleration (simple Code-33-lite purity gate).",
    )
    ap.add_argument(
        "--gate-tightness-pct",
        type=float,
        default=0.0,
        help="If >0, require 15-bar close tightness (max-min)/avg <= value (e.g. 0.06)",
    )
    args = ap.parse_args()

    repo_root = ROOT.parent
    fa_path = repo_root / args.fa_csv
    price_dir = repo_root / args.price_dir
    universe_path = repo_root / args.universe
    out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    forward_days_list = sorted(set(args.forward_days))
    topNs = sorted(set(args.topN))
    max_topN = max(topNs)
    bench_symbol = args.bench

    if not fa_path.exists():
        print(f"[ERROR] FA CSV not found: {fa_path}")
        return 1
    fa_full = pd.read_csv(fa_path)
    if "report_date" not in fa_full.columns or "symbol" not in fa_full.columns:
        print("[ERROR] fa_minervini.csv missing 'symbol' or 'report_date'")
        return 1
    fa_full["report_date"] = pd.to_datetime(fa_full["report_date"])
    fa_full["symbol"] = fa_full["symbol"].astype(str).str.strip().str.upper()

    # Universe
    universe_syms = _load_universe(universe_path)
    if not universe_syms:
        print(f"[ERROR] Universe file empty: {universe_path}")
        return 1

    # Price data
    price_data = load_price_data(price_dir)
    if not price_data:
        print(f"[ERROR] No price data in {price_dir}")
        return 1
    bench_df = price_data.get(bench_symbol)
    if bench_df is None or bench_df.empty:
        print(f"[ERROR] Benchmark {bench_symbol} not in price data")
        return 1

    # Asof dates (month-end)
    asof_dates = get_month_end_trading_dates(price_data, bench_symbol, start, end)
    if not asof_dates:
        print("[ERROR] No month-end dates in range")
        return 1

    # Precompute benchmark forward returns
    bench_returns: dict[tuple[pd.Timestamp, int], float] = {}
    for asof in asof_dates:
        for fd in forward_days_list:
            ret, ok = forward_return_at_asof(bench_df, asof, fd)
            bench_returns[(asof, fd)] = ret if ok and ret is not None else np.nan

    # Collect E8 trades: only Top max_topN per asof
    rows: list[dict] = []
    for asof in asof_dates:
        fa_latest = load_fa_latest_per_symbol_asof(fa_full, asof)
        if fa_latest.empty:
            continue
        fa_latest = fa_latest[fa_latest["symbol"].isin(universe_syms)].copy()
        if fa_latest.empty:
            continue

        # RS_6m map + percentile
        rs_6m_map, _ = compute_rs_6m(price_data, asof, index_symbol=bench_symbol)
        symbols = fa_latest["symbol"].tolist()
        rs_6m_pct_map = rs_percentile_in_universe(rs_6m_map, symbols)

        cand_rows: list[dict] = []
        for _, row in fa_latest.iterrows():
            sym = row["symbol"]
            if sym not in price_data or price_data[sym].empty:
                continue
            if not fa_core_gate_e8(row):
                continue
            if args.gate_accel_purity:
                accel_conf = str(row.get("accel_confidence", "") or "").strip().lower()
                try:
                    accel_2_ok = int(row.get("earnings_accel_2step_flag")) == 1
                except Exception:
                    accel_2_ok = False
                if not (accel_conf == "high" and accel_2_ok):
                    continue
            rs_pct = rs_6m_pct_map.get(sym, np.nan)
            # RS_6m hard gate if requested
            if args.rs_min > 0.0 and (not np.isfinite(rs_pct) or rs_pct < args.rs_min):
                continue
            px = price_data[sym]
            # Optional simple setup gate: not extended vs MA10/MA20
            if args.gate_not_extended:
                feat = price_features_at_asof(px, asof)
                if feat is None:
                    continue
                close = feat["close"]
                ma10 = feat["ma10"]
                ma20 = feat["ma20"]
                extended_10 = close > ma10 * 1.10 if ma10 else False
                extended_20 = close > ma20 * 1.15 if ma20 else False
                if extended_10 and extended_20:
                    continue
            if args.gate_tightness_pct > 0.0:
                recent = px[px["date"] <= asof].sort_values("date").tail(15)
                if len(recent) < 15:
                    continue
                closes = recent["close"].astype(float)
                avg_c = float(closes.mean())
                if avg_c <= 0:
                    continue
                tightness = float((closes.max() - closes.min()) / avg_c)
                if tightness > args.gate_tightness_pct:
                    continue
            score = fa_score_e8(row, rs_pct)
            # Forward returns & alpha
            entry_asof = asof
            rec: dict = {
                "asof_date": entry_asof.strftime("%Y-%m-%d"),
                "symbol": sym,
                "score_e8": float(score),
                "rs_6m_pct": float(rs_pct) if np.isfinite(rs_pct) else np.nan,
            }
            for fd in forward_days_list:
                ret, ok = forward_return_at_asof(px, entry_asof, fd)
                b = bench_returns.get((entry_asof, fd), np.nan)
                rec[f"ret_{fd}"] = ret if ok and ret is not None else np.nan
                rec[f"bench_{fd}"] = b
                if ok and ret is not None and np.isfinite(b):
                    rec[f"alpha_{fd}"] = float(ret - b)
                else:
                    rec[f"alpha_{fd}"] = np.nan
            cand_rows.append(rec)

        if not cand_rows:
            continue
        cand_df = pd.DataFrame(cand_rows)
        cand_df = cand_df.sort_values("score_e8", ascending=False).reset_index(drop=True)
        cand_df["rank"] = cand_df.index + 1
        cand_df = cand_df[cand_df["rank"] <= max_topN]
        rows.extend(cand_df.to_dict(orient="records"))

    trades_df = pd.DataFrame(rows)
    if trades_df.empty:
        print("[WARN] No E8 trades; nothing to summarize.")
        return 0

    trades_path = out_dir / "fa_score_trades.csv"
    trades_df.to_csv(trades_path, index=False)

    # Pooled metrics per N and horizon
    summary: dict = {
        "config": {
            "fa_csv": str(fa_path),
            "price_dir": str(price_dir),
            "universe": str(universe_path),
            "bench": bench_symbol,
            "start": args.start,
            "end": args.end,
            "freq": "monthly",
            "forward_days": forward_days_list,
            "topN": topNs,
            "rs_min": args.rs_min,
            "gate_not_extended": bool(args.gate_not_extended),
            "gate_accel_purity": bool(args.gate_accel_purity),
            "gate_tightness_pct": float(args.gate_tightness_pct),
        },
        "n_periods": len(asof_dates),
        "topN_metrics": {},
    }

    for N in topNs:
        metrics_N: dict[str, dict[str, float | int | None]] = {}
        sel = trades_df[trades_df["rank"] <= N]
        for fd in forward_days_list:
            col = f"alpha_{fd}"
            a = sel[col].dropna()
            n = len(a)
            if n == 0:
                metrics_N[str(fd)] = {
                    "trade_count": 0,
                    "median_alpha": None,
                    "mean_alpha": None,
                    "hit_rate_alpha_pos": None,
                    "p25_alpha": None,
                    "p75_alpha": None,
                }
            else:
                metrics_N[str(fd)] = {
                    "trade_count": int(n),
                    "median_alpha": float(a.median()),
                    "mean_alpha": float(a.mean()),
                    "hit_rate_alpha_pos": float((a > 0).mean()),
                    "p25_alpha": float(a.quantile(0.25)),
                    "p75_alpha": float(a.quantile(0.75)),
                }
        summary["topN_metrics"][str(N)] = metrics_N

    summary_path = out_dir / "fa_score_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Console summary for N=20 (typical) if available
    metrics20 = summary["topN_metrics"].get("20") or summary["topN_metrics"].get(str(max_topN))
    if metrics20:
        m126 = metrics20.get("126", {})
        m252 = metrics20.get("252", {})
        print(
            "[E8] Top20 Tier-A scoring on U1: "
            f"126d trades={m126.get('trade_count')} "
            f"median_alpha={m126.get('median_alpha')} "
            f"hit_rate={m126.get('hit_rate_alpha_pos')}"
        )
        print(
            f"     252d trades={m252.get('trade_count')} "
            f"median_alpha={m252.get('median_alpha')} "
            f"hit_rate={m252.get('hit_rate_alpha_pos')}"
        )
    print(f"[E8] Wrote trades to {trades_path} and summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

