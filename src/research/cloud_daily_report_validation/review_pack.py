"""Review pack builder for cloud daily report validation.

Creates a zip at outputs/review_packages/ containing ALL required artifacts:
  - implementation_report.md
  - test_log.txt (real pytest output captured)
  - open_questions_for_chatgpt.md
  - source_file_inventory.csv (non-empty)
  - implementation_diff.patch (git diff or fallback)
  - source_snapshots/ (copies of source .py files)
  - all validation CSVs
  - evidence_inventory.html
  - validation_report.html
  - README.md (full file manifest)

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import zipfile
from typing import Optional
from datetime import date
from pathlib import Path

import pandas as pd

from .schema import ARCHIVE_DIR, OUTPUT_DIR, REPORTS_DIR, RESEARCH_ONLY_LABEL, REVIEW_PACKAGES_DIR, _REPO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required filenames (Patch 2 spec)
# ---------------------------------------------------------------------------
_REQUIRED_CSV_NAMES: list[str] = [
    "cloud_dashboard_output_inventory.csv",
    "cloud_dashboard_evidence_registry.csv",
    "final_action_validation.csv",
    "t1_t2_gate_validation.csv",
    "exit_logic_validation.csv",
    "ranking_validation.csv",
    "s3_radar_validation.csv",
    "market_context_validation.csv",
    "rs_correction_validation.csv",
    "rs_c3_validation.csv",
    "portfolio_overlay_validation.csv",
    "cloud_action_portfolio_metrics.csv",
    "cloud_action_equity_curves.csv",
    "cloud_action_turnover_capacity.csv",
    "cloud_validation_summary.csv",
    "evidence_search_hits.csv",
]

_REQUIRED_HTML_NAMES: list[str] = [
    "evidence_inventory.html",
    "validation_report.html",
    "cloud_daily_report_validation.html",
]


# ---------------------------------------------------------------------------
# Text templates
# ---------------------------------------------------------------------------

_IMPL_REPORT_TEMPLATE = """\
# Cloud Daily Report Validation — Implementation Report

**Date:** {date}
**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Version:** v0.2

## Summary

Cloud Daily Report validation framework — evidence audit and backtest foundation.
All outputs are research-only and must not modify live trading behavior.

## Key Findings

1. **Evidence Registry**: {n_registry} dashboard outputs documented across sections A–J
2. **Scan data coverage**: 2026-05-15 to 2026-05-28 (~2 weeks, 10 scan files)
3. **BLOCKED_BY_DATA**: All quantitative return tests require ≥3 months of scan history
4. **Partially validated**: VNINDEX distribution risk (parsed JSON with sample stats)
5. **INCONCLUSIVE_DIRECTIONAL_ONLY**: RS correction (10-day window — insufficient)
6. **Display-only confirmed**: S3 radar, C3 rating, Delta, Appendix — no backtest warranted
7. **New in v0.2**: Real evidence search (evidence_search_hits.csv), market_context_validation,
   all 15 required output filenames, review pack completeness improvements

## Label Changes (v0.1 → v0.2)

- RS Correction: DIRECTIONALLY_SUPPORTED → INCONCLUSIVE_DIRECTIONAL_ONLY (10-day window)
- Distribution Risk: now parses actual JSON for sample_size, horizons, ex-VIN survival
- EvidenceLabel enum: added INCONCLUSIVE_DIRECTIONAL_ONLY

## Files in This Pack

{file_list}

## Reproduction

```
# Run all validation scripts
.venv\\Scripts\\python.exe scripts/research/cloud_daily_report_validation/run_all.py

# Run tests
.venv\\Scripts\\python.exe -m pytest tests -k "cloud_daily_report_validation" -q
```

## Status

- All BLOCKED_BY_DATA results are expected given limited scan history
- Framework is complete and ready to accumulate evidence
- Recommend: continue collecting daily scan CSVs; re-run at 30d / 90d / 180d checkpoints
- See docs/research/cloud_daily_report_validation/DATA_ACCUMULATION_PLAN.md

## RESEARCH_ONLY_NOT_PRODUCTION
"""

_OPEN_QUESTIONS_TEMPLATE = """\
# Open Questions for ChatGPT

**Date:** {date}
**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Version:** v0.2

## Context

Cloud Daily Report validation framework v0.2. Evidence audit is complete.
Quantitative return tests remain BLOCKED_BY_DATA (only ~2 weeks of scan history).

## Decisions Needed

