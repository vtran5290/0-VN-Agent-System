"""
Phase35 CSV validation — Patch 1 / Test 17-18 verification.

Run from repo root:
    .venv\Scripts\python.exe data\research\portfolio_optimization\missing_work\phase35_csv_validation.py

Checks:
1. Header field count == 47
2. Every data row has exactly 47 fields (no shifted rows)
3. No None key in DictReader (catches extra trailing comma)
4. Categorical fields have no leading/trailing whitespace
"""

import csv
import sys
from pathlib import Path

BASE = Path(__file__).parent
SCHEMA_FILE = BASE / "phase35_daily_scan_schema.csv"
SAMPLE_FILE = BASE / "phase35_daily_scan_sample.csv"

EXPECTED_FIELDS = 47

CATEGORICAL = {
    "final_action",
    "final_action_reason",
    "strategy_classification",
    "recommendation",
    "liq_warn_T1",
    "liq_warn_full",
    "breadth_zone",
    "s3_shadow_final_action",
}

VALID_STRATEGY_CLASSIFICATIONS = {
    "A3_PRODUCTION", "PTS_SHADOW", "S3_PAPER_SHADOW",
    "S3_RESEARCH_ONLY", "WATCH_ONLY", "SKIP",
}

VALID_FINAL_ACTIONS = {
    "NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH", "WAIT_PB", "ADD_T2",
    "HOLD_T1_ONLY", "NO_T2_BREADTH", "SKIP_LIQUIDITY", "SKIP_VNINDEX_BEAR",
    "NEW_S3_SHADOW", "S3_SHADOW_HOLD", "S3_SHADOW_EXIT", "WATCH_ONLY",
}

errors = []
warnings = []


def check_schema():
    with open(SCHEMA_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    field_rows = [r for r in rows[1:] if any(r)]  # skip blank
    n = len(field_rows)
    if n != EXPECTED_FIELDS:
        errors.append(f"SCHEMA: expected {EXPECTED_FIELDS} field rows, got {n}")
    else:
        print(f"  SCHEMA OK: {n} fields")


def check_sample():
    with open(SAMPLE_FILE, newline="", encoding="utf-8") as f:
        raw_rows = list(csv.reader(f))

    header = raw_rows[0]
    n_header = len(header)
    if n_header != EXPECTED_FIELDS:
        errors.append(f"SAMPLE HEADER: expected {EXPECTED_FIELDS} fields, got {n_header}")
        return
    print(f"  SAMPLE HEADER: {n_header} fields OK")

    with open(SAMPLE_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        data_rows = list(reader)

    for i, row in enumerate(data_rows, 1):
        sym = row.get("symbol", f"row_{i}")

        # Check for None key (extra trailing comma)
        if None in row:
            errors.append(f"  {sym}: None key present — extra trailing comma or field shift")
            continue

        # Check field count
        n_row = len(row)
        if n_row != EXPECTED_FIELDS:
            errors.append(f"  {sym}: {n_row} fields, expected {EXPECTED_FIELDS}")
        else:
            print(f"  {sym}: {n_row} fields OK")

        # Check categorical whitespace
        for col in CATEGORICAL:
            val = row.get(col, "")
            if val and val != val.strip():
                errors.append(f"  {sym}.{col}: leading/trailing whitespace: {repr(val)}")

        # Check valid enum values
        sc = row.get("strategy_classification", "").strip()
        if sc and sc not in VALID_STRATEGY_CLASSIFICATIONS:
            errors.append(f"  {sym}.strategy_classification: unknown value {repr(sc)}")

        fa = row.get("final_action", "").strip()
        if fa and fa not in VALID_FINAL_ACTIONS:
            errors.append(f"  {sym}.final_action: unknown value {repr(fa)}")

        s3_fa = row.get("s3_shadow_final_action", "").strip()
        if s3_fa and s3_fa not in VALID_FINAL_ACTIONS:
            errors.append(f"  {sym}.s3_shadow_final_action: unknown value {repr(s3_fa)}")


def check_classification_csv():
    clf = BASE / "updated_final_candidate_classification.csv"
    with open(clf, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    gk_rows = [r for r in rows if r.get("candidate", "").startswith("S3_GK5")]
    for r in gk_rows:
        clf_val = r.get("classification", "")
        if clf_val == "PARALLEL_PAPER_RESEARCH":
            errors.append(f"CLASSIFICATION: S3_GK5_max60_top100 still PARALLEL_PAPER_RESEARCH — should be FUTURE_RETEST_REQUIRED")
        elif clf_val == "FUTURE_RETEST_REQUIRED":
            print(f"  S3_GK5 classification: FUTURE_RETEST_REQUIRED OK")
        else:
            warnings.append(f"  S3_GK5 classification: {clf_val} (unexpected)")


print("=== Phase35 CSV Validation ===")
print(f"\n[1] Schema: {SCHEMA_FILE.name}")
check_schema()

print(f"\n[2] Sample: {SAMPLE_FILE.name}")
check_sample()

print(f"\n[3] Classification CSV")
check_classification_csv()

print()
if errors:
    print(f"FAIL — {len(errors)} error(s):")
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
else:
    if warnings:
        for w in warnings:
            print(f"  WARN: {w}")
    print("ALL CHECKS PASSED")
    sys.exit(0)
