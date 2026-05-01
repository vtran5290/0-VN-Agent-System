# minervini_backtest/scripts/run_berkshire_cohort.py — Berkshire-style FA cohort backtest (VN)
"""
Run FA cohort backtest with Berkshire Brain assumptions (quality, moat, margin of safety).
Multiple config presets are run; results are compared for optimization.

Usage (from repo root):
  cd minervini_backtest && python scripts/run_berkshire_cohort.py --fa-csv ../data/fa_minervini.csv

Or with custom FA path:
  cd minervini_backtest && python scripts/run_berkshire_cohort.py --fa-csv ../data/fa_minervini.csv --horizons 8 13 26
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
from dataclasses import asdict

ROOT = Path(__file__).resolve().parent.parent  # minervini_backtest
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fa_cohort.fa_filters import FaFilterConfig
from fa_cohort.cohort_backtest import run_cohort_backtest


# Berkshire presets (VN-adapted). Tweak these to optimize backtest results.
BERKSHIRE_PRESETS = {
    "B1_strict": FaFilterConfig(
        roe_min=18,
        debt_to_equity_max=0.8,
        gross_margin_min=0.25,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    "B1_base": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=1.0,
        gross_margin_min=0.20,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    "B1_relaxed": FaFilterConfig(
        roe_min=12,
        debt_to_equity_max=1.2,
        gross_margin_min=0.15,
        sales_yoy_min=5,
        earnings_yoy_min=None,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    "B2_pro": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=0.8,
        gross_margin_min=0.30,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    "B_cigar": FaFilterConfig(
        roe_min=10,
        debt_to_equity_max=1.5,
        gross_margin_min=0.10,
        sales_yoy_min=0,
        earnings_yoy_min=None,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Tuned for VN: balance quality vs cohort size so 13w/26w alpha stays strong
    "B1_tuned": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    "B1_long_only": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=0.9,
        gross_margin_min=0.22,
        sales_yoy_min=10,
        earnings_yoy_min=3,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # --- Berkshire duo tweaks: quality first, margin of safety, avoid value traps ---
    # Stricter quality (fewer names, higher bar) — "wonderful company"
    "B_quality_first": FaFilterConfig(
        roe_min=16,
        debt_to_equity_max=0.9,
        gross_margin_min=0.20,
        sales_yoy_min=10,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Margin of safety: require earnings growth (avoid value traps)
    "B_margin_safety": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Less leverage only — "debt discipline"
    "B_low_leverage": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=0.85,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=0,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Moat emphasis: higher gross margin, keep ROE 15
    "B_moat_plus": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=0.95,
        gross_margin_min=0.22,
        sales_yoy_min=8,
        earnings_yoy_min=3,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Slightly softer than B1_long_only on GM to get 8w positive
    "B_long_softer_gm": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=0.9,
        gross_margin_min=0.20,
        sales_yoy_min=10,
        earnings_yoy_min=3,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Sweet spot search: between B1_tuned and B1_base
    "B_sweet_spot": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=0.95,
        gross_margin_min=0.19,
        sales_yoy_min=8,
        earnings_yoy_min=3,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Refined: margin of safety + slightly stronger moat (GM 20%)
    "B_margin_moat": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.20,
        sales_yoy_min=8,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Refined: margin_safety with lower D/E (debt discipline)
    "B_margin_low_debt": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=0.9,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=5,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Push earnings growth to 7% (stronger margin of safety)
    "B_margin_strict": FaFilterConfig(
        roe_min=15,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=10,
        earnings_yoy_min=7,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Grid-search winner: best weighted Berkshire score on 8/13/26w.
    "B_margin_elite": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=7,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=False,
        require_earnings_accel=False,
    ),
    # Execution quality: same Berkshire durability, but require EPS acceleration as a proxy
    # for moat widening / management execution in a VN quarterly dataset.
    "B_exec_elite": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=7,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=True,
        require_earnings_accel=False,
    ),
    # Strongest long-horizon compounder profile, but weaker at 26w than B_exec_elite.
    "B_exec_compounder": FaFilterConfig(
        roe_min=14,
        debt_to_equity_max=1.0,
        gross_margin_min=0.18,
        sales_yoy_min=8,
        earnings_yoy_min=7,
        margin_yoy_min=0,
        eps_yoy_min=None,
        require_eps_accel=True,
        require_earnings_accel=True,
    ),
}


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Berkshire-style FA cohort backtest (VN)")
    p.add_argument("--fa-csv", required=True, help="Path to FA CSV (e.g. ../data/fa_minervini.csv)")
    p.add_argument("--horizons", nargs="+", type=int, default=[8, 13, 26], help="Hold horizons in weeks")
    p.add_argument("--bench", default="VNINDEX", help="Benchmark symbol")
    p.add_argument("--start", default=None, help="Min report_date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="Max report_date YYYY-MM-DD")
    p.add_argument("--presets", nargs="+", default=list(BERKSHIRE_PRESETS.keys()), help="Preset names to run")
    p.add_argument("--out-base", default=None, help="Base dir for outputs (default: outputs/berkshire_<preset>)")
    args = p.parse_args()

    fa_csv = Path(args.fa_csv)
    if not fa_csv.exists():
        print(f"[ERROR] FA CSV not found: {fa_csv}")
        return 1

    results = []
    for name in args.presets:
        if name not in BERKSHIRE_PRESETS:
            print(f"[WARN] Unknown preset {name}, skip")
            continue
        cfg = BERKSHIRE_PRESETS[name]
        out_dir = Path(args.out_base or str(ROOT / "outputs" / f"berkshire_{name}"))
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[RUN] {name} -> {out_dir}")
        run_cohort_backtest(
            fa_csv=fa_csv,
            horizons=args.horizons,
            bench_symbol=args.bench,
            start=args.start,
            end=args.end,
            cfg=cfg,
            out_dir=out_dir,
        )
        # Read summary to get verdict and key metrics
        summary_md = out_dir / "summary.md"
        yearly_alpha_path = out_dir / "yearly_alpha.csv"
        if summary_md.exists():
            text = summary_md.read_text(encoding="utf-8")
            verdict = "PASS" if "**PASS**" in text else "FAIL"
        else:
            verdict = "?"
        median_alpha_by_h = {}
        if yearly_alpha_path.exists():
            import pandas as pd
            ya = pd.read_csv(yearly_alpha_path)
            for h in args.horizons:
                sub = ya[ya["horizon_weeks"] == h]
                if not sub.empty:
                    median_alpha_by_h[h] = float(sub["alpha"].median())
        results.append({
            "preset": name,
            "verdict": verdict,
            "config": asdict(cfg),
            "median_alpha_by_horizon": median_alpha_by_h,
        })

    # Write comparison
    out_base = ROOT / "outputs" / "berkshire_comparison"
    out_base.mkdir(parents=True, exist_ok=True)
    comparison_path = out_base / "berkshire_comparison.json"
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Comparison written to {comparison_path}")

    # Print table
    print("\n--- Berkshire cohort comparison ---")
    for r in results:
        alphas = r.get("median_alpha_by_horizon", {})
        alpha_str = " | ".join(f"{h}w: {alphas.get(h, 0):.2%}" for h in args.horizons)
        print(f"  {r['preset']:12} {r['verdict']:4}  {alpha_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