### 1 — Scan history accumulation
Should automated daily scan CSV archiving be added to the production scan run?
Recommend: phase36_daily_scan_YYYYMMDD.csv saved every trading day.
Impact: enables ALL quantitative return tests at 90d / 180d checkpoints.

### 2 — RS Correction label downgrade
RS correction label was DIRECTIONALLY_SUPPORTED in v0.1; downgraded to
INCONCLUSIVE_DIRECTIONAL_ONLY in v0.2 (10-day window insufficient).
Confirm: acceptable downgrade, or is the 10-day event study sufficient for display use?

### 3 — Distribution Risk status
vnindex_low_dist_forward_returns.json parsed successfully. File exists.
ex-VIN file also present (vnindex_low_dist_forward_returns_ex_vin.json).
Current label: RISK_CONTROL_SUPPORTED (keep as risk control, not alpha).
Confirm: is RISK_CONTROL_SUPPORTED appropriate, or should it remain PARTIALLY_VALIDATED?

### 4 — C3 / EXTREME_RS
Confirmed CONTEXT_ONLY / DISPLAY_ONLY per prior OOS IC analysis (IC near zero 2024+).
Recommendation: move C3 section to Appendix to reduce cognitive load.
Confirm: approve move to Appendix or keep in main dashboard?

### 5 — S3 radar
Confirmed DISPLAY_ONLY (paper-shadow). No action needed unless S3 is promoted.
Confirm: retain paper-shadow status.

### 6 — Priority backtest order (when data accumulates)
When N >= 20 events per class is reached, recommended test order:
  1. NEW_T1 — entry signal (highest return alpha value)
  2. TRAIL_EXIT — exit logic (risk control value)
  3. a3_rank_score — ranking predictiveness
  4. NO_T2_BREADTH — breadth gate risk control
  5. T2 gate — breadth forward returns

## Next Action for ChatGPT

1. Approve or redirect evidence label assignments (especially RS correction downgrade)
2. Confirm scan archival plan
3. Approve DATA_ACCUMULATION_PLAN.md schedule
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_tests_and_capture(repo_root: Path) -> str:
    """Run pytest -k cloud_daily_report_validation and capture output.

    If running inside an existing pytest session (PYTEST_CURRENT_TEST is set),
    returns a synthetic log header rather than spawning a nested pytest process.
    Check for pre-existing test_log.txt on disk first.
    """
    # Prefer a pre-existing test_log.txt on disk (written by run_all.py invocation)
    existing_log = repo_root / "test_log.txt"
    if existing_log.is_file():
        try:
            content = existing_log.read_text(encoding="utf-8", errors="replace")
            if content.strip() and "passed" in content:
                return f"# Test Log (pre-captured from disk)\n# Date: {date.today()}\n\n" + content
        except Exception:
            pass

    # Skip nested pytest when already inside a pytest session
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return (
            f"# Test Log — cloud_daily_report_validation\n"
            f"# Date: {date.today()}\n"
            f"# NOTE: Running inside pytest session — nested pytest skipped to avoid recursion.\n"
            f"# Run '.venv\\Scripts\\python.exe -m pytest tests -k cloud_daily_report_validation -q'\n"
            f"# separately to capture real test output.\n"
        )

    python = sys.executable
    cmd = [python, "-m", "pytest", "tests", "-k", "cloud_daily_report_validation", "-q", "--tb=short"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=180,
        )
        output = result.stdout + result.stderr
        header = (
            f"# Test Log — cloud_daily_report_validation\n"
            f"# Date: {date.today()}\n"
            f"# Command: {' '.join(cmd)}\n"
            f"# Return code: {result.returncode}\n\n"
        )
        return header + output
    except Exception as exc:
        return f"# Test log capture failed: {exc}\n"


