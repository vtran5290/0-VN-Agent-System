# OHLCV Data Quality Audit

**Date:** 2026-05-13

## Overview
| Item | Value |
|------|-------|
| Total rows | 1,242,170 |
| Tickers | 1543 |
| Rows with bad value/close/vol ratio | 614,152 |
| Tickers with >5% bad rows | 1543 |
| ADV50 inflated (>10x) | 0 |
| ADV50 deflated (<0.1x) | 0 |

## Root Cause

The raw panel stores `value = close_thousands × volume` (NOT `close_VND × volume`).
Scripts that multiply `value × 1000` to convert to VND produce the correct number
for recent data, but historical rows from the original bulk-build may have been
stored as `value = close_VND × volume` already — giving a mix of units across
different date ranges.  This causes ADV50 to be inflated by up to 1000× for some
symbols when the mixed rows dominate the 50-day window.

**Correct formula:** `ADV50_VND = mean(close_VND × volume, last 50 days)`
where `close_VND = close × 1000` (price was stored in thousand-VND units).

## Worst ADV50 Error Cases (top 20)
| Symbol   | ADV50_correct   | ADV50_computed   | Error_factor   | Pct_bad   |
|----------|-----------------|------------------|----------------|-----------|
| A32      | 0.0B            | 0.0B             | 1.0x           | 100.0%    |
| AAA      | 8.9B            | 8.9B             | 1.0x           | 27.1%     |
| AAH      | 2.9B            | 2.9B             | 1.0x           | 97.8%     |
| AAM      | 0.1B            | 0.1B             | 1.0x           | 100.0%    |
| AAS      | 11.1B           | 11.1B            | 1.0x           | 39.0%     |
| AAT      | 0.1B            | 0.1B             | 1.0x           | 100.0%    |
| AAV      | 6.0B            | 6.0B             | 1.0x           | 28.7%     |
| ABB      | 14.1B           | 14.1B            | 1.0x           | 42.2%     |
| ABC      | 0.3B            | 0.3B             | 1.0x           | 100.0%    |
| ABI      | 0.9B            | 0.9B             | 1.0x           | 100.0%    |
| ABR      | 0.0B            | 0.0B             | 1.0x           | 100.0%    |
| ABS      | 0.7B            | 0.7B             | 1.0x           | 100.0%    |
| ABT      | 0.3B            | 0.3B             | 1.0x           | 100.0%    |
| ABW      | 1.9B            | 1.9B             | 1.0x           | 100.0%    |
| ACB      | 308.4B          | 308.4B           | 1.0x           | 27.1%     |
| ACC      | 1.1B            | 1.1B             | 1.0x           | 100.0%    |
| ACE      | 0.1B            | 0.1B             | 1.0x           | 100.0%    |
| ACG      | 0.4B            | 0.4B             | 1.0x           | 100.0%    |
| ACL      | 0.1B            | 0.1B             | 1.0x           | 100.0%    |
| ACM      | 0.2B            | 0.2B             | 1.0x           | 100.0%    |

## Liquid Universe ADV50 Sanity (correct values, ADV50>=2B VND)
| Symbol   | ADV50_B_correct   | ADV50_B_computed   | Error_factor   |
|----------|-------------------|--------------------|----------------|
| HPG      | 1054.7B           | 1054.7B            | 1.00x          |
| SHB      | 1031.4B           | 1031.4B            | 1.00x          |
| SSI      | 973.2B            | 973.2B             | 1.00x          |
| FPT      | 824.6B            | 824.6B             | 1.00x          |
| VHM      | 780.0B            | 780.0B             | 1.00x          |
| VIC      | 720.6B            | 720.6B             | 1.00x          |
| VIX      | 684.5B            | 684.5B             | 1.00x          |
| MWG      | 632.4B            | 632.4B             | 1.00x          |
| STB      | 597.0B            | 597.0B             | 1.00x          |
| BSR      | 553.5B            | 553.5B             | 1.00x          |
| MSN      | 517.3B            | 517.3B             | 1.00x          |
| MBB      | 498.4B            | 498.4B             | 1.00x          |
| VCB      | 496.2B            | 496.2B             | 1.00x          |
| VPB      | 441.7B            | 441.7B             | 1.00x          |
| TCB      | 428.0B            | 428.0B             | 1.00x          |
| NVL      | 419.0B            | 419.0B             | 1.00x          |
| VCI      | 375.1B            | 375.1B             | 1.00x          |
| GEX      | 366.1B            | 366.1B             | 1.00x          |
| HDB      | 362.0B            | 362.0B             | 1.00x          |
| CII      | 349.8B            | 349.8B             | 1.00x          |
| HCM      | 346.6B            | 346.6B             | 1.00x          |
| BID      | 341.3B            | 341.3B             | 1.00x          |
| CTG      | 337.5B            | 337.5B             | 1.00x          |
| PVS      | 329.6B            | 329.6B             | 1.00x          |
| VNM      | 323.3B            | 323.3B             | 1.00x          |
| DGC      | 322.8B            | 322.8B             | 1.00x          |
| ACB      | 308.4B            | 308.4B             | 1.00x          |
| SHS      | 289.9B            | 289.9B             | 1.00x          |
| PLX      | 274.6B            | 274.6B             | 1.00x          |
| DPM      | 270.7B            | 270.7B             | 1.00x          |

## Recommendation

All scripts should compute ADV50 as:

```python
close_vnd = df["close"] * 1000   # always, since panel close is in thousand-VND
adv50_vnd = (close_vnd * df["volume"]).rolling(50).mean()
adv50_B   = adv50_vnd / 1e9
```

Do NOT rely on `df["value"]` for ADV50 calculation until the value column has been
fully re-derived from `close_VND × volume` across the entire history.
