# Implementation Status Patch Notes (Round 2)

Date: 2026-05-16

---

## Problem

Previous version of `S3_UPGRADE_IMPLEMENTATION_NOTES.md` had a section titled
"Code Changes Needed in portfolio_optimization_final_steps.py" — but the surrounding
context implied the package was complete ("All 8 tasks complete").

This created ambiguity: is Phase35 implemented in code, or is this a spec/handoff?

---

## Clarification

**This is a HANDOFF / SPEC PACKAGE.**

Code changes to `portfolio_optimization_final_steps.py` are PENDING — not yet implemented.

The scan script still produces Phase34 output (37 fields). The Phase35 schema (47 fields)
is a specification for what the scan should output after code changes.

---

## Fix Applied

`S3_UPGRADE_IMPLEMENTATION_NOTES.md` updated:
- Added prominent header: "HANDOFF / SPEC PACKAGE ONLY — Code changes PENDING"
- Renamed section from "Code Changes Needed" to "Pending Code Changes"
- Added "Open Items (Code — Not Yet Done)" table with priority levels
- Removed any implication that code changes were already applied

`UPDATED_FINAL_OPEN_ITEMS.md`:
- Phase35 scan notes now say "47 fields, validated clean" (schema/sample correct)
- No claim of code implementation

---

## What IS Complete

- All classification documents updated
- Phase35 schema (47 fields) defined and validated
- Phase35 sample CSV clean (47 fields per row, verified)
- AFL with locked max_hold=60
- Paper ledger headers
- Dashboard spec, runbook, rules, tests — all as spec/docs

## What Is NOT Complete (Code)

- `run_scan()` still outputs Phase34 (37 fields)
- `strategy_classification` not yet updated to assign S3_PAPER_SHADOW
- Order router guard for S3_PAPER_SHADOW not yet in code
- Paper ledger load not yet connected to scan state
- `tests/test_s3_shadow_containment.py` not yet created
