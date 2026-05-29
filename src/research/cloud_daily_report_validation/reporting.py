"""HTML report generation for cloud daily report validation.

All reports include a RESEARCH_ONLY_NOT_PRODUCTION banner.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from .schema import (
    ARCHIVE_DIR,
    RESEARCH_ONLY_LABEL,
    EvidenceLabel,
    EvidenceStatus,
    DashboardRecommendation,
)

logger = logging.getLogger(__name__)

_BANNER_STYLE = (
    "background:#b00020;color:#fff;padding:16px 20px;font-size:18px;"
    "font-weight:bold;text-align:center;border-radius:6px;margin-bottom:20px;"
    "font-family:monospace;letter-spacing:0.5px;"
)

_BASE_CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;}
h1{color:#1a1a2e;border-bottom:3px solid #b00020;padding-bottom:8px;}
h2{color:#16213e;margin-top:30px;}
h3{color:#0f3460;}
table{border-collapse:collapse;width:100%;margin-bottom:24px;background:#fff;
  box-shadow:0 1px 4px rgba(0,0,0,.1);}
th{background:#16213e;color:#fff;padding:10px 12px;text-align:left;font-size:13px;}
td{padding:8px 12px;border-bottom:1px solid #e0e0e0;font-size:12px;}
tr:hover{background:#f0f4ff;}
.badge-blocked{background:#b00020;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.badge-display{background:#6c757d;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.badge-partial{background:#fd7e14;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.badge-not-tested{background:#dc3545;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.badge-context{background:#6f42c1;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.badge-workflow{background:#17a2b8;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;}
.section-box{background:#fff;border-radius:8px;padding:16px;margin-bottom:20px;
  box-shadow:0 1px 4px rgba(0,0,0,.1);}
.stat-row{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px;}
.stat-card{background:#fff;border-radius:8px;padding:16px 24px;min-width:160px;
  box-shadow:0 1px 4px rgba(0,0,0,.1);text-align:center;}
.stat-card .number{font-size:32px;font-weight:bold;color:#1a1a2e;}
.stat-card .label{font-size:12px;color:#666;margin-top:4px;}
"""


def _badge(status: str) -> str:
    s = str(status).upper()
    if "BLOCKED" in s:
        return f'<span class="badge-blocked">{status}</span>'
    elif "DISPLAY" in s:
        return f'<span class="badge-display">{status}</span>'
    elif "PARTIAL" in s:
        return f'<span class="badge-partial">{status}</span>'
    elif "NOT_BACKTESTED" in s or "NOT BACKTESTED" in s:
        return f'<span class="badge-not-tested">{status}</span>'
    elif "CONTEXT" in s:
        return f'<span class="badge-context">{status}</span>'
    elif "WORKFLOW" in s:
        return f'<span class="badge-workflow">{status}</span>'
    return f'<span>{status}</span>'


def _df_to_html_table(df: pd.DataFrame, highlight_cols: list[str] | None = None) -> str:
    if df.empty:
        return "<p><em>No data.</em></p>"
    cols = list(df.columns)
    rows_html = []
    for _, row in df.iterrows():
        cells = []
        for col in cols:
            val = str(row[col]) if row[col] is not None else ""
            if highlight_cols and col in highlight_cols:
                val = _badge(val)
            cells.append(f"<td>{val}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")
    header = "".join(f"<th>{c}</th>" for c in cols)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"


