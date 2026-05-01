from __future__ import annotations

import argparse
import json
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.cohort_backtest import _load_price_data, load_fa_csv
from fa_cohort.fa_filters import FaFilterConfig
from scripts.sweep_berkshire_grid import evaluate_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Ultra-long Berkshire sweep for 104/156/208/260w.")
    parser.add_argument("--fa-csv", required=True)
    parser.add_argument("--bench", default="VNINDEX")
    parser.add_argument("--horizons", nargs="+", type=int, default=[104, 156, 208, 260])
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--out-json",
        default=str(ROOT / "outputs" / "berkshire_comparison" / "ultralong_grid_top.json"),
    )
    args = parser.parse_args()

    fa_df = load_fa_csv(args.fa_csv)
    price_data = _load_price_data()
    weights = {104: 0.8, 156: 1.0, 208: 1.2, 260: 1.4}

    # Search around the current ultra-long leaders: B2_pro / B_low_leverage / B1_base.
    search_space = {
        "roe_min": [14, 15, 16, 17],
        "debt_to_equity_max": [0.70, 0.80, 0.90, 1.00],
        "gross_margin_min": [0.20, 0.22, 0.25, 0.28, 0.30, 0.32],
        "sales_yoy_min": [0, 4, 6, 8, 10],
        "earnings_yoy_min": [0, 3, 5, 7, 9],
    }

    results: list[dict] = []
    total = 0
    for roe_min, debt_to_equity_max, gross_margin_min, sales_yoy_min, earnings_yoy_min in product(
        search_space["roe_min"],
        search_space["debt_to_equity_max"],
        search_space["gross_margin_min"],
        search_space["sales_yoy_min"],
        search_space["earnings_yoy_min"],
    ):
        total += 1
        cfg = FaFilterConfig(
            eps_yoy_min=None,
            sales_yoy_min=sales_yoy_min,
            roe_min=roe_min,
            debt_to_equity_max=debt_to_equity_max,
            margin_yoy_min=0,
            require_eps_accel=False,
            earnings_yoy_min=earnings_yoy_min,
            require_earnings_accel=False,
            gross_margin_min=gross_margin_min,
        )
        result = evaluate_config(
            fa_df=fa_df,
            price_data=price_data,
            cfg=cfg,
            horizons=args.horizons,
            bench_symbol=args.bench,
            weights=weights,
        )
        if result is not None:
            results.append(result)
        if total % 50 == 0:
            print(f"Progress: {total} configs tested...", flush=True)

    results.sort(
        key=lambda item: (
            int(item["pass"]),
            item["score"],
            item["median_alpha_by_horizon"].get(260, 0.0),
            item["median_alpha_by_horizon"].get(208, 0.0),
            item["median_alpha_by_horizon"].get(156, 0.0),
            item["median_alpha_by_horizon"].get(104, 0.0),
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
            f"104w={a.get(104, 0.0):.2%} 156w={a.get(156, 0.0):.2%} "
            f"208w={a.get(208, 0.0):.2%} 260w={a.get(260, 0.0):.2%} "
            f"cfg=roe>={cfg['roe_min']}, d/e<={cfg['debt_to_equity_max']}, "
            f"gm>={cfg['gross_margin_min']}, sales>={cfg['sales_yoy_min']}, "
            f"earn>={cfg['earnings_yoy_min']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
