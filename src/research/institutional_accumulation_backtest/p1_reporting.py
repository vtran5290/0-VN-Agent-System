from __future__ import annotations

from pathlib import Path

import pandas as pd


def _tbl(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    if df.empty:
        return "<p><i>No data</i></p>"
    if cols:
        use = [c for c in cols if c in df.columns]
        if use:
            return df[use].to_html(index=False)
    return df.to_html(index=False)


def write_p1_html_report(
    out: Path,
    *,
    summary: pd.DataFrame,
    measurement: pd.DataFrame,
    autopsy: pd.DataFrame,
    components: pd.DataFrame,
    lead_lag: pd.DataFrame,
    buckets: pd.DataFrame,
    unit_audit: pd.DataFrame,
    distribution_flag_diagnostic: pd.DataFrame,
    regimes: pd.DataFrame,
    horizons: pd.DataFrame,
    thresholds: pd.DataFrame,
) -> None:
    top_summary = _tbl(summary, ["area", "diagnostic_label", "evidence", "recommended_next_step"])
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>P1 Score Inversion Diagnostic</title>
<style>body{{font-family:Arial,sans-serif;background:#0b0f14;color:#d9e1ea;padding:18px}}table{{border-collapse:collapse;width:100%;margin:10px 0}}td,th{{border:1px solid #2a3442;padding:6px}}h2{{margin-top:24px}}.note{{background:#1b2532;padding:10px;border-left:4px solid #6ca4ff}}</style>
</head><body>
<h1>P1 Institutional Accumulation Score Inversion Diagnostic</h1>
<div class="note">Diagnostic truth mode: no signal optimization, no production trading path changes.</div>
<h2>Executive summary</h2>
{top_summary}
<h2>What P1 tested</h2>
<ul>
<li>Measurement integrity and filtering robustness</li>
<li>Score decile autopsy with feature/risk profile</li>
<li>Component contribution and failure modes</li>
<li>Lead/lag signal behavior (descriptive vs predictive)</li>
<li>Accumulation vs exhaustion bucket behavior</li>
<li>Regime and horizon dependency</li>
<li>Tier threshold diagnostics</li>
</ul>
<h2>Measurement integrity</h2>
{_tbl(measurement)}
<h2>Score decile autopsy</h2>
{_tbl(autopsy)}
<h2>Component diagnostics</h2>
{_tbl(components)}
<h2>Lead/lag findings</h2>
{_tbl(lead_lag)}
<h2>Accumulation vs exhaustion</h2>
{_tbl(buckets)}
<h2>Extension unit audit</h2>
{_tbl(unit_audit)}
<h2>Distribution flag diagnostic</h2>
{_tbl(distribution_flag_diagnostic)}
<h2>Regime dependency</h2>
{_tbl(regimes)}
<h2>Horizon dependency</h2>
{_tbl(horizons)}
<h2>Tier threshold diagnostics</h2>
{_tbl(thresholds)}
<h2>P1 conclusion</h2>
<p>P1 provides diagnostic labels only. Results are for research interpretation and failure-mode mapping, not production optimization.</p>
<h2>Recommended P2 direction</h2>
<p>Use the diagnostic summary labels to choose between measurement fixes, regime/horizon gating, component redesign, and threshold rework. Do not optimize blindly.</p>
<h2>Limitations</h2>
<ul>
<li>OHLCV-only context; PIT fund context remains unavailable.</li>
<li>Historical coverage quality is stronger in recent years (2022 onward).</li>
<li>Portfolio-level investable simulation still requires non-overlapping holdings and rebalance accounting.</li>
</ul>
</body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

