"""
Tier A distribution analyzer — payoff shape for Mark brain.

Reads trades.csv from historical hit-rate (monthly), filters Tier_A trades,
and computes distribution metrics for alpha_126 / alpha_252.
No changes to FA or timing logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Analyze Tier_A alpha distribution (126/252d) from trades.csv"
    )
    ap.add_argument(
        "--trades-csv",
        default="minervini_backtest/outputs/minervini_hit_rate_monthly/trades.csv",
        help="Path to trades.csv produced by run_minervini_historical_hit_rate (monthly)",
    )
    ap.add_argument(
        "--out-dir",
        default="minervini_backtest/outputs/minervini_hit_rate_monthly",
        help="Output directory for dist_report.md and dist_summary.json",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent.parent  # repo root
    trades_path = root / args.trades_csv
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not trades_path.exists():
        print(f"[ERROR] trades.csv not found: {trades_path}")
        return 1

    df = pd.read_csv(trades_path)
    if "tier" not in df.columns:
        print("[ERROR] trades.csv missing 'tier' column")
        return 1

    tier_a = df[df["tier"] == "A"].copy()
    if tier_a.empty:
        print("[WARN] No Tier_A trades found")
        summary = {
            "trade_count": 0,
            "horizons": {},
            "verdict": "no_data",
        }
        (out_dir / "dist_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        (out_dir / "dist_report.md").write_text(
            "# Tier A Distribution\n\nNo Tier_A trades found.\n", encoding="utf-8"
        )
        return 0

    horizons = [126, 252]
    metrics: dict[str, dict[str, float | int | None]] = {}

    def _safe_quantile(series: pd.Series, q: float) -> float | None:
        s = series.dropna()
        if s.empty:
            return None
        return float(s.quantile(q))

    for fd in horizons:
        col = f"alpha_{fd}"
        if col not in tier_a.columns:
            continue
        alphas = tier_a[col].dropna()
        n = len(alphas)
        if n == 0:
            metrics[str(fd)] = {
                "trade_count": 0,
                "median": None,
                "mean": None,
                "p10": None,
                "p25": None,
                "p75": None,
                "p90": None,
                "min": None,
                "max": None,
                "tail_ratio": None,
            }
            continue
        median = float(alphas.median())
        mean = float(alphas.mean())
        p10 = _safe_quantile(alphas, 0.10)
        p25 = _safe_quantile(alphas, 0.25)
        p75 = _safe_quantile(alphas, 0.75)
        p90 = _safe_quantile(alphas, 0.90)
        min_v = float(alphas.min())
        max_v = float(alphas.max())
        if p10 is not None and p10 < 0:
            tail_ratio = float(p90 / abs(p10)) if p90 is not None else None
        else:
            tail_ratio = None

        metrics[str(fd)] = {
            "trade_count": int(n),
            "median": median,
            "mean": mean,
            "p10": p10,
            "p25": p25,
            "p75": p75,
            "p90": p90,
            "min": min_v,
            "max": max_v,
            "tail_ratio": tail_ratio,
        }

    # Verdict per user rule: convex if
    # mean > median AND (p90 - p50) > (p50 - p10) AND max > 3 * p75
    verdict = {}
    for fd in horizons:
        m = metrics.get(str(fd))
        if not m or m["trade_count"] == 0:
            verdict[str(fd)] = "no_data"
            continue
        median = m["median"]
        mean = m["mean"]
        p10 = m["p10"]
        p90 = m["p90"]
        p75 = m["p75"]
        max_v = m["max"]
        if (
            median is not None
            and mean is not None
            and p10 is not None
            and p90 is not None
            and p75 is not None
            and max_v is not None
        ):
            cond_mean = mean > median
            cond_asym = (p90 - median) > (median - p10)
            cond_tail = max_v > 3.0 * p75
            verdict[str(fd)] = "convex" if (cond_mean and cond_asym and cond_tail) else "linear_or_moderate"
        else:
            verdict[str(fd)] = "unknown"

    summary = {
        "trade_count": int(sum(m["trade_count"] for m in metrics.values() if m)),
        "horizons": metrics,
        "verdict": verdict,
    }
    (out_dir / "dist_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Markdown report
    lines: list[str] = [
        "# Tier A Distribution — Mark brain",
        "",
        "Based on trades.csv from monthly historical hit-rate (Tier_A only).",
        "",
    ]
    for fd in horizons:
        m = metrics.get(str(fd))
        lines.append(f"## Horizon {fd} trading days")
        if not m or m["trade_count"] == 0:
            lines.append("No data.")
            lines.append("")
            continue
        lines.extend(
            [
                f"- trade_count: {m['trade_count']}",
                f"- median_alpha: {m['median']}",
                f"- mean_alpha: {m['mean']}",
                f"- p10: {m['p10']}",
                f"- p25: {m['p25']}",
                f"- p75: {m['p75']}",
                f"- p90: {m['p90']}",
                f"- min: {m['min']}",
                f"- max: {m['max']}",
                f"- tail_ratio (p90/|p10|): {m['tail_ratio']}",
                f"- verdict: {verdict.get(str(fd))}",
                "",
            ]
        )

    (out_dir / "dist_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"[TierA Distribution] Wrote {out_dir / 'dist_summary.json'} and {out_dir / 'dist_report.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

