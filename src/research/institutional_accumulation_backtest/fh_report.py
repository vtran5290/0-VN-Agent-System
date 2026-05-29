"""Phase 7: Full-history HTML report generator.

RESEARCH_ONLY_NOT_PRODUCTION — every section states this.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"

_RESEARCH_BANNER = """
<div class="banner">
  ⚠️ <strong>RESEARCH_ONLY_NOT_PRODUCTION</strong> — No A3/S3/OMS/final_action/DNSE/live trading/sizing/Phase36 production behavior changed.
</div>
"""

_CSS = """
body{font-family:system-ui,sans-serif;max-width:1400px;margin:0 auto;padding:16px;color:#1a1a1a}
h1{color:#1a3a6e;border-bottom:3px solid #1a3a6e;padding-bottom:8px}
h2{color:#1a3a6e;border-left:4px solid #1a3a6e;padding-left:10px;margin-top:32px}
h3{color:#2c5282}
.banner{background:#fffbea;border:2px solid #d69e2e;border-radius:6px;padding:12px 16px;margin:12px 0;font-weight:600}
.blocked{background:#fff5f5;border:1px solid #fc8181;border-radius:4px;padding:8px;color:#c53030}
.supported{background:#f0fff4;border:1px solid #68d391;border-radius:4px;padding:8px;color:#276749}
.inconclusive{background:#ebf8ff;border:1px solid #63b3ed;border-radius:4px;padding:8px;color:#2b6cb0}
.rejected{background:#fff5f5;border:1px solid #fc8181;border-radius:4px;padding:8px;color:#c53030}
table{border-collapse:collapse;width:100%;font-size:0.85rem;margin:12px 0}
th{background:#1a3a6e;color:#fff;padding:6px 10px;text-align:left}
td{padding:5px 10px;border-bottom:1px solid #e2e8f0}
tr:nth-child(even){background:#f7fafc}
.label-PORTFOLIO_PROMISING{color:#276749;font-weight:700}
.label-RISK_REDUCTION_ONLY{color:#744210;font-weight:600}
.label-REJECTED_PORTFOLIO,.label-REJECTED{color:#c53030;font-weight:600}
.label-INCONCLUSIVE{color:#2b6cb0}
.label-BLOCKED_BY_DATA,.label-BLOCKED_BY_DATA_COVERAGE{color:#718096;font-style:italic}
.label-STATISTICALLY_SUPPORTED{color:#276749;font-weight:700}
.label-DIRECTIONALLY_SUPPORTED{color:#285e61;font-weight:600}
.toc{background:#f7fafc;border:1px solid #e2e8f0;border-radius:4px;padding:16px;margin:16px 0}
.toc a{color:#1a3a6e;text-decoration:none}
.toc a:hover{text-decoration:underline}
.toc li{margin:4px 0}
"""


def _df_to_html(df: pd.DataFrame, max_rows: int = 100) -> str:
    if df is None or df.empty:
        return "<p><em>(no data)</em></p>"
    df2 = df.head(max_rows).copy()
    # Apply label classes
    def _td(col: str, val: Any) -> str:
        s = html.escape(str(val) if val is not None else "")
        if col in ("label", "coverage_label", "status"):
            cls = f"label-{val}" if val else ""
            return f'<td class="{cls}">{s}</td>'
        return f"<td>{s}</td>"

    header = "".join(f"<th>{html.escape(c)}</th>" for c in df2.columns)
    rows_html = ""
    for _, row in df2.iterrows():
        cells = "".join(_td(c, v) for c, v in row.items())
        rows_html += f"<tr>{cells}</tr>"
    total = len(df)
    note = f"<p><em>Showing {min(max_rows, total)} of {total} rows.</em></p>" if total > max_rows else ""
    return f"<table><tr>{header}</tr>{rows_html}</table>{note}"


def write_fh_html_report(
    out_path: Path,
    coverage_summary: pd.DataFrame,
    coverage_audit: pd.DataFrame,
    universe_yearly: pd.DataFrame,
    universe_weekly: pd.DataFrame,
    score_decile: pd.DataFrame,
    component_validation: pd.DataFrame,
    distribution_flag: pd.DataFrame,
    top_decile_exhaustion: pd.DataFrame,
    variant_event: pd.DataFrame,
    portfolio_metrics: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    compare_df: pd.DataFrame,
    comparison_answers: dict[str, str],
    run_date: str,
    adv_unit_audit: pd.DataFrame | None = None,
    adv_unit_summary: pd.DataFrame | None = None,
    membership_effectiveness: pd.DataFrame | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def sec(anchor: str, title: str, body: str, banner: bool = True) -> str:
        b = _RESEARCH_BANNER if banner else ""
        return f'<h2 id="{anchor}">{html.escape(title)}</h2>{b}{body}'

    # TOC
    sections = [
        ("executive-summary", "1. Executive Summary"),
        ("data-coverage", "2. Data Coverage Audit"),
        ("universe-design", "3. Universe Design"),
        ("universe-membership", "4. Universe Membership (Ticker-Level)"),
        ("adv-unit-audit", "5. ADV Unit Audit"),
        ("fixed-20b-invalid", "6. Why Fixed 20B Was Invalid Pre-2024"),
        ("score-decile", "7. Score Decile Validation"),
        ("top-decile-exhaustion", "8. Top-Decile Exhaustion"),
        ("distribution-risk", "9. Distribution-Risk Validation"),
        ("variant-event", "10. Variant Event Validation"),
        ("portfolio-simulation", "11. Portfolio Simulation"),
        ("comparison-2024", "12. 2024+ Comparison"),
        ("ex-vin", "13. Ex-VIN Sensitivity"),
        ("what-supported", "14. What Is Supported"),
        ("what-rejected", "15. What Is Rejected"),
        ("research-only", "16. What Remains Research-Only"),
        ("dashboard", "17. Dashboard Implications"),
        ("open-questions", "18. Open Questions"),
    ]
    toc_items = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in sections)
    toc_html = f'<div class="toc"><h3>Table of Contents</h3><ul>{toc_items}</ul></div>'

    # Section bodies
    s_exec = f"""
<p><strong>Run date:</strong> {run_date}</p>
<p>This report documents the full-history Institutional Accumulation backtest rebuild (2012–2026 target; actual coverage constrained by available data).</p>
<ul>
  <li><strong>Data range (stock universe):</strong> 2017-05-18 → 2026-05-27 (ta_ohlcv_panel.parquet primary)</li>
  <li><strong>2012-2016:</strong> BLOCKED_BY_DATA_COVERAGE for stock universe; only VNINDEX available</li>
  <li><strong>Pre-2019 portfolio:</strong> BLOCKED_BY_SPARSE_UNIVERSE (fewer than 200 tickers)</li>
  <li><strong>Universe approach:</strong> Replaced fixed 20B ADV with relative top-N ADV per scan date</li>
  <li><strong>No production changes:</strong> A3, S3, OMS, final_action, DNSE, sizing, Phase36 untouched</li>
</ul>
{_RESEARCH_BANNER}
<h3>Key Findings</h3>
{_df_to_html(coverage_summary, 20)}
"""

    # Coverage
    s_coverage = f"""
<h3>Summary</h3>
{_df_to_html(coverage_summary)}
<h3>Per-Ticker Audit (first 100)</h3>
{_df_to_html(coverage_audit, 100)}
"""

    # Universe
    s_universe = f"""
<p>Multiple universes replace the single fixed 20B ADV50 threshold.
Top-N and percentile universes ensure enough candidates exist in pre-2024 data.</p>
<h3>Universe Coverage by Year</h3>
{_df_to_html(universe_yearly)}
<h3>Universe Design Legend</h3>
<ul>
  <li><strong>U0_ADV50_20B</strong> — Fixed 20B threshold (MODERN_CAPACITY_ONLY, use 2024+ only)</li>
  <li><strong>U1_TOP_N_ADV50</strong> — Top N by ADV50 per scan date (full-history comparable)</li>
  <li><strong>U2_TOP_PCT_ADV50</strong> — Top percentile by ADV50 per scan date</li>
  <li><strong>U3_ADV50_*B</strong> — Absolute threshold sensitivity</li>
</ul>
"""

    # Universe membership section
    _membership_eff_html = _df_to_html(membership_effectiveness) if membership_effectiveness is not None else "<p><em>Run Phase 13 to generate effectiveness audit.</em></p>"
    _portfolio_filter_note = ""
    if not portfolio_metrics.empty and "label" in portfolio_metrics.columns:
        n_promising = int((portfolio_metrics["label"] == "PORTFOLIO_PROMISING").sum())
        _portfolio_filter_note = (
            f"<div class='supported'><strong>v0.2 ticker-level filter applied.</strong> "
            f"0 PORTFOLIO_PROMISING is valid evidence after fix — all universes now test "
            f"distinct (scan_date, ticker) sets.</div>"
            if n_promising == 0 else
            f"<div class='supported'><strong>v0.2 ticker-level filter applied.</strong> "
            f"{n_promising} PORTFOLIO_PROMISING combination(s) found.</div>"
        )

    s_membership = f"""
<div class="supported">
<strong>v0.2 fix: Universe filtering is now ticker-level (scan_date, ticker) pairs.</strong><br>
v0.1 bug: All 5 universes tested identical rows because filtering was date-only
(<code>scan_dates.isin(active_dates)</code>). Fixed by deriving a
<code>universe_membership_wide.parquet</code> from the panel (288k rows), grouping by
<code>scan_date</code>, ranking tickers by <code>adv50_vnd</code>, and applying the same
<code>_assign_universe_membership()</code> logic used in Phase 1. Each universe now
tests a distinct (scan_date, ticker) subset — TOP_100 is a strict subset of TOP_200
which is a strict subset of TOP_300.
</div>
{_portfolio_filter_note}
<h3>Universe Filter Effectiveness by Year</h3>
{_membership_eff_html}
<h3>2012–2016 Data Caveat</h3>
<div class="inconclusive">
The panel parquet (<code>ta_ohlcv_panel.parquet</code>) starts 2017-05-18. Scan dates
before this date have very few tickers (&lt;200) from the supplemental
<code>minervini_backtest/data/raw/</code> CSV sources (~102 tickers). Full-history
conclusions are therefore most reliable for 2019–2026 where panel coverage is &gt;400
tickers. Pre-2019 results are <strong>indicative only</strong>.
</div>
"""

    # ADV unit audit section
    _adv_audit_html = _df_to_html(adv_unit_audit) if adv_unit_audit is not None else "<p><em>Run Phase 12 to generate ADV unit audit.</em></p>"
    _adv_summary_html = _df_to_html(adv_unit_summary) if adv_unit_summary is not None else ""

    s_adv_audit = f"""
<div class="blocked">
<strong>ADV unit inflation detected in 2017-2018 (universe_coverage_by_year.csv).</strong><br>
U0_ADV50_20B avg_adv50 = <strong>8 TRILLION VND in 2017</strong> vs 13B in 2019.
The formula <code>close × volume × 1000</code> assumes close is in kVND. If close was
stored in full VND in 2017-2018 parquet data, the formula over-estimates by ~1000x.
The panel's <code>adv50_vnd</code> column (computed by <code>build_panel_fast /
add_indicators</code>) is the ground truth — the ADV audit below compares the raw formula
against it to characterise the discrepancy.
</div>
<h3>ADV Unit Audit (sample tickers × years)</h3>
{_adv_audit_html}
<h3>Panel ADV50 Summary by Year (ground truth)</h3>
{_adv_summary_html}
<p><small><em>Note: For Phase 4/5 validation and portfolio simulation, the panel's
<code>adv50_vnd</code> column is used for universe membership (not the raw formula),
so this inflation does NOT affect the fixed-universe filtered results.
The inflation affects Phase 1 universe_coverage_by_year.csv counts only.</em></small></p>
"""

    s_fixed20b = f"""
<div class="blocked">
<strong>Fixed 20B ADV50 is not valid for full-history testing.</strong><br>
Vietnam market liquidity evolved dramatically from 2012 to 2024. A ticker needing 20B VND ADV50 would
have zero candidates in most weeks before 2022. This creates artificial sparsity — not a real market signal.
The P3.2 "modern" run correctly restricted to 2024+ for this reason. The full-history test uses
relative (top-N) liquidity thresholds to compare apples-to-apples across time periods.
</div>
<h3>Zero-Candidate Weeks by Universe and Year</h3>
{_df_to_html(universe_yearly[universe_yearly.get("zero_weeks", pd.Series(0)) > 0] if not universe_yearly.empty and "zero_weeks" in universe_yearly.columns else universe_yearly, 50)}
"""

    s_decile = f"""
<h3>Score Decile vs 20-day Forward Excess Returns</h3>
{_df_to_html(score_decile)}
"""

    s_exhaustion = f"""
<h3>Top-Decile Exhaustion (Decile 9)</h3>
{_df_to_html(top_decile_exhaustion)}
"""

    s_dist = f"""
<h3>Distribution-Risk Flag vs Forward Returns</h3>
{_df_to_html(distribution_flag)}
"""

    s_variant = f"""
<h3>Variant Event Validation by Year</h3>
{_df_to_html(variant_event, 100)}
"""

    s_portfolio = f"""
<h3>Portfolio Metrics (all universes)</h3>
{_df_to_html(portfolio_metrics)}
<h3>Yearly Returns</h3>
{_df_to_html(yearly_returns, 100)}
"""

    s_compare = f"""
<h3>Full-History vs P3.2 Modern (2024+) Comparison</h3>
{_df_to_html(compare_df)}
<h3>Key Questions</h3>
<ul>
{"".join(f'<li><strong>{html.escape(k)}:</strong> {html.escape(v)}</li>' for k, v in comparison_answers.items())}
</ul>
"""

    s_exvin = f"""
<p>Ex-VIN universe (excludes VIC, VHM, VRE) removes the Vingroup distortion on VNINDEX 2025-2026.
Results are compared in the variant event table above filtered to <code>year=ex_vin</code>.</p>
<h3>Ex-VIN Results</h3>
{_df_to_html(variant_event[variant_event.get("year", pd.Series()) == "ex_vin"] if not variant_event.empty and "year" in variant_event.columns else pd.DataFrame())}
"""

    # Labels
    pm = portfolio_metrics if not portfolio_metrics.empty else pd.DataFrame()
    promising = pm[pm.get("label", pd.Series()) == "PORTFOLIO_PROMISING"] if not pm.empty and "label" in pm.columns else pd.DataFrame()
    risk_red = pm[pm.get("label", pd.Series()) == "RISK_REDUCTION_ONLY"] if not pm.empty and "label" in pm.columns else pd.DataFrame()
    rejected = pm[pm.get("label", pd.Series()) == "REJECTED_PORTFOLIO"] if not pm.empty and "label" in pm.columns else pd.DataFrame()

    s_supported = f"""
<div class="supported">
<strong>What is supported by this full-history backtest:</strong>
<ul>
{"<li>PORTFOLIO_PROMISING variants: " + str(len(promising)) + " combinations</li>" if not promising.empty else "<li>No PORTFOLIO_PROMISING combinations found in full history</li>"}
{"<li>RISK_REDUCTION_ONLY (drawdown improvement): " + str(len(risk_red)) + " combinations</li>" if not risk_red.empty else ""}
</ul>
</div>
{_df_to_html(promising, 30)}
"""

    s_rejected = f"""
<div class="rejected">
<strong>What is rejected by this full-history backtest:</strong>
<ul>
{"<li>REJECTED_PORTFOLIO: " + str(len(rejected)) + " combinations</li>" if not rejected.empty else "<li>No REJECTED_PORTFOLIO combinations explicitly flagged</li>"}
<li>Fixed 20B ADV50 as the only full-history universe: REJECTED as methodology</li>
<li>Any 2012 backtest claim: BLOCKED_BY_DATA_COVERAGE</li>
</ul>
</div>
{_df_to_html(rejected, 30)}
"""

    s_research_only = """
<div class="inconclusive">
<strong>What remains research-only (do not promote to production):</strong>
<ul>
  <li>All portfolio variants (PORTFOLIO_PROMISING → research candidate only)</li>
  <li>Top-N universe selection methodology</li>
  <li>Full-history score panel using parquet as data source</li>
  <li>Ex-VIN sensitivity results</li>
  <li>Regime-gated variants (V9)</li>
</ul>
No production trading logic changed. No final_action. No OMS. No DNSE. No sizing.
</div>
"""

    s_dashboard = """
<p>Dashboard implications (pending review approval):</p>
<ul>
  <li>If PORTFOLIO_PROMISING confirmed: consider adding full-history universe coverage metric to operator dashboard</li>
  <li>Distribution-risk filter: if DIRECTIONALLY_SUPPORTED, maintain existing distribution_risk_flag display</li>
  <li>Top-decile visualization: if DIRECTIONALLY_SUPPORTED, maintain decile ranking display</li>
  <li>Do NOT change Phase36 production scan behavior based on this research alone</li>
</ul>
"""

    s_questions = """
<h3>Open Questions for ChatGPT Review</h3>
<ol>
  <li>Does the full-history top-200 universe provide sufficient evidence to change the operator dashboard universe filter from fixed 20B?</li>
  <li>Given VIN distortion in 2025-2026, should the ex-VIN universe be the primary benchmark for future backtests?</li>
  <li>Are the pre-2022 years (230-251 tickers) sufficient to draw regime-level conclusions?</li>
  <li>Should the distribution-risk filter be used as a hard exclude or a soft penalty?</li>
  <li>What additional data sources would be needed for a true 2012-2016 stock backtest?</li>
</ol>
"""

    # Assemble all sections
    body = "".join(
        [
            toc_html,
            sec("executive-summary", sections[0][1], s_exec, banner=False),
            sec("data-coverage", sections[1][1], s_coverage),
            sec("universe-design", sections[2][1], s_universe),
            sec("universe-membership", sections[3][1], s_membership, banner=False),
            sec("adv-unit-audit", sections[4][1], s_adv_audit, banner=False),
            sec("fixed-20b-invalid", sections[5][1], s_fixed20b),
            sec("score-decile", sections[6][1], s_decile),
            sec("top-decile-exhaustion", sections[7][1], s_exhaustion),
            sec("distribution-risk", sections[8][1], s_dist),
            sec("variant-event", sections[9][1], s_variant),
            sec("portfolio-simulation", sections[10][1], s_portfolio),
            sec("comparison-2024", sections[11][1], s_compare),
            sec("ex-vin", sections[12][1], s_exvin),
            sec("what-supported", sections[13][1], s_supported, banner=False),
            sec("what-rejected", sections[14][1], s_rejected, banner=False),
            sec("research-only", sections[15][1], s_research_only, banner=False),
            sec("dashboard", sections[16][1], s_dashboard),
            sec("open-questions", sections[17][1], s_questions),
        ]
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Full-History Institutional Accumulation Validation 2012–2026 — {run_date}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Full-History Institutional Accumulation Validation</h1>
<p><em>RESEARCH_ONLY_NOT_PRODUCTION | Run: {run_date}</em></p>
{body}
<hr>
<p><small>Generated: {run_date} | Source: ta_ohlcv_panel.parquet + minervini_backtest/data/raw/ |
No A3/S3/OMS/final_action/DNSE/live trading/sizing changed.</small></p>
</body>
</html>"""

    out_path.write_text(html_doc, encoding="utf-8")
    print(f"[Phase 7] HTML report: {out_path} ({len(html_doc):,} bytes)")