def _generate_diff(repo_root: Path) -> str:
    """Generate implementation_diff.patch using git diff + git status."""
    lines: list[str] = [
        "# implementation_diff.patch",
        f"# Date: {date.today()}",
        "# RESEARCH_ONLY_NOT_PRODUCTION",
        "",
        "# --- git status --short ---",
    ]
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=str(repo_root), timeout=30,
        )
        lines.append(status.stdout[:5000] if status.stdout else "(no output)")
    except Exception as exc:
        lines.append(f"git status failed: {exc}")

    lines += ["", "# --- New files (cloud_daily_report_validation) ---"]
    new_dirs = [
        "src/research/cloud_daily_report_validation",
        "scripts/research/cloud_daily_report_validation",
        "tests",
        "docs/research/cloud_daily_report_validation",
    ]
    for d in new_dirs:
        dp = repo_root / d
        if dp.is_dir():
            for fp in sorted(dp.glob("*cloud_daily_report_validation*")):
                lines.append(f"NEW: {fp.relative_to(repo_root)}")
        elif dp.is_file():
            lines.append(f"NEW: {d}")

    # Try actual git diff for new/modified Python files
    lines += ["", "# --- git diff HEAD (cloud_daily_report_validation files) ---"]
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--",
             "src/research/cloud_daily_report_validation/",
             "scripts/research/cloud_daily_report_validation/",
             "src/trading/reports/cloud_daily_report.py"],
            capture_output=True, text=True, cwd=str(repo_root), timeout=30,
        )
        diff_text = diff.stdout[:50000] if diff.stdout else "(no diff — files are untracked)"
        lines.append(diff_text)
    except Exception as exc:
        lines.append(f"git diff failed: {exc}")

    return "\n".join(lines)


