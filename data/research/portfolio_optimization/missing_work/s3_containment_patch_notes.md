# S3 Containment Patch Notes (Round 2)

Date: 2026-05-16

---

## Problem

Previous gate tests (10 tests) covered the main containment scenarios but were written
at a level of abstraction that a reviewer could not easily audit for completeness.

Specifically missing:
- Explicit tests for each S3 final_action enum value (NEW_S3_SHADOW, S3_SHADOW_HOLD, S3_SHADOW_EXIT)
- Test for live_manual / live_auto mode override
- Test for a3_s3_lead_5d only affecting sort order (not size or logic)
- Test for P&L file separation (not just separation of files, but separation of equity curve)
- Schema field count assertion (Test 16)
- Categorical whitespace assertion (Test 18)
- Enum value validation (Test 19-20)

---

## Fix Applied

`S3_SHADOW_GATE_TESTS.md` expanded from 10 to 20 tests, organized into 4 sections:
- A: max_hold and Exit Enforcement (Tests 1-4)
- B: No-Live-Order Containment (Tests 5-10)
- C: A3 Lead Rule and P&L Separation (Tests 11-15)
- D: Schema and Data Integrity (Tests 16-20)

Status: SPEC ONLY — these are behavioral specifications. The automated test file
`tests/test_s3_shadow_containment.py` is listed as a pending code item.

---

## Key Containment Invariants (All Now in Tests)

| Invariant | Test |
|-----------|------|
| NEW_S3_SHADOW → paper only | Test 6 |
| S3_SHADOW_HOLD → no broker | Test 7 |
| S3_SHADOW_EXIT → paper ledger only | Test 8 |
| No DNSE for S3 | Test 9 |
| live_auto cannot override S3 guard | Test 10 |
| a3_s3_lead_5d only changes sort order | Test 13 |
| A3/S3 equity curves separate | Test 15 |
| Schema has 47 fields | Test 16 |
| All sample rows have 47 fields | Test 17 |
