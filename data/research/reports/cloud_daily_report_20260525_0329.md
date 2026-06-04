# Cloud Daily Report — 2026-05-25 03:29 UTC

**Mode:** PRE-ATC PREVIEW | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 5.27bn VND | **Positions:** data\raw\current_positions_derived.json

> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW
> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged
- intraday_quote_coverage_pct < 100%: 98.0%
- missing_quote_count=2

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: NTP, BID, VGI, DXS, VCB, CTR (breadth gate)
- Review would-be A3 candidate(s) if close now; wait for EOD confirmation. (NTP, VCB, CTR)
- Review exit-risk holdings: PVS, HCM

### WATCH / PREPARE
- 6 would-be NEW_T1 if close now
- S3 paper setups: 20
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 31.1%)
- Do not trade S3 as live capital
- Do not use intraday preview as order source
- Do not duplicate held positions: BID, VCB
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NTP | NEW_T1_MANUAL_REVIEW_BREADTH | 1.00 | 60.60 | 58.18 | 71.51 | 58.92 |  |
| BID | NEW_T1_MANUAL_REVIEW_BREADTH | 0.94 | 43.00 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| VGI | NEW_T1_MANUAL_REVIEW_BREADTH | 0.92 | 94.20 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| DXS | NEW_T1_MANUAL_REVIEW_BREADTH | 0.91 | 8.08 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| VCB | NEW_T1_MANUAL_REVIEW_BREADTH | 0.36 | 63.50 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| CTR | NEW_T1_MANUAL_REVIEW_BREADTH | 0.22 | 93.00 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 160.00 | 2.94 |
| KOS | NO_T2_BREADTH | 38.30 | 0.98 |
| TRC | NO_T2_BREADTH | 74.90 | 0.98 |
| PSI | NO_T2_BREADTH | 8.60 | 0.92 |
| SAB | NO_T2_BREADTH | 48.10 | 0.92 |
| OIL | NO_T2_BREADTH | 15.60 | 0.89 |
| LPB | NO_T2_BREADTH | 53.20 | 0.77 |
| VPL | NO_T2_BREADTH | 93.40 | 0.76 |
| MSB | NO_T2_BREADTH | 14.40 | 0.68 |
| ILS | NO_T2_BREADTH | 26.30 | 0.53 |
| FUEVN100 | NO_T2_BREADTH | 26.60 | 0.49 |
| PHP | NO_T2_BREADTH | 36.60 | 0.45 |
| QNS | NO_T2_BREADTH | 48.60 | 0.42 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| VCG | TRAIL_EXIT | 21.00 | 22.59 | Close 21.0 < trail 22.593 (2.5xATR14). Exit remaining per A3 rules. |
| EIB | TRAIL_EXIT | 21.20 | 22.39 | Close 21.2 < trail 22.387 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.65 | 16.82 | Close 15.65 < trail 16.823 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 39.90 | 40.25 | Close 39.9 < trail 40.25 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.00 | 14.53 | Close 14.0 < trail 14.529 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | TRAIL_EXIT | 11.25 | 11.26 | Close 11.25 < trail 11.259 (2.5xATR14). Exit remaining per A3 rules. |
| VTO | TRAIL_EXIT | 11.85 | 12.08 | Close 11.85 < trail 12.08 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 35.30 | 36.72 | Close 35.3 < trail 36.72 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.20 | 13.30 | Close 13.2 < trail 13.298 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.20 | 14.37 | Close 14.2 < trail 14.366 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 76.00 | 78.50 | Close 76.0 < trail 78.5 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 28.50 | 28.67 | Close 28.5 < trail 28.67 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 59.00 | 61.40 | Close 59.0 < trail 61.396 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.60 | 16.96 | Close 15.6 < trail 16.961 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.20 | 6.74 | Close 6.2 < trail 6.739 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.40 | 8.31 | Close 7.4 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 31.70 | 33.89 | Close 31.7 < trail 33.893 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 79.40 | 83.48 | Close 79.4 < trail 83.482 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 25.85 | 26.95 | Close 25.85 < trail 26.952 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.25 | 44.62 | Close 41.25 < trail 44.62 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | TRAIL_EXIT | 8.28 | 10.32 | Close 8.28 < trail 10.325 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 31.50 | 33.71 | Close 31.5 < trail 33.712 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.60 | 13.12 | Close 11.6 < trail 13.12 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 138.00 | 147.07 | Close 138.0 < trail 147.071 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 11.95 | 13.27 | Close 11.95 < trail 13.266 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.50 | 19.18 | Close 15.5 < trail 19.179 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | TRAIL_EXIT | 23.15 | 29.23 | Close 23.15 < trail 29.229 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.20 | 7.34 | Close 7.2 < trail 7.343 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 35.82 | 36.21 | Close 35.82 < trail 36.213 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.60 | 13.75 | Close 13.6 < trail 13.746 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.60 | 23.26 | Close 22.6 < trail 23.257 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 17.55 | 19.73 | Close 17.55 < trail 19.727 (2.5xATR14). Exit remaining per A3 rules. |
| PVP | TRAIL_EXIT | 18.05 | 18.62 | Close 18.05 < trail 18.616 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 153.80 | 154.11 | Close 153.8 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| VJC | TRAIL_EXIT | 170.10 | 176.54 | Close 170.1 < trail 176.536 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.64 | 2.85 | Close 2.64 < trail 2.855 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.60 | 36.13 | Close 34.6 < trail 36.129 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.65 | 42.64 | Close 40.65 < trail 42.638 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 26.35 | 27.93 | Close 26.35 < trail 27.934 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 108.80 | 178.20 | Close 108.8 < trail 178.2 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.3106
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 9

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-22 | 2026-05-22 | no |
| ex_vin_proxy | 2026-05-22 | 2026-05-22 | no |
| vin_group | 2026-05-22 | 2026-05-22 | no |
- VNINDEX raw: **CORRECTION_RISK** (dist 10/25/50: 4/5/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 4/5/8)
- VIN distortion flag: **False**
- VIN group warning: **DOWNTREND_WARNING**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **41.6% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.1% (base 40.5%)**
- P(-10% correction within 75D) ex-VIN: **47.7% (base 44.3%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.


## H. Delta vs Previous