def generate_evidence_inventory_html(
    registry_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
) -> str:
    """Generate HTML evidence inventory report.

    Starts with RESEARCH_ONLY banner.
    Shows what has evidence, what is display-only, what needs new backtest, what is blocked.
    """
    today = str(date.today())
    n_total = len(registry_df)
    n_needs_backtest = int(registry_df["needs_new_backtest"].sum()) if "needs_new_backtest" in registry_df.columns else 0
    n_display_only = int((registry_df["evidence_status"] == EvidenceStatus.DISPLAY_ONLY.value).sum()) if "evidence_status" in registry_df.columns else 0
    n_blocked = int((registry_df["evidence_status"] == EvidenceStatus.BLOCKED_BY_DATA.value).sum()) if "evidence_status" in registry_df.columns else 0
    n_partial = int((registry_df["evidence_status"] == EvidenceStatus.PARTIALLY_VALIDATED.value).sum()) if "evidence_status" in registry_df.columns else 0

    # Summarize by section
    section_summary = ""
    if not registry_df.empty and "dashboard_section" in registry_df.columns:
        for section, grp in registry_df.groupby("dashboard_section"):
            status_counts = grp["evidence_status"].value_counts().to_dict() if "evidence_status" in grp.columns else {}
            status_str = "; ".join(f"{k}: {v}" for k, v in status_counts.items())
            display_cols = ["dashboard_output", "evidence_status", "evidence_label", "needs_new_backtest", "notes"]
            display_cols = [c for c in display_cols if c in grp.columns]
            section_summary += f"""
<div class="section-box">
<h3>Section: {section}</h3>
<p><small>{status_str}</small></p>
{_df_to_html_table(grp[display_cols], highlight_cols=["evidence_status", "evidence_label"])}
</div>"""

    # Output inventory summary
    output_inv_html = ""
    if not inventory_df.empty:
        output_inv_html = f"""
<h2>Output Inventory (Sections A–J)</h2>
<div class="section-box">
{_df_to_html_table(inventory_df, highlight_cols=["output_type"])}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloud Daily Report — Evidence Inventory</title>
<style>{_BASE_CSS}</style>
</head>
<body>
<div style="{_BANNER_STYLE}">{RESEARCH_ONLY_LABEL}</div>
<h1>Cloud Daily Report — Evidence Inventory</h1>
<p><strong>Generated:</strong> {today} &nbsp;|&nbsp; <strong>Label:</strong> {RESEARCH_ONLY_LABEL}</p>
<p>This inventory documents the validation status of every output in the Cloud Daily Report dashboard.
It does NOT modify any live trading signal, final_action logic, or OMS behavior.</p>

<div class="stat-row">
  <div class="stat-card"><div class="number">{n_total}</div><div class="label">Total Outputs</div></div>
  <div class="stat-card"><div class="number" style="color:#b00020">{n_needs_backtest}</div><div class="label">Need New Backtest</div></div>
  <div class="stat-card"><div class="number" style="color:#6c757d">{n_display_only}</div><div class="label">Display-Only</div></div>
  <div class="stat-card"><div class="number" style="color:#b00020">{n_blocked}</div><div class="label">Blocked by Data</div></div>
  <div class="stat-card"><div class="number" style="color:#fd7e14">{n_partial}</div><div class="label">Partially Validated</div></div>
</div>

<h2>Evidence Registry by Section</h2>
{section_summary}

{output_inv_html}

<hr>
<p style="font-size:11px;color:#999;">
{RESEARCH_ONLY_LABEL} — outputs from this framework must not be used to
modify live trading signals, final_action logic, or OMS behavior.
</p>
</body>
</html>"""
    return html


