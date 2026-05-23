"""
Build institutional_accumulation_scan_chatgpt.zip for ChatGPT QA + optimization.

Fail-closed: aborts if outputs, prompt claims, or tests do not match PACKAGE_INTEGRITY.json rules.

Usage:
  python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-04-30
  python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-04-30 --no-refresh
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "outputs" / "review_packages"
OUT_ZIP = OUT_DIR / "institutional_accumulation_scan_chatgpt.zip"
EXTRACT_DIR_NAME = "institutional_accumulation_scan_chatgpt"
STALE_MARKER = "STALE_EXTRACT_DO_NOT_REVIEW.txt"
REVIEW_PACKAGES_README = "README_DO_NOT_USE_EXTRACTED_COPIES.txt"

PROMPT_ORCHESTRATOR = (
    "docs/trading/CHATGPT_INSTITUTIONAL_ACCUMULATION_SCAN_REVIEW_PROMPT.md",
    "REVIEW_PROMPT.md",
)

FILES: list[tuple[str, str]] = [
    PROMPT_ORCHESTRATOR,
    ("docs/trading/INSTITUTIONAL_ACCUMULATION_REVIEW_WORKFLOW.md", "WORKFLOW.md"),
    (
        "docs/trading/CLAUDE_CODE_INSTITUTIONAL_ACCUMULATION_REVIEW_PROMPT.md",
        "prompts/CLAUDE_CODE_REVIEW_PROMPT.md",
    ),
    (
        "docs/trading/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md",
        "prompts/INSTITUTIONAL_ACCUMULATION_WEEKLY_REPORT_SPEC.md",
    ),
    (
        "docs/trading/RETURN_HANDOVER_TO_CHATGPT_TEMPLATE.md",
        "prompts/RETURN_HANDOVER_TO_CHATGPT_TEMPLATE.md",
    ),
    ("docs/trading/CURSOR_IMPLEMENTATION_TEMPLATE.md", "prompts/CURSOR_IMPLEMENTATION_TEMPLATE.md"),
    ("docs/trading/INSTITUTIONAL_ACCUMULATION_SCAN.md", "docs/INSTITUTIONAL_ACCUMULATION_SCAN.md"),
    ("docs/research/VIN_EMA_CLOUD_BASELINE.md", "docs/VIN_EMA_CLOUD_BASELINE.md"),
    ("docs/SMART_MONEY_DATA_CONTRACT.md", "docs/SMART_MONEY_DATA_CONTRACT.md"),
    (
        "data/smart_money/priors/apr2026_default_priors.json",
        "data/smart_money/priors/apr2026_default_priors.json",
    ),
    (
        "data/smart_money/_template.smart_money_month.json",
        "data/smart_money/_template.smart_money_month.json",
    ),
    (
        "data/decision/institutional_accumulation_compact.json",
        "outputs/institutional_accumulation_compact.json",
    ),
    (
        "tests/test_institutional_accumulation_scan.py",
        "tests/test_institutional_accumulation_scan.py",
    ),
]

SCAN_GLOB = REPO / "src" / "scans" / "institutional_accumulation"
SPOT_CHECK_SYMBOLS = ["MBB", "CTG", "MWG", "HPG", "GMD", "VIC", "VHM", "VCB", "STB", "PNJ", "FPT", "BID"]

REQUIRED_SCAN_OUTPUTS = [
    "institutional_accumulation_{as_of}.csv",
    "institutional_accumulation_{as_of}_top80.csv",
    "institutional_accumulation_{as_of}.json",
    "institutional_accumulation_{as_of}.md",
    "emerging_accumulation_{as_of}.csv",
]


def _review_packages_readme_text() -> str:
    return """Institutional Accumulation Scan — review package directory

IMPORTANT
=========
- Review ONLY the file: institutional_accumulation_scan_chatgpt.zip
- Do NOT review extracted copies in subfolders under this directory.
- Extracted folders may be STALE and will not auto-refresh when the zip is rebuilt.

Source of truth inside the zip:
- PACKAGE_INTEGRITY.json (machine-readable metrics + hashes)
- outputs/institutional_accumulation_{date}.csv

Rebuild:
  python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of YYYY-MM-DD
"""


def _stale_marker_text(built_at: str) -> str:
    return f"""STALE — DO NOT USE FOR REVIEW

This folder is an old manual extraction of institutional_accumulation_scan_chatgpt.zip.
It is NOT updated when the zip is rebuilt.