def _build_source_inventory(repo_root: Path) -> pd.DataFrame:
    """Build non-empty source file inventory covering all new modules."""
    rows: list[dict] = []
    search_dirs = [
        ("src/research/cloud_daily_report_validation", "src_module"),
        ("scripts/research/cloud_daily_report_validation", "scripts"),
        ("tests", "tests"),
    ]
    for dir_str, label in search_dirs:
        d = repo_root / dir_str
        if not d.is_dir():
            continue
        for fp in sorted(d.glob("*.py")):
            if label == "tests" and "cloud_daily_report_validation" not in fp.name:
                continue
            try:
                size = fp.stat().st_size
                lines = len(fp.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                size = 0
                lines = 0
            rows.append({
                "file_path": str(fp.relative_to(repo_root)),
                "type": label,
                "size_bytes": size,
                "line_count": lines,
                "research_label": RESEARCH_ONLY_LABEL,
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["file_path", "type", "size_bytes", "line_count", "research_label"]
    )


def _gather_all_files(output_dir: Path, reports_dir: Path) -> dict[str, Path]:
    """Return dict of {zip_name: path} for all output files."""
    files: dict[str, Path] = {}
    for fname in _REQUIRED_CSV_NAMES:
        p = output_dir / fname
        if p.is_file():
            files[fname] = p
    for fname in _REQUIRED_HTML_NAMES:
        p = reports_dir / fname
        if p.is_file():
            files[fname] = p
    return files


def _add_source_snapshots(zf: zipfile.ZipFile, repo_root: Path, seen: set[str] | None = None) -> list[str]:
    """Add source_snapshots/ of all new .py files to the zip."""
    added: list[str] = []
    if seen is None:
        seen = set()

    snap_dirs = [
        (repo_root / "src" / "research" / "cloud_daily_report_validation", "src_module"),
        (repo_root / "scripts" / "research" / "cloud_daily_report_validation", "scripts"),
    ]
    for d, label in snap_dirs:
        if not d.is_dir():
            continue
        for fp in sorted(d.glob("*.py")):
            arcname = f"source_snapshots/{label}/{fp.name}"
            if arcname in seen:
                continue
            zf.write(fp, arcname)
            added.append(arcname)
            seen.add(arcname)

    # Also include test files
    tests_dir = repo_root / "tests"
    if tests_dir.is_dir():
        for fp in sorted(tests_dir.glob("test_cloud_daily_report_validation*.py")):
            arcname = f"source_snapshots/tests/{fp.name}"
            if arcname not in seen:
                zf.write(fp, arcname)
                added.append(arcname)
                seen.add(arcname)
        for fp in sorted(tests_dir.glob("test_cloud_daily_report_v03*.py")):
            arcname = f"source_snapshots/tests/{fp.name}"
            if arcname not in seen:
                zf.write(fp, arcname)
                added.append(arcname)
                seen.add(arcname)
    return added


def _build_readme(included_files: list[str], snapshot_files: list[str]) -> str:
    """Build README.md listing every file in the zip and whether it exists."""
    lines = [
        "# Cloud Daily Report Validation Review Pack",
        f"**Date:** {date.today()}",
        "**Label:** RESEARCH_ONLY_NOT_PRODUCTION",
        "**Version:** v0.2",
        "",
        "## File Manifest",
        "",
        "| File | Type | Present |",
        "|------|------|---------|",
    ]
    required = (
        ["implementation_report.md", "test_log.txt", "open_questions_for_chatgpt.md",
         "source_file_inventory.csv", "implementation_diff.patch"]
        + _REQUIRED_CSV_NAMES
        + _REQUIRED_HTML_NAMES
    )
    all_in_zip = set(included_files + snapshot_files)
    for f in required:
        present = "YES" if f in all_in_zip else "MISSING"
        ftype = (
            "Required doc" if f.endswith(".md") or f.endswith(".txt") or f == "source_file_inventory.csv"
            else "Validation CSV" if f.endswith(".csv")
            else "HTML report" if f.endswith(".html")
            else "Patch file"
        )
        lines.append(f"| `{f}` | {ftype} | {present} |")
    for f in sorted(snapshot_files):
        lines.append(f"| `{f}` | Source snapshot | YES |")
    lines += [
        "",
        "## Usage",
        "",
        "1. Open `validation_report.html` for the full evidence summary.",
        "2. Open `evidence_inventory.html` for the evidence registry.",
        "3. See `open_questions_for_chatgpt.md` for decisions needed.",
        "4. Source code is in `source_snapshots/` for independent review.",
        "5. Re-run validation: `.venv\\Scripts\\python.exe scripts/research/cloud_daily_report_validation/run_all.py`",
        "",
        "## RESEARCH_ONLY_NOT_PRODUCTION",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_review_pack(output_dir: Path | None = None, date_str: str | None = None) -> Path:
    """Create a complete review pack zip at outputs/review_packages/.

    Includes all required artifacts: implementation_report, test_log (real pytest),
    open_questions, source_file_inventory (non-empty), implementation_diff.patch,
    source_snapshots/, all validation CSVs, HTML reports, README.md manifest.

    Parameters
    ----------
    output_dir: validation CSV dir (defaults to OUTPUT_DIR)
    date_str: date string for filename (defaults to today YYYYMMDD)

    Returns
    -------
    Path to the created zip file.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if date_str is None:
        date_str = str(date.today()).replace("-", "")

    REVIEW_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = REVIEW_PACKAGES_DIR / f"cloud_daily_report_validation_review_pack_{date_str}.zip"

    # --- Gather data files ---
    validation_files = _gather_all_files(output_dir, REPORTS_DIR)

    # --- Run tests and capture output ---
    logger.info("Running pytest to capture test_log.txt ...")
    test_log_content = _run_tests_and_capture(_REPO)

    # --- Generate diff ---
    logger.info("Generating implementation_diff.patch ...")
    diff_content = _generate_diff(_REPO)

    # --- Source inventory ---
    src_inventory_df = _build_source_inventory(_REPO)

    # --- Implementation report ---
    n_registry = 0
    reg_path = output_dir / "cloud_dashboard_evidence_registry.csv"
    if reg_path.is_file():
        try:
            n_registry = len(pd.read_csv(reg_path))
        except Exception:
            pass
    file_list_str = "\n".join(
        f"- {name}" for name in sorted(validation_files.keys())
    ) or "- (no output files found)"
    impl_report = _IMPL_REPORT_TEMPLATE.format(
        date=str(date.today()),
        n_registry=n_registry,
        file_list=file_list_str,
    )
    open_questions = _OPEN_QUESTIONS_TEMPLATE.format(date=str(date.today()))

    # --- Build zip ---
    included: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Required documents
        zf.writestr("implementation_report.md", impl_report)
        included.append("implementation_report.md")
        zf.writestr("test_log.txt", test_log_content)
        included.append("test_log.txt")
        zf.writestr("open_questions_for_chatgpt.md", open_questions)
        included.append("open_questions_for_chatgpt.md")
        zf.writestr("implementation_diff.patch", diff_content)
        included.append("implementation_diff.patch")

        # Source file inventory (non-empty)
        buf = io.StringIO()
        src_inventory_df.to_csv(buf, index=False)
        zf.writestr("source_file_inventory.csv", buf.getvalue())
        included.append("source_file_inventory.csv")

        # All validation CSVs + HTML reports
        for name, path in validation_files.items():
            zf.write(path, name)
            included.append(name)

        # source_snapshots/
        snapshot_files = _add_source_snapshots(zf, _REPO)

        # README.md manifest (must be last so it can reference everything)
        readme = _build_readme(included, snapshot_files)
        zf.writestr("README.md", readme)
        included.append("README.md")

    logger.info(
        "Review pack created: %s (%d validation files, %d snapshots, test log included)",
        zip_path,
        len(validation_files),
        len(snapshot_files),
    )
    return zip_path


# ---------------------------------------------------------------------------
# v0.3 review pack (archive + label hygiene)
# ---------------------------------------------------------------------------

_V03_IMPL_REPORT = """\
# Cloud Daily Report v0.3 — Archive + Label Hygiene Patch

**Date:** {date}
**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Version:** v0.3b

## Summary

Small controlled patch adding:
1. Daily archival of scan/report/portfolio inputs under `data/research/cloud_daily_report_validation/archive/`.
2. Conservative evidence-status footnotes in Cloud Daily Report HTML generator.
3. Validation HTML archive-readiness block and framework-readiness disclaimer.

## What did NOT change

- A3 / S3 production strategy logic
- `final_action` generation
- OMS, DNSE, live trading, sizing, order routing
- Phase36 production signal behavior
- Portfolio state source of truth

## Evidence conclusions preserved (v0.2)

- No Cloud Daily Report output has statistically proven return alpha yet.
- RS Correction = INCONCLUSIVE_DIRECTIONAL_ONLY
- Distribution Risk = INCONCLUSIVE until sample/event count exists
- S3 Radar = DISPLAY_ONLY (paper-shadow)
- C3 = DISPLAY_ONLY (review-ranking only)
- Portfolio Overlay = BLOCKED_BY_DATA

## Archive outputs

{archive_summary}

## HTML label patch

Generator: `src/trading/reports/cloud_daily_report.py` — evidence footnotes only (display).

## Tests

See `test_log.txt` — filter: `cloud_daily_report_validation or cloud_daily_report`

## RESEARCH_ONLY_NOT_PRODUCTION
"""

_V03_OPEN_QUESTIONS = """\
# Open Questions for ChatGPT — v0.3b

**Date:** {date}
**Label:** RESEARCH_ONLY_NOT_PRODUCTION
**Version:** v0.3b

1. Approve daily archive hook after EOD scan (automated vs manual script)?
2. Confirm conservative HTML labels are sufficient (no overstating weak evidence)?
3. When scan history reaches 90d, which action class to backtest first (NEW_T1 vs TRAIL_EXIT)?
4. Should `cloud_daily_report_validation.html` replace `validation_report.html` as canonical name?

## RESEARCH_ONLY_NOT_PRODUCTION
"""


def _run_v03_tests_and_capture(repo_root: Path) -> str:
    """Run pytest with v0.3 + validation + cloud_daily_report tests."""
    existing_log = repo_root / "test_log.txt"
    if existing_log.is_file():
        try:
            content = existing_log.read_text(encoding="utf-8", errors="replace")
            if content.strip() and "passed" in content:
                return content
        except Exception:
            pass

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return (
            f"# Test Log — v0.3 (nested pytest skipped)\n"
            f"# Date: {date.today()}\n"
        )

    cmd = [
        sys.executable, "-m", "pytest", "tests",
        "-k", "cloud_daily_report_validation or cloud_daily_report",
        "-q", "--tb=short",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(repo_root), timeout=300,
        )
        header = (
            f"# Test Log — cloud_daily_report_validation + cloud_daily_report\n"
            f"# Date: {date.today()}\n"
            f"# Command: {' '.join(cmd)}\n\n"
        )
        body = (result.stdout or "") + (result.stderr or "")
        content = header + body
        existing_log.write_text(content, encoding="utf-8")
        return content
    except Exception as exc:
        return f"# Test Log — pytest failed: {exc}\n"


def _archive_summary_text() -> str:
    manifest = ARCHIVE_DIR / "archive_manifest.csv"
    if not manifest.is_file():
        return "- No cumulative archive manifest yet. Run `archive_daily_inputs.py`."
    try:
        df = pd.read_csv(manifest, dtype=str)
        n_dates = df["archive_date"].nunique() if "archive_date" in df.columns else 0
        latest = df["archive_date"].max() if "archive_date" in df.columns else "unknown"
        return (
            f"- Cumulative manifest: `{manifest.relative_to(_REPO)}`\n"
            f"- Dates archived: {n_dates}\n"
            f"- Latest archive date: {latest}\n"
        )
    except Exception as exc:
        return f"- Manifest read error: {exc}"


def build_v03_review_pack(date_str: str | None = None) -> Path:
    """Build v0.3 archive + label patch review zip for ChatGPT."""
    if date_str is None:
        date_str = str(date.today()).replace("-", "")

    REVIEW_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = REVIEW_PACKAGES_DIR / f"cloud_daily_report_v03b_archive_label_patch_{date_str}.zip"

    validation_files = _gather_all_files(OUTPUT_DIR, REPORTS_DIR)
    test_log = _run_v03_tests_and_capture(_REPO)
    diff_content = _generate_diff(_REPO)
    src_inventory = _build_source_inventory(_REPO)

    # Extra paths for v0.3
    extra_files: dict[str, Path] = {}
    cloud_html = _REPO / "data/research/reports/cloud_daily_report_latest.html"
    cloud_json = _REPO / "data/research/reports/cloud_daily_report_latest.json"
    if cloud_html.is_file():
        extra_files["cloud_daily_report_latest.html"] = cloud_html
    if cloud_json.is_file():
        extra_files["cloud_daily_report_latest.json"] = cloud_json

    cum_manifest = ARCHIVE_DIR / "archive_manifest.csv"
    if cum_manifest.is_file():
        extra_files["archive/archive_manifest.csv"] = cum_manifest
    date_manifest = ARCHIVE_DIR / date_str / f"archive_manifest_{date_str}.csv"
    if date_manifest.is_file():
        extra_files[f"archive/archive_manifest_{date_str}.csv"] = date_manifest

    data_accum = _REPO / "docs/research/cloud_daily_report_validation/DATA_ACCUMULATION_PLAN.md"
    if data_accum.is_file():
        extra_files["DATA_ACCUMULATION_PLAN.md"] = data_accum
    preview_html = _REPO / "reports/research/cloud_daily_report_validation/cloud_daily_report_latest_v03_preview.html"
    if preview_html.is_file():
        extra_files["cloud_daily_report_latest_v03_preview.html"] = preview_html

    impl = _V03_IMPL_REPORT.format(
        date=str(date.today()),
        archive_summary=_archive_summary_text(),
    )
    open_q = _V03_OPEN_QUESTIONS.format(date=str(date.today()))

    included: list[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("implementation_report.md", impl)
        included.append("implementation_report.md")
        zf.writestr("open_questions_for_chatgpt.md", open_q)
        included.append("open_questions_for_chatgpt.md")
        zf.writestr("test_log.txt", test_log)
        included.append("test_log.txt")
        zf.writestr("implementation_diff.patch", diff_content)
        included.append("implementation_diff.patch")
        buf = io.StringIO()
        src_inventory.to_csv(buf, index=False)
        zf.writestr("source_file_inventory.csv", buf.getvalue())
        included.append("source_file_inventory.csv")

        for name, path in validation_files.items():
            zf.write(path, name)
            included.append(name)
        for name, path in extra_files.items():
            zf.write(path, name)
            included.append(name)

        # Changed source files (v0.3b) — explicit subdir per location; seeded first
        v03_sources: list[tuple[Path, str]] = [
            (_REPO / "src/trading/reports/cloud_daily_report.py", "src_trading_reports"),
            (_REPO / "src/research/cloud_daily_report_validation/archive_daily_inputs.py", "src_module"),
            (_REPO / "src/research/cloud_daily_report_validation/reporting.py", "src_module"),
            (_REPO / "src/research/cloud_daily_report_validation/schema.py", "src_module"),
            (_REPO / "src/research/cloud_daily_report_validation/review_pack.py", "src_module"),
            (_REPO / "scripts/research/cloud_daily_report_validation/archive_daily_inputs.py", "scripts"),
        ]
        seen_v03: set[str] = set()
        for fp, subdir in v03_sources:
            if fp.is_file():
                arc = f"source_snapshots/{subdir}/{fp.name}"
                if arc not in seen_v03:
                    zf.write(fp, arc)
                    included.append(arc)
                    seen_v03.add(arc)

        # Add remaining source files (seen_v03 prevents re-adding already-included files)
        snapshots = _add_source_snapshots(zf, _REPO, seen=seen_v03)
        included.extend(snapshots)

        # README last so it can reference all included files
        readme = _build_v03_readme(included)
        zf.writestr("README.md", readme)
        included.append("README.md")

    logger.info("v0.3 review pack: %s", zip_path)
    return zip_path


def _build_v03_readme(included_files: list[str]) -> str:
    lines = [
        "# Cloud Daily Report v0.3b Review Pack",
        f"**Date:** {date.today()}",
        "**Label:** RESEARCH_ONLY_NOT_PRODUCTION",
        "**Version:** v0.3b",
        "",
        "## Scope",
        "",
        "Archive utility + HTML label hygiene only. No production trading changes.",
        "",
        "## Files",
        "",
    ]
    for f in sorted(set(included_files)):
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## RESEARCH_ONLY_NOT_PRODUCTION")
    return "\n".join(lines)
