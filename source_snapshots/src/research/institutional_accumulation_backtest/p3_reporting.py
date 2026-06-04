from __future__ import annotations

from pathlib import Path

import pandas as pd

SAFETY_BANNER = (
    "Research-only. No production trading logic changed. No final_action. No OMS. No DNSE. No sizing."
)


def _tbl(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if df.empty:
        return "<p><i>No data</i></p>"
    if cols:
        use = [c for c in cols if c in df.columns]
        if use:
            return df[use].to_html(index=False)
    return df.to_html(index=False)


def _note() -> str:
    return f'<div class="note">{SAFETY_BANNER} RESEARCH_ONLY_NOT_PRODUCTION</div>'


def write_p3_html_report(
    out: Path,
    *,
    portfolio_metrics: pd.DataFrame,
    diagnostic_summary: pd.DataFrame,
    turnover_capacity: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_returns: pd.DataFrame,
    equity_curves: pd.DataFrame,
    p2_summary: pd.DataFrame | None = None,
) -> None:
    base_eq = equity_curves[equity_curves.get("cost_scenario", "base") == "base"] if "cost_scenario" in equity_curves.columns else equity_curves
    headline = portfolio_metrics[
        (portfolio_metrics["split"] == "full_sample")
        & (portfolio_metrics["top_n"] == 20)
        & (portfolio_metrics["rank_mode"] == "score_desc")
    ].copy()
    if "cagr" in headline.columns:
        leaderboard = headline.sort_values("cagr", ascending=False, na_position="last")
    else:
        leaderboard = headline

    promising = diagnostic_summary[diagnostic_summary["label"] == "PORTFOLIO_PROMISING"]
    rejected = diagnostic_summary[diagnostic_summary["label"] == "REJECTED_PORTFOLIO"]
    risk_only = diagnostic_summary[diagnostic_summary["label"] == "RISK_REDUCTION_ONLY"]

    p2_block = ""
    if p2_summary is not None and not p2_summary.empty:
        p2_block = _tbl(p2_summary, ["variant_id", "label", "evidence"])

    eq_tail = base_eq.sort_values(["portfolio_id", "scan_date"]).groupby("portfolio_id").tail(1) if not base_eq.empty else base_eq

    if turnover_capacity.empty:
        turnover_tbl = "<p><i>No turnover data</i></p>"
    else:
        turnover_tbl = _tbl(
            turnover_capacity.groupby(["portfolio_id", "split"]).agg({"turnover": "mean", "holdings": "mean"}).reset_index()
        )

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>P3 Portfolio Simulation</title>
<style>body{{font-family:Arial,sans-serif;background:#0b0f14;color:#d9e1ea;padding:18px}}
table{{border-collapse:collapse;width:100%;margin:10px 0}}td,th{{border:1px solid #2a3442;padding:6px}}
h2{{margin-top:24px}}.note{{background:#1b2532;padding:10px;border-left:4px solid #6ca4ff;margin:10px 0}}</style>
</head><body>
<h1>P3 Non-Overlapping Portfolio Simulation</h1>
{_note()}
<h2>Executive summary</h2>
{_tbl(diagnostic_summary, ["portfolio_id", "label", "evidence", "recommended_next_step"])}
<h2>P2 research reminder</h2>
{p2_block if p2_block else "<p>P2 diagnostic summary not loaded.</p>"}
{_note()}
<h2>Portfolio leaderboard (full_sample, top_n=20, score_desc, base cost)</h2>
{_tbl(leaderboard, ["portfolio_id", "cagr", "sharpe", "max_drawdown", "excess_vs_vnindex", "excess_vs_ew_universe", "avg_turnover", "avg_holdings"])}
<h2>Equity curve endpoints (base cost)</h2>
{_tbl(eq_tail, ["portfolio_id", "split", "scan_date", "equity", "net_return"])}
<h2>Turnover and capacity</h2>
{turnover_tbl}
<h2>Yearly returns</h2>
{_tbl(yearly_returns)}
<h2>Regime returns</h2>
{_tbl(regime_returns)}
<h2>Promising portfolios</h2>
{_tbl(promising)}
<h2>Rejected portfolios</h2>
{_tbl(rejected)}
<h2>Risk-reduction-only portfolios</h2>
{_tbl(risk_only)}
<h2>Limitations</h2>
<ul>
<li>Weekly non-overlapping rebalance; holding return from T+1 entry to next scan close (not overlapping 20d/60d diagnostics).</li>
<li>Equal-weight top-N; no position sizing or production OMS integration.</li>
<li>Transaction costs are scenario estimates applied to turnover only.</li>
<li>VNINDEX cap-weight filter may be distorted by Vingroup concentration in 2025–2026.</li>
</ul>
<h2>Recommended next step</h2>
<p>If no portfolio is PORTFOLIO_PROMISING, keep production unchanged and treat P2/P3 as research-only filters.</p>
{_note()}
</body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