Use only: outputs/review_packages/institutional_accumulation_scan_chatgpt.zip
Built/archived at: {built_at}
"""


def _handle_stale_extracted_folder() -> str | None:
    """Archive stale extracted review dir; return archive path if moved."""
    extract = OUT_DIR / EXTRACT_DIR_NAME
    if not extract.is_dir():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root = OUT_DIR / "_archive_stale_extracts"
    archive_root.mkdir(parents=True, exist_ok=True)
    dest = archive_root / f"{EXTRACT_DIR_NAME}_{ts}"
    marker = _stale_marker_text(ts)
    (extract / STALE_MARKER).write_text(marker, encoding="utf-8")
    shutil.move(str(extract), str(dest))
    print(f"Archived stale extracted folder -> {dest}")
    return str(dest)


def _write_review_packages_readme() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / REVIEW_PACKAGES_README).write_text(_review_packages_readme_text(), encoding="utf-8")


def _readme_zip(zip_name: str, as_of: str, integrity: dict, *, refresh_scan: bool) -> str:
    mode = "refresh+build" if refresh_scan else "no-refresh (packaged existing outputs only)"
    return f"""Institutional Accumulation Scan v1.1 — ChatGPT review package
Built: {integrity.get('package_built_at')}
Zip: {zip_name}
As-of: {as_of}
Build mode: {mode}

REVIEW SAFETY (read first)
==========================
- Review THIS zip only — not previously extracted folders under review_packages/.
- PACKAGE_INTEGRITY.json is the machine-readable source of truth for row counts and emerging count.
- REVIEW_PROMPT.md claims must match PACKAGE_INTEGRITY.json.

Integrity snapshot:
  rows_scored={integrity.get('rows_scored')}
  emerging_count={integrity.get('emerging_count')}
  etf_excluded_e1vfvn30={integrity.get('etf_excluded_e1vfvn30')}
  vic_emerging={integrity.get('vic_emerging')}
  vhm_daily_cmf_missing={integrity.get('vhm_daily_cmf_missing')}
  tests_passed={integrity.get('tests_passed')} ({integrity.get('tests_passed_count')} tests)
  validator_status={integrity.get('validator_status')}

REGENERATE (refresh scan + zip):
  python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of {as_of}

Package only (no scan):
  python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of {as_of} --no-refresh
