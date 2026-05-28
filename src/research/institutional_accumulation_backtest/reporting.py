from __future__ import annotations

from pathlib import Path

import pandas as pd
from .evidence_labels import build_evidence_summary


SAFETY_NOTE = (
    "Research-only validation. This backtest does not set final_action, OMS orders, DNSE routing, "
    "position sizing, or live execution. Real capital remains NO-GO unless separately promoted through an explicit future gate."
)


def write_html_report(
    path: Path,
    *,
    metrics: pd.DataFrame,
    yearly: pd.DataFrame,
    regime: pd.DataFrame,
    ablation: pd.DataFrame,
    risk: pd.DataFrame,
    dist_flag: pd.DataFrame,
    vin: pd.DataFrame,
    warning_validation: pd.DataFrame,
    changes_event: pd.DataFrame,
    coverage_summary: dict[str, object],
    context_mode: str,
    run_status: str = "INCONCLUSIVE",
    benchmark_ok: bool = False,
    ex_vin_ok: bool = False,
) -> None:
    top = metrics.sort_values("gross_return", ascending=False).head(12)
    evidence_summary, ab = build_evidence_summary(
        ablation=ablation,
        yearly=yearly,
        coverage_summary=coverage_summary,
        metrics=metrics,
        dist_flag=dist_flag,
        warning_validation=warning_validation,
        changes_event=changes_event,
        context_mode=context_mode,
    )
    strategy_status = {
        "S1B_tier12_equal": evidence_summary.get("tier12", ("INCONCLUSIVE", ""))[0],
        "S3_fund_tagged_tier123": evidence_summary.get("fund_backed", ("INCONCLUSIVE", ""))[0],
        "S3_emerging_only": evidence_summary.get("emerging_list", ("INCONCLUSIVE", ""))[0],
    }
    top = top.copy()
    top["evidence_status"] = top["strategy"].map(strategy_status).fillna("INCONCLUSIVE")
    evidence_list = [
        ("Runtime validation", "RUN_COMPLETE" if run_status == "RUN_COMPLETE" else run_status),
        ("Composite score", "INCONCLUSIVE / possible inversion. Do not use as buy-ranking alpha until P1 diagnosis."),
        ("Tier 1", evidence_summary.get("tier1", ("INCONCLUSIVE", ""))[0]),
        ("Tier 1/2", evidence_summary.get("tier12", ("INCONCLUSIVE", ""))[0]),
        ("Distribution risk flag", evidence_summary.get("distribution_risk_flag", ("INCONCLUSIVE", ""))[0]),
        ("Risk penalty", evidence_summary.get("risk_penalty", ("INCONCLUSIVE", ""))[0]),
        ("Emerging list", evidence_summary.get("emerging_list", ("INCONCLUSIVE", ""))[0]),
        ("Fund-backed", evidence_summary.get("fund_backed", ("INCONCLUSIVE", ""))[0]),
        ("Warning system", evidence_summary.get("warning_system", ("INCONCLUSIVE", ""))[0]),
        ("Changes/upgrades", evidence_summary.get("changes_upgrades", ("INCONCLUSIVE", ""))[0]),
    ]
    evidence_html = "".join([f"<li><b>{k}:</b> {v}</li>" for k, v in evidence_list])
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Institutional Accumulation Backtest Summary</title>
<style>body{{font-family:Arial,sans-serif;background:#0b0f14;color:#d9e1ea;padding:18px}}table{{border-collapse:collapse;width:100%;margin:10px 0}}td,th{{border:1px solid #2a3442;padding:6px}}.note{{background:#19212c;padding:10px;border-left:4px solid #5fa8ff}}h2{{margin-top:24px}}</style>
</head><body>
<h1>Institutional Accumulation Backtest Summary</h1>
<div class="note">{SAFETY_NOTE}</div>
<p><b>Context mode:</b> {context_mode}</p>
<p><b>Run status:</b> {run_status}</p>
<p><b>Benchmark gate:</b> {"OK" if benchmark_ok else "BLOCKED_BY_DATA"} | <b>ex-VIN gate:</b> {"OK" if ex_vin_ok else "INCONCLUSIVE"}</p>
<h2>Executive Summary</h2>
<p>This report validates stock-picking signals from the Institutional Accumulation workflow across full and ex-VIN slices.</p>
<h2>Evidence Summary</h2>
<ul>
{evidence_html}
</ul>
<h2>PASS / FAIL Dashboard (Ablation)</h2>
{ab[['component','spread_q5_q1','evidence_status','note']].to_html(index=False)}
<h2>Tier/Strategy Validation</h2>
{top.to_html(index=False)}
<h2>Score Decile / Yearly</h2>
{yearly.to_html(index=False)}
<h2>Regime Table</h2>
{regime.to_html(index=False)}
<h2>Risk Penalty Validation</h2>
{risk.to_html(index=False)}
<h2>Distribution Flag Validation</h2>
{dist_flag.to_html(index=False)}
<h2>VIN Sensitivity</h2>
{vin.to_html(index=False)}
<h2>Warnings Validation</h2>
{warning_validation.to_html(index=False)}
<h2>Changes Event Study</h2>
{changes_event.to_html(index=False)}
<h2>Methodology / Limitations</h2>
<ul>
<li>No lookahead by construction (features only up to scan_date).</li>
<li>PIT monthly context only if historical monthly files exist.</li>
<li>Synthetic Apr-2026 context is labeled sensitivity-only.</li>
</ul>
<h2>Critical finding — score decile inversion</h2>
<p>The composite institutional accumulation score is not currently validated as a buy-ranking signal.</p>
<p>In the current OHLCV-only backtest, the highest score decile does not show robust forward outperformance. In some calibration views, the highest decile has worse forward outcome probability than mid-range deciles.</p>
<p>This means the score should remain research-only and must not be used as a production buy signal, sizing input, OMS input, or final_action input.</p>
<p>P1 should investigate whether the issue comes from score component scaling, risk penalty interaction, money-flow features rewarding exhaustion rather than accumulation, regime dependence, liquidity/sample effects, or tier threshold design.</p>
<h2>Portfolio simulation caveat</h2>
<p>The current portfolio summary is a research diagnostic, not a fully investable portfolio simulation.</p>
<p>Some portfolio metrics compound overlapping 20-day forward returns from weekly scan dates, and CAGR annualization is not yet calibrated to a non-overlapping portfolio equity curve.</p>
<p>Therefore: use portfolio outputs for directional diagnostics only; do not quote absolute CAGR/gross_return/max_drawdown as investable performance; P1 must rebuild portfolio simulation with non-overlapping holdings, proper rebalance accounting, and correct annualization.</p>
<h2>Effective sample period limitation</h2>
<p>Although the requested backtest start is 2012-01-01 and the first generated scan date is 2017-05-19, usable forward-return coverage is materially stronger from 2022 onward. Some earlier years, especially 2019–2021, contain many NaN forward outcomes due to source-data coverage.</p>
<p>Therefore, current conclusions should be treated as mainly supported by the 2022–2026 sample, not a full 2012–2026 cycle.</p>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
