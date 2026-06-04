# Cloud Daily Report — 2026-05-31 10:48 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.56bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: GSP, VEA (breadth gate)
- Review next-open candidate(s): GSP, VEA (pending levels)
- Review exit-risk holdings: VCB, PVS, HCM, HDB, MSB, POW, VHM, GEE

### WATCH / PREPARE
- S3 paper setups: 20
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 28.4%)
- Do not trade S3 as live capital
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GSP | NEW_T1_MANUAL_REVIEW_BREADTH | 0.99 | 11.30 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| VEA | NEW_T1_MANUAL_REVIEW_BREADTH | 0.95 | 34.80 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 156.20 | 2.93 |
| OIL | NO_T2_BREADTH | 15.10 | 1.00 |
| VGI | NO_T2_BREADTH | 93.10 | 0.99 |
| CTR | NO_T2_BREADTH | 88.50 | 0.98 |
| TRC | NO_T2_BREADTH | 75.30 | 0.98 |
| BID | NO_T2_BREADTH | 42.00 | 0.93 |
| VTO | NO_T2_BREADTH | 12.20 | 0.93 |
| PSI | NO_T2_BREADTH | 8.80 | 0.87 |
| VPL | NO_T2_BREADTH | 93.50 | 0.85 |
| ILS | NO_T2_BREADTH | 27.90 | 0.49 |
| FUEVN100 | NO_T2_BREADTH | 26.77 | 0.48 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.30 | 22.42 | Close 21.3 < trail 22.423 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.05 | 22.73 | Close 20.05 < trail 22.727 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.05 | 16.82 | Close 15.05 < trail 16.823 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.10 | 14.56 | Close 14.1 < trail 14.564 (2.5xATR14). Exit remaining per A3 rules. |
| LPB | TRAIL_EXIT | 52.00 | 52.57 | Close 52.0 < trail 52.571 (2.5xATR14). Exit remaining per A3 rules. |
| VCB | TRAIL_EXIT | 62.00 | 62.49 | Close 62.0 < trail 62.489 (2.5xATR14). Exit remaining per A3 rules. |
| KOS | TRAIL_EXIT | 38.00 | 38.43 | Close 38.0 < trail 38.432 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 32.25 | 34.30 | Close 32.25 < trail 34.295 (2.5xATR14). Exit remaining per A3 rules. |
| SAB | TRAIL_EXIT | 46.95 | 47.34 | Close 46.95 < trail 47.345 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 34.90 | 36.61 | Close 34.9 < trail 36.612 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 39.00 | 40.41 | Close 39.0 < trail 40.411 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.10 | 14.45 | Close 14.1 < trail 14.446 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.70 | 8.31 | Close 7.7 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 27.45 | 29.00 | Close 27.45 < trail 29.0 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 16.10 | 16.94 | Close 16.1 < trail 16.943 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 58.70 | 61.36 | Close 58.7 < trail 61.361 (2.5xATR14). Exit remaining per A3 rules. |
| TDP | TRAIL_EXIT | 28.60 | 29.27 | Close 28.6 < trail 29.27 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.00 | 13.41 | Close 13.0 < trail 13.414 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 25.90 | 26.96 | Close 25.9 < trail 26.961 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 74.70 | 79.29 | Close 74.7 < trail 79.286 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 40.85 | 44.91 | Close 40.85 < trail 44.905 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.00 | 6.79 | Close 6.0 < trail 6.793 (2.5xATR14). Exit remaining per A3 rules. |
| DXS | TRAIL_EXIT | 7.56 | 7.73 | Close 7.56 < trail 7.73 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 30.50 | 34.04 | Close 30.5 < trail 34.043 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 137.10 | 147.91 | Close 137.1 < trail 147.911 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 76.30 | 83.07 | Close 76.3 < trail 83.071 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.15 | 13.17 | Close 11.15 < trail 13.173 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.10 | 19.71 | Close 15.1 < trail 19.714 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 11.50 | 13.31 | Close 11.5 < trail 13.311 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| NAB | TRAIL_EXIT | 11.70 | 12.27 | Close 11.7 < trail 12.268 (2.5xATR14). Exit remaining per A3 rules. |
| MSB | TP1_PARTIAL | 15.30 | 14.91 | Close 15.3 >= TP1 15.045 (+18%). Take partial per A3 DP-first. |
| DSE | TRAIL_EXIT | 22.75 | 23.25 | Close 22.75 < trail 23.248 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.70 | 13.86 | Close 13.7 < trail 13.863 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 35.75 | 36.34 | Close 35.75 < trail 36.345 (2.5xATR14). Exit remaining per A3 rules. |
| PHP | TRAIL_EXIT | 36.60 | 36.71 | Close 36.6 < trail 36.714 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 171.90 | 177.43 | Close 171.9 < trail 177.429 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.70 | 36.24 | Close 34.7 < trail 36.245 (2.5xATR14). Exit remaining per A3 rules. |
| QNS | TRAIL_EXIT | 47.60 | 48.22 | Close 47.6 < trail 48.221 (2.5xATR14). Exit remaining per A3 rules. |
| PVP | TRAIL_EXIT | 17.75 | 18.88 | Close 17.75 < trail 18.875 (2.5xATR14). Exit remaining per A3 rules. |
| CDC | TRAIL_EXIT | 20.70 | 21.14 | Close 20.7 < trail 21.136 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.63 | 2.85 | Close 2.63 < trail 2.848 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.45 | 43.14 | Close 40.45 < trail 43.138 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 156.00 | 153.61 | Close 156.0 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| HNG | TRAIL_EXIT | 7.00 | 7.41 | Close 7.0 < trail 7.414 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 24.00 | 27.76 | Close 24.0 < trail 27.764 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 102.10 | 191.54 | Close 102.1 < trail 191.539 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.2841
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 7

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-29 | 2026-05-19 | no |
| ex_vin_proxy | 2026-05-29 | 2026-05-19 | no |
| vin_group | 2026-05-29 | 2026-05-19 | no |
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-29**
- Index as-of: **2026-05-19**
- Breadth lag (sessions): **-8**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/8)
- VIN distortion flag: **False**
- VIN group warning: **CORRECTION_RISK**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **44.4% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.4% (base 40.6%)**
- P(-10% correction within 75D) ex-VIN: **44.5% (base 44.4%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.


### RS vs VNINDEX (correction leg)

| Metric | Value |
| --- | --- |
| Anchor date | 2026-05-15 (close 1921.6) |
| End date | 2026-05-19 (close 1912.93) |
| VNINDEX return | -0.45% |
| Drawdown from peak | -0.45% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 129 |
| Leaders (RS≥+3%) | 31 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VGI | 89.2→101.5 | +13.79% | +14.24% | -16.17% | +4.50% | +20.67% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VTP | 65.1→71.7 | +10.14% | +10.59% | -18.05% | -3.12% | +14.93% | Y | — | — | — | — | —/— |
| CTR | 84.9→93.4 | +10.01% | +10.46% | -10.63% | +2.49% | +13.12% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| L40 | 69.1→74.2 | +7.38% | +7.83% | -0.75% | +5.96% | +6.71% | Y | — | WATCH_ONLY | — | none | N/Y |
| ILS | 24.4→26.1 | +6.97% | +7.42% | +26.59% | +29.42% | +2.83% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VVS | 105.0→111.7 | +6.38% | +6.83% | -21.59% | -19.19% | +2.40% | Y | — | — | — | — | —/— |
| VCB | 60.7→64.4 | +6.10% | +6.55% | -5.86% | +3.30% | +9.16% | Y | Y | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| BVH | 67.1→71.0 | +5.81% | +6.26% | -18.99% | -8.52% | +10.47% | Y | — | — | — | — | —/— |
| PC1 | 17.85→18.85 | +5.60% | +6.05% | -43.19% | -35.30% | +7.89% | Y | Y | not_in_scan | — | — | —/— |
| SBT | 20.2→21.3 | +5.45% | +5.90% | -15.98% | -7.86% | +8.12% | Y | — | — | — | — | —/— |
| APS | 6.7→7.0 | +4.48% | +4.93% | -0.16% | +11.55% | +11.71% | Y | — | WATCH_ONLY | — | none | N/Y |
| PHP | 35.9→37.5 | +4.46% | +4.91% | -1.37% | -1.52% | -0.15% | — | — | TRAIL_EXIT | — | same_day | Y/Y |
| HCM | 28.75→30.0 | +4.35% | +4.80% | +2.57% | +6.62% | +4.05% | Y | Y | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| CDC | 21.0→21.9 | +4.29% | +4.74% | -23.54% | -25.48% | -1.94% | — | — | TRAIL_EXIT | — | same_day | N/N |
| TV1 | 23.5→24.5 | +4.26% | +4.71% | -38.49% | -30.42% | +8.07% | Y | — | — | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VGI | 89.2→101.5 | +13.79% | +14.24% | -16.17% | +4.50% | +20.67% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VTP | 65.1→71.7 | +10.14% | +10.59% | -18.05% | -3.12% | +14.93% | Y | — | — | — | — | —/— |
| CTR | 84.9→93.4 | +10.01% | +10.46% | -10.63% | +2.49% | +13.12% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| L40 | 69.1→74.2 | +7.38% | +7.83% | -0.75% | +5.96% | +6.71% | Y | — | WATCH_ONLY | — | none | N/Y |
| ILS | 24.4→26.1 | +6.97% | +7.42% | +26.59% | +29.42% | +2.83% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VVS | 105.0→111.7 | +6.38% | +6.83% | -21.59% | -19.19% | +2.40% | Y | — | — | — | — | —/— |
| VCB | 60.7→64.4 | +6.10% | +6.55% | -5.86% | +3.30% | +9.16% | Y | Y | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| BVH | 67.1→71.0 | +5.81% | +6.26% | -18.99% | -8.52% | +10.47% | Y | — | — | — | — | —/— |
| PC1 | 17.85→18.85 | +5.60% | +6.05% | -43.19% | -35.30% | +7.89% | Y | Y | not_in_scan | — | — | —/— |
| SBT | 20.2→21.3 | +5.45% | +5.90% | -15.98% | -7.86% | +8.12% | Y | — | — | — | — | —/— |
| APS | 6.7→7.0 | +4.48% | +4.93% | -0.16% | +11.55% | +11.71% | Y | — | WATCH_ONLY | — | none | N/Y |
| HCM | 28.75→30.0 | +4.35% | +4.80% | +2.57% | +6.62% | +4.05% | Y | Y | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| TV1 | 23.5→24.5 | +4.26% | +4.71% | -38.49% | -30.42% | +8.07% | Y | — | — | — | — | —/— |
| MSB | 13.9→14.45 | +3.96% | +4.41% | +1.23% | +9.11% | +7.88% | Y | Y | TP1_PARTIAL | — | lead_1_5 | Y/Y |
| FOX | 83.3→86.5 | +3.84% | +4.29% | -6.63% | +2.34% | +8.97% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PDR | 16.55→16.85 | +1.81% | +2.26% | -7.61% | -2.37% | +5.24% | Y | — | — | — | — | —/— |
| FUEVN100 | 26.44→26.91 | +1.78% | +2.23% | -4.41% | -0.81% | +3.60% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| VEA | 34.3→34.9 | +1.75% | +2.20% | -5.83% | -0.62% | +5.21% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| CMG | 27.7→28.15 | +1.62% | +2.08% | -14.16% | -6.34% | +7.82% | Y | — | — | — | — | —/— |
| BSI | 35.0→35.55 | +1.57% | +2.02% | -13.88% | -7.72% | +6.16% | Y | — | — | — | — | —/— |
| PVI | 79.3→80.5 | +1.51% | +1.96% | -6.81% | -0.57% | +6.24% | Y | — | — | — | — | —/— |
| VPI | 61.9→62.8 | +1.45% | +1.91% | -2.04% | +1.32% | +3.36% | Y | — | — | — | — | —/— |
| APG | 4.81→4.87 | +1.25% | +1.70% | -17.46% | -9.44% | +8.02% | Y | — | — | — | — | —/— |
| PSI | 8.5→8.6 | +1.18% | +1.63% | -0.62% | +5.14% | +5.76% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| MIG | 17.3→17.5 | +1.16% | +1.61% | -16.20% | -7.08% | +9.12% | Y | — | WATCH_ONLY | — | none | N/N |
| NBC | 8.6→8.7 | +1.16% | +1.61% | -23.91% | -18.98% | +4.93% | Y | — | — | — | — | —/— |
| EVF | 13.65→13.8 | +1.10% | +1.55% | -9.66% | -6.54% | +3.12% | Y | — | — | — | — | —/— |
| HT1 | 13.8→13.95 | +1.09% | +1.54% | -19.76% | -13.34% | +6.42% | Y | — | — | — | — | —/— |
| KSV | 157.3→159.0 | +1.08% | +1.53% | -8.41% | -6.54% | +1.87% | Y | — | NO_T2_BREADTH | — | lead_11_20 | Y/Y |
| DPG | 40.1→40.5 | +1.00% | +1.45% | -17.08% | -9.60% | +7.48% | Y | — | TRAIL_EXIT | — | same_day | N/N |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REE | 60.3→53.7 | -10.95% | -10.49% | -16.72% | -21.86% | -5.14% | — | — | — | — | — | —/— |
| BMP | 157.2→141.1 | -10.24% | -9.79% | +1.48% | -11.98% | -13.46% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| VIW | 26.7→24.0 | -10.11% | -9.66% | -34.26% | -26.43% | +7.83% | Y | — | — | — | — | —/— |
| HPA | 38.45→35.1 | -8.71% | -8.26% | -7.30% | -11.14% | -3.84% | — | — | — | — | — | —/— |
| PHR | 71.3→65.4 | -8.27% | -7.82% | +6.23% | +1.23% | -5.00% | — | — | WATCH_ONLY | — | none | Y/Y |
| DPR | 44.2→40.6 | -8.14% | -7.69% | +1.05% | -5.61% | -6.66% | — | — | WATCH_ONLY | — | none | Y/Y |
| BIG | 6.8→6.3 | -7.35% | -6.90% | +1.46% | -16.38% | -17.84% | — | — | WATCH_ONLY | — | none | Y/N |
| DRI | 15.1→14.1 | -6.62% | -6.17% | +8.83% | +4.19% | -4.64% | — | — | TRAIL_EXIT | — | none | Y/Y |
| MWG | 82.0→78.2 | -4.63% | -4.18% | -7.73% | -8.93% | -1.20% | — | — | TRAIL_EXIT | — | after_a3 | N/N |
| CTD | 76.6→73.1 | -4.57% | -4.12% | -16.81% | -15.75% | +1.06% | Y | — | — | — | — | —/— |
| TCB | 34.05→32.6 | -4.26% | -3.81% | -1.98% | -2.92% | -0.94% | — | — | HOLD_T1_ONLY | — | lead_6_10 | N/Y |
| IDC | 43.9→42.1 | -4.10% | -3.65% | -16.19% | -18.85% | -2.66% | — | — | — | — | — | —/— |
| PIV | 8.1→7.8 | -3.70% | -3.25% | +7.49% | +3.22% | -4.27% | — | — | WATCH_ONLY | — | none | Y/Y |
| DSH | 17.1→16.5 | -3.51% | -3.06% | +10.53% | +2.73% | -7.80% | — | — | — | — | — | —/— |
| HAH | 57.5→55.5 | -3.48% | -3.03% | -3.67% | -2.53% | +1.14% | Y | — | — | — | — | —/— |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## RS C3 Context (RS line acceleration)

**FACTS** (context only; does not change final_action)

> **OOS3 regime active:** C3 IC near zero in 2024+. Use as sort/display only — hard filter not operative.

_Data as of: 2026-05-25_

| Symbol | C3 Rating | C3 Zone | #Top50 | T2 Context | Late Chase | final_action | EMA dist% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DXS | 99 | EXTREME_RS | — | — | — | TRAIL_EXIT | -4.42% |
| CII | 98 | EXTREME_RS | #1 | — | — | WATCH_ONLY | — |
| VCG | 98 | EXTREME_RS | #2 | — | — | TRAIL_EXIT | -5.60% |
| APS | 98 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| LPB | 97 | EXTREME_RS | #3 | — | — | TRAIL_EXIT | +0.39% |
| L40 | 96 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| DXG | 93 | EXTREME_RS | #4 | — | — | WATCH_ONLY | — |
| HHS | 93 | EXTREME_RS | #5 | — | — | TRAIL_EXIT | -6.84% |
| TCH | 93 | EXTREME_RS | #6 | — | — | TRAIL_EXIT | -6.80% |
| NVL | 92 | EXTREME_RS | #7 | — | — | TRAIL_EXIT | -6.52% |
| GEX | 91 | EXTREME_RS | #8 | — | — | WATCH_ONLY | — |
| NRC | 90 | EXTREME_RS | — | — | — | TRAIL_EXIT | -3.72% |
| ASM | 89 | LEADER_ZONE | — | — | — | WATCH_ONLY | — |
| VIX | 88 | LEADER_ZONE | #9 | — | — | WATCH_ONLY | — |
| HUT | 87 | LEADER_ZONE | #10 | — | — | TRAIL_EXIT | +1.62% |

_RS C3 is review-ranking context only and does not set or override final_action. IC near zero in OOS3 2024+. Use as sort/prioritization display only._

**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet` · **classification:** REVIEW_RANKING_ONLY


## H. Delta vs Previous