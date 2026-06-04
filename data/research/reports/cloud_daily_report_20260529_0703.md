# Cloud Daily Report — 2026-05-29 07:03 UTC

**Mode:** PRE-LUNCH PREVIEW | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.82bn VND | **Positions:** data\raw\current_positions_derived.json

> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW
> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged
- intraday_quote_coverage_pct < 100%: 99.0%
- missing_quote_count=1

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: VEA (breadth gate)
- Review would-be A3 candidate(s) if close now; wait for EOD confirmation. (GSP, VEA)
- Review exit-risk holdings: HCM, PVS, HDB, MSB, POW, VHM

### WATCH / PREPARE
- 2 would-be NEW_T1 if close now
- S3 paper setups: 17
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 28.4%)
- Do not trade S3 as live capital
- Do not use intraday preview as order source
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VEA | NEW_T1_MANUAL_REVIEW_BREADTH | 0.95 | 34.80 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 157.00 | 2.94 |
| VGI | NO_T2_BREADTH | 93.50 | 0.99 |
| SAB | NO_T2_BREADTH | 47.20 | 0.98 |
| BID | NO_T2_BREADTH | 42.50 | 0.98 |
| VCB | NO_T2_BREADTH | 62.80 | 0.97 |
| VTO | NO_T2_BREADTH | 12.10 | 0.96 |
| CTR | NO_T2_BREADTH | 90.00 | 0.94 |
| TRC | NO_T2_BREADTH | 76.00 | 0.93 |
| LPB | NO_T2_BREADTH | 53.00 | 0.88 |
| OIL | NO_T2_BREADTH | 14.70 | 0.86 |
| PSI | NO_T2_BREADTH | 8.90 | 0.80 |
| ILS | NO_T2_BREADTH | 27.00 | 0.61 |
| FUEVN100 | NO_T2_BREADTH | 26.80 | 0.47 |
| QNS | NO_T2_BREADTH | 48.50 | 0.46 |
| PHP | NO_T2_BREADTH | 36.80 | 0.45 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.35 | 22.32 | Close 21.35 < trail 22.325 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.60 | 22.78 | Close 20.6 < trail 22.78 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.45 | 16.83 | Close 15.45 < trail 16.832 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.60 | 8.33 | Close 7.6 < trail 8.329 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.00 | 14.56 | Close 14.0 < trail 14.564 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | TRAIL_EXIT | 11.20 | 11.29 | Close 11.2 < trail 11.295 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 32.25 | 33.88 | Close 32.25 < trail 33.884 (2.5xATR14). Exit remaining per A3 rules. |
| KOS | TRAIL_EXIT | 37.90 | 38.43 | Close 37.9 < trail 38.432 (2.5xATR14). Exit remaining per A3 rules. |
| TCB | TRAIL_EXIT | 32.60 | 32.75 | Close 32.6 < trail 32.748 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 27.55 | 28.95 | Close 27.55 < trail 28.946 (2.5xATR14). Exit remaining per A3 rules. |
| VPL | TRAIL_EXIT | 91.80 | 92.72 | Close 91.8 < trail 92.718 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.10 | 14.37 | Close 14.1 < trail 14.366 (2.5xATR14). Exit remaining per A3 rules. |
| TDP | TRAIL_EXIT | 28.80 | 29.23 | Close 28.8 < trail 29.234 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.10 | 13.41 | Close 13.1 < trail 13.414 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.60 | 44.72 | Close 41.6 < trail 44.718 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 58.80 | 61.29 | Close 58.8 < trail 61.289 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 75.50 | 78.95 | Close 75.5 < trail 78.946 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.50 | 17.01 | Close 15.5 < trail 17.014 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 38.70 | 40.29 | Close 38.7 < trail 40.286 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 25.85 | 26.89 | Close 25.85 < trail 26.889 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 34.35 | 36.54 | Close 34.35 < trail 36.541 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 77.70 | 83.12 | Close 77.7 < trail 83.125 (2.5xATR14). Exit remaining per A3 rules. |
| DXS | TRAIL_EXIT | 7.64 | 7.74 | Close 7.64 < trail 7.736 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.00 | 6.76 | Close 6.0 < trail 6.757 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 138.30 | 146.70 | Close 138.3 < trail 146.696 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 30.60 | 33.86 | Close 30.6 < trail 33.864 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.25 | 13.15 | Close 11.25 < trail 13.146 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.05 | 19.65 | Close 15.05 < trail 19.652 (2.5xATR14). Exit remaining per A3 rules. |
| MSB | TP1_PARTIAL | 15.10 | 14.74 | Close 15.1 >= TP1 15.045 (+18%). Take partial per A3 DP-first. |
| HHS | TRAIL_EXIT | 11.40 | 13.30 | Close 11.4 < trail 13.302 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.20 | 7.43 | Close 7.2 < trail 7.432 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 35.79 | 36.28 | Close 35.79 < trail 36.277 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.60 | 23.26 | Close 22.6 < trail 23.257 (2.5xATR14). Exit remaining per A3 rules. |
| POW | TRAIL_EXIT | 13.85 | 13.88 | Close 13.85 < trail 13.88 (2.5xATR14). Exit remaining per A3 rules. |
| CDC | TRAIL_EXIT | 20.80 | 20.92 | Close 20.8 < trail 20.921 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.65 | 36.23 | Close 34.65 < trail 36.227 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.65 | 2.84 | Close 2.65 < trail 2.844 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 170.40 | 176.68 | Close 170.4 < trail 176.679 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.50 | 42.91 | Close 40.5 < trail 42.914 (2.5xATR14). Exit remaining per A3 rules. |
| PVP | TRAIL_EXIT | 17.50 | 18.88 | Close 17.5 < trail 18.875 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 157.70 | 153.38 | Close 157.7 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| HPG | TRAIL_EXIT | 24.00 | 27.61 | Close 24.0 < trail 27.613 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 107.80 | 191.66 | Close 107.8 < trail 191.664 (2.5xATR14). Exit remaining per A3 rules. |

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
| vnindex_raw | 2026-05-28 | 2026-05-28 | no |
| ex_vin_proxy | 2026-05-28 | 2026-05-28 | no |
| vin_group | 2026-05-28 | 2026-05-28 | no |
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-27**
- Index as-of: **2026-05-28**
- Breadth lag (sessions): **1**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **CORRECTION_RISK** (dist 10/25/50: 3/6/9)
- ex-VIN proxy: **CORRECTION_RISK** (dist 10/25/50: 4/6/8)
- VIN distortion flag: **False**
- VIN group warning: **DOWNTREND_WARNING**
- Distribution Risk Lens is market context only and does not change final_action.
- **ex-VIN proxy is derived and is NOT a native exchange index.**
- _NOT true ex-VIN index; see vnindex_low_dist_ex_vin.py methodology_
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **41.6% (base 39.0%)**
- P(-5% correction within 25D) ex-VIN: **42.1% (base 40.5%)**
- P(-10% correction within 75D) ex-VIN: **47.8% (base 44.3%)**
- Comparison: Raw and ex-VIN proxy broadly aligned on distribution warning.


