# Cloud Daily Report — 2026-06-01 09:50 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.56bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged
- distribution_risk_lens: NEEDS_REVIEW: stale index view; probabilities may be caveated.

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: GSP, VEA, ACB (breadth gate)
- Review next-open candidate(s): GSP, ACB (pending levels)
- Review exit-risk holdings: VCB, MSB, BID, PVS, HCM, HDB, POW, VHM, GEE

### WATCH / PREPARE
- S3 paper setups: 18
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 28.0%)
- Do not trade S3 as live capital
- Do not duplicate held positions: ACB
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GSP | NEW_T1_MANUAL_REVIEW_BREADTH | 0.99 | 11.30 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| VEA | NEW_T1_MANUAL_REVIEW_BREADTH | 0.96 | 34.80 | 33.41 | 41.06 | 34.05 |  |
| ACB | NEW_T1_MANUAL_REVIEW_BREADTH | 0.27 | 24.90 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 158.40 | 3.00 |
| CTR | NO_T2_BREADTH | 88.00 | 0.95 |
| VGI | NO_T2_BREADTH | 92.10 | 0.95 |
| OIL | NO_T2_BREADTH | 14.90 | 0.94 |
| TRC | NO_T2_BREADTH | 76.00 | 0.94 |
| VTO | NO_T2_BREADTH | 12.20 | 0.93 |
| ILS | NO_T2_BREADTH | 26.00 | 0.88 |
| FUEVN100 | NO_T2_BREADTH | 26.90 | 0.46 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.40 | 22.44 | Close 21.4 < trail 22.441 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.50 | 16.78 | Close 15.5 < trail 16.779 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.20 | 22.74 | Close 20.2 < trail 22.736 (2.5xATR14). Exit remaining per A3 rules. |
| LPB | TRAIL_EXIT | 51.80 | 52.84 | Close 51.8 < trail 52.839 (2.5xATR14). Exit remaining per A3 rules. |
| SAB | TRAIL_EXIT | 47.20 | 47.41 | Close 47.2 < trail 47.407 (2.5xATR14). Exit remaining per A3 rules. |
| VCB | TRAIL_EXIT | 62.20 | 62.52 | Close 62.2 < trail 62.525 (2.5xATR14). Exit remaining per A3 rules. |
| KOS | TRAIL_EXIT | 38.10 | 38.41 | Close 38.1 < trail 38.414 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 35.05 | 36.86 | Close 35.05 < trail 36.862 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.20 | 14.60 | Close 14.2 < trail 14.6 (2.5xATR14). Exit remaining per A3 rules. |
| MSB | TRAIL_EXIT | 14.25 | 14.74 | Close 14.25 < trail 14.738 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.10 | 14.46 | Close 14.1 < trail 14.455 (2.5xATR14). Exit remaining per A3 rules. |
| PSI | TRAIL_EXIT | 8.70 | 8.70 | Close 8.7 < trail 8.704 (2.5xATR14). Exit remaining per A3 rules. |
| VPL | TRAIL_EXIT | 92.20 | 92.72 | Close 92.2 < trail 92.718 (2.5xATR14). Exit remaining per A3 rules. |
| VPB | TRAIL_EXIT | 26.95 | 27.01 | Close 26.95 < trail 27.014 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 79.10 | 82.62 | Close 79.1 < trail 82.625 (2.5xATR14). Exit remaining per A3 rules. |
| BID | TRAIL_EXIT | 41.90 | 41.93 | Close 41.9 < trail 41.93 (2.5xATR14). Exit remaining per A3 rules. |
| TCB | TRAIL_EXIT | 32.35 | 32.66 | Close 32.35 < trail 32.659 (2.5xATR14). Exit remaining per A3 rules. |
| TDP | TRAIL_EXIT | 28.60 | 29.42 | Close 28.6 < trail 29.421 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.00 | 13.44 | Close 13.0 < trail 13.441 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 38.60 | 40.39 | Close 38.6 < trail 40.393 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 58.30 | 61.34 | Close 58.3 < trail 61.343 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 27.15 | 28.97 | Close 27.15 < trail 28.973 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 74.70 | 79.32 | Close 74.7 < trail 79.321 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 25.75 | 27.01 | Close 25.75 < trail 27.014 (2.5xATR14). Exit remaining per A3 rules. |
| DXS | TRAIL_EXIT | 7.63 | 7.81 | Close 7.63 < trail 7.812 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.00 | 6.79 | Close 6.0 < trail 6.793 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 31.20 | 34.44 | Close 31.2 < trail 34.438 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.90 | 8.29 | Close 7.9 < trail 8.293 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 137.10 | 148.54 | Close 137.1 < trail 148.536 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 30.40 | 34.16 | Close 30.4 < trail 34.159 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.20 | 13.19 | Close 11.2 < trail 13.191 (2.5xATR14). Exit remaining per A3 rules. |
| NAB | TRAIL_EXIT | 11.95 | 12.22 | Close 11.95 < trail 12.223 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.25 | 19.78 | Close 15.25 < trail 19.777 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 11.60 | 13.30 | Close 11.6 < trail 13.302 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.80 | 13.86 | Close 13.8 < trail 13.863 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.69 | 2.84 | Close 2.69 < trail 2.839 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 152.00 | 153.04 | Close 152.0 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| E1VFVN30 | TRAIL_EXIT | 35.60 | 36.34 | Close 35.6 < trail 36.335 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.50 | 23.21 | Close 22.5 < trail 23.212 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.70 | 36.27 | Close 34.7 < trail 36.271 (2.5xATR14). Exit remaining per A3 rules. |
| QNS | TRAIL_EXIT | 47.60 | 48.35 | Close 47.6 < trail 48.346 (2.5xATR14). Exit remaining per A3 rules. |
| PHP | TRAIL_EXIT | 36.80 | 36.82 | Close 36.8 < trail 36.821 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 171.00 | 178.07 | Close 171.0 < trail 178.071 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.65 | 43.21 | Close 40.65 < trail 43.209 (2.5xATR14). Exit remaining per A3 rules. |
| CDC | TRAIL_EXIT | 20.60 | 21.37 | Close 20.6 < trail 21.368 (2.5xATR14). Exit remaining per A3 rules. |
| CTG | TRAIL_EXIT | 34.55 | 34.60 | Close 34.55 < trail 34.6 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.00 | 7.45 | Close 7.0 < trail 7.45 (2.5xATR14). Exit remaining per A3 rules. |
| PVP | TRAIL_EXIT | 17.50 | 18.91 | Close 17.5 < trail 18.911 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 24.05 | 27.77 | Close 24.05 < trail 27.773 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 105.00 | 192.59 | Close 105.0 < trail 192.593 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.2803
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
| vnindex_raw | 2026-05-29 | 2026-06-01 | YES |
| ex_vin_proxy | 2026-05-29 | 2026-06-01 | YES |
| vin_group | 2026-05-29 | 2026-06-01 | YES |

