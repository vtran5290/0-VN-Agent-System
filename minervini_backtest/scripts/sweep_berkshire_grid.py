from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.cohort_backtest import (
    _cohort_for_quarter,
    _horizon_exit,
    _load_price_data,
    _next_trading_day_close,
    load_fa_csv,
)
from fa_cohort.fa_filters import FaFilterConfig


def evaluate_config(
    fa_df: pd.DataFrame,
    price_data: dict[str, pd.DataFrame],
    cfg: FaFilterConfig,
    horizons: list[int],
    bench_symbol: str = "VNINDEX",
    weights: dict[int, float] | None = None,
) -> dict | None:
    cohort_df = _cohort_for_quarter(fa_df, cfg)
    if cohort_df.empty:
        return None

    bench_df = price_data.get(bench_symbol.upper())
    if bench_df is None or bench_df.empty:
        raise ValueError(f"Benchmark symbol {bench_symbol} not found.")

    records: list[dict] = []
    for _, row in cohort_df.iterrows():
        sym = row["symbol"]
        px = price_data.get(sym)
        if px is None or px.empty:
            continue
        entry = _next_trading_day_close(px, row["report_date"])
        if entry is None:
            continue
        entry_dt, entry_px = entry
        bench_entry = _next_trading_day_close(bench_df, entry_dt)
        if bench_entry is None:
            continue
        bench_entry_dt, bench_entry_px = bench_entry

        for weeks in horizons:
            exit_pair = _horizon_exit(px, entry_dt, weeks)
            bench_exit_pair = _horizon_exit(bench_df, bench_entry_dt, weeks)
            if exit_pair is None or bench_exit_pair is None:
                continue
            _, exit_px = exit_pair
            _, bench_exit_px = bench_exit_pair
            ret = (exit_px / entry_px) - 1.0
            bench_ret = (bench_exit_px / bench_entry_px) - 1.0
            records.append(
                {
                    "year": entry_dt.year,
                    "horizon_weeks": weeks,
                    "alpha": ret - bench_ret,
                }
            )

    if not records:
        return None

    yearly_alpha = pd.DataFrame(records).groupby(["year", "horizon_weeks"])["alpha"].median().reset_index()
    median_alpha_by_h = yearly_alpha.groupby("horizon_weeks")["alpha"].median().to_dict()
    if any(h not in median_alpha_by_h for h in horizons):
        return None

    years_pos = int((yearly_alpha.groupby("year")["alpha"].median() > 0).sum())
    pass_flag = all(median_alpha_by_h[h] > 0 for h in horizons) and years_pos >= 3

    # Buffett-style score: favor longer horizons through explicit weights.
    weights = weights or {8: 0.20, 13: 0.30, 26: 0.50, 52: 0.70}
    score = sum(median_alpha_by_h[h] * weights.get(h, 0.25) for h in horizons)
    if any(median_alpha_by_h[h] <= 0 for h in horizons):
        score -= 1.0

    annual_counts = cohort_df.groupby("year")["symbol"].nunique()
    return {
        "score": score,
        "pass": pass_flag,
        "years_positive": years_pos,
        "median_alpha_by_horizon": median_alpha_by_h,
        "avg_annual_n": float(annual_counts.mean()) if not annual_counts.empty else 0.0,
        "config": asdict(cfg),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grid search Berkshire VN cohort assumptions.")
    parser.add_argument("--fa-csv", required=True)
    parser.add_argument("--bench", default="VNINDEX")
    parser.add_argument("--horizons", nargs="+", type=int, default=[8, 13, 26])
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--out-json",
        default=str(ROOT / "outputs" / "berkshire_comparison" / "grid_search_top.json"),
    )
    args = parser.parse_args()

    fa_df = load_fa_csv(args.fa_csv)
    price_data = _load_price_data()

    # Keep the search tight around the current winners so turnaround stays practical.
    search_space = {
        "roe_min": [14, 15],
        "debt_to_equity_max": [0.95, 1.00],
        "gross_margin_min": [0.18, 0.19, 0.20],
        "sales_yoy_min": [8, 9],
        "earnings_yoy_min": [7, 8],
        "margin_yoy_min": [0, 2, 5],
        "eps_yoy_min": [None, 10],
    }

    results: list[dict] = []
    total = 0
    for (
        roe_min,
        debt_to_equity_max,
        gross_margin_min,
        sales_yoy_min,
        earnings_yoy_min,
        margin_yoy_min,
        eps_yoy_min,
    ) in product(
        search_space["roe_min"],
        search_space["debt_to_equity_max"],
        search_space["gross_margin_min"],
        search_space["sales_yoy_min"],
        search_space["earnings_yoy_min"],
        search_space["margin_yoy_min"],
        search_space["eps_yoy_min"],
    ):
        total += 1
        cfg = FaFilterConfig(
            roe_min=roe_min,
            debt_to_equity_max=debt_to_equity_max,
            gross_margin_min=gross_margin_min,
            sales_yoy_min=sales_yoy_min,
            earnings_yoy_min=earnings_yoy_min,
            margin_yoy_min=margin_yoy_min,
            eps_yoy_min=eps_yoy_min,
            require_eps_accel=False,
            require_earnings_accel=False,
        )
        result = evaluate_config(
            fa_df=fa_df,
            price_data=price_data,
            cfg=cfg,
            horizons=args.horizons,
            bench_symbol=args.bench,
        )
        if result is not None:
            results.append(result)
        if total % 25 == 0:
            print(f"Progress: {total} configs tested...", flush=True)

    results.sort(
        key=lambda item: (
            int(item["pass"]),
            item["score"],
            item["median_alpha_by_horizon"].get(26, 0.0),
            item["median_alpha_by_horizon"].get(13, 0.0),
            item["median_alpha_by_horizon"].get(8, 0.0),
        ),
        reverse=True,
    )
    top = results[: args.top_k]

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(top, indent=2), encoding="utf-8")

    print(f"Evaluated {total} configs; saved top {len(top)} to {out_path}")
    for idx, item in enumerate(top[:10], start=1):
        a = item["median_alpha_by_horizon"]
        cfg = item["config"]
        print(
            f"{idx:02d}. pass={item['pass']} score={item['score']:.4f} "
            f"8w={a.get(8, 0.0):.2%} 13w={a.get(13, 0.0):.2%} 26w={a.get(26, 0.0):.2%} "
            f"cfg=roe>={cfg['roe_min']}, d/e<={cfg['debt_to_equity_max']}, "
                f"gm>={cfg['gross_margin_min']}, sales>={cfg['sales_yoy_min']}, "
                f"earn>={cfg['earnings_yoy_min']}, margin_yoy>={cfg['margin_yoy_min']}, "
                f"eps_yoy>={cfg['eps_yoy_min']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