### RS vs VNINDEX (correction leg)

| Metric | Value |
| --- | --- |
| Anchor date | 2026-05-15 (close 1921.6) |
| End date | 2026-05-28 (close 1863.67) |
| VNINDEX return | -3.01% |
| Drawdown from peak | -3.01% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 171 |
| Leaders (RS≥+3%) | 75 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C69 | 15.9→17.8 | +11.95% | +14.96% | -10.67% | +14.02% | +24.69% | Y | — | — | — | — | —/— |
| VVS | 105.0→117.0 | +11.43% | +14.44% | -21.59% | -1.85% | +19.74% | Y | — | — | — | — | —/— |
| ILS | 24.4→27.0 | +10.66% | +13.67% | +26.59% | +26.23% | -0.36% | — | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| POM | 4.3→4.7 | +9.30% | +12.32% | -0.72% | +21.16% | +21.88% | Y | — | — | — | — | —/— |
| MSB | 13.9→15.1 | +8.63% | +11.65% | +1.23% | +21.45% | +20.22% | Y | Y | TP1_PARTIAL | — | lead_1_5 | Y/Y |
| VND | 16.45→17.8 | +8.21% | +11.22% | -10.59% | +11.55% | +22.14% | Y | Y | WATCH_ONLY | — | none | N/Y |
| MIG | 17.3→18.6 | +7.51% | +10.53% | -16.20% | +6.33% | +22.53% | Y | — | WATCH_ONLY | — | none | N/N |
| F88 | 147.9→159.0 | +7.51% | +10.52% | +4.00% | -4.08% | -8.08% | — | — | WATCH_ONLY | — | none | Y/Y |
| PC1 | 17.85→19.05 | +6.72% | +9.74% | -43.19% | -8.20% | +34.99% | Y | Y | not_in_scan | — | — | —/— |
| NAF | 49.9→53.2 | +6.61% | +9.63% | -9.21% | +7.26% | +16.47% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.3 | +6.60% | +9.62% | -14.41% | +6.26% | +20.67% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.0 | +6.01% | +9.02% | -10.63% | +3.74% | +14.37% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| ACB | 23.3→24.65 | +5.79% | +8.81% | -11.14% | +5.54% | +16.68% | Y | Y | WATCH_ONLY | — | none | N/Y |
| MST | 7.8→8.2 | +5.13% | +8.14% | -15.36% | +1.88% | +17.24% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.3 | +4.99% | +8.01% | -14.27% | +5.99% | +20.26% | Y | — | — | — | — | —/— |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C69 | 15.9→17.8 | +11.95% | +14.96% | -10.67% | +14.02% | +24.69% | Y | — | — | — | — | —/— |
| VVS | 105.0→117.0 | +11.43% | +14.44% | -21.59% | -1.85% | +19.74% | Y | — | — | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +12.32% | -0.72% | +21.16% | +21.88% | Y | — | — | — | — | —/— |
| MSB | 13.9→15.1 | +8.63% | +11.65% | +1.23% | +21.45% | +20.22% | Y | Y | TP1_PARTIAL | — | lead_1_5 | Y/Y |
| VND | 16.45→17.8 | +8.21% | +11.22% | -10.59% | +11.55% | +22.14% | Y | Y | WATCH_ONLY | — | none | N/Y |
| MIG | 17.3→18.6 | +7.51% | +10.53% | -16.20% | +6.33% | +22.53% | Y | — | WATCH_ONLY | — | none | N/N |
| PC1 | 17.85→19.05 | +6.72% | +9.74% | -43.19% | -8.20% | +34.99% | Y | Y | not_in_scan | — | — | —/— |
| NAF | 49.9→53.2 | +6.61% | +9.63% | -9.21% | +7.26% | +16.47% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.3 | +6.60% | +9.62% | -14.41% | +6.26% | +20.67% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.0 | +6.01% | +9.02% | -10.63% | +3.74% | +14.37% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| ACB | 23.3→24.65 | +5.79% | +8.81% | -11.14% | +5.54% | +16.68% | Y | Y | WATCH_ONLY | — | none | N/Y |
| MST | 7.8→8.2 | +5.13% | +8.14% | -15.36% | +1.88% | +17.24% | Y | — | — | — | — | —/— |
| NNC | 45.05→47.3 | +4.99% | +8.01% | -14.27% | +5.99% | +20.26% | Y | — | — | — | — | —/— |
| VGI | 89.2→93.5 | +4.82% | +7.84% | -16.17% | +3.51% | +19.68% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| PSI | 8.5→8.9 | +4.71% | +7.72% | -0.62% | +10.53% | +11.15% | Y | — | NO_T2_BREADTH | — | lead_1_5 | Y/Y |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ABB | 15.2→15.5 | +1.97% | +4.99% | -4.11% | +3.98% | +8.09% | Y | — | WATCH_ONLY | — | none | Y/Y |
| VAB | 10.2→10.4 | +1.96% | +4.98% | -10.14% | +2.11% | +12.25% | Y | — | — | — | — | —/— |
| KLB | 14.15→14.4 | +1.77% | +4.78% | -8.22% | +0.65% | +8.87% | Y | — | WATCH_ONLY | — | none | N/N |
| VGS | 23.2→23.6 | +1.72% | +4.74% | -16.88% | -3.02% | +13.86% | Y | — | — | — | — | —/— |
| SHS | 17.7→18.0 | +1.69% | +4.71% | -10.43% | +8.43% | +18.86% | Y | — | — | — | — | —/— |
| BVS | 26.0→26.4 | +1.54% | +4.55% | -14.02% | +4.18% | +18.20% | Y | — | — | — | — | —/— |
| TIG | 6.6→6.7 | +1.52% | +4.53% | -13.93% | +0.65% | +14.58% | Y | — | — | — | — | —/— |
| APS | 6.7→6.8 | +1.49% | +4.51% | -0.16% | +15.90% | +16.06% | Y | — | WATCH_ONLY | — | none | N/Y |
| VEA | 34.3→34.8 | +1.46% | +4.47% | -5.83% | +5.15% | +10.98% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| CTF | 17.9→18.15 | +1.40% | +4.41% | -9.32% | -2.81% | +6.51% | Y | — | — | — | — | —/— |
| FUEVN100 | 26.44→26.8 | +1.36% | +4.38% | -4.41% | +2.59% | +7.00% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| HNM | 7.5→7.6 | +1.33% | +4.35% | -14.47% | -0.65% | +13.82% | Y | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| TPB | 15.7→15.9 | +1.27% | +4.29% | -12.78% | -1.51% | +11.27% | Y | — | — | — | — | —/— |
| CSM | 11.9→12.05 | +1.26% | +4.28% | -12.25% | -1.38% | +10.87% | Y | — | — | — | — | —/— |
| VIB | 16.1→16.3 | +1.24% | +4.26% | -16.74% | -5.40% | +11.34% | Y | — | — | — | — | —/— |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TAL | 45.95→31.0 | -32.54% | -29.52% | -5.77% | -30.15% | -24.38% | — | — | — | — | — | —/— |
| CRC | 8.21→6.67 | -18.76% | -15.74% | -18.98% | -26.22% | -7.24% | — | — | — | — | — | —/— |
| TCX | 51.2→41.8 | -18.36% | -15.34% | -10.70% | -17.55% | -6.85% | — | Y | not_in_scan | — | — | —/— |
| DXG | 16.05→13.35 | -16.82% | -13.81% | -3.66% | -9.75% | -6.09% | — | — | WATCH_ONLY | — | none | N/N |
| NVL | 17.3→15.05 | -13.01% | -9.99% | -7.05% | -25.94% | -18.89% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| SSB | 16.5→14.45 | -12.42% | -9.41% | -11.16% | -12.56% | -1.40% | — | — | WATCH_ONLY | — | none | N/N |
| HHS | 13.0→11.4 | -12.31% | -9.29% | -15.03% | -13.64% | +1.39% | Y | — | TRAIL_EXIT | — | lead_6_10 | N/N |
| REE | 60.3→53.0 | -12.11% | -9.09% | -16.72% | -11.02% | +5.70% | Y | — | — | — | — | —/— |
| BMP | 157.2→138.3 | -12.02% | -9.01% | +1.48% | -4.23% | -5.71% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| PVP | 19.85→17.5 | -11.84% | -8.82% | +28.21% | -0.48% | -28.69% | — | — | TRAIL_EXIT | — | same_day | Y/Y |
| VIW | 26.7→23.6 | -11.61% | -8.60% | -34.26% | -39.45% | -5.19% | — | — | — | — | — | —/— |
| HPA | 38.45→34.0 | -11.57% | -8.56% | -7.30% | -7.58% | -0.28% | — | — | — | — | — | —/— |
| PVD | 33.7→30.0 | -10.98% | -7.96% | -6.87% | -0.99% | +5.88% | Y | — | — | — | — | —/— |
| GEE | 121.0→107.8 | -10.91% | -7.89% | -46.17% | -38.45% | +7.72% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| FTS | 26.65→23.8 | -10.69% | -7.68% | -12.87% | -7.81% | +5.06% | Y | — | — | — | — | —/— |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## RS C3 Context (RS line acceleration)