"""


def _consensus_spot_check_reference(as_of: str) -> str:
    priors_path = REPO / "data/smart_money/priors/apr2026_default_priors.json"
    priors = json.loads(priors_path.read_text(encoding="utf-8")) if priors_path.is_file() else {}
    rows = []
    for t in priors.get("consensus_core") or []:
        rows.append({"ticker": t, "fund_context_bucket": "consensus_core"})
    for t in priors.get("consensus_second_ring") or []:
        rows.append({"ticker": t, "fund_context_bucket": "consensus_second_ring"})
    for t in priors.get("commentary_mentions") or []:
        if t not in {r["ticker"] for r in rows}:
            rows.append({"ticker": t, "fund_context_bucket": "fund_commentary_mention"})
    for t in priors.get("selective_fund_bets") or []:
        if t not in {r["ticker"] for r in rows}:
            rows.append({"ticker": t, "fund_context_bucket": "selective_fund_bet"})
    ref = pd.DataFrame(rows)
    scan_csv = REPO / "outputs" / "scans" / f"institutional_accumulation_{as_of}.csv"
    if scan_csv.is_file():
        act = pd.read_csv(scan_csv)
        keep = [
            "ticker",
            "tier",
            "institutional_accumulation_score",
            "fund_context_bucket",
            "has_fund_disclosure_tag",
            "emerging_accumulation_candidate",
            "score_money_flow",
            "score_context",
            "vingroup_distortion_flag",
            "vingroup_distortion_diagnosis",
        ]
        keep = [c for c in keep if c in act.columns]
        act = act[act["ticker"].isin(ref["ticker"]) | act["ticker"].isin(SPOT_CHECK_SYMBOLS)][keep]
        ref = ref.merge(act, on="ticker", how="outer")
    return ref.to_csv(index=False)


def _run_full_scan(as_of: str, smart_money_month: str | None = None) -> None:
    cmd = [sys.executable, "-m", "src.scans.institutional_accumulation.run", "--as-of", as_of]
    if smart_money_month:
        cmd.extend(["--smart-money-month", smart_money_month])
    print("Running FULL universe scan:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(REPO), check=False)
    if r.returncode != 0:
        print(f"ERROR: scan exited {r.returncode}", file=sys.stderr)
        raise SystemExit(1)


def _require_scan_outputs(as_of: str) -> None:
    scans = REPO / "outputs" / "scans"
    missing = []
    for pattern in REQUIRED_SCAN_OUTPUTS:
        p = scans / pattern.format(as_of=as_of)
        if not p.is_file():
            missing.append(str(p.relative_to(REPO)))
    if missing:
        print("ERROR: required scan outputs missing:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        raise SystemExit(1)


def build(
    as_of: str = "2026-04-30",
    refresh_scan: bool = True,
    smart_money_month: str | None = "2026-04",
) -> Path:
    from scripts.reporting.validate_institutional_accumulation_package import validate

    _write_review_packages_readme()
    archived = _handle_stale_extracted_folder()
    if archived:
        print(f"(stale extract archived; do not review {archived})")

    if refresh_scan:
        print("BUILD MODE: refresh + build (full scan then package)")
        _run_full_scan(as_of, smart_money_month=smart_money_month)
    else:
        print("=" * 72)
        print("WARNING: BUILD MODE = --no-refresh")
        print("Packaging EXISTING outputs/scans/ only. No scan rerun.")
        print("If code changed, run without --no-refresh first.")
        print("=" * 72)

    _require_scan_outputs(as_of)

    errors, integrity = validate(as_of, check_prompt=True, require_tests=True)
    if errors:
        print("PACKAGE_INTEGRITY_FAIL — zip build aborted (fail-closed)", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise SystemExit(1)

    integrity["package_built_at"] = datetime.now(timezone.utc).isoformat()
    integrity["build_mode"] = "refresh+build" if refresh_scan else "no-refresh"
    integrity["smart_money_month"] = smart_money_month
    integrity["market_scan_as_of"] = as_of
    if archived:
        integrity["stale_extract_archived"] = archived

    integrity_json = json.dumps(integrity, indent=2, ensure_ascii=False)
    scans = REPO / "outputs" / "scans"
    (scans / "PACKAGE_INTEGRITY.json").write_text(integrity_json, encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme_zip(OUT_ZIP.name, as_of, integrity, refresh_scan=refresh_scan))
        manifest.append("README.txt")

        zf.writestr("PACKAGE_INTEGRITY.json", integrity_json)
        manifest.append("PACKAGE_INTEGRITY.json")

        for rel, arc in FILES:
            src = REPO / rel
            if not src.is_file():
                print(f"ERROR: required package file missing: {rel}", file=sys.stderr)
                raise SystemExit(1)
            zf.write(src, arc)
            manifest.append(arc)

        if SCAN_GLOB.is_dir():
            zf.write(SCAN_GLOB / "__init__.py", "src/scans/institutional_accumulation/__init__.py")
            scans_init = REPO / "src" / "scans" / "__init__.py"
            if scans_init.is_file():
                zf.write(scans_init, "src/scans/__init__.py")
            for py in sorted(SCAN_GLOB.glob("*.py")):
                if py.name == "__init__.py":
                    continue
                arc = f"src/scans/institutional_accumulation/{py.name}"
                zf.write(py, arc)
                manifest.append(arc)

        for pattern in [
            *REQUIRED_SCAN_OUTPUTS,
            "institutional_accumulation_diff_{as_of}.json",
            "institutional_accumulation_latest.csv",
            "PACKAGE_INTEGRITY_AUDIT_20260521.md",
            "institutional_accumulation_operator_summary_{as_of}.md",
            "institutional_accumulation_operator_summary_{as_of}.html",
            "institutional_accumulation_operator_summary_{as_of}.json",
            "institutional_accumulation_weekly_brief_{as_of}.md",
            "institutional_accumulation_weekly_brief_{as_of}.html",
            "institutional_accumulation_compact_{as_of}.json",
        ]:
            name = pattern.format(as_of=as_of) if "{as_of}" in pattern else pattern
            p = scans / name
            if not p.is_file() and name in [x.format(as_of=as_of) for x in REQUIRED_SCAN_OUTPUTS]:
                print(f"ERROR: required output missing in zip: {name}", file=sys.stderr)
                raise SystemExit(1)
            if p.is_file():
                zf.write(p, f"outputs/{name}")
                manifest.append(f"outputs/{name}")

        zf.writestr("outputs/consensus_spot_check_reference.csv", _consensus_spot_check_reference(as_of))
        manifest.append("outputs/consensus_spot_check_reference.csv")

        manifest.append("PACKAGE_INTEGRITY.json")
        zf.writestr("MANIFEST.txt", "\n".join(sorted(set(manifest))))

    print(f"\nWrote {OUT_ZIP} ({OUT_ZIP.stat().st_size / 1024:.1f} KB, {len(set(manifest))} files)")
    print("validator_status:", integrity["validator_status"])
    print("ChatGPT: upload zip + paste REVIEW_PROMPT.md")
    return OUT_ZIP


def main() -> None:
    ap = argparse.ArgumentParser(description="Build ChatGPT review zip (fail-closed integrity).")
    ap.add_argument("--as-of", default="2026-04-30")
    ap.add_argument(
        "--smart-money-month",
        default="2026-04",
        help="Fund disclosure context month (default 2026-04 = April priors). Market OHLCV still uses --as-of.",
    )
    ap.add_argument(
        "--no-refresh",
        action="store_true",
        help="Package existing outputs/scans only; does NOT rerun scan.",
    )
    args = ap.parse_args()
    sm = args.smart_money_month.strip() if args.smart_money_month else None
    build(as_of=args.as_of, refresh_scan=not args.no_refresh, smart_money_month=sm)


if __name__ == "__main__":
    main()