def generate_archive_status_html() -> str:
    """Generate an archive-readiness status block for embedding in the validation HTML."""
    manifest_path = ARCHIVE_DIR / "archive_manifest.csv"
    if not manifest_path.exists():
        return (
            '<div class="section-box" style="border-left:4px solid #fd7e14;">'
            '<h3>v0.3 Archive Status</h3>'
            '<p><strong>No archive manifest found.</strong> '
            'Run <code>scripts/research/cloud_daily_report_validation/archive_daily_inputs.py</code> '
            'to start archiving daily inputs.</p>'
            '<p>Archive path: <code>data/research/cloud_daily_report_validation/archive/</code></p>'
            '</div>'
        )
    try:
        df = __import__("pandas").read_csv(manifest_path, dtype=str)
        n_dates = df["archive_date"].nunique() if "archive_date" in df.columns else 0
        n_total = len(df)
        n_archived = int((df.get("notes", __import__("pandas").Series()) == "archived").sum())
        n_missing = int((df.get("exists", __import__("pandas").Series()) == "False").sum())
        latest_date = df["archive_date"].max() if "archive_date" in df.columns else "unknown"
        rows_html = ""
        for _, row in df.tail(14).iterrows():
            status_color = "#28a745" if row.get("exists") == "True" else "#b00020"
            rows_html += (
                f"<tr>"
                f"<td>{row.get('archive_date','')}</td>"
                f"<td>{row.get('file_type','')}</td>"
                f"<td style='color:{status_color}'>{row.get('notes','')}</td>"
                f"<td>{row.get('file_size_bytes','')}</td>"
                f"</tr>"
            )
        return (
            '<div class="section-box" style="border-left:4px solid #28a745;">'
            '<h3>v0.3 Archive Status</h3>'
            f'<p>Dates archived: <strong>{n_dates}</strong> &nbsp;|&nbsp; '
            f'Total entries: <strong>{n_total}</strong> &nbsp;|&nbsp; '
            f'Archived OK: <strong>{n_archived}</strong> &nbsp;|&nbsp; '
            f'Source missing: <strong>{n_missing}</strong> &nbsp;|&nbsp; '
            f'Latest: <strong>{latest_date}</strong></p>'
            '<p>Archive path: <code>data/research/cloud_daily_report_validation/archive/</code></p>'
            '<table><thead><tr>'
            '<th>Date</th><th>File Type</th><th>Status</th><th>Size (bytes)</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>'
            '<p><small>Showing last 14 manifest entries. '
            'Run archive script daily after EOD scan to build history.</small></p>'
            '</div>'
        )
    except Exception as exc:
        return (
            f'<div class="section-box"><h3>v0.3 Archive Status</h3>'
            f'<p>Error reading manifest: {exc}</p></div>'
        )


def generate_validation_html(all_results: dict[str, Any]) -> str:
    """Generate main validation report HTML from all_results dict.

    all_results: mapping of test_name -> DataFrame (result of each test)
    """
    today = str(date.today())

    sections_html = ""
    for test_name, result in all_results.items():
        if isinstance(result, pd.DataFrame):
            n = len(result)
            n_blocked = int((result.get("evidence_label", pd.Series(dtype=str)) == EvidenceLabel.BLOCKED_BY_DATA.value).sum()) if "evidence_label" in result.columns else 0
            highlight = ["evidence_label", "evidence_status", "dashboard_recommendation"] if isinstance(result, pd.DataFrame) else []
            highlight = [c for c in highlight if c in result.columns]
            sections_html += f"""
<div class="section-box">
<h2>{test_name.replace("_", " ").title()} ({n} rows, {n_blocked} blocked)</h2>
{_df_to_html_table(result, highlight_cols=highlight)}
</div>"""
        else:
            sections_html += f"""
<div class="section-box">
<h2>{test_name}</h2>
<p>{result}</p>
</div>"""

    archive_status_html = generate_archive_status_html()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloud Daily Report — Validation Results</title>
<style>{_BASE_CSS}</style>
</head>
<body>
<div style="{_BANNER_STYLE}">{RESEARCH_ONLY_LABEL}</div>
<h1>Cloud Daily Report — Validation Results</h1>
<p><strong>Generated:</strong> {today} &nbsp;|&nbsp; <strong>Label:</strong> {RESEARCH_ONLY_LABEL}</p>
<p>All validation results use scan data from 2026-05-15 to 2026-05-28 only.
Most quantitative tests are BLOCKED_BY_DATA due to insufficient history.
This is expected — accumulate 3+ months of daily scan history for robust event studies.</p>
<p><strong>v0.2/v0.3 proves framework readiness, not alpha.</strong>
No Cloud Daily Report output is statistically proven to add return alpha.</p>

{archive_status_html}

{sections_html}

<hr>
<p style="font-size:11px;color:#999;">
{RESEARCH_ONLY_LABEL} — this report must not be used to modify live trading behavior.
</p>
</body>
</html>"""
    return html
