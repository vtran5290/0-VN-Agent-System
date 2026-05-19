# Cloud Daily Report — 2026-05-19 15:06 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.40bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged

## B. Decision Summary

### ACTION NOW
- 2 manual-review required (breadth gate)
- Prepare next-open order for NTP, OIL, TRC, CTG (pending levels)

### WATCH / PREPARE
- S3 paper setups: 59
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 31.8%)
- Do not trade S3 as live capital
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GSP | NEW_T1_MANUAL_REVIEW_BREADTH | 0.93 | 11.50 | 11.04 | 13.57 | 11.27 |  |
| OIL | NEW_T1_MANUAL_REVIEW_BREADTH | 0.84 | 15.60 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| PVS | NO_T2_BREADTH | 40.00 | 0.99 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.70 | 22.35 | Close 21.7 < trail 22.352 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.80 | 16.91 | Close 15.8 < trail 16.907 (2.5xATR14). Exit remaining per A3 rules. |
| MCH | TRAIL_EXIT | 131.00 | 143.12 | Close 131.0 < trail 143.125 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.90 | 44.68 | Close 41.9 < trail 44.682 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.40 | 8.31 | Close 7.4 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 31.65 | 33.82 | Close 31.65 < trail 33.82 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.70 | 13.13 | Close 11.7 < trail 13.129 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | TRAIL_EXIT | 24.40 | 29.19 | Close 24.4 < trail 29.193 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | TRAIL_EXIT | 8.21 | 10.29 | Close 8.21 < trail 10.293 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 78.20 | 83.27 | Close 78.2 < trail 83.268 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 23.00 | 23.31 | Close 23.0 < trail 23.311 (2.5xATR14). Exit remaining per A3 rules. |
| REE | TRAIL_EXIT | 53.70 | 69.09 | Close 53.7 < trail 69.093 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 17.50 | 19.81 | Close 17.5 < trail 19.807 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.67 | 2.85 | Close 2.67 < trail 2.853 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.70 | 36.15 | Close 34.7 < trail 36.146 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 26.25 | 27.99 | Close 26.25 < trail 27.988 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.50 | 43.01 | Close 40.5 < trail 43.013 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 121.30 | 179.68 | Close 121.3 < trail 179.682 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.3182
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 5

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/9)
- ex-VIN proxy: **CAUTION** (dist 10/25/50: 2/3/7)
- VIN distortion flag: **True**
- VIN group warning: **CAUTION**
- Distribution Risk Lens is market context only and does not change final_action.
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **32.8% (base 39.2%)**
- P(-5% correction within 25D) ex-VIN: **36.1% (base 40.4%)**
- P(-10% correction within 75D) ex-VIN: **39.0% (base 44.2%)**
- Comparison: VNINDEX raw may be VIN-skewed when distortion_flag is true; prefer ex_vin_proxy for broad market context.


## H. Delta vs Previous
- Removed: PVS