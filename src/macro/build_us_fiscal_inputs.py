# src/macro/build_us_fiscal_inputs.py — Orchestrator: FRED + Treasury → single us_fiscal_inputs.json
"""
Single CLI to build data/features/macro/us_fiscal_inputs.json from FRED and Treasury.
No manual merge. Run before scoring.
Usage: python -m src.macro.build_us_fiscal_inputs --asof YYYY-MM-DD [--force]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.macro.fred_fetch_us_fiscal_stress import (
    REPO_ROOT,
    build_derived as fred_build_derived,
    run_fetch as fred_run_fetch,
)
from src.macro.treasury_auctions_fetch import (
    map_to_us_fiscal_stress_auctions,
    run_fetch as treasury_run_fetch,
)

OUT_PATH = REPO_ROOT / "data" / "features" / "macro" / "us_fiscal_inputs.json"
# Pack weights for coverage (must match pack scoring_config.weights)
COMPONENT_WEIGHTS = {
    "term_premium": 0.25,
    "long_end_yields": 0.15,
    "auction_demand": 0.25,
    "funding_stress": 0.20,
    "fiscal_path": 0.15,
}


def _has(v: Any) -> bool:
    return v is not None and v != "" and str(v).lower() != "null"


def coverage_and_quality(merged: dict) -> tuple[float, str]:
    """Compute coverage_weight (0..1) and signal_quality (high|medium|low) from merged inputs."""
    y = merged.get("yields") or {}
    tp = merged.get("term_premium") or {}
    a = merged.get("auctions") or {}
    f = merged.get("funding_stress") or {}
    fp = merged.get("fiscal_path") or {}

    term_ok = _has(tp.get("ust_10y_term_premium_bps"))
    yields_ok = _has(y.get("ust_10y_yield_pct")) or _has(y.get("ust_30y_yield_pct"))
    auction_ok = _has(a.get("ust_10y_bid_to_cover")) or _has(a.get("ust_30y_bid_to_cover"))
    funding_ok = _has(f.get("sofr_value")) or _has(f.get("sofr_spread_bps"))
    fiscal_ok = _has(fp.get("primary_deficit_pct_gdp")) or _has(fp.get("interest_cost_pct_gdp"))

    weight = 0.0
    if term_ok:
        weight += COMPONENT_WEIGHTS["term_premium"]
    if yields_ok:
        weight += COMPONENT_WEIGHTS["long_end_yields"]
    if auction_ok:
        weight += COMPONENT_WEIGHTS["auction_demand"]
    if funding_ok:
        weight += COMPONENT_WEIGHTS["funding_stress"]
    if fiscal_ok:
        weight += COMPONENT_WEIGHTS["fiscal_path"]

    if weight >= 0.7:
        quality = "high"
    elif weight >= 0.4:
        quality = "medium"
    else:
        quality = "low"
    return round(weight, 2), quality


def build(asof: str | None, force: bool) -> dict:
    """Run FRED fetch (or use cache), Treasury fetch, merge into one schema-stable dict."""
    snapshot_fred = fred_run_fetch(asof=asof, force=force)
    fred_derived = fred_build_derived(snapshot_fred)

    treasury_snapshot = treasury_run_fetch()
    auctions = map_to_us_fiscal_stress_auctions(treasury_snapshot)

    merged: dict = {
        "asof_date": fred_derived.get("asof_date"),
        "source": "build_us_fiscal_inputs",
        "yields": fred_derived.get("yields", {}),
        "term_premium": fred_derived.get("term_premium", {}),
        "auctions": auctions,
        "funding_stress": fred_derived.get("funding_stress", {}),
        "fiscal_path": fred_derived.get("fiscal_path", {}),
        "usd": fred_derived.get("usd", {"dxy_trend": "unknown"}),
        "policy": fred_derived.get("policy", {"policy_stance": "neutral", "policy_delta_3m_bps": None}),
    }
    if fred_derived.get("real_rates"):
        merged["real_rates"] = fred_derived["real_rates"]
    if fred_derived.get("flags"):
        merged["flags"] = fred_derived["flags"]
    cov, _ = coverage_and_quality(merged)
    merged["coverage_weight"] = cov
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build us_fiscal_inputs.json from FRED + Treasury (no manual merge)."
    )
    parser.add_argument("--asof", type=str, default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true", help="Bypass FRED cache")
    parser.add_argument("--out", type=str, default=None, help=f"Output path (default: {OUT_PATH})")
    args = parser.parse_args()

    merged = build(asof=args.asof, force=args.force)
    out_path = Path(args.out) if args.out else OUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, sort_keys=True)

    coverage, quality = coverage_and_quality(merged)
    print(f"Wrote {out_path}")
    print(f"coverage_weight={coverage} signal_quality_preview={quality}")
    if merged.get("flags"):
        print(f"flags={merged['flags']}")


if __name__ == "__main__":
    main()
