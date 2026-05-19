# Cloud Daily Report — 2026-05-19 15:02 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.40bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged

## B. Decision Summary

### ACTION NOW
- 3 manual-review required (breadth gate)
- Prepare next-open order for KOS, TCB, GSP, OIL, TRC (pending levels)

### WATCH / PREPARE
- S3 paper setups: 56
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 31.8%)
- Do not trade S3 as live capital
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GSP | NEW_T1_MANUAL_REVIEW_BREADTH | 0.83 | 11.70 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| PVS | NEW_T1_MANUAL_REVIEW_BREADTH | 0.67 | 42.50 | 40.80 | 50.15 | 40.12 |  |
| OIL | NEW_T1_MANUAL_REVIEW_BREADTH | 0.36 | 17.00 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.70 | 22.34 | Close 21.7 < trail 22.343 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.80 | 16.85 | Close 15.8 < trail 16.854 (2.5xATR14). Exit remaining per A3 rules. |
| MCH | TRAIL_EXIT | 132.00 | 143.21 | Close 132.0 < trail 143.214 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.50 | 8.31 | Close 7.5 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| MZG | TRAIL_EXIT | 13.20 | 13.28 | Close 13.2 < trail 13.279 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 42.00 | 44.68 | Close 42.0 < trail 44.682 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 32.05 | 33.89 | Close 32.05 < trail 33.891 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.80 | 13.10 | Close 11.8 < trail 13.102 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 79.00 | 83.23 | Close 79.0 < trail 83.232 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | TRAIL_EXIT | 24.45 | 29.19 | Close 24.45 < trail 29.193 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | TRAIL_EXIT | 8.21 | 10.29 | Close 8.21 < trail 10.293 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.95 | 23.28 | Close 22.95 < trail 23.284 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 17.85 | 19.87 | Close 17.85 < trail 19.87 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.69 | 2.85 | Close 2.69 < trail 2.855 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 41.40 | 42.79 | Close 41.4 < trail 42.789 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.80 | 36.12 | Close 34.8 < trail 36.12 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 26.45 | 28.00 | Close 26.45 < trail 28.005 (2.5xATR14). Exit remaining per A3 rules. |
| REE | TRAIL_EXIT | 52.80 | 69.24 | Close 52.8 < trail 69.236 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 119.80 | 179.43 | Close 119.8 < trail 179.432 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.3182
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 4

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- VNINDEX raw: **CAUTION** (dist 10/25/50: 2/3/8)
- ex-VIN proxy: **CAUTION** (dist 10/25/50: 1/2/6)
- VIN distortion flag: **True**
- VIN group warning: **CAUTION**
- Distribution Risk Lens is market context only and does not change final_action.
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **35.3% (base 39.2%)**
- P(-5% correction within 25D) ex-VIN: **40.3% (base 40.4%)**
- P(-10% correction within 75D) ex-VIN: **44.4% (base 44.2%)**
- Comparison: VNINDEX raw may be VIN-skewed when distortion_flag is true; prefer ex_vin_proxy for broad market context.


## H. Delta vs Previous