"""
run_minervini_tier_ablation.py
==============================

Monthly hit-rate ablation for Tier S quality gates.

Purpose:
- Keep Tier S core logic intact.
- Test which single "quality gate" softening, if any, increases breadth while
  preserving edge better than broad A3.

Variants:
- S: strict baseline
- no_roe: ignore `roe<...`
- no_debt: ignore `debt_to_equity>...`
- no_margin: ignore `gross_margin_yoy<...`
- no_roe_debt: ignore roe + debt
- no_roe_margin: ignore roe + margin
- no_debt_margin: ignore debt + margin
- A3: ignore all three above
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
    forward_return_at_asof,
    fa_gate_with_reasons,
    price_features_at_asof,
)


def _load_universe(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _variant_pass(reasons: list[str], variant: str) -> tuple[bool, list[str]]:
    ignore_prefixes: dict[str, tuple[str, ...]] = {
        "S": (),
        "no_roe": ("roe<",),
        "no_debt": ("debt_to_equity>",),
        "no_margin": ("gross_margin_yoy<",),
        "no_roe_debt": ("roe<", "debt_to_equity>"),
        "no_roe_margin": ("roe<", "gross_margin_yoy<"),
        "no_debt_margin": ("debt_to_equity>", "gross_margin_yoy<"),
        "A3": ("roe<", "debt_to_equity>", "gross_margin_yoy<"),
    }
    prefixes = ignore_prefixes.get(variant, ())
    kept = [r for r in reasons if not any(r.startswith(p) for p in prefixes)]
    return len(kept) == 0, kept


def main() -> int:
    ap = argparse.ArgumentParser(description="Ablation of Tier S quality gates on monthly hit-rate")
    ap.add_argument("--fa-csv", default="data/fa_minervini.csv")
    ap.add_argument("--price-dir", default="minervini_backtest/data/raw")
    ap.add_argument("--universe", default="config/universe_186.txt")
    ap.add_argument("--bench", default="VNINDEX")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--end", default="2026-12-31")
    ap.add_argument("--forward-days", nargs="+", type=int, default=[126, 252])
    ap.add_argument("--out-dir", default="minervini_backtest/outputs/minervini_tier_ablation_U1")
    args = ap.parse_args()

    repo_root = ROOT.parent
    fa_path = repo_root / args.fa_csv
    price_dir = repo_root / args.price_dir
    universe_path = repo_root / args.universe
    out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    fa_full = pd.read_csv(fa_path)
    fa_full["report_date"] = pd.to_datetime(fa_full["report_date"])
    fa_full["symbol"] = fa_full["symbol"].astype(str).str.strip().str.upper()

    universe = set(_load_universe(universe_path))
    price_data = load_price_data(price_dir)
    bench_df = price_data.get(args.bench)
    if bench_df is None or bench_df.empty:
        print(f"[ERROR] Missing benchmark {args.bench}")
        return 1

    asof_dates = get_month_end_trading_dates(
        price_data, args.bench, pd.Timestamp(args.start), pd.Timestamp(args.end)
    )
    if not asof_dates:
        print("[ERROR] No month-end dates")
        return 1

    fwd_days = sorted(set(args.forward_days))
    bench_returns: dict[tuple[pd.Timestamp, int], float] = {}
    for asof in asof_dates:
        for fd in fwd_days:
            ret, ok = forward_return_at_asof(bench_df, asof, fd)
            bench_returns[(asof, fd)] = ret if ok and ret is not None else np.nan

    variants = [
        "S",
        "no_roe",
        "no_debt",
        "no_margin",
        "no_roe_debt",
        "no_roe_margin",
        "no_debt_margin",
        "A3",
    ]
    rows: list[dict] = []

    for asof in asof_dates:
        fa_latest = load_fa_latest_per_symbol_asof(fa_full, asof)
        fa_latest = fa_latest[fa_latest["symbol"].isin(universe)].copy()
        if fa_latest.empty:
            continue
        for _, row in fa_latest.iterrows():
            sym = row["symbol"]
            px = price_data.get(sym)
            if px is None or px.empty:
                continue
            feat = price_features_at_asof(px, asof)
            if feat is None:
                continue
            tech_breakout = feat["close"] > feat["high20"]
            tech_ma = feat["ma5"] > feat["ma10"] and feat["ma10"] > feat["ma20"]
            has_tech = tech_breakout or tech_ma
            base_pass, reasons = fa_gate_with_reasons(row)
            for variant in variants:
                fa_pass, kept = _variant_pass(reasons, variant)
                if not fa_pass or not has_tech:
                    continue
                rec = {
                    "asof_date": asof.strftime("%Y-%m-%d"),
                    "symbol": sym,
                    "variant": variant,
                    "tech_breakout_20d": bool(tech_breakout),
                    "tech_ma_stacked": bool(tech_ma),
                }
                for fd in fwd_days:
                    ret, ok = forward_return_at_asof(px, asof, fd)
                    b = bench_returns.get((asof, fd), np.nan)
                    rec[f"alpha_{fd}"] = float(ret - b) if ok and ret is not None and np.isfinite(b) else np.nan
                rows.append(rec)

    trades = pd.DataFrame(rows)
    trades.to_csv(out_dir / "ablation_trades.csv", index=False)

    summary: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for variant in variants:
        v = trades[trades["variant"] == variant]
        periods = v["asof_date"].nunique()
        entry: dict[str, dict[str, float | int | None] | int] = {
            "trade_count": int(len(v)),
            "periods_with_trade": int(periods),
        }
        for fd in fwd_days:
            a = v[f"alpha_{fd}"].dropna()
            if len(a) == 0:
                entry[str(fd)] = {
                    "median_alpha": None,
                    "mean_alpha": None,
                    "hit_rate_alpha_pos": None,
                    "p25_alpha": None,
                    "p75_alpha": None,
                }
            else:
                entry[str(fd)] = {
                    "median_alpha": float(a.median()),
                    "mean_alpha": float(a.mean()),
                    "hit_rate_alpha_pos": float((a > 0).mean()),
                    "p25_alpha": float(a.quantile(0.25)),
                    "p75_alpha": float(a.quantile(0.75)),
                }
        summary[variant] = entry  # type: ignore[assignment]

    with (out_dir / "ablation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("[Tier Ablation] Summary:")
    for variant in variants:
        s = summary[variant]
        m126 = s.get("126", {})
        print(
            f"  {variant}: trades={s['trade_count']} periods={s['periods_with_trade']} "
            f"median126={m126.get('median_alpha')} hit126={m126.get('hit_rate_alpha_pos')}"
        )
    print(f"[Tier Ablation] Wrote: {out_dir / 'ablation_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