**FACTS** (context only; does not change final_action)

> **OOS3 regime active:** C3 IC near zero in 2024+. Use as sort/display only — hard filter not operative.

_Data as of: 2026-05-25_

| Symbol | C3 Rating | C3 Zone | #Top50 | T2 Context | Late Chase | final_action | EMA dist% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DXS | 99 | EXTREME_RS | — | — | — | TRAIL_EXIT | -3.85% |
| CII | 98 | EXTREME_RS | #1 | — | — | WATCH_ONLY | — |
| VCG | 98 | EXTREME_RS | #2 | — | — | TRAIL_EXIT | -3.58% |
| APS | 98 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| LPB | 97 | EXTREME_RS | #3 | Y | — | NO_T2_BREADTH | +2.36% |
| L40 | 96 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| DXG | 93 | EXTREME_RS | #4 | — | — | WATCH_ONLY | — |
| HHS | 93 | EXTREME_RS | #5 | — | — | TRAIL_EXIT | -8.31% |
| TCH | 93 | EXTREME_RS | #6 | — | — | TRAIL_EXIT | -5.00% |
| NVL | 92 | EXTREME_RS | #7 | — | — | TRAIL_EXIT | -7.47% |
| GEX | 91 | EXTREME_RS | #8 | — | — | WATCH_ONLY | — |
| NRC | 90 | EXTREME_RS | — | — | — | TRAIL_EXIT | -4.09% |
| ASM | 89 | LEADER_ZONE | — | — | — | WATCH_ONLY | — |
| VIX | 88 | LEADER_ZONE | #9 | — | — | WATCH_ONLY | — |
| HUT | 87 | LEADER_ZONE | #10 | — | — | TRAIL_EXIT | -2.00% |

_RS C3 is review-ranking context only and does not set or override final_action. IC near zero in OOS3 2024+. Use as sort/prioritization display only._

**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet` · **classification:** REVIEW_RANKING_ONLY


## H. Delta vs Previous