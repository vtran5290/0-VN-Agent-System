"""
Build vn_weekly_report_chatgpt_review.zip for third-party ChatGPT review.

Usage:
  python -m scripts.reporting.build_chatgpt_review_zip
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / "vn_weekly_report_chatgpt_review.zip"

# (repo_relative, zip_path)
FILES = [
    ("docs/reporting/WEEKLY_REPORT_CHATGPT_REVIEW_PROMPT.md", "REVIEW_PROMPT.md"),
    ("docs/reporting/WEEKLY_REPORT_CURSOR_PATCH_BRIEF.md", "CURSOR_PATCH_BRIEF.md"),
    ("docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md", "docs/WEEKLY_REPORT_GENERATION_FLOW.md"),
    ("docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md", "docs/WEEKLY_REPORT_STRATEGY_SYNC.md"),
    ("docs/reporting/WEEKLY_REPORT_COMMAND_CENTER_REVIEW_PROMPT.md", "docs/ARCHIVE_REVIEW_PROMPT_v1.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/REAL_CAPITAL_READINESS.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("config/weekly_report_strategy.yaml", "config/weekly_report_strategy.yaml"),
    ("scripts/ingest/weekly_lean_sections.py", "scripts/weekly_lean_sections.py"),
    ("scripts/ingest/scan_ssot.py", "scripts/scan_ssot.py"),
    ("scripts/ingest/portfolio_decision_enrich.py", "scripts/portfolio_decision_enrich.py"),
    ("scripts/reporting/report_format.py", "scripts/reporting/report_format.py"),
    ("scripts/reporting/metric_registry.py", "scripts/reporting/metric_registry.py"),
    ("scripts/reporting/render_weekly_report.py", "scripts/render_weekly_report.py"),
    ("templates/weekly_report_lean.html.j2", "templates/weekly_report_lean.html.j2"),
    ("templates/weekly_report_portfolio_blocks.j2", "templates/weekly_report_portfolio_blocks.j2"),
    ("tests/test_lean_weekly_report.py", "tests/test_lean_weekly_report.py"),
    ("tests/test_portfolio_command_center_report.py", "tests/test_portfolio_command_center_report.py"),
    ("tests/test_report_format.py", "tests/test_report_format.py"),
    ("tests/test_weekly_report_p0_fixes.py", "tests/test_weekly_report_p0_fixes.py"),
    ("reports/latest/index.html", "outputs/reports_latest_index.html"),
    ("data/processed/weekly_report.json", "outputs/data_processed_weekly_report.json"),
    ("data/decision/weekly_report.md", "outputs/data_decision_weekly_report.md"),
    ("data/raw/current_positions_derived.json", "outputs/current_positions_derived.json"),
    ("data/raw/manual_inputs.json", "outputs/manual_inputs.json"),
    ("data/alerts/sell_signals.json", "outputs/sell_signals.json"),
    ("data/raw/tech_status.json", "outputs/tech_status.json"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
        "outputs/phase36_daily_scan_schema.csv",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
        "outputs/phase36_daily_scan_sample.csv",
    ),
    ("data/master/sector_map.csv", "outputs/sector_map.csv"),
    ("reports/latest/vnindex_downtrend_probability_v2.md", "outputs/vnindex_downtrend_v2.md"),
]

LEAN_KEYS = [
    "metadata", "portfolio_command_center", "market_pulse", "portfolio_summary",
    "position_decisions", "watchlist_board", "smart_kpi_board", "decision_layer",
    "data_quality_compact", "visualizations_smart", "execution_monitoring",
]


def _readme() -> str:
    return f"""VN Weekly Report — ChatGPT review package
Built: {datetime.now().isoformat(timespec='seconds')}

HOW TO USE
==========
1. Start a new ChatGPT chat.
2. Attach: vn_weekly_report_chatgpt_review.zip
3. Paste the full text of REVIEW_PROMPT.md (or say: "Follow REVIEW_PROMPT.md in the zip").
4. Open outputs/reports_latest_index.html locally while ChatGPT reviews.

CONTENTS
========
REVIEW_PROMPT.md          — Copy-paste prompt for ChatGPT (this review)
CURSOR_PATCH_BRIEF.md     — Cursor implementation brief (validate this)
outputs/reports_latest_index.html — Live lean report (open in browser)
scripts/ + templates/   — Source for cross-check
tests/                    — Existing + proposed tests in brief
docs/                     — Generation flow, strategy sync, NO-GO capital

RELATED ZIPs (not included)
===========================
vn_weekly_report_lean_handoff.zip     — Full code+outputs handoff
vn_weekly_report_cursor_patch.zip     — Cursor-only patch subset (if present)

REGENERATE REPORT
=================
  .venv\\Scripts\\python.exe -m scripts.ingest.run_weekly_update
  .venv\\Scripts\\python.exe -m scripts.reporting.render_weekly_report

RUN TESTS
=========
  .venv\\Scripts\\python.exe -m pytest tests/test_report_format.py tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py tests/test_weekly_report_p0_fixes.py -q

BUILD THIS ZIP
==============
  .venv\\Scripts\\python.exe -m scripts.reporting.build_chatgpt_review_zip
"""


def _trim_json(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {k: raw.get(k) for k in LEAN_KEYS if k in raw}
    pd = out.get("position_decisions", {})
    if isinstance(pd, dict) and isinstance(pd.get("rows"), list):
        rows = pd["rows"]
        if len(rows) > 10:
            out["position_decisions"] = {**pd, "rows": rows[:10], "rows_truncated": len(rows)}
    return json.dumps(out, indent=2, ensure_ascii=False)


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readme = OUT_DIR / "README_CHATGPT.txt"
    readme.write_text(_readme(), encoding="utf-8")

    manifest: list[str] = []
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(readme, "README.txt")
        manifest.append("README.txt")
        for rel, arc in FILES:
            src = REPO / rel
            if src.exists():
                zf.write(src, arc)
                manifest.append(arc)
        proc = REPO / "data/processed/weekly_report.json"
        if proc.exists():
            zf.writestr("outputs/processed_weekly_report_lean_keys.json", _trim_json(proc))
            manifest.append("outputs/processed_weekly_report_lean_keys.json")
        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))

    print(f"Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB, {len(manifest)} files)")
    return OUT_ZIP


if __name__ == "__main__":
    build()