NEEDS_REVIEW: stale index view; probabilities may be caveated.
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-29**
- Index as-of: **2026-06-01**
- Breadth lag (sessions): **1**
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
| End date | 2026-06-01 (close 1844.54) |
| VNINDEX return | -4.01% |
| Drawdown from peak | -4.01% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 185 |
| Leaders (RS≥+3%) | 98 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KSF | 84.8→103.1 | +21.58% | +25.59% | -5.93% | +17.14% | +23.07% | Y | — | — | — | — | —/— |
| F88 | 147.9→172.0 | +16.29% | +20.30% | +4.00% | +12.42% | +8.42% | Y | — | WATCH_ONLY | — | none | Y/Y |
| POM | 4.3→4.9 | +13.95% | +17.96% | -0.72% | +26.15% | +26.87% | Y | — | — | — | — | —/— |
| C69 | 15.9→17.7 | +11.32% | +15.33% | -10.67% | +11.83% | +22.50% | Y | — | — | — | — | —/— |
| VVS | 105.0→115.7 | +10.19% | +14.20% | -21.59% | +1.30% | +22.89% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.4 | +7.55% | +11.56% | -14.41% | +7.06% | +21.47% | Y | — | — | — | — | —/— |
| MIG | 17.3→18.6 | +7.51% | +11.52% | -16.20% | +6.20% | +22.40% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.9 | +6.87% | +10.88% | -11.14% | +8.31% | +19.45% | Y | Y | NEW_T1_MR | Y | same_day | Y/Y |
| VND | 16.45→17.55 | +6.69% | +10.70% | -10.59% | +8.85% | +19.44% | Y | Y | WATCH_ONLY | — | none | N/Y |
| ILS | 24.4→26.0 | +6.56% | +10.57% | +26.59% | +21.44% | -5.15% | — | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| BIC | 23.15→24.65 | +6.48% | +10.49% | -9.92% | +3.87% | +13.79% | Y | — | WATCH_ONLY | — | none | N/N |
| PC1 | 17.85→19.0 | +6.44% | +10.45% | -43.19% | -3.53% | +39.66% | Y | Y | not_in_scan | — | — | —/— |
| MST | 7.8→8.3 | +6.41% | +10.42% | -15.36% | +1.73% | +17.09% | Y | — | — | — | — | —/— |
| NAF | 49.9→52.7 | +5.61% | +9.62% | -9.21% | +7.09% | +16.30% | Y | — | — | — | — | —/— |
| PET | 47.0→49.6 | +5.53% | +9.54% | -11.31% | +7.64% | +18.95% | Y | — | — | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KSF | 84.8→103.1 | +21.58% | +25.59% | -5.93% | +17.14% | +23.07% | Y | — | — | — | — | —/— |
| F88 | 147.9→172.0 | +16.29% | +20.30% | +4.00% | +12.42% | +8.42% | Y | — | WATCH_ONLY | — | none | Y/Y |
| POM | 4.3→4.9 | +13.95% | +17.96% | -0.72% | +26.15% | +26.87% | Y | — | — | — | — | —/— |
| C69 | 15.9→17.7 | +11.32% | +15.33% | -10.67% | +11.83% | +22.50% | Y | — | — | — | — | —/— |
| VVS | 105.0→115.7 | +10.19% | +14.20% | -21.59% | +1.30% | +22.89% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.4 | +7.55% | +11.56% | -14.41% | +7.06% | +21.47% | Y | — | — | — | — | —/— |
| MIG | 17.3→18.6 | +7.51% | +11.52% | -16.20% | +6.20% | +22.40% | Y | — | — | — | — | —/— |
| ACB | 23.3→24.9 | +6.87% | +10.88% | -11.14% | +8.31% | +19.45% | Y | Y | NEW_T1_MR | Y | same_day | Y/Y |
| VND | 16.45→17.55 | +6.69% | +10.70% | -10.59% | +8.85% | +19.44% | Y | Y | WATCH_ONLY | — | none | N/Y |
| BIC | 23.15→24.65 | +6.48% | +10.49% | -9.92% | +3.87% | +13.79% | Y | — | WATCH_ONLY | — | none | N/N |
| PC1 | 17.85→19.0 | +6.44% | +10.45% | -43.19% | -3.53% | +39.66% | Y | Y | not_in_scan | — | — | —/— |
| MST | 7.8→8.3 | +6.41% | +10.42% | -15.36% | +1.73% | +17.09% | Y | — | — | — | — | —/— |
| NAF | 49.9→52.7 | +5.61% | +9.62% | -9.21% | +7.09% | +16.30% | Y | — | — | — | — | —/— |
| PET | 47.0→49.6 | +5.53% | +9.54% | -11.31% | +7.64% | +18.95% | Y | — | — | — | — | —/— |
| KDC | 48.6→51.2 | +5.35% | +9.36% | -8.73% | +11.94% | +20.67% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DRC | 12.7→12.95 | +1.97% | +5.98% | -14.49% | +2.08% | +16.57% | Y | — | — | — | — | —/— |
| FUEVN100 | 26.44→26.9 | +1.74% | +5.75% | -4.41% | +2.45% | +6.86% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| VPI | 61.9→62.9 | +1.62% | +5.63% | -2.04% | +3.12% | +5.16% | Y | — | — | — | — | —/— |
| VEA | 34.3→34.8 | +1.46% | +5.47% | -5.83% | +4.71% | +10.54% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| DVM | 7.0→7.1 | +1.43% | +5.44% | -17.31% | -10.74% | +6.57% | Y | — | — | — | — | —/— |
| BMI | 14.5→14.7 | +1.38% | +5.39% | -16.45% | -2.46% | +13.99% | Y | — | — | — | — | —/— |
| DPG | 40.1→40.65 | +1.37% | +5.38% | -17.08% | -8.55% | +8.53% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| BCM | 54.0→54.7 | +1.30% | +5.31% | -10.92% | +2.95% | +13.87% | Y | — | — | — | — | —/— |
| PPT | 15.4→15.6 | +1.30% | +5.31% | -11.36% | +1.16% | +12.52% | Y | — | WATCH_ONLY | — | none | Y/Y |
| VDS | 13.6→13.75 | +1.10% | +5.11% | -18.15% | -4.00% | +14.15% | Y | — | — | — | — | —/— |
| NLG | 26.5→26.75 | +0.94% | +4.95% | -17.31% | -3.26% | +14.05% | Y | — | — | — | — | —/— |
| PAC | 22.05→22.25 | +0.91% | +4.92% | -18.59% | -1.04% | +17.55% | Y | — | — | — | — | —/— |
| DLG | 2.67→2.69 | +0.75% | +4.76% | -17.71% | -0.95% | +16.76% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| KSV | 157.3→158.4 | +0.70% | +4.71% | -8.41% | -1.71% | +6.70% | Y | — | NO_T2_BREADTH | — | lead_11_20 | Y/Y |
| PAT | 66.6→67.0 | +0.60% | +4.61% | -16.99% | -0.96% | +16.03% | Y | — | — | — | — | —/— |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TAL | 45.95→30.5 | -33.62% | -29.61% | -5.77% | -30.64% | -24.87% | — | — | — | — | — | —/— |
| PAN | 32.95→24.3 | -26.25% | -22.24% | -3.12% | -23.19% | -20.07% | — | — | — | — | — | —/— |
| CRC | 8.21→6.43 | -21.68% | -17.67% | -18.98% | -27.88% | -8.90% | — | — | — | — | — | —/— |
| TCX | 51.2→41.5 | -18.95% | -14.94% | -10.70% | -16.07% | -5.37% | — | Y | not_in_scan | — | — | —/— |
| DXG | 16.05→13.2 | -17.76% | -13.75% | -3.66% | -14.33% | -10.67% | — | — | WATCH_ONLY | — | none | N/N |
| TCO | 15.5→13.15 | -15.16% | -11.15% | +11.01% | -12.40% | -23.41% | — | — | — | — | — | —/— |
| REE | 60.3→51.2 | -15.09% | -11.08% | -16.72% | -15.83% | +0.89% | — | — | — | — | — | —/— |
| SSB | 16.5→14.2 | -13.94% | -9.93% | -11.16% | -14.71% | -3.55% | — | — | WATCH_ONLY | — | none | N/N |
| GEE | 121.0→105.0 | -13.22% | -9.21% | -46.17% | -39.42% | +6.75% | Y | Y | TRAIL_EXIT | — | same_day | N/N |
| VIW | 26.7→23.2 | -13.11% | -9.10% | -34.26% | -33.20% | +1.06% | Y | — | — | — | — | —/— |
| DGC | 51.5→44.85 | -12.91% | -8.90% | -16.75% | -15.50% | +1.25% | Y | — | — | — | — | —/— |
| BMP | 157.2→137.1 | -12.79% | -8.78% | +1.48% | -8.09% | -9.57% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| PIV | 8.1→7.1 | -12.35% | -8.34% | +7.49% | -4.82% | -12.31% | — | — | WATCH_ONLY | — | none | Y/Y |
| HID | 4.65→4.09 | -12.04% | -8.03% | -15.03% | -10.38% | +4.65% | Y | — | — | — | — | —/— |
| NVL | 17.3→15.25 | -11.85% | -7.84% | -7.05% | -19.64% | -12.59% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## RS C3 Context (RS line acceleration)

