# Cloud Daily Report — 2026-05-29 11:17 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.82bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged

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
| End date | 2026-05-29 (close 1863.49) |
| VNINDEX return | -3.02% |
| Drawdown from peak | -3.02% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 153 |
| Leaders (RS≥+3%) | 72 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ILS | 24.4→27.9 | +14.34% | +17.37% | +26.59% | +29.26% | +2.67% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| C69 | 15.9→18.1 | +13.84% | +16.86% | -10.67% | +12.62% | +23.29% | Y | — | — | — | — | —/— |
| POM | 4.3→4.8 | +11.63% | +14.65% | -0.72% | +22.57% | +23.29% | Y | — | — | — | — | —/— |
| KSF | 84.8→93.8 | +10.61% | +13.64% | -5.93% | +1.45% | +7.38% | Y | — | — | — | — | —/— |
| MSB | 13.9→15.3 | +10.07% | +13.10% | +1.23% | +21.89% | +20.66% | Y | Y | TP1_PARTIAL | — | lead_1_5 | Y/Y |
| F88 | 147.9→162.1 | +9.60% | +12.63% | +4.00% | -1.66% | -5.66% | — | — | WATCH_ONLY | — | none | Y/Y |
| VVS | 105.0→115.0 | +9.52% | +12.55% | -21.59% | +1.26% | +22.85% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.35 | +8.40% | +11.43% | -43.19% | -1.53% | +41.66% | Y | Y | not_in_scan | — | — | —/— |
| MIG | 17.3→18.65 | +7.80% | +10.83% | -16.20% | +5.46% | +21.66% | Y | — | WATCH_ONLY | — | none | N/N |
| NVB | 10.6→11.4 | +7.55% | +10.57% | -14.41% | +8.06% | +22.47% | Y | — | — | — | — | —/— |
| NAF | 49.9→53.6 | +7.41% | +10.44% | -9.21% | +8.11% | +17.32% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.9 | +6.87% | +9.89% | -11.14% | +5.45% | +16.59% | Y | Y | WATCH_ONLY | — | none | N/Y |
| VPL | 88.4→93.5 | +5.77% | +8.79% | +2.28% | +8.60% | +6.32% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| MST | 7.8→8.2 | +5.13% | +8.15% | -15.36% | +0.73% | +16.09% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.3 | +4.99% | +8.02% | -14.27% | +5.19% | +19.46% | Y | — | — | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ILS | 24.4→27.9 | +14.34% | +17.37% | +26.59% | +29.26% | +2.67% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| C69 | 15.9→18.1 | +13.84% | +16.86% | -10.67% | +12.62% | +23.29% | Y | — | — | — | — | —/— |
| POM | 4.3→4.8 | +11.63% | +14.65% | -0.72% | +22.57% | +23.29% | Y | — | — | — | — | —/— |
| KSF | 84.8→93.8 | +10.61% | +13.64% | -5.93% | +1.45% | +7.38% | Y | — | — | — | — | —/— |
| MSB | 13.9→15.3 | +10.07% | +13.10% | +1.23% | +21.89% | +20.66% | Y | Y | TP1_PARTIAL | — | lead_1_5 | Y/Y |
| VVS | 105.0→115.0 | +9.52% | +12.55% | -21.59% | +1.26% | +22.85% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.35 | +8.40% | +11.43% | -43.19% | -1.53% | +41.66% | Y | Y | not_in_scan | — | — | —/— |
| MIG | 17.3→18.65 | +7.80% | +10.83% | -16.20% | +5.46% | +21.66% | Y | — | WATCH_ONLY | — | none | N/N |
| NVB | 10.6→11.4 | +7.55% | +10.57% | -14.41% | +8.06% | +22.47% | Y | — | — | — | — | —/— |
| NAF | 49.9→53.6 | +7.41% | +10.44% | -9.21% | +8.11% | +17.32% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.9 | +6.87% | +9.89% | -11.14% | +5.45% | +16.59% | Y | Y | WATCH_ONLY | — | none | N/Y |
| VPL | 88.4→93.5 | +5.77% | +8.79% | +2.28% | +8.60% | +6.32% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| MST | 7.8→8.2 | +5.13% | +8.15% | -15.36% | +0.73% | +16.09% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.3 | +4.99% | +8.02% | -14.27% | +5.19% | +19.46% | Y | — | — | — | — | —/— |
| PET | 47.0→49.15 | +4.57% | +7.60% | -11.31% | +4.51% | +15.82% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DRC | 12.7→12.95 | +1.97% | +4.99% | -14.49% | -0.12% | +14.37% | Y | — | — | — | — | —/— |
| PHP | 35.9→36.6 | +1.95% | +4.97% | -1.37% | +1.44% | +2.81% | Y | — | TRAIL_EXIT | — | same_day | Y/Y |
| SHS | 17.7→18.0 | +1.69% | +4.72% | -10.43% | +6.00% | +16.43% | Y | — | — | — | — | —/— |
| TIG | 6.6→6.7 | +1.52% | +4.54% | -13.93% | +1.01% | +14.94% | Y | — | — | — | — | —/— |
| MCH | 133.0→135.0 | +1.50% | +4.53% | -13.22% | -1.97% | +11.25% | Y | — | — | — | — | —/— |
| VEA | 34.3→34.8 | +1.46% | +4.48% | -5.83% | +3.69% | +9.52% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| DHC | 36.2→36.7 | +1.38% | +4.41% | -8.77% | +2.01% | +10.78% | Y | — | WATCH_ONLY | — | none | Y/Y |
| DHA | 47.4→48.05 | +1.37% | +4.40% | -5.84% | +6.15% | +11.99% | Y | — | — | — | — | —/— |
| DSE | 22.45→22.75 | +1.34% | +4.36% | -14.29% | -1.38% | +12.91% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| PPT | 15.4→15.6 | +1.30% | +4.32% | -11.36% | +0.14% | +11.50% | Y | — | WATCH_ONLY | — | none | Y/Y |
| TPB | 15.7→15.9 | +1.27% | +4.30% | -12.78% | -2.66% | +10.12% | Y | — | — | — | — | —/— |
| HUT | 15.9→16.1 | +1.26% | +4.28% | -14.69% | +0.75% | +15.44% | Y | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| FUEVN100 | 26.44→26.77 | +1.25% | +4.27% | -4.41% | +0.86% | +5.27% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| PAC | 22.05→22.3 | +1.13% | +4.16% | -18.59% | -2.05% | +16.54% | Y | — | — | — | — | —/— |
| BMI | 14.5→14.65 | +1.03% | +4.06% | -16.45% | -3.49% | +12.96% | Y | — | — | — | — | —/— |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TAL | 45.95→31.0 | -32.54% | -29.51% | -5.77% | -31.77% | -26.00% | — | — | — | — | — | —/— |
| PAN | 32.95→24.45 | -25.80% | -22.77% | -3.12% | -22.89% | -19.77% | — | — | — | — | — | —/— |
| CRC | 8.21→6.3 | -23.26% | -20.24% | -18.98% | -30.51% | -11.53% | — | — | — | — | — | —/— |
| DXG | 16.05→13.05 | -18.69% | -15.67% | -3.66% | -15.49% | -11.83% | — | — | WATCH_ONLY | — | none | N/N |
| TCX | 51.2→42.0 | -17.97% | -14.94% | -10.70% | -17.50% | -6.80% | — | Y | not_in_scan | — | — | —/— |
| GEE | 121.0→102.1 | -15.62% | -12.60% | -46.17% | -42.13% | +4.04% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| SSB | 16.5→14.0 | -15.15% | -12.13% | -11.16% | -16.67% | -5.51% | — | — | WATCH_ONLY | — | none | N/N |
| VIW | 26.7→23.1 | -13.48% | -10.46% | -34.26% | -44.30% | -10.04% | — | — | — | — | — | —/— |
| BMP | 157.2→137.1 | -12.79% | -9.76% | +1.48% | -6.34% | -7.82% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| NVL | 17.3→15.1 | -12.72% | -9.69% | -7.05% | -26.85% | -19.80% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| DIG | 14.95→13.05 | -12.71% | -9.68% | -6.86% | -11.73% | -4.87% | — | — | — | — | — | —/— |
| REE | 60.3→52.7 | -12.60% | -9.58% | -16.72% | -13.11% | +3.61% | Y | — | — | — | — | —/— |
| SZC | 25.9→22.65 | -12.55% | -9.52% | -18.60% | -17.23% | +1.37% | Y | — | — | — | — | —/— |
| PIV | 8.1→7.1 | -12.35% | -9.32% | +7.49% | -5.84% | -13.33% | — | — | WATCH_ONLY | — | none | Y/Y |
| LDG | 3.21→2.83 | -11.84% | -8.81% | -19.30% | -17.76% | +1.54% | Y | — | — | — | — | —/— |

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