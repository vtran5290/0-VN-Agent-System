# Institutional Accumulation Scan — Package Integrity Audit (2026-05-21)

## Current package contract (use this)

| Field | Value |
|-------|--------|
| Market scan as-of | **2026-05-21** |
| Fund context month | **2026-04** (`apr2026_default_priors.json`) |
| Rows scored | **1562** |
| Emerging | **28** |
| E1VFVN30 | absent |
| VIC emerging | false |
| VHM `vingroup_distortion_flag` | **false** at this as-of (P1-c N/A) |
| Tests | 17 passed (`test_institutional_accumulation_scan.py`) |

**Source of truth:** `PACKAGE_INTEGRITY.json` inside the zip + `outputs/institutional_accumulation_2026-05-21.csv`.

## Review safety

- Use **only** `institutional_accumulation_scan_chatgpt.zip` — not extracted folders under `review_packages/`.
- Ignore stale April-only comparison notes unless filenames include `2026-05-21`.
- Operator start: `outputs/institutional_accumulation_operator_summary_2026-05-21.html`.

## Historical note (April 30 pre-refresh)

Earlier reviews used **2026-04-30** with **24 emerging**. This package is **May 21 market** + **April fund** context — do not mix counts.

## Validate before upload

```powershell
python -m scripts.reporting.validate_institutional_accumulation_package
python -m scripts.reporting.build_institutional_accumulation_scan_chatgpt_zip --as-of 2026-05-21 --smart-money-month 2026-04 --no-refresh
```
