"""STAGED ONLY — weekly.py integration patch for diversity breadth monitor.

STATUS: DO NOT MERGE — Gate B FAIL (2026-06-28).
Pre-registered gate not met on full sample (r=-0.058, hit=50.6%, rolling stability=0%).

If Gate B is re-run and passes after methodology fixes (PIT VN100, adjusted prices),
apply the snippet below inside src/report/weekly.py after the Regime Engine section.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

# --- PATCH: add import near top of weekly.py ---
# from src.research.diversity_breadth import build_diversity_portfolio_returns
# from pathlib import Path as _Path

INTEGRATION_SNIPPET = '''
    # --- Breadth Indicator (diversity spread) — RESEARCH_ONLY ---
    _breadth_path = REPO / "data" / "research" / "diversity_breadth" / "diversity_portfolio_returns.parquet"
    lines.append("")
    lines.append("## Breadth Indicator (diversity spread)")
    lines.append("- **Label:** RESEARCH_ONLY — Gate B monitor; not production gate.")
    if not _breadth_path.exists():
        lines.append("- **Unknown:** run `python scripts/run_diversity_breadth.py` to build series.")
    else:
        import pandas as _pd
        _b = _pd.read_parquet(_breadth_path)
        _b = _b.sort_values("date")
        _latest = _b.iloc[-1]
        _spread = float(_latest["spread_p050_vs_p100"])
        _med = float(_b["spread_p050_vs_p100"].median())
        _tail = _b["spread_p050_vs_p100"].tail(4)
        _trend = float(_tail.mean() - _b["spread_p050_vs_p100"].tail(8).head(4).mean())
        _signal = "above median (p=0.50 > cap-weight tilt)" if _spread > _med else "below median"
        lines.append(f"- **Current spread (p0.50 − p1.00):** {_spread:.4f}")
        lines.append(f"- **Historical median:** {_med:.4f}")
        lines.append(f"- **4-week trend (avg spread):** {_trend:+.4f}")
        lines.append(f"- **Signal:** {_signal}")
        lines.append("- **Source:** FireAnt OHLCV panel, top-100 ADV proxy universe, monthly rebalance.")
        lines.append("- **Caveat:** VN100 PIT membership approximated; VNINDEX proxy for forward tests.")
'''


def describe_patch() -> str:
    return (
        "Insert INTEGRATION_SNIPPET in weekly report builder after Regime Engine section (~line 780). "
        "Requires data/research/diversity_breadth/diversity_portfolio_returns.parquet from run_diversity_breadth.py."
    )
