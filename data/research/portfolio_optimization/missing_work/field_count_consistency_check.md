# Phase35 Field Count Consistency Check

Date: 2026-05-16 (Round 2 patch)

---

## Authoritative Count: 47 fields

Schema file: `phase35_daily_scan_schema.csv` — 47 data rows (confirmed by validation script)

Composition:
- 37 Phase34 base fields (as_of_date through final_action_reason)
- 10 new S3 shadow fields:
  1. a3_s3_lead_5d
  2. s3_shadow_active
  3. s3_shadow_bars_since
  4. s3_shadow_entry_price
  5. s3_shadow_tp1_price
  6. s3_shadow_trail_price
  7. s3_shadow_max_hold_remaining
  8. s3_shadow_paper_pnl_pct
  9. s3_shadow_final_action
  10. s3_gk5_top100

Total: 47

---

## Why Not 49?

Earlier documents said "49 fields (37 + 12)". The "12" count was wrong.
Actual new fields added: 10 (not 12). The 49 figure was never reconciled against
the actual schema file. The validator confirmed 47.

---

## Files Updated (Round 2)

| File | Old claim | New claim |
|------|-----------|-----------|
| `phase35_daily_scan_schema.csv` | (was correct: 47) | 47 (unchanged) |
| `phase35_daily_scan_sample.csv` | (was correct: 47 header) | 47 (validated) |
| `UPDATED_FINAL_DAILY_RUNBOOK.md` | "49 fields" × 2 | "47 fields" |
| `UPDATED_FINAL_OPEN_ITEMS.md` | "49 fields (37 + 12 S3 shadow)" | "47 fields (37 + 10 new S3 shadow)" |
| `S3_UPGRADE_IMPLEMENTATION_NOTES.md` | "49 fields (37 + 12)" | "47 fields (37 base + 10 new)" |
| `S3_SHADOW_GATE_TESTS.md` | Test 9: "49 fields" | Test 16: "47 fields" |
| `PHASE35_REVIEW_PROMPT.md` | "49 fields" | Corrected in Round 2 prompt |

---

## Validation Command

```
.venv\Scripts\python.exe data\research\portfolio_optimization\missing_work\phase35_csv_validation.py
```

Expected output: ALL CHECKS PASSED
