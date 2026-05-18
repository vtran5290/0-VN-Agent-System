"""
Build full handoff zip: lean weekly report code + docs + outputs + tests.

Usage:
  python -m scripts.reporting.build_weekly_handoff_zip
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages" / "weekly_report_lean"
ZIP_PATH = OUT_DIR / "vn_weekly_report_lean_handoff.zip"

CODE_AND_DOCS: list[tuple[str, str]] = [
    ("README_HANDOFF.txt", "README.txt"),
    ("docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md", "docs/WEEKLY_REPORT_GENERATION_FLOW.md"),
    ("docs/reporting/WEEKLY_REPORT_COMMAND_CENTER_REVIEW_PROMPT.md", "docs/REVIEW_PROMPT.md"),
    ("docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md", "docs/WEEKLY_REPORT_STRATEGY_SYNC.md"),
    ("docs/reporting/KPI_IMPORTANCE_BACKTEST_PROMPT.md", "docs/KPI_IMPORTANCE_BACKTEST_PROMPT.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/REAL_CAPITAL_READINESS.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/ema_cloud_strategy_spec.md", "docs/ema_cloud_strategy_spec.md"),
    ("docs/WEEKLY_FULL_FETCH.md", "docs/WEEKLY_FULL_FETCH.md"),
    ("config/weekly_report_strategy.yaml", "config/weekly_report_strategy.yaml"),
    ("scripts/reporting/report_format.py", "scripts/reporting/report_format.py"),
    ("scripts/reporting/metric_registry.py", "scripts/reporting/metric_registry.py"),
    ("scripts/reporting/render_weekly_report.py", "scripts/reporting/render_weekly_report.py"),
    ("scripts/reporting/build_weekly_handoff_zip.py", "scripts/reporting/build_weekly_handoff_zip.py"),
    ("scripts/ingest/scan_ssot.py", "scripts/ingest/scan_ssot.py"),
    ("scripts/ingest/weekly_lean_sections.py", "scripts/ingest/weekly_lean_sections.py"),
    ("scripts/ingest/portfolio_decision_enrich.py", "scripts/ingest/portfolio_decision_enrich.py"),
    ("scripts/ingest/normalize_weekly_report.py", "scripts/ingest/normalize_weekly_report.py"),
    ("scripts/ingest/run_weekly_update.py", "scripts/ingest/run_weekly_update.py"),
    ("templates/weekly_report_lean.html.j2", "templates/weekly_report_lean.html.j2"),
    ("templates/weekly_report_portfolio_blocks.j2", "templates/weekly_report_portfolio_blocks.j2"),
    ("templates/weekly_report.html.j2", "templates/weekly_report_legacy.html.j2"),
    ("tests/test_report_format.py", "tests/test_report_format.py"),
    ("tests/test_lean_weekly_report.py", "tests/test_lean_weekly_report.py"),
    ("tests/test_portfolio_command_center_report.py", "tests/test_portfolio_command_center_report.py"),
]

OUTPUTS: list[tuple[str, str]] = [
    ("reports/latest/index.html", "outputs/reports_latest_index.html"),
    ("reports/archive/2026-05-17/index.html", "outputs/reports_archive_2026-05-17_index.html"),
    ("data/processed/weekly_report.json", "outputs/data_processed_weekly_report.json"),
    ("data/decision/weekly_report.md", "outputs/data_decision_weekly_report.md"),
    ("data/decision/weekly_report.json", "outputs/data_decision_weekly_report.json"),
    ("data/raw/current_positions_derived.json", "outputs/current_positions_derived.json"),
    ("data/raw/manual_inputs.json", "outputs/manual_inputs.json"),
    ("data/alerts/sell_signals.json", "outputs/sell_signals.json"),
    ("data/raw/tech_status.json", "outputs/tech_status.json"),
    ("data/decision/allocation_plan.json", "outputs/allocation_plan.json"),
    ("data/state/regime_state.json", "outputs/regime_state.json"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
        "outputs/phase36_daily_scan_schema.csv",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv",
        "outputs/phase36_daily_scan_sample.csv",
    ),
    ("data/master/sector_map.csv", "outputs/sector_map.csv"),
    ("config/watchlist.txt", "outputs/watchlist.txt"),
    ("reports/latest/vnindex_downtrend_probability_v2.md", "outputs/vnindex_downtrend_v2.md"),
]

LEAN_JSON_KEYS = [
    "metadata",
    "portfolio_command_center",
    "regime_rules",
    "market_pulse",
    "portfolio_summary",
    "position_decisions",
    "watchlist_board",
    "smart_kpi_board",
    "global_macro_narrative",
    "vn_liquidity_narrative",
    "visualizations_smart",
    "decision_layer",
    "decision_review",
    "data_quality_compact",
    "data_freshness",
    "sector_exposure",
    "metric_registry",
    "execution_monitoring",
    "probability_allocation",
    "regime_engine",
]


def _readme() -> str:
    return f"""VN Weekly Report — Lean Portfolio Command Center (full handoff)
