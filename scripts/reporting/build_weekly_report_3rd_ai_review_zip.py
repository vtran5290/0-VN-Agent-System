"""
Build outputs/review_packages/vn_weekly_report_3rd_ai_review.zip for 3rd-party AI review.

Usage:
  python -m scripts.reporting.build_weekly_report_3rd_ai_review_zip
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / "vn_weekly_report_3rd_ai_review.zip"

# Python modules required for pytest in extracted zip (import closure for packaged tests).
PYTHON_MODULES: list[tuple[str, str]] = [
    ("pytest.ini", "pytest.ini"),
    ("scripts/__init__.py", "scripts/__init__.py"),
    ("scripts/ingest/__init__.py", "scripts/ingest/__init__.py"),
    ("scripts/ingest/config.py", "scripts/ingest/config.py"),
    ("scripts/ingest/legacy_adapter.py", "scripts/ingest/legacy_adapter.py"),
    ("scripts/ingest/normalize_weekly_report.py", "scripts/ingest/normalize_weekly_report.py"),
    ("scripts/ingest/portfolio_decision_enrich.py", "scripts/ingest/portfolio_decision_enrich.py"),
    ("scripts/ingest/scan_ssot.py", "scripts/ingest/scan_ssot.py"),
    ("scripts/ingest/weekly_lean_sections.py", "scripts/ingest/weekly_lean_sections.py"),
    ("scripts/ingest/run_weekly_update.py", "scripts/ingest/run_weekly_update.py"),
    ("scripts/reporting/__init__.py", "scripts/reporting/__init__.py"),
    ("scripts/reporting/report_format.py", "scripts/reporting/report_format.py"),
    ("scripts/reporting/metric_registry.py", "scripts/reporting/metric_registry.py"),
    ("scripts/reporting/render_weekly_report.py", "scripts/reporting/render_weekly_report.py"),
    ("scripts/reporting/build_chatgpt_review_zip.py", "scripts/reporting/build_chatgpt_review_zip.py"),
    ("scripts/reporting/build_weekly_review_zip.py", "scripts/reporting/build_weekly_review_zip.py"),
    ("scripts/reporting/build_weekly_report_3rd_ai_review_zip.py", "scripts/reporting/build_weekly_report_3rd_ai_review_zip.py"),
    ("scripts/utils/__init__.py", "scripts/utils/__init__.py"),
    ("scripts/utils/io.py", "scripts/utils/io.py"),
    ("scripts/utils/date_utils.py", "scripts/utils/date_utils.py"),
    ("scripts/utils/logging_utils.py", "scripts/utils/logging_utils.py"),
    ("scripts/utils/validation.py", "scripts/utils/validation.py"),
    ("tests/conftest.py", "tests/conftest.py"),
    ("tests/fixtures/phase36_daily_scan_review_fixture.csv", "tests/fixtures/phase36_daily_scan_review_fixture.csv"),
]

# (repo_relative, zip_internal_path)
FILES: list[tuple[str, str]] = [
    ("docs/reporting/WEEKLY_REPORT_3RD_AI_REVIEW_PROMPT.md", "REVIEW_PROMPT.md"),
    ("docs/reporting/WEEKLY_REPORT_REVIEW_PACKAGE_README.md", "README.md"),
    ("docs/reporting/WEEKLY_REPORT_GENERATION_FLOW.md", "docs/WEEKLY_REPORT_GENERATION_FLOW.md"),
    ("docs/reporting/WEEKLY_REPORT_STRATEGY_SYNC.md", "docs/WEEKLY_REPORT_STRATEGY_SYNC.md"),
    ("docs/reporting/WEEKLY_REPORT_COMMAND_CENTER_REVIEW_PROMPT.md", "docs/ARCHIVE_COMMAND_CENTER_REVIEW_PROMPT.md"),
    ("docs/reporting/KPI_IMPORTANCE_BACKTEST_PROMPT.md", "docs/KPI_IMPORTANCE_BACKTEST_PROMPT.md"),
    ("docs/WEEKLY_FULL_FETCH.md", "docs/WEEKLY_FULL_FETCH.md"),
    ("docs/trading/REAL_CAPITAL_READINESS.md", "docs/REAL_CAPITAL_READINESS.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/reporting/WEEKLY_REPORT_CURSOR_PATCH_BRIEF.md", "archive/CURSOR_PATCH_BRIEF.md"),
    ("docs/reporting/WEEKLY_REPORT_CHATGPT_REVIEW_PROMPT.md", "archive/CHATGPT_REVIEW_PROMPT_ARCHIVE.md"),
    ("config/weekly_report_strategy.yaml", "config/weekly_report_strategy.yaml"),
    ("config/watchlist.txt", "config/watchlist.txt"),
    ("templates/weekly_report_lean.html.j2", "templates/weekly_report_lean.html.j2"),
    ("templates/weekly_report_portfolio_blocks.j2", "templates/weekly_report_portfolio_blocks.j2"),
    ("tests/test_lean_weekly_report.py", "tests/test_lean_weekly_report.py"),
    ("tests/test_portfolio_command_center_report.py", "tests/test_portfolio_command_center_report.py"),
    ("tests/test_report_format.py", "tests/test_report_format.py"),
    ("tests/test_weekly_report_p0_fixes.py", "tests/test_weekly_report_p0_fixes.py"),
    ("tests/test_weekly_report_review_fixture.py", "tests/test_weekly_report_review_fixture.py"),
    ("reports/latest/index.html", "outputs/reports_latest_index.html"),
    ("data/processed/weekly_report.json", "outputs/data_processed_weekly_report.json"),
    ("data/decision/weekly_report.json", "data/decision/weekly_report.json"),
    ("data/decision/weekly_report.md", "outputs/data_decision_weekly_report.md"),
    ("data/alerts/market_flags.json", "data/alerts/market_flags.json"),
    ("data/raw/current_positions_derived.json", "data/raw/current_positions_derived.json"),
    ("data/raw/current_positions_derived.json", "samples/current_positions_derived.json"),
    ("data/raw/manual_inputs.json", "data/raw/manual_inputs.json"),
    ("data/raw/manual_inputs.json", "samples/manual_inputs.json"),
    ("data/raw/manual_inputs_prev.json", "data/raw/manual_inputs_prev.json"),
    ("data/raw/manual_inputs_prev.json", "samples/manual_inputs_prev.json"),
    ("data/alerts/sell_signals.json", "samples/sell_signals.json"),
    ("data/raw/tech_status.json", "data/raw/tech_status.json"),
    ("data/raw/tech_status.json", "samples/tech_status.json"),
    ("data/state/regime_state.json", "samples/regime_state.json"),
    ("data/decision/allocation_plan.json", "samples/allocation_plan.json"),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_schema.csv",
        "samples/phase36_daily_scan_schema.csv",
    ),
    (
        "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv",
        "samples/phase36_daily_scan_latest.csv",
    ),
    ("samples/phase36_daily_scan_review_fixture.csv", "samples/phase36_daily_scan_review_fixture.csv"),
    ("samples/REVIEW_FIXTURE_README.txt", "samples/REVIEW_FIXTURE_README.txt"),
    ("data/master/sector_map.csv", "data/master/sector_map.csv"),
    ("data/master/sector_map.csv", "samples/sector_map.csv"),
    ("data/alerts/sell_signals.json", "data/alerts/sell_signals.json"),
]

EXCLUDE_NAME_PARTS = (
    ".env",
    "credentials",
    "dnse",
    "fireant_token",
    "broker",
    "live_order",
    "paper_trade/orders",
)

LEAN_KEYS = [
    "metadata",
    "portfolio_command_center",
    "market_pulse",
    "portfolio_summary",
    "position_decisions",
    "watchlist_board",
    "smart_kpi_board",
    "global_macro_narrative",
    "vn_liquidity_narrative",
    "decision_layer",
    "data_quality_compact",
    "visualizations_smart",
    "regime_rules",
    "metric_registry",
]

SECRET_IN_CONTENT = re.compile(
    r"(FIREANT_TOKEN|DNSE_|API_KEY|Bearer eyJ|secret|password)\s*[=:]\s*\S+",
    re.I,
)

ZIP_README_TESTS = """VN Weekly Report — 3rd AI review package
==========================================

