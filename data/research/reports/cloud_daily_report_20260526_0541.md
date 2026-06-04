# Cloud Daily Report — 2026-05-26 05:41 UTC

**Mode:** EOD | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 5.27bn VND | **Positions:** data\raw\current_positions_derived.json

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: BID, VGI, DXS, VCB, CTR (breadth gate)
- Review next-open candidate(s): VCB, CTR (pending levels)
- Review exit-risk holdings: HCM, PVS

### WATCH / PREPARE
- S3 paper setups: 19
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 31.1%)
- Do not trade S3 as live capital
- Do not duplicate held positions: BID, VCB
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BID | NEW_T1_MANUAL_REVIEW_BREADTH | 0.94 | 43.00 | 41.28 | 50.74 | 41.19 |  |
| VGI | NEW_T1_MANUAL_REVIEW_BREADTH | 0.91 | 94.40 | 90.62 | 111.39 | 88.79 |  |
| DXS | NEW_T1_MANUAL_REVIEW_BREADTH | 0.89 | 8.12 | 7.79 | 9.58 | 7.76 |  |
| VCB | NEW_T1_MANUAL_REVIEW_BREADTH | 0.86 | 63.70 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |
| CTR | NEW_T1_MANUAL_REVIEW_BREADTH | 0.30 | 92.00 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 164.50 | 2.81 |
| NTP | NO_T2_BREADTH | 60.60 | 1.00 |
| TRC | NO_T2_BREADTH | 75.50 | 0.95 |
| SAB | NO_T2_BREADTH | 47.90 | 0.94 |
| PSI | NO_T2_BREADTH | 8.60 | 0.93 |
| OIL | NO_T2_BREADTH | 14.70 | 0.83 |
| LPB | NO_T2_BREADTH | 54.00 | 0.72 |
| MSB | NO_T2_BREADTH | 14.45 | 0.69 |
| VPL | NO_T2_BREADTH | 95.70 | 0.67 |
| ILS | NO_T2_BREADTH | 26.40 | 0.56 |
| FUEVN100 | NO_T2_BREADTH | 26.80 | 0.46 |
| PHP | NO_T2_BREADTH | 36.80 | 0.43 |
| QNS | NO_T2_BREADTH | 48.90 | 0.40 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.50 | 22.40 | Close 21.5 < trail 22.396 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.90 | 22.58 | Close 20.9 < trail 22.584 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.65 | 16.87 | Close 15.65 < trail 16.868 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 77.20 | 78.32 | Close 77.2 < trail 78.321 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 60.00 | 61.34 | Close 60.0 < trail 61.343 (2.5xATR14). Exit remaining per A3 rules. |
| KOS | TRAIL_EXIT | 38.25 | 38.32 | Close 38.25 < trail 38.316 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 32.80 | 33.96 | Close 32.8 < trail 33.964 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 28.15 | 28.65 | Close 28.15 < trail 28.652 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 26.40 | 26.87 | Close 26.4 < trail 26.871 (2.5xATR14). Exit remaining per A3 rules. |
| VTO | TRAIL_EXIT | 11.85 | 12.08 | Close 11.85 < trail 12.08 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.50 | 8.29 | Close 7.5 < trail 8.293 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | TRAIL_EXIT | 11.15 | 11.26 | Close 11.15 < trail 11.259 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 13.80 | 14.55 | Close 13.8 < trail 14.546 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.10 | 13.28 | Close 13.1 < trail 13.28 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.10 | 14.35 | Close 14.1 < trail 14.348 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.60 | 16.98 | Close 15.6 < trail 16.979 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.20 | 6.76 | Close 6.2 < trail 6.757 (2.5xATR14). Exit remaining per A3 rules. |
| TDP | TRAIL_EXIT | 28.60 | 29.05 | Close 28.6 < trail 29.046 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.70 | 13.11 | Close 11.7 < trail 13.111 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 78.70 | 83.38 | Close 78.7 < trail 83.375 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.00 | 44.58 | Close 41.0 < trail 44.575 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 31.35 | 33.69 | Close 31.35 < trail 33.686 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 34.30 | 36.69 | Close 34.3 < trail 36.693 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 38.00 | 40.11 | Close 38.0 < trail 40.107 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 139.40 | 146.91 | Close 139.4 < trail 146.911 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 12.05 | 13.30 | Close 12.05 < trail 13.302 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | TRAIL_EXIT | 8.10 | 10.29 | Close 8.1 < trail 10.295 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | TRAIL_EXIT | 23.35 | 29.24 | Close 23.35 < trail 29.238 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.50 | 19.41 | Close 15.5 < trail 19.411 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 35.89 | 36.22 | Close 35.89 < trail 36.224 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 173.80 | 176.07 | Close 173.8 < trail 176.071 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.65 | 13.80 | Close 13.65 < trail 13.8 (2.5xATR14). Exit remaining per A3 rules. |
| CDC | TRAIL_EXIT | 21.00 | 21.03 | Close 21.0 < trail 21.029 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 17.50 | 19.74 | Close 17.5 < trail 19.736 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.70 | 36.12 | Close 34.7 < trail 36.12 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.63 | 2.85 | Close 2.63 < trail 2.853 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.60 | 42.74 | Close 40.6 < trail 42.736 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.00 | 7.31 | Close 7.0 < trail 7.307 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.10 | 23.20 | Close 22.1 < trail 23.204 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 158.70 | 154.88 | Close 158.7 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| PVP | TRAIL_EXIT | 17.25 | 18.66 | Close 17.25 < trail 18.661 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 24.10 | 27.59 | Close 24.1 < trail 27.586 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 111.00 | 189.95 | Close 111.0 < trail 189.95 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.3106
- Breadth zone: DEFENSE
- T1 permission: OK
- T2 permission: BLOCKED
- Sector L4 stress: 0
- Liquidity warnings: 8

