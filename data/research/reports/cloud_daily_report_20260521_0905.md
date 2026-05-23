# Cloud Daily Report — 2026-05-21 09:05 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.88bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged
- distribution_risk_lens: PRIMARY_VIEW_STALE or lens NEEDS_REVIEW — see freshness table

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: TRC, NTP, DXS, OIL, VGI, BID, VCB (breadth gate)
- Review next-open candidate(s): NTP, DXS, VGI, BID, VCB (pending levels)

### WATCH / PREPARE
- S3 paper setups: 21
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 31.1%)
- Do not trade S3 as live capital
- Do not duplicate held positions: OIL, BID, VCB
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TRC | NEW_T1_MANUAL_REVIEW_BREADTH | 0.98 | 74.90 | 71.90 | 88.38 | 73.06 |  |
| NTP | NEW_T1_MANUAL_REVIEW_BREADTH | 0.95 | 61.20 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| DXS | NEW_T1_MANUAL_REVIEW_BREADTH | 0.90 | 8.08 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| OIL | NEW_T1_MANUAL_REVIEW_BREADTH | 0.88 | 15.60 | 14.98 | 18.41 | 14.55 |  |
| VGI | NEW_T1_MANUAL_REVIEW_BREADTH | 0.81 | 96.00 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| BID | NEW_T1_MANUAL_REVIEW_BREADTH | 0.34 | 43.80 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| VCB | NEW_T1_MANUAL_REVIEW_BREADTH | 0.23 | 64.90 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 156.60 | 2.96 |
| KOS | NO_T2_BREADTH | 38.30 | 0.98 |
| PVS | NO_T2_BREADTH | 40.40 | 0.96 |
| SAB | NO_T2_BREADTH | 48.00 | 0.92 |
| PSI | NO_T2_BREADTH | 8.70 | 0.85 |
| HCM | NO_T2_BREADTH | 28.90 | 0.83 |
| LPB | NO_T2_BREADTH | 53.20 | 0.74 |
| VPL | NO_T2_BREADTH | 93.50 | 0.73 |
| MSB | NO_T2_BREADTH | 14.45 | 0.62 |
| FUEVN100 | NO_T2_BREADTH | 26.78 | 0.45 |
| QNS | NO_T2_BREADTH | 48.70 | 0.40 |
| PVP | NO_T2_BREADTH | 18.75 | 0.36 |
| PHP | NO_T2_BREADTH | 37.30 | 0.35 |
| ILS | NO_T2_BREADTH | 27.30 | 0.27 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.40 | 22.41 | Close 21.4 < trail 22.405 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.80 | 22.51 | Close 20.8 < trail 22.512 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.60 | 16.68 | Close 15.6 < trail 16.68 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 32.80 | 33.84 | Close 32.8 < trail 33.839 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.00 | 14.46 | Close 14.0 < trail 14.457 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | TRAIL_EXIT | 11.25 | 11.26 | Close 11.25 < trail 11.259 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.30 | 6.70 | Close 6.3 < trail 6.704 (2.5xATR14). Exit remaining per A3 rules. |
| VTO | TRAIL_EXIT | 11.90 | 12.07 | Close 11.9 < trail 12.071 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 36.20 | 36.46 | Close 36.2 < trail 36.461 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 76.20 | 78.54 | Close 76.2 < trail 78.536 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.70 | 16.91 | Close 15.7 < trail 16.907 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.15 | 14.38 | Close 14.15 < trail 14.375 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.10 | 13.32 | Close 13.1 < trail 13.316 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 58.80 | 61.34 | Close 58.8 < trail 61.343 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.70 | 44.69 | Close 41.7 < trail 44.691 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.40 | 8.31 | Close 7.4 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 79.50 | 83.34 | Close 79.5 < trail 83.339 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 25.85 | 26.93 | Close 25.85 < trail 26.934 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 31.60 | 33.63 | Close 31.6 < trail 33.632 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | TRAIL_EXIT | 8.28 | 10.32 | Close 8.28 < trail 10.321 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.50 | 13.11 | Close 11.5 < trail 13.111 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 139.40 | 146.54 | Close 139.4 < trail 146.536 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | TRAIL_EXIT | 23.50 | 29.28 | Close 23.5 < trail 29.282 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 11.85 | 13.27 | Close 11.85 < trail 13.266 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.30 | 18.96 | Close 15.3 < trail 18.964 (2.5xATR14). Exit remaining per A3 rules. |
| REE | TRAIL_EXIT | 53.30 | 69.49 | Close 53.3 < trail 69.486 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 173.50 | 177.12 | Close 173.5 < trail 177.125 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.20 | 7.31 | Close 7.2 < trail 7.307 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 36.00 | 36.24 | Close 36.0 < trail 36.245 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 17.80 | 19.77 | Close 17.8 < trail 19.771 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.66 | 2.85 | Close 2.66 < trail 2.853 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.50 | 13.65 | Close 13.5 < trail 13.648 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 26.55 | 27.94 | Close 26.55 < trail 27.943 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.90 | 42.67 | Close 40.9 < trail 42.673 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.40 | 36.14 | Close 34.4 < trail 36.138 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.00 | 23.27 | Close 22.0 < trail 23.266 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 159.80 | 154.46 | Close 159.8 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| GEE | TRAIL_EXIT | 113.50 | 179.02 | Close 113.5 < trail 179.021 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.3106
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 7

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **NEEDS_REVIEW**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-21 | 2026-05-21 | no |
| ex_vin_proxy | 2026-05-19 | 2026-05-21 | YES |
| vin_group | 2026-05-15 | 2026-05-21 | YES |

**NEEDS_REVIEW:** Stale view(s) — probabilities shown for last available row, not implied to be fully as-of requested date.
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/8)
- ex-VIN proxy: **CAUTION** (dist 10/25/50: 2/3/7)
- VIN distortion flag: **True**
- VIN group warning: **CAUTION**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **32.8% (base 39.2%)**
- P(-5% correction within 25D) ex-VIN: **36.1% (base 40.4%)**
- P(-10% correction within 75D) ex-VIN: **39.0% (base 44.2%)**
- Comparison: VNINDEX raw may be VIN-skewed when distortion_flag is true; prefer ex_vin_proxy for broad market context.


## H. Delta vs Previous
- New: NTP, VCB