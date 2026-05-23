# Institutional Accumulation Scan v1.1 — P1 hardening validation (2026-04-30)

**Patches:** emerging risk gate (≤30), ETF/open-fund exclusion, VIN `daily_CMF_missing` diagnosis.

| Metric | Before P1 | After P1 |
|--------|-----------|----------|
| Scored rows | 1,564 | 1,562 |
| Emerging candidates | 36 | 24 |
| E1VFVN30 in scan | yes (Tier 3, emerging) | **removed** |
| `execution_leakage_check` | ok | **ok** |

## P1 acceptance

| Item | Status |
|------|--------|
| `EMERGING_MAX_RISK_PENALTY = 30` | PASS |
| TNT / KSF / PVP not emerging (risk > 30) | PASS |
| E1VFVN30 excluded (sector Quỹ mở) | PASS |
| VHM diagnosis includes `daily_CMF_missing` when daily CMF null | PASS (verify in CSV) |
| `tests/test_institutional_accumulation_scan.py` (17 tests) | PASS |

## Regenerate

```powershell
python -m pytest tests/test_institutional_accumulation_scan.py -q
python -m src.scans.institutional_accumulation.run --as-of 2026-04-30
```
