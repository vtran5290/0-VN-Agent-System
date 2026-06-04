# Cloud Daily Report — 2026-05-29 10:50 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.82bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: GSP, VEA (breadth gate)
- Review next-open candidate(s): GSP, VEA (pending levels)
- Review exit-risk holdings: VCB, PVS, HCM, HDB, MSB, POW, VHM

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
| vnindex_raw | 2026-05-29 | 2026-05-29 | no |
| ex_vin_proxy | 2026-05-29 | 2026-05-29 | no |
| vin_group | 2026-05-29 | 2026-05-29 | no |
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-29**
- Index as-of: **2026-05-29**
- Breadth lag (sessions): **0**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **CORRECTION_RISK** (dist 10/25/50: 3/6/9)
- ex-VIN proxy: **CORRECTION_RISK** (dist 10/25/50: 3/6/8)
- VIN distortion flag: **False**
- VIN group warning: **DOWNTREND_WARNING**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **41.6% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.1% (base 40.6%)**
- P(-10% correction within 75D) ex-VIN: **47.8% (base 44.4%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.


### RS vs VNINDEX (correction leg)

| Metric | Value |
| --- | --- |
| Anchor date | 2026-05-15 (close 1921.6) |
| End date | 2026-05-18 (close 1927.94) |
| VNINDEX return | +0.33% |
| Drawdown from peak | +0.33% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 104 |
| Leaders (RS≥+3%) | 26 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ILS | 24.4→27.0 | +10.66% | +10.33% | +26.59% | +41.28% | +14.69% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VGI | 89.2→97.5 | +9.30% | +8.97% | -16.17% | -3.68% | +12.49% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| PLC | 22.4→24.4 | +8.93% | +8.60% | -13.70% | -3.24% | +10.46% | Y | — | — | — | — | —/— |
| OIL | 15.8→17.0 | +7.59% | +7.27% | -1.46% | +7.80% | +9.26% | Y | — | NO_T2_BREADTH | — | none | Y/N |
| PVC | 15.7→16.8 | +7.01% | +6.68% | -13.64% | -6.47% | +7.17% | Y | — | — | — | — | —/— |
| PLX | 42.2→45.15 | +6.99% | +6.66% | -3.11% | +6.37% | +9.48% | Y | — | — | — | — | —/— |
| BVH | 67.1→71.7 | +6.86% | +6.53% | -18.99% | -10.18% | +8.81% | Y | — | — | — | — | —/— |
| PVD | 33.7→35.8 | +6.23% | +5.90% | -6.87% | +1.91% | +8.78% | Y | — | — | — | — | —/— |
| APS | 6.7→7.1 | +5.97% | +5.64% | -0.16% | +9.32% | +9.48% | Y | — | WATCH_ONLY | — | none | N/Y |
| TV1 | 23.5→24.8 | +5.53% | +5.20% | -38.49% | -32.37% | +6.12% | Y | — | — | — | — | —/— |
| BID | 42.95→45.3 | +5.47% | +5.14% | -1.91% | +5.34% | +7.25% | Y | Y | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| PVB | 27.8→29.3 | +5.40% | +5.07% | -11.36% | -3.90% | +7.46% | Y | — | — | — | — | —/— |
| BSR | 31.75→33.45 | +5.35% | +5.02% | +12.50% | +20.85% | +8.35% | Y | — | WATCH_ONLY | — | none | Y/Y |
| PVT | 24.05→25.3 | +5.20% | +4.87% | +1.85% | +11.43% | +9.58% | Y | — | WATCH_ONLY | — | none | Y/Y |
| VTP | 65.1→68.2 | +4.76% | +4.43% | -18.05% | -12.08% | +5.97% | Y | — | — | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ILS | 24.4→27.0 | +10.66% | +10.33% | +26.59% | +41.28% | +14.69% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VGI | 89.2→97.5 | +9.30% | +8.97% | -16.17% | -3.68% | +12.49% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| PLC | 22.4→24.4 | +8.93% | +8.60% | -13.70% | -3.24% | +10.46% | Y | — | — | — | — | —/— |
| OIL | 15.8→17.0 | +7.59% | +7.27% | -1.46% | +7.80% | +9.26% | Y | — | NO_T2_BREADTH | — | none | Y/N |
| PVC | 15.7→16.8 | +7.01% | +6.68% | -13.64% | -6.47% | +7.17% | Y | — | — | — | — | —/— |
| PLX | 42.2→45.15 | +6.99% | +6.66% | -3.11% | +6.37% | +9.48% | Y | — | — | — | — | —/— |
| BVH | 67.1→71.7 | +6.86% | +6.53% | -18.99% | -10.18% | +8.81% | Y | — | — | — | — | —/— |
| PVD | 33.7→35.8 | +6.23% | +5.90% | -6.87% | +1.91% | +8.78% | Y | — | — | — | — | —/— |
| APS | 6.7→7.1 | +5.97% | +5.64% | -0.16% | +9.32% | +9.48% | Y | — | WATCH_ONLY | — | none | N/Y |
| TV1 | 23.5→24.8 | +5.53% | +5.20% | -38.49% | -32.37% | +6.12% | Y | — | — | — | — | —/— |
| BID | 42.95→45.3 | +5.47% | +5.14% | -1.91% | +5.34% | +7.25% | Y | Y | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| PVB | 27.8→29.3 | +5.40% | +5.07% | -11.36% | -3.90% | +7.46% | Y | — | — | — | — | —/— |
| BSR | 31.75→33.45 | +5.35% | +5.02% | +12.50% | +20.85% | +8.35% | Y | — | WATCH_ONLY | — | none | Y/Y |
| PVT | 24.05→25.3 | +5.20% | +4.87% | +1.85% | +11.43% | +9.58% | Y | — | WATCH_ONLY | — | none | Y/Y |
| VTP | 65.1→68.2 | +4.76% | +4.43% | -18.05% | -12.08% | +5.97% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HBC | 5.1→5.2 | +1.96% | +1.63% | -8.22% | -5.11% | +3.11% | Y | — | — | — | — | —/— |
| CTS | 28.05→28.6 | +1.96% | +1.63% | -8.22% | -4.19% | +4.03% | Y | — | — | — | — | —/— |
| NVB | 10.6→10.8 | +1.89% | +1.56% | -14.41% | -10.64% | +3.77% | Y | — | — | — | — | —/— |
| DDV | 26.8→27.3 | +1.87% | +1.54% | -13.85% | -10.94% | +2.91% | Y | — | — | — | — | —/— |
| EVF | 13.65→13.9 | +1.83% | +1.50% | -9.66% | -7.78% | +1.88% | Y | — | — | — | — | —/— |
| NAF | 49.9→50.8 | +1.80% | +1.47% | -9.21% | -5.47% | +3.74% | Y | — | — | — | — | —/— |
| VPI | 61.9→63.0 | +1.78% | +1.45% | -2.04% | +0.07% | +2.11% | Y | — | — | — | — | —/— |
| SBT | 20.2→20.55 | +1.73% | +1.40% | -15.98% | -13.23% | +2.75% | Y | — | — | — | — | —/— |
| SHS | 17.7→18.0 | +1.69% | +1.36% | -10.43% | -8.17% | +2.26% | Y | — | — | — | — | —/— |
| FTS | 26.65→27.1 | +1.69% | +1.36% | -12.87% | -9.41% | +3.46% | Y | — | — | — | — | —/— |
| CMG | 27.7→28.15 | +1.62% | +1.29% | -14.16% | -10.33% | +3.83% | Y | — | — | — | — | —/— |
| LPB | 51.5→52.3 | +1.55% | +1.22% | -0.93% | +2.57% | +3.50% | Y | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| CSV | 26.1→26.5 | +1.53% | +1.20% | -15.99% | -11.40% | +4.59% | Y | — | — | — | — | —/— |
| BSI | 35.0→35.5 | +1.43% | +1.10% | -13.88% | -10.99% | +2.89% | Y | — | — | — | — | —/— |
| POW | 14.1→14.3 | +1.42% | +1.09% | -1.00% | +2.51% | +3.51% | Y | Y | TRAIL_EXIT | — | same_day | Y/Y |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REE | 60.3→52.8 | -12.44% | -12.77% | -16.72% | -25.71% | -8.99% | — | — | — | — | — | —/— |
| VIW | 26.7→24.3 | -8.99% | -9.32% | -34.26% | -38.62% | -4.36% | — | — | — | — | — | —/— |
| HPA | 38.45→35.8 | -6.89% | -7.22% | -7.30% | -12.36% | -5.06% | — | — | — | — | — | —/— |
| DSH | 17.1→16.1 | -5.85% | -6.18% | +10.53% | -1.84% | -12.37% | — | — | — | — | — | —/— |
| CTD | 76.6→73.2 | -4.44% | -4.77% | -16.81% | -18.02% | -1.21% | — | — | — | — | — | —/— |
| BIG | 6.8→6.5 | -4.41% | -4.74% | +1.46% | -2.23% | -3.69% | — | — | WATCH_ONLY | — | none | Y/N |
| PNJ | 67.3→64.7 | -3.86% | -4.19% | -46.76% | -47.82% | -1.06% | — | — | WATCH_ONLY | — | none | N/N |
| MWG | 82.0→79.0 | -3.66% | -3.99% | -7.73% | -8.32% | -0.59% | — | — | TRAIL_EXIT | — | after_a3 | N/N |
| HHP | 14.45→14.0 | -3.11% | -3.44% | +7.84% | +5.38% | -2.46% | — | — | WATCH_ONLY | — | none | Y/Y |
| MSR | 39.6→38.5 | -2.78% | -3.11% | -23.24% | -23.56% | -0.32% | — | — | — | — | — | —/— |
| ELC | 16.6→16.15 | -2.71% | -3.04% | -18.49% | -17.60% | +0.89% | — | — | — | — | — | —/— |
| NDN | 11.2→10.9 | -2.68% | -3.01% | +0.52% | -0.21% | -0.73% | — | — | WATCH_ONLY | — | none | N/Y |
| VRE | 34.0→33.1 | -2.65% | -2.98% | +13.64% | +5.90% | -7.74% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| VHM | 158.0→154.0 | -2.53% | -2.86% | +14.36% | +5.34% | -9.02% | — | Y | TP1_PARTIAL | — | same_day | Y/Y |
| IDC | 43.9→42.8 | -2.51% | -2.84% | -16.19% | -17.72% | -1.53% | — | — | — | — | — | —/— |

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