PRIMARY ARTIFACT
  outputs/reports_latest_index.html — open in browser

RUN TESTS (from extracted zip root)
  python -m pytest tests/test_report_format.py tests/test_lean_weekly_report.py \\
    tests/test_portfolio_command_center_report.py tests/test_weekly_report_p0_fixes.py \\
    tests/test_weekly_report_review_fixture.py -q

Requires: pytest, pyyaml, jinja2 (same as repo dev env).

REVIEW SCAN FIXTURE (not production SSOT)
  samples/phase36_daily_scan_review_fixture.csv
  tests/fixtures/phase36_daily_scan_review_fixture.csv
  See samples/REVIEW_FIXTURE_README.txt

PRODUCTION SCAN in package (weak coverage for 14 holdings)
  samples/phase36_daily_scan_latest.csv — only FPT/AAA/SSI in current snapshot

REGENERATE (on machine with full repo + FIREANT_TOKEN, not in zip)
  python -m scripts.ingest.run_weekly_update
  python -m scripts.reporting.render_weekly_report

REBUILD THIS ZIP
  python -m scripts.reporting.build_weekly_report_3rd_ai_review_zip
"""


def _safe_to_include(rel: str) -> bool:
    low = rel.lower().replace("\\", "/")
    return not any(x in low for x in EXCLUDE_NAME_PARTS)


def _trim_json(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {k: raw.get(k) for k in LEAN_KEYS if k in raw}
    pd = out.get("position_decisions", {})
    if isinstance(pd, dict) and isinstance(pd.get("rows"), list):
        rows = pd["rows"]
        if len(rows) > 14:
            out["position_decisions"] = {**pd, "rows": rows[:14], "rows_truncated": len(rows)}
    wl = out.get("watchlist_board", {})
    if isinstance(wl, dict) and isinstance(wl.get("candidates"), list):
        c = wl["candidates"]
        if len(c) > 20:
            out["watchlist_board"] = {**wl, "candidates": c[:20], "candidates_truncated": len(c)}
    return json.dumps(out, indent=2, ensure_ascii=False)


def _packaging_audit(html_path: Path) -> str:
    lines = [
        "# Packaging audit snapshot",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## HTML artifact",
        f"- Path: `{html_path.relative_to(REPO).as_posix() if html_path.exists() else 'MISSING'}`",
        f"- Exists: {html_path.exists()}",
    ]
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="replace")
        lines += [
            f"- Size: {html_path.stat().st_size:,} bytes",
            f"- Literal None in HTML: {'>None<' in html or 'class=\"mono\">None' in html}",
            f"- TRAIL_EXIT in HTML: {'TRAIL_EXIT' in html}",
            f"- Review fixture packaged: yes (samples/phase36_daily_scan_review_fixture.csv)",
        ]
    lines += [
        "",
        "## Tests in zip",
        "pytest.ini + scripts/* + tests/* — run from zip root:",
        "  python -m pytest tests/test_report_format.py tests/test_lean_weekly_report.py \\",
        "    tests/test_portfolio_command_center_report.py tests/test_weekly_report_p0_fixes.py \\",
        "    tests/test_weekly_report_review_fixture.py -q",
    ]
    return "\n".join(lines) + "\n"


def _add_file(zf: zipfile.ZipFile, rel: str, arc: str, manifest: list[str], skipped: list[str]) -> None:
    if not _safe_to_include(rel):
        skipped.append(rel)
        return
    src = REPO / rel
    if not src.is_file():
        skipped.append(f"{rel} (missing)")
        return
    if src.suffix in (".json", ".md", ".yaml", ".csv", ".html", ".j2", ".py", ".txt", ".ini"):
        text = src.read_text(encoding="utf-8", errors="replace")
        if SECRET_IN_CONTENT.search(text[:8000]):
            skipped.append(f"{rel} (secret pattern in content)")
            return
    zf.write(src, arc)
    manifest.append(arc)


def build() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = REPO / "reports" / "latest" / "index.html"
    audit = _packaging_audit(html)

    manifest: list[str] = []
    skipped: list[str] = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", ZIP_README_TESTS)
        manifest.append("README.txt")
        zf.writestr("PACKAGING_AUDIT.md", audit)
        manifest.append("PACKAGING_AUDIT.md")

        for rel, arc in PYTHON_MODULES:
            _add_file(zf, rel, arc, manifest, skipped)

        for rel, arc in FILES:
            _add_file(zf, rel, arc, manifest, skipped)

        proc = REPO / "data/processed/weekly_report.json"
        if proc.exists():
            zf.writestr("outputs/processed_weekly_report_lean_keys.json", _trim_json(proc))
            manifest.append("outputs/processed_weekly_report_lean_keys.json")

        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))
        if skipped:
            zf.writestr("SKIPPED_FILES.txt", "\n".join(skipped))

    print(f"Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB, {len(manifest)} files)")
    if skipped:
        print(f"Skipped {len(skipped)} paths — see SKIPPED_FILES.txt in zip")
    return OUT_ZIP


if __name__ == "__main__":
    build()
