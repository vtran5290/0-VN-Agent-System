"""
Package integrity validation for Institutional Accumulation Scan review zip.

Fail-closed: build must not proceed when outputs, prompt claims, or tests disagree.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SCANS = REPO / "outputs" / "scans"
PROMPT_PATH = REPO / "docs/trading/CHATGPT_INSTITUTIONAL_ACCUMULATION_SCAN_REVIEW_PROMPT.md"
TEST_MODULE = "tests/test_institutional_accumulation_scan.py"
METHODOLOGY_VERSION = "v1.1"
EXPECTED_TEST_COUNT = 17


@dataclass(frozen=True)
class PromptClaims:
    """Numeric/text claims embedded in REVIEW_PROMPT.md (must match measured outputs)."""

    rows_scored: int
    emerging_count: int
    tests_passed: int
    vic_not_emerging: bool
    etf_e1vfvn30_absent: bool
    vhm_daily_cmf_missing: bool


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (r.stdout or "").strip() if r.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _git_status_summary() -> str:
    try:
        r = subprocess.run(
            ["git", "status", "--short", "--", "src/scans/institutional_accumulation", "tests/test_institutional_accumulation_scan.py", "scripts/reporting"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
        )
        lines = [ln for ln in (r.stdout or "").strip().splitlines() if ln.strip()]
        return f"{len(lines)} changed paths" if lines else "clean (scoped paths)"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def _run_tests() -> tuple[bool, int | None, str]:
    """Run pytest on institutional accumulation tests; return (passed, count, summary)."""
    if not (REPO / TEST_MODULE).is_file():
        return False, None, "test file missing"
    cmd = [sys.executable, "-m", "pytest", TEST_MODULE, "-q", "--tb=no"]
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, None, str(e)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"(\d+)\s+passed", out)
    n_passed = int(m.group(1)) if m else None
    ok = r.returncode == 0 and n_passed == EXPECTED_TEST_COUNT
    summary = out.strip().splitlines()[-1] if out.strip() else f"exit_code={r.returncode}"
    return ok, n_passed, summary


def parse_prompt_claims(prompt_text: str) -> PromptClaims | None:
    """Extract review-package claims from orchestrator markdown."""
    rows_m = re.search(r"Rows scored\s*\|\s*\*\*(\d+)\*\*", prompt_text)
    emerg_m = re.search(r"Emerging candidates\s*\|\s*\*\*(\d+)\*\*", prompt_text)
    tests_m = re.search(r"\*\*(\d+)\s+passed\*\*", prompt_text)
    if not (rows_m and emerg_m and tests_m):
        return None
    vic_not = bool(re.search(r"VIC\s+\*\*not\*\*\s+emerging", prompt_text, re.I))
    etf_absent = bool(re.search(r"E1VFVN30\s+absent", prompt_text, re.I))
    return PromptClaims(
        rows_scored=int(rows_m.group(1)),
        emerging_count=int(emerg_m.group(1)),
        tests_passed=int(tests_m.group(1)),
        vic_not_emerging=vic_not,
        etf_e1vfvn30_absent=etf_absent,
        vhm_daily_cmf_missing=False,  # P1-c is conditional; not a flat output claim
    )


def collect_integrity_facts(as_of: str = "2026-04-30") -> dict[str, Any]:
    """Measure source-of-truth facts from disk outputs (not from prompt)."""
    csv_path = SCANS / f"institutional_accumulation_{as_of}.csv"
    json_path = SCANS / f"institutional_accumulation_{as_of}.json"
    emerg_path = SCANS / f"emerging_accumulation_{as_of}.csv"

    facts: dict[str, Any] = {
        "scan_date": as_of,
        "methodology_version": METHODOLOGY_VERSION,
        "csv_exists": csv_path.is_file(),
        "rows_scored": None,
        "emerging_count": None,
        "etf_excluded_e1vfvn30": None,
        "vic_emerging": None,
        "vhm_daily_cmf_missing": None,
        "json_emerging_count": None,
        "emerging_csv_rows": None,
        "tests_present": (REPO / TEST_MODULE).is_file(),
        "tests_passed": None,
        "tests_passed_count": None,
        "tests_summary": None,
        "output_file_hashes": {},
    }

    if not csv_path.is_file():
        return facts

    df = pd.read_csv(csv_path)
    facts["rows_scored"] = int(len(df))
    facts["emerging_count"] = int((df["emerging_accumulation_candidate"] == True).sum())  # noqa: E712
    facts["etf_excluded_e1vfvn30"] = "E1VFVN30" not in df["ticker"].values
    if "VIC" in df["ticker"].values:
        facts["vic_emerging"] = bool(df.loc[df["ticker"] == "VIC"].iloc[0]["emerging_accumulation_candidate"])
    if "VHM" in df["ticker"].values:
        vhm_row = df.loc[df["ticker"] == "VHM"].iloc[0]
        diag = str(vhm_row.get("vingroup_distortion_diagnosis", "") or "")
        vin_flag = bool(vhm_row.get("vingroup_distortion_flag", False))
        facts["vhm_distortion_flag"] = vin_flag
        facts["vhm_daily_cmf_missing_in_diagnosis"] = "daily_CMF_missing" in diag
        if vin_flag:
            facts["vhm_p1c_check_status"] = (
                "pass" if facts["vhm_daily_cmf_missing_in_diagnosis"] else "fail_missing_in_diagnosis"
            )
        else:
            facts["vhm_p1c_check_status"] = "not_applicable_flag_off"
        # Back-compat field: True only when check passed or N/A (not a claim that string exists in CSV)
        facts["vhm_daily_cmf_missing"] = facts["vhm_p1c_check_status"] in (
            "pass",
            "not_applicable_flag_off",
        )

    if json_path.is_file():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        facts["methodology_version"] = payload.get("methodology_version", METHODOLOGY_VERSION)
        facts["json_emerging_count"] = payload.get("emerging_accumulation", {}).get("count")

    if emerg_path.is_file():
        facts["emerging_csv_rows"] = int(len(pd.read_csv(emerg_path)))

    for name in [
        f"institutional_accumulation_{as_of}.csv",
        f"institutional_accumulation_{as_of}.json",
        f"emerging_accumulation_{as_of}.csv",
        f"institutional_accumulation_{as_of}_top80.csv",
    ]:
        p = SCANS / name
        digest = _sha256(p)
        if digest:
            facts["output_file_hashes"][name] = digest

    tests_ok, n_passed, summary = _run_tests()
    facts["tests_passed"] = tests_ok
    facts["tests_passed_count"] = n_passed
    facts["tests_summary"] = summary

    return facts


def validate(
    as_of: str = "2026-04-30",
    *,
    check_prompt: bool = True,
    require_tests: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    """
    Full integrity validation. Returns (errors, integrity_payload).
    Empty errors => OK to build zip.
    """
    errors: list[str] = []
    facts = collect_integrity_facts(as_of)

    if not facts["csv_exists"]:
        errors.append(f"Missing scan CSV for as-of {as_of}")
        payload = _build_integrity_payload(facts, errors, as_of)
        return errors, payload

    if facts["json_emerging_count"] is not None and facts["json_emerging_count"] != facts["emerging_count"]:
        errors.append(
            f"json emerging count {facts['json_emerging_count']} != csv {facts['emerging_count']}"
        )
    if facts["emerging_csv_rows"] is not None and facts["emerging_csv_rows"] != facts["emerging_count"]:
        errors.append(
            f"emerging csv rows {facts['emerging_csv_rows']} != main csv emerging {facts['emerging_count']}"
        )
    if not facts["etf_excluded_e1vfvn30"]:
        errors.append("E1VFVN30 must not appear in main scan CSV")
    if facts["vic_emerging"] is True:
        errors.append("VIC must not be emerging_accumulation_candidate")
    if facts.get("vhm_distortion_flag") and not facts.get("vhm_daily_cmf_missing_in_diagnosis"):
        errors.append(
            "VHM vingroup_distortion_flag=true but diagnosis lacks daily_CMF_missing"
        )
    if facts.get("vhm_p1c_check_status") is None and "VHM" not in str(errors):
        errors.append("VHM not in scan — cannot verify P1-c diagnosis")

    if not facts["tests_present"]:
        errors.append(f"{TEST_MODULE} missing")
    elif require_tests and not facts["tests_passed"]:
        errors.append(
            f"tests must pass ({EXPECTED_TEST_COUNT} expected, got {facts['tests_passed_count']!r}: {facts['tests_summary']})"
        )

    if check_prompt and PROMPT_PATH.is_file():
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
        claims = parse_prompt_claims(prompt_text)
        if claims is None:
            errors.append("Could not parse required claims from REVIEW_PROMPT.md")
        else:
            if claims.rows_scored != facts["rows_scored"]:
                errors.append(
                    f"prompt claims rows {claims.rows_scored} != output {facts['rows_scored']}"
                )
            if claims.emerging_count != facts["emerging_count"]:
                errors.append(
                    f"prompt claims emerging {claims.emerging_count} != output {facts['emerging_count']}"
                )
            if claims.tests_passed != facts["tests_passed_count"]:
                errors.append(
                    f"prompt claims tests {claims.tests_passed} != actual {facts['tests_passed_count']}"
                )
            if claims.vic_not_emerging and facts["vic_emerging"] is True:
                errors.append("prompt claims VIC not emerging but output has VIC emerging=true")
            if claims.etf_e1vfvn30_absent and not facts["etf_excluded_e1vfvn30"]:
                errors.append("prompt claims E1VFVN30 absent but E1VFVN30 is in CSV")
            if facts.get("vhm_p1c_check_status") == "fail_missing_in_diagnosis":
                errors.append("VHM distortion flag on but diagnosis lacks daily_CMF_missing")
    elif check_prompt:
        errors.append(f"Missing prompt file: {PROMPT_PATH}")

    payload = _build_integrity_payload(facts, errors, as_of)
    return errors, payload


def _build_integrity_payload(facts: dict[str, Any], errors: list[str], as_of: str) -> dict[str, Any]:
    return {
        "package_built_at": None,
        "methodology_version": facts.get("methodology_version", METHODOLOGY_VERSION),
        "scan_date": as_of,
        "rows_scored": facts.get("rows_scored"),
        "emerging_count": facts.get("emerging_count"),
        "etf_excluded_e1vfvn30": facts.get("etf_excluded_e1vfvn30"),
        "vic_emerging": facts.get("vic_emerging"),
        "vhm_distortion_flag": facts.get("vhm_distortion_flag"),
        "vhm_daily_cmf_missing_in_diagnosis": facts.get("vhm_daily_cmf_missing_in_diagnosis"),
        "vhm_p1c_check_status": facts.get("vhm_p1c_check_status"),
        "vhm_daily_cmf_missing": facts.get("vhm_daily_cmf_missing"),
        "tests_present": facts.get("tests_present"),
        "tests_passed": facts.get("tests_passed"),
        "tests_passed_count": facts.get("tests_passed_count"),
        "tests_summary": facts.get("tests_summary"),
        "output_file_hashes": facts.get("output_file_hashes", {}),
        "source_branch": _git_branch(),
        "git_status_summary": _git_status_summary(),
        "validator_status": "FAIL" if errors else "PASS",
        "validator_errors": errors,
        "review_safety": {
            "use_zip_only": True,
            "do_not_review_extracted_folders": True,
            "integrity_json_is_source_of_truth": True,
        },
    }


def validate_or_exit(as_of: str = "2026-04-30", *, check_prompt: bool = True) -> dict[str, Any]:
    errors, payload = validate(as_of, check_prompt=check_prompt)
    if errors:
        print("PACKAGE_INTEGRITY_FAIL — build aborted")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print("PACKAGE_INTEGRITY_OK")
    print(f"  rows={payload['rows_scored']} emerging={payload['emerging_count']} tests={payload['tests_passed_count']}")
    return payload


def main() -> int:
    errors, payload = validate()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if errors:
        print("PACKAGE_INTEGRITY_FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("PACKAGE_INTEGRITY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