### VNINDEX Distribution Risk Lens
- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-25 | 2026-05-25 | no |
| ex_vin_proxy | 2026-05-25 | 2026-05-25 | no |
| vin_group | 2026-05-25 | 2026-05-25 | no |
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/5/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/5/8)
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


### RS vs VNINDEX (correction leg)

| Metric | Value |
| --- | --- |
| Anchor date | 2026-05-15 (close 1921.6) |
| End date | 2026-05-25 (close 1886.03) |
| VNINDEX return | -1.85% |
| Drawdown from peak | -1.85% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 151 |
| Leaders (RS≥+3%) | 47 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C69 | 15.9→17.9 | +12.58% | +14.43% | -10.67% | +11.03% | +21.70% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.55 | +9.52% | +11.37% | -43.19% | -26.06% | +17.13% | Y | Y | not_in_scan | — | — | —/— |
| NVB | 10.6→11.6 | +9.43% | +11.29% | -14.41% | +3.91% | +18.32% | Y | — | — | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.15% | -0.72% | +13.09% | +13.81% | Y | — | — | — | — | —/— |
| CTR | 84.9→92.0 | +8.36% | +10.21% | -10.63% | +6.69% | +17.32% | Y | — | NEW_T1_MR | Y | same_day | Y/Y |
| VPL | 88.4→95.7 | +8.26% | +10.11% | +2.28% | +12.52% | +10.24% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| ILS | 24.4→26.4 | +8.20% | +10.05% | +26.59% | +35.24% | +8.65% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VND | 16.45→17.6 | +6.99% | +8.84% | -10.59% | +4.80% | +15.39% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.7 | +5.88% | +7.73% | -14.27% | -0.06% | +14.21% | Y | — | — | — | — | —/— |
| VGI | 89.2→94.4 | +5.83% | +7.68% | -16.17% | +0.84% | +17.01% | Y | — | NEW_T1_MR | Y | none | Y/N |
| F88 | 147.9→155.9 | +5.41% | +7.26% | +4.00% | -4.29% | -8.29% | — | — | WATCH_ONLY | — | none | Y/Y |
| DHA | 47.4→49.75 | +4.96% | +6.81% | -5.84% | +7.79% | +13.63% | Y | — | — | — | — | —/— |
| VCB | 60.7→63.7 | +4.94% | +6.79% | -5.86% | +5.69% | +11.55% | Y | Y | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| LPB | 51.5→54.0 | +4.85% | +6.71% | -0.93% | +13.35% | +14.28% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| KSV | 157.3→164.5 | +4.58% | +6.43% | -8.41% | +0.63% | +9.04% | Y | — | NO_T2_BREADTH | — | lead_11_20 | Y/Y |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C69 | 15.9→17.9 | +12.58% | +14.43% | -10.67% | +11.03% | +21.70% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.55 | +9.52% | +11.37% | -43.19% | -26.06% | +17.13% | Y | Y | not_in_scan | — | — | —/— |
| NVB | 10.6→11.6 | +9.43% | +11.29% | -14.41% | +3.91% | +18.32% | Y | — | — | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.15% | -0.72% | +13.09% | +13.81% | Y | — | — | — | — | —/— |
| CTR | 84.9→92.0 | +8.36% | +10.21% | -10.63% | +6.69% | +17.32% | Y | — | NEW_T1_MR | Y | same_day | Y/Y |
| VPL | 88.4→95.7 | +8.26% | +10.11% | +2.28% | +12.52% | +10.24% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| ILS | 24.4→26.4 | +8.20% | +10.05% | +26.59% | +35.24% | +8.65% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| VND | 16.45→17.6 | +6.99% | +8.84% | -10.59% | +4.80% | +15.39% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.7 | +5.88% | +7.73% | -14.27% | -0.06% | +14.21% | Y | — | — | — | — | —/— |
| VGI | 89.2→94.4 | +5.83% | +7.68% | -16.17% | +0.84% | +17.01% | Y | — | NEW_T1_MR | Y | none | Y/N |
| DHA | 47.4→49.75 | +4.96% | +6.81% | -5.84% | +7.79% | +13.63% | Y | — | — | — | — | —/— |
| VCB | 60.7→63.7 | +4.94% | +6.79% | -5.86% | +5.69% | +11.55% | Y | Y | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| LPB | 51.5→54.0 | +4.85% | +6.71% | -0.93% | +13.35% | +14.28% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| KSV | 157.3→164.5 | +4.58% | +6.43% | -8.41% | +0.63% | +9.04% | Y | — | NO_T2_BREADTH | — | lead_11_20 | Y/Y |
| TIG | 6.6→6.9 | +4.55% | +6.40% | -13.93% | +1.44% | +15.37% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ABB | 15.2→15.5 | +1.97% | +3.82% | -4.11% | +2.48% | +6.59% | Y | — | WATCH_ONLY | — | none | Y/Y |
| TSA | 15.4→15.7 | +1.95% | +3.80% | -8.22% | +1.07% | +9.29% | Y | — | — | — | — | —/— |
| PAN | 32.95→33.55 | +1.82% | +3.67% | -3.12% | +1.84% | +4.96% | Y | — | — | — | — | —/— |
| VGT | 11.7→11.9 | +1.71% | +3.56% | -14.62% | -2.38% | +12.24% | Y | — | — | — | — | —/— |
| TV1 | 23.5→23.9 | +1.70% | +3.55% | -38.49% | -21.88% | +16.61% | Y | — | — | — | — | —/— |
| CTF | 17.9→18.2 | +1.68% | +3.53% | -9.32% | -0.44% | +8.88% | Y | — | — | — | — | —/— |
| MBS | 19.4→19.7 | +1.55% | +3.40% | -14.50% | -2.05% | +12.45% | Y | — | — | — | — | —/— |
| VFS | 13.1→13.3 | +1.53% | +3.38% | -10.46% | +1.55% | +12.01% | Y | — | — | — | — | —/— |
| VJC | 171.3→173.8 | +1.46% | +3.31% | -5.52% | -2.63% | +2.89% | Y | — | TRAIL_EXIT | — | same_day | Y/Y |
| FUEVN100 | 26.44→26.8 | +1.36% | +3.21% | -4.41% | +1.14% | +5.55% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| BIC | 23.15→23.45 | +1.30% | +3.15% | -9.92% | -2.81% | +7.11% | Y | — | WATCH_ONLY | — | none | N/N |
| DPG | 40.1→40.6 | +1.25% | +3.10% | -17.08% | -5.79% | +11.29% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| PSI | 8.5→8.6 | +1.18% | +3.03% | -0.62% | +5.95% | +6.57% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| NBC | 8.6→8.7 | +1.16% | +3.01% | -23.91% | -10.92% | +12.99% | Y | — | — | — | — | —/— |
| MIG | 17.3→17.5 | +1.16% | +3.01% | -16.20% | -0.97% | +15.23% | Y | — | TRAIL_EXIT | — | same_day | N/N |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TCX | 51.2→43.4 | -15.23% | -13.38% | -10.70% | -16.11% | -5.41% | — | Y | not_in_scan | — | — | —/— |
| PVP | 19.85→17.25 | -13.10% | -11.25% | +28.21% | -2.98% | -31.19% | — | — | TRAIL_EXIT | — | same_day | Y/Y |
| REE | 60.3→52.4 | -13.10% | -11.25% | -16.72% | -20.68% | -3.96% | — | — | — | — | — | —/— |
| HPA | 38.45→33.8 | -12.09% | -10.24% | -7.30% | -11.41% | -4.11% | — | — | — | — | — | —/— |
| BMP | 157.2→139.4 | -11.32% | -9.47% | +1.48% | -8.61% | -10.09% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| BSR | 31.75→28.2 | -11.18% | -9.33% | +12.50% | +7.12% | -5.38% | — | — | WATCH_ONLY | — | none | Y/Y |
| PVD | 33.7→30.0 | -10.98% | -9.13% | -6.87% | -7.50% | -0.63% | — | — | — | — | — | —/— |
| NVL | 17.3→15.5 | -10.40% | -8.55% | -7.05% | -18.88% | -11.83% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| FTS | 26.65→23.9 | -10.32% | -8.47% | -12.87% | -12.03% | +0.84% | — | — | — | — | — | —/— |
| HPG | 26.55→24.1 | -9.23% | -7.38% | -15.22% | -16.09% | -0.87% | — | — | TRAIL_EXIT | — | same_day | N/N |
| GVR | 37.75→34.3 | -9.14% | -7.29% | +7.22% | +3.19% | -4.03% | — | — | TRAIL_EXIT | — | after_a3 | Y/Y |
| DIG | 14.95→13.6 | -9.03% | -7.18% | -6.86% | -5.43% | +1.43% | Y | — | — | — | — | —/— |
| PIV | 8.1→7.4 | -8.64% | -6.79% | +7.49% | -4.18% | -11.67% | — | — | WATCH_ONLY | — | none | Y/Y |
| DRI | 15.1→13.8 | -8.61% | -6.76% | +8.83% | +4.61% | -4.22% | — | — | TRAIL_EXIT | — | none | Y/Y |
| PVT | 24.05→22.0 | -8.52% | -6.67% | +1.85% | -2.67% | -4.52% | — | — | WATCH_ONLY | — | none | Y/Y |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## H. Delta vs Previous