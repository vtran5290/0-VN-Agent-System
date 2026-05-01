#!/usr/bin/env python3
"""
Export Berkshire-style FA cohort presets to a single markdown document
for pasting into ChatGPT (or other LLM) to request parameter optimization.

Usage:
  python minervini_backtest/scripts/export_presets_for_optimization.py
  python minervini_backtest/scripts/export_presets_for_optimization.py --out artifacts/presets_for_optimization.md

Output: human-readable spec of all presets (config params + backtest results).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPARISON_JSON = ROOT / "outputs" / "berkshire_comparison" / "berkshire_comparison.json"

# Param definitions for the optimizer (ChatGPT) to understand bounds and meaning
PARAM_SPEC = """
## Parameter definitions (for optimization)

| Parameter | Type | Description | Typical range / notes |
|-----------|------|-------------|------------------------|
| sales_yoy_min | number or null | Minimum YoY sales growth (%) | 0–15; null = no filter |
| roe_min | number | Minimum ROE (%) | 10–20 |
| debt_to_equity_max | number | Maximum D/E ratio | 0.8–1.5 |
| gross_margin_min | number | Minimum gross margin (0–1) | 0.10–0.30 |
| earnings_yoy_min | number or null | Minimum YoY earnings growth (%) | 0–10; null = no filter |
| eps_yoy_min | number or null | Minimum YoY EPS growth (%) | null in current presets |
| margin_yoy_min | number | Minimum YoY margin change | 0 in current presets |
| require_eps_accel | boolean | Require EPS acceleration (q/q or y/y) | false = more cohorts; true = stricter, fewer |
| require_earnings_accel | boolean | Require earnings acceleration | false = more cohorts; true = stricter |
"""

HORIZON_WEEKS = [26, 52, 78, 104, 156, 208, 260]  # 0.5y, 1y, 1.5y, 2y, 3y, 4y, 5y


def main() -> None:
    ap = argparse.ArgumentParser(description="Export presets for ChatGPT optimization")
    ap.add_argument("--out", type=Path, default=None, help="Write markdown to this file; default stdout")
    ap.add_argument("--json-path", type=Path, default=COMPARISON_JSON, help="Path to berkshire_comparison.json")
    args = ap.parse_args()

    path = args.json_path if args.json_path.is_absolute() else ROOT / args.json_path
    if not path.exists():
        print(f"Error: {path} not found.")
        return

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    lines = [
        "# Berkshire-style FA cohort presets — for parameter optimization",
        "",
        "Context: Vietnam stock backtest. Each preset is a set of fundamental filters (sales growth, ROE, D/E, gross margin, earnings growth, acceleration flags). Backtest ranks stocks by these filters, forms cohorts, and measures **median alpha vs benchmark** over multiple holding horizons (weeks).",
        "",
        "**Goal:** Propose new preset(s) or adjust existing parameters to improve median alpha across horizons (especially 104w and 156w) while keeping verdict PASS (no large negative alpha at any horizon).",
        "",
        PARAM_SPEC.strip(),
        "",
        "---",
        "",
        "## Current presets and backtest results",
        "",
    ]

    for i, item in enumerate(data):
        preset = item.get("preset", "?")
        verdict = item.get("verdict", "?")
        config = item.get("config", {})
        alpha = item.get("median_alpha_by_horizon", {})

        lines.append(f"### Preset: `{preset}` (verdict: **{verdict}**)")
        lines.append("")
        lines.append("**Config:**")
        for k, v in sorted(config.items()):
            lines.append(f"- `{k}`: {repr(v)}")
        lines.append("")
        lines.append("**Median alpha by horizon (decimal, e.g. 0.05 = 5%):**")
        for w in HORIZON_WEEKS:
            val = alpha.get(str(w))
            if val is not None:
                pct = f"{val * 100:.2f}%"
                lines.append(f"- {w}w: {val:.4f} ({pct})")
            else:
                lines.append(f"- {w}w: —")
        lines.append("")
        lines.append("")

    body = "\n".join(lines)

    if args.out:
        out_path = args.out if args.out.is_absolute() else Path.cwd() / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        print(f"Written to {out_path}")
    else:
        print(body)


if __name__ == "__main__":
    main()