**FACTS** (context only; does not change final_action)

> **OOS3 regime active:** C3 IC near zero in 2024+. Use as sort/display only — hard filter not operative.

_Data as of: 2026-05-25_

| Symbol | C3 Rating | C3 Zone | #Top50 | T2 Context | Late Chase | final_action | EMA dist% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DXS | 99 | EXTREME_RS | — | — | — | TRAIL_EXIT | -3.21% |
| CII | 98 | EXTREME_RS | #1 | — | — | WATCH_ONLY | — |
| VCG | 98 | EXTREME_RS | #2 | — | — | TRAIL_EXIT | -4.45% |
| APS | 98 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| LPB | 97 | EXTREME_RS | #3 | — | — | TRAIL_EXIT | +0.00% |
| L40 | 96 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| SHS | 94 | EXTREME_RS | #4 | — | — | WATCH_ONLY | — |
| DXG | 93 | EXTREME_RS | #5 | — | — | WATCH_ONLY | — |
| HHS | 93 | EXTREME_RS | #6 | — | — | TRAIL_EXIT | -5.48% |
| TCH | 93 | EXTREME_RS | #7 | — | — | TRAIL_EXIT | -3.65% |
| NVL | 92 | EXTREME_RS | #8 | — | — | TRAIL_EXIT | -5.09% |
| GEX | 91 | EXTREME_RS | #9 | — | — | WATCH_ONLY | — |
| NRC | 90 | EXTREME_RS | — | — | — | TRAIL_EXIT | -3.37% |
| ASM | 89 | LEADER_ZONE | — | — | — | WATCH_ONLY | — |
| VIX | 88 | LEADER_ZONE | #10 | — | — | WATCH_ONLY | — |

_RS C3 is review-ranking context only and does not set or override final_action. IC near zero in OOS3 2024+. Use as sort/prioritization display only._

**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet` · **classification:** REVIEW_RANKING_ONLY


## H. Delta vs Previous
- New: ACB