Built: {datetime.now().isoformat(timespec="seconds")}

CONTENTS
========
README.txt              — this file
docs/                   — generation flow, review prompt, strategy sync, KPI research prompt
config/                 — weekly_report_strategy.yaml (B_cloud20_100 / A3_PRODUCTION)
scripts/                — enrich, scan SSOT, lean sections, format, render
templates/              — weekly_report_lean.html.j2 (active), legacy template
tests/                  — format + lean + command center tests (19 passing)
outputs/                — latest HTML, processed JSON, inputs, scan sample

QUICK START
===========
1. Open outputs/reports_latest_index.html in a browser.
2. Read docs/WEEKLY_REPORT_GENERATION_FLOW.md for pipeline.
3. Regenerate:
     python -m scripts.ingest.run_weekly_update
     python -m scripts.reporting.render_weekly_report

TESTS
=====
  python -m pytest tests/test_report_format.py tests/test_lean_weekly_report.py tests/test_portfolio_command_center_report.py -q

NOTES
=====
- Renderer uses templates/weekly_report_lean.html.j2 (not legacy).
- Scan SSOT: phase36 CSV; production filter A3_PRODUCTION.
- No EMA recompute; no order routing; capital NO-GO per REAL_CAPITAL_READINESS.md.
"""


def _trim_lean_json(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {k: raw.get(k) for k in LEAN_JSON_KEYS if k in raw}
    for block in ("position_decisions", "watchlist_board"):
        if block in out and isinstance(out[block], dict):
            key = "rows" if "rows" in out[block] else "candidates"
            rows = out[block].get(key)
            if isinstance(rows, list) and len(rows) > 8:
                out[block] = {**out[block], key: rows[:8], f"{key}_truncated_total": len(rows)}
    return json.dumps(out, indent=2, ensure_ascii=False)


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    readme_path = OUT_DIR / "README_HANDOFF.txt"
    readme_path.write_text(_readme(), encoding="utf-8")

    manifest: list[str] = []
    missing: list[str] = []

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, arc in CODE_AND_DOCS:
            src = readme_path if rel == "README_HANDOFF.txt" else REPO / rel
            if src.exists():
                zf.write(src, arc)
                manifest.append(arc)
            else:
                missing.append(rel)

        for rel, arc in OUTPUTS:
            src = REPO / rel
            if src.exists():
                zf.write(src, arc)
                manifest.append(arc)
            else:
                missing.append(rel)

        proc = REPO / "data/processed/weekly_report.json"
        if proc.exists():
            zf.writestr("outputs/processed_weekly_report_lean_keys.json", _trim_lean_json(proc))
            manifest.append("outputs/processed_weekly_report_lean_keys.json")

        zf.writestr(
            "MANIFEST.txt",
            "Included files:\n" + "\n".join(sorted(manifest)) + "\n\nMissing (skipped):\n" + "\n".join(missing or ["(none)"]),
        )

    mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {ZIP_PATH}")
    print(f"  Size: {ZIP_PATH.stat().st_size / 1024:.1f} KB ({mb:.2f} MB)")
    print(f"  Files: {len(manifest)}")
    if missing:
        print(f"  Skipped missing: {len(missing)}")
    return ZIP_PATH


if __name__ == "__main__":
    build()
