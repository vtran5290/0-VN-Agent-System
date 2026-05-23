"""Weekly-style brief MD + HTML (synced on every scan)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .weekly_brief_html import render_weekly_brief_html


def weekly_brief_paths(output_dir: Path, scan_date: str) -> tuple[Path, Path]:
    md = output_dir / f"institutional_accumulation_weekly_brief_{scan_date}.md"
    html = output_dir / f"institutional_accumulation_weekly_brief_{scan_date}.html"
    return md, html


def build_weekly_brief_md_auto(
    op_payload: Dict[str, Any],
    df: pd.DataFrame,
    scan_json: Dict[str, Any],
) -> str:
    """Scan-derived weekly brief skeleton (macro sections = edit placeholders)."""
    scan_date = str(op_payload.get("scan_date") or "")
    diag = op_payload.get("bucket_diagnostics") or {}
    tiers = diag.get("tier_counts") or {}
    sector = (scan_json.get("sector_summary") or {})
    emerging = scan_json.get("emerging_accumulation") or {}
    changes = op_payload.get("changes_since_previous") or {}
    op_html = f"outputs/scans/institutional_accumulation_operator_summary_{scan_date}.html"

    lines = [
        "# Institutional Accumulation Weekly Brief — Research Only",
        "",
        f"**As-of:** {scan_date} | **Methodology:** {op_payload.get('methodology_version', 'v1.1')} "
        f"| **Rows scored:** {diag.get('rows_scored', len(df))}  ",
        f"**Regime:** `{op_payload.get('regime_label')}` | **Context:** {op_payload.get('context_source')}  ",
        "",
        "> **Safety:** Research ranking / prioritization only. Does **not** set `final_action`, "
        "orders, OMS, sizing, or execution.",
        "",
        f"**Operator HTML:** `{op_html}` | **CSV:** `institutional_accumulation_{scan_date}.csv`",
        "",
        "---",
        "",
        "## Global Macro + Fed (brief)",
        "",
        "**FACTS** — _Edit: pull from `data/decision/weekly_report.md` or Unknown._",
        "",
        "**INTERPRETATION** — _Edit after FACTS._",
        "",
        "## Vietnam Policy + Liquidity (brief)",
        "",
        "**FACTS** — _Edit: OMO / interbank / credit / FX from weekly packet or Unknown._",
        "",
        "**INTERPRETATION** — _Edit after FACTS._",
        "",
        "## Market internals (scan-derived)",
        "",
        "**FACTS**",
        "",
        f"- Tier 1: **{tiers.get('Tier 1', 0)}** | Tier 2: **{tiers.get('Tier 2', 0)}** | "
        f"Tier 3: **{tiers.get('Tier 3', 0)}** | Reject: **{tiers.get('Reject', 0)}**",
        f"- Emerging accumulation (universe): **{diag.get('emerging_count_total', 0)}**",
        f"- Top-tier fund-backed (Tier 1–3): **{diag.get('count_top_tier_fund_backed', 0)}**",
        f"- VIN distortion flags (Tier 1–3): **{diag.get('count_top_tier_vin_distortion_flag', 0)}**",
        f"- Dominant sector (Tier 1–2): **{sector.get('dominant_sector') or '—'}** "
        f"(concentration warning: **{sector.get('concentration_warning', False)}**)",
        f"- Emerging top count (JSON): **{emerging.get('count', 0)}**",
        "",
        "**INTERPRETATION** — _Edit: breadth / narrow leadership vs regime tag._",
        "",
        "## Sectors & Companies (accumulation lens)",
        "",
        "_See operator summary for cards; edit table below from `institutional_accumulation_{date}_top80.csv`._",
        "",
        "## Decision layer (research only)",
        "",
        "**Top 3 research actions** — _Edit._",
        "",
        "**Top 3 methodology risks** — _Edit._",
        "",
        f"**Changes since previous:** {changes.get('summary_line') or changes.get('note') or '—'}",
        "",
        "## Validation & data integrity",
        "",
        f"- Workflow warnings: {len(op_payload.get('key_warnings') or [])} elevated message(s) in operator summary",
        "",
        "## Signals to monitor next week",
        "",
        "- _Edit — bullet list._",
        "",
        "## If X happens → do Y (research steps only)",
        "",
        "| If | Then (research) |",
        "| --- | --- |",
        "| _Edit_ | _Edit_ |",
        "",
        "---",
        "",
        "*End weekly brief — institutional accumulation scan only.*",
        "",
    ]
    return "\n".join(lines)


def write_weekly_brief_html_from_md(md_path: Path, html_path: Path, scan_date: str) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    html_path.write_text(render_weekly_brief_html(md_text, scan_date=scan_date), encoding="utf-8")


def sync_weekly_brief_html(
    output_dir: Path,
    scan_date: str,
    *,
    regenerate_md: bool = False,
    op_payload: Optional[Dict[str, Any]] = None,
    df: Optional[pd.DataFrame] = None,
    scan_json: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Ensure weekly brief MD exists (optional auto-create) and always refresh HTML from MD.
    """
    md_path, html_path = weekly_brief_paths(output_dir, scan_date)
    if regenerate_md or not md_path.is_file():
        if op_payload is None or df is None or scan_json is None:
            raise ValueError("regenerate_md requires op_payload, df, and scan_json")
        md_path.write_text(
            build_weekly_brief_md_auto(op_payload, df, scan_json),
            encoding="utf-8",
        )
    if not md_path.is_file():
        raise FileNotFoundError(f"Weekly brief MD missing: {md_path}")
    write_weekly_brief_html_from_md(md_path, html_path, scan_date)
    return {"weekly_brief_md": str(md_path), "weekly_brief_html": str(html_path)}


def write_weekly_brief_artifacts(
    output_dir: Path,
    scan_date: str,
    op_payload: Dict[str, Any],
    df: pd.DataFrame,
    scan_json: Dict[str, Any],
    *,
    preserve_existing_md: bool = True,
) -> Dict[str, str]:
    """
    After scan: create MD if missing; always sync HTML from current MD.
    Set preserve_existing_md=False to overwrite MD with auto skeleton.
    """
    md_path, _ = weekly_brief_paths(output_dir, scan_date)
    regenerate = not preserve_existing_md or not md_path.is_file()
    return sync_weekly_brief_html(
        output_dir,
        scan_date,
        regenerate_md=regenerate,
        op_payload=op_payload,
        df=df,
        scan_json=scan_json,
    )
