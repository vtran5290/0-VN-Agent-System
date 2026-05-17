# Phase35 CSV Patch Notes (Round 2)

Date: 2026-05-16

---

## Problem Found by Reviewer

`phase35_daily_scan_sample.csv` had 6 malformed rows (ABB, BIC, BIG, BMP, BSR, CII).

Root cause: S3-only rows (no A3 active signal) had `pb_trigger_price`, `tp1_price`, and
`trail_price` all blank. These were originally written with 4 consecutive blank fields
instead of 3, shifting every field from `final_action` onward one column to the right.

Effect:
- `final_action` column received a blank value (the extra blank)
- `final_action_reason` received the actual `final_action` enum value
- `a3_s3_lead_5d` received the reason text
- All subsequent S3 shadow fields were shifted

Reviewer identified this as corrupting the final_action, s3_shadow_final_action,
and s3_gk5_top100 fields for S3 rows.

---

## Fix Applied

Regenerated `phase35_daily_scan_sample.csv` using Python `csv.writer` to eliminate
manual comma-counting errors. Each row was defined as a Python list of exactly 47
values, with assertion checks before writing.

Changed for S3 rows: `S3_PAPER_SHADOW,,,,,FINAL_ACTION` → `S3_PAPER_SHADOW,,,,FINAL_ACTION`
(4 commas → 3 commas; 3 separators for pb_trigger_price, tp1_price, trail_price)

---

## Field Count: 47 (Not 49)

All docs previously claiming "49 fields" have been corrected to "47 fields".

Actual count: 37 Phase34 base fields + 10 new S3 shadow fields = 47 total.

The "49" claim in earlier documents overcounted by 2. The Phase34 schema itself
had 37 fields (confirmed by `phase34_daily_scan_schema.csv`). The 10 new S3 fields:
a3_s3_lead_5d, s3_shadow_active, s3_shadow_bars_since, s3_shadow_entry_price,
s3_shadow_tp1_price, s3_shadow_trail_price, s3_shadow_max_hold_remaining,
s3_shadow_paper_pnl_pct, s3_shadow_final_action, s3_gk5_top100.

---

## Validation

`phase35_csv_validation.py` runs clean:
- Schema: 47 fields ✓
- Sample header: 47 fields ✓
- All 10 data rows: 47 fields ✓
- No None keys ✓
- No categorical whitespace ✓
- S3_GK5 classification: FUTURE_RETEST_REQUIRED ✓
