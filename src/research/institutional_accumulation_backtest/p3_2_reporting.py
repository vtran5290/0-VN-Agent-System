"""HTML report for P3.2 Modern-Liquidity Portfolio.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SAFETY_BANNER = (
    "RESEARCH_ONLY_NOT_PRODUCTION — No A3 / S3 / OMS / final_action / DNSE / "
    "live orders / sizing / Phase36 production behavior changed."
)

_STYLE = """
body{font-family:system-ui,sans-serif;background:#0b0f14;color:#d4dce6;
     max-width:1500px;margin:0 auto;padding:1.5rem}
h1{color:#7ab3ff} h2{color:#9ec4ff;border-bottom:1px solid #2a3442;padding-bottom:4px;margin-top:2rem}
h3{color:#b8d0ff}
.banner{background:#1e1a0a;border:2px solid #ffc107;padding:.9rem 1.2rem;
        border-radius:6px;margin-bottom:1.5rem;font-weight:bold;color:#ffc107}
.pill{display:inline-block;padding:3px 10px;border-radius:4px;font-size:.8rem;
      font-weight:bold;margin:2px}
.PORTFOLIO_PROMISING{background:#0d4a26;color:#3ddc84}
.RISK_REDUCTION_ONLY{background:#2a2500;color:#ffd54f}
.REJECTED_PORTFOLIO{background:#4a0d0d;color:#ff6b6b}
.INCONCLUSIVE{background:#1e2535;color:#aab8cc}
.BLOCKED_BY_DATA{background:#2a1f00;color:#ffa726}
table{border-collapse:collapse;width:100%;font-size:.78rem;margin-bottom:1.5rem}
th{background:#1a2b44;color:#8ab4d9;padding:5px 7px;text-align:left;white-space:nowrap}
td{padding:4px 7px;border-bottom:1px solid #1c2535}
tr:hover{background:#131b28}
.pos{color:#3ddc84} .neg{color:#ff6b6b} .neu{color:#aab8cc}
nav{position:sticky;top:0;background:#0b0f14;border-bottom:1px solid #1c2535;
    padding:.4rem 0;z-index:10;margin-bottom:1rem}
nav a{color:#7ab3ff;text-decoration:none;margin-right:1.2rem;font-size:.82rem}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.5rem}
.card{background:#111922;border:1px solid #2a3442;border-radius:6px;padding:1rem}
.card .val{font-size:1.4rem;font-weight:bold}
.card .lbl{font-size:.75rem;color:#6a7d94;margin-top:2px}
"""


def _v(x: Any, pct: bool = False, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if isinstance(x, float):
        s = f"{x * 100:.{decimals}f}%" if pct else f"{x:.{decimals}f}"
        cls = "pos" if x > 0 else ("neg" if x < 0 else "neu")
        return f'<span class="{cls}">{s}</span>'
    return str(x)


def _pill(label: str) -> str:
    return f'<span class="pill {label}">{label}</span>'


def _tbl(df: pd.DataFrame, cols: list[str] | None = None, pct_cols: set[str] | None = None, max_rows: int = 500) -> str:
    if df.empty:
        return "<p><em>No data</em></p>"
    pct_cols = pct_cols or set()
    use = [c for c in (cols or df.columns) if c in df.columns]
    sub = df[use].head(max_rows)
    header = "".join(f"<th>{c}</th>" for c in use)
    body_rows: list[str] = []
    for _, r in sub.iterrows():
        cells: list[str] = []
        for c in use:
            val = r[c]
            if c == "label":
                cells.append(f"<td>{_pill(str(val))}</td>")
            elif isinstance(val, float):
                cells.append(f"<td>{_v(val, pct=c in pct_cols)}</td>")
            else:
                cells.append(f"<td>{val}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _headline_card(label: str, val: str, sublabel: str = "") -> str:
    return (
        f'<div class="card"><div class="val">{val}</div>'
        f'<div class="lbl">{label}</div>'
        + (f'<div class="lbl" style="margin-top:4px">{sublabel}</div>' if sublabel else "")
        + "</div>"
    )


def write_p3_2_html(
    out: Path,
    *,
    portfolio_metrics: pd.DataFrame,
    diagnostic_summary: pd.DataFrame,
    equity_curves: pd.DataFrame,
    turnover_capacity: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    sensitivity: pd.DataFrame,
    run_date: str,
) -> None:

    pct = {"cagr", "cumulative_net_return", "cumulative_vnindex_return", "excess_vs_vnindex",
           "excess_vs_ew_universe", "max_drawdown", "hit_rate", "annualized_vol", "avg_weekly_return",
           "ret_20d_mean", "ret_60d_mean", "ret_20d_hit_rate", "ret_60d_hit_rate", "excess_20d_mean",
           "year_return"}

    # Primary headline: modern_20b, top_n=20, score_desc, base cost
    headline = portfolio_metrics[
        (portfolio_metrics["split"] == "modern_20b")
        & (portfolio_metrics["top_n"] == 20)
        & (portfolio_metrics["rank_mode"] == "score_desc")
    ].copy()

    diag_20b = diagnostic_summary[diagnostic_summary["liq_threshold_label"] == "20b"].copy()
    n_promising = int((diag_20b["label"] == "PORTFOLIO_PROMISING").sum())
    n_rejected = int((diag_20b["label"] == "REJECTED_PORTFOLIO").sum())
    n_blocked = int((diag_20b["label"] == "BLOCKED_BY_DATA").sum())

    # Best CAGR row
    best_row = headline.sort_values("cagr", ascending=False, na_position="last").iloc[0] if not headline.empty else None
    best_card = _headline_card(
        "Best CAGR (modern_20b, top20)",
        _v(float(best_row["cagr"]) if best_row is not None else None, pct=True),
        str(best_row["portfolio_id"]) if best_row is not None else "—",
    )
    promising_card = _headline_card("Promising (20B, top20)", str(n_promising), "at score_desc / modern_20b")
    blocked_card = _headline_card("Blocked", str(n_blocked), "avg_holdings < 10 or insufficient weeks")

    # Yearly returns table (primary split)
    yr_primary = (
        yearly_returns[
            (yearly_returns["split"] == "modern_20b")
            & (yearly_returns["top_n"] == 20)
            & (yearly_returns["rank_mode"] == "score_desc")
        ]
        if not yearly_returns.empty and "split" in yearly_returns.columns
        else pd.DataFrame()
    )

    # Sensitivity highlight columns (guard against empty)
    _all_sens_cols = ["portfolio_id", "liq_label", "n_scans", "avg_holdings_at_top_n",
                      "ret_20d_mean", "ret_20d_hit_rate", "excess_20d_mean",
                      "ret_60d_mean", "ret_60d_hit_rate"]
    sens_cols = [c for c in _all_sens_cols if sensitivity.empty or c in sensitivity.columns]

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>P3.2 Modern-Liquidity Portfolio — Institutional Accumulation Backtest</title>
<style>{_STYLE}</style></head><body>
<div class="banner">⚠ {SAFETY_BANNER}</div>
<h1>P3.2 Modern-Liquidity Portfolio Simulation</h1>
<p><strong>Run date:</strong> {run_date} &nbsp;|&nbsp;
<strong>Primary window:</strong> 2024-01-01 onward &nbsp;|&nbsp;
<strong>Primary liquidity:</strong> ADV50 ≥ 20B VND</p>

<nav>
  <a href="#summary">Summary</a>
  <a href="#leaderboard">Leaderboard</a>
  <a href="#sensitivity">Sensitivity</a>
  <a href="#yearly">Yearly</a>
  <a href="#turnover">Turnover</a>
  <a href="#exvin">Ex-VIN</a>
  <a href="#limits">Limitations</a>
</nav>

<div class="grid3">{best_card}{promising_card}{blocked_card}</div>

<h2 id="summary">Diagnostic Summary (primary: modern_20b)</h2>
{_tbl(diag_20b, ["portfolio_id", "label", "evidence", "recommended_next_step"])}

<h2 id="leaderboard">Portfolio Leaderboard (modern_20b, top_n=20, score_desc)</h2>
{_tbl(headline.sort_values("cagr", ascending=False, na_position="last"),
      ["portfolio_id", "n_weeks", "avg_holdings", "weeks_lt10_holdings",
       "cagr", "annualized_vol", "sharpe", "sortino",
       "max_drawdown", "hit_rate", "avg_weekly_return",
       "cumulative_net_return", "cumulative_vnindex_return", "excess_vs_vnindex",
       "excess_vs_ew_universe", "avg_turnover", "avg_adv_participation"],
      pct_cols=pct)}

<h2>All threshold × variant summary (top_n=20, score_desc)</h2>
{_tbl(
    portfolio_metrics[
        (portfolio_metrics["top_n"] == 20) & (portfolio_metrics["rank_mode"] == "score_desc")
        & (portfolio_metrics["split"].str.startswith("modern_") & ~portfolio_metrics["split"].str.endswith("_ex_vin"))
    ].sort_values(["liq_threshold_label", "portfolio_id"]),
    ["portfolio_id", "split", "liq_threshold_label", "n_weeks", "avg_holdings",
     "cagr", "sharpe", "max_drawdown", "excess_vs_vnindex", "excess_vs_ew_universe", "avg_turnover"],
    pct_cols=pct
)}

<h2>Full metrics table (all top_n, all rank_modes, modern splits)</h2>
{_tbl(
    portfolio_metrics[portfolio_metrics["split"].str.startswith("modern_")].sort_values(
        ["split", "portfolio_id", "top_n", "rank_mode"]
    ),
    ["portfolio_id", "split", "liq_threshold_label", "top_n", "rank_mode", "n_weeks",
     "avg_holdings", "weeks_lt10_holdings",
     "cagr", "sharpe", "max_drawdown", "hit_rate",
     "excess_vs_vnindex", "excess_vs_ew_universe", "avg_turnover"],
    pct_cols=pct,
    max_rows=300
)}

<h2 id="sensitivity">Liquidity Threshold Sensitivity (pre-computed ret_20d / ret_60d)</h2>
{_tbl(sensitivity, cols=sens_cols if sens_cols else None, pct_cols=pct)}

<h2 id="yearly">Yearly Returns (modern_20b, top_n=20, score_desc)</h2>
{_tbl(yr_primary, pct_cols=pct)}

<h2 id="turnover">Turnover and Capacity (modern splits)</h2>
{_tbl(
    turnover_capacity[turnover_capacity["split"].str.startswith("modern_")].groupby(
        ["portfolio_id", "split", "top_n", "rank_mode"]
    ).agg(avg_turnover=("turnover", "mean"), avg_holdings=("holdings", "mean")).reset_index()
    if not turnover_capacity.empty else pd.DataFrame(),
    pct_cols=set()
)}

<h2 id="exvin">Ex-VIN Comparison (modern_20b_ex_vin, top_n=20, score_desc)</h2>
{_tbl(
    portfolio_metrics[
        (portfolio_metrics["split"] == "modern_20b_ex_vin")
        & (portfolio_metrics["top_n"] == 20)
        & (portfolio_metrics["rank_mode"] == "score_desc")
    ].sort_values("cagr", ascending=False, na_position="last"),
    ["portfolio_id", "n_weeks", "avg_holdings", "cagr", "sharpe", "max_drawdown",
     "excess_vs_vnindex", "excess_vs_ew_universe"],
    pct_cols=pct
)}

<h2 id="limits">Limitations</h2>
<ul>
<li>Primary window: 2024-01-01 to 2026-05-27 — approximately 2.4 years, 124 weekly scans. Insufficient for robust statistical conclusions.</li>
<li>VNINDEX cumulative return in this window is ~+74% (strong bull). All excess-return comparisons must be interpreted in this context.</li>
<li>Weekly non-overlapping rebalance; exit at next scan-date close. Equal-weight top-N. No position sizing.</li>
<li>Transaction costs are scenario estimates applied to turnover only.</li>
<li>Liquidity threshold (20B VND ADV50) may systematically select large-cap names with specific sector exposures.</li>
<li>VNINDEX cap-weight distortion from Vingroup concentration in 2025–2026 may inflate the benchmark.</li>
<li>No walk-forward validation, no bootstrap significance tests.</li>
</ul>

<footer style="margin-top:3rem;border-top:1px solid #1c2535;padding-top:1rem;color:#4a5a6a;font-size:.75rem">
  {SAFETY_BANNER} | Generated {run_date}
</footer>
</body></html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
