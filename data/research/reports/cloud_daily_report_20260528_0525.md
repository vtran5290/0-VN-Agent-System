# Cloud Daily Report — 2026-05-28 05:25 UTC

**Mode:** PRE-LUNCH PREVIEW | **VNINDEX:** BULL | **Breadth:** DEFENSE | **T1:** OK | **T2:** BLOCKED | **NAV:** 4.82bn VND | **Positions:** data\raw\current_positions_derived.json

> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW
> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.

> Daily scan is source of truth. AFL is visual only.

## Warnings
- Data starts 2012-01-03 (after 2012); shorter history flagged

## B. Decision Summary

### ACTION NOW
- Prepare manual review checklist for next-open candidates: CTR, VEA (breadth gate)
- Review would-be A3 candidate(s) if close now; wait for EOD confirmation. (VEA)
- Review exit-risk holdings: HCM, PVS

### WATCH / PREPARE
- 1 would-be NEW_T1 if close now
- S3 paper setups: 18
- T2 candidates (ADD_T2 + WAIT_PB): 0

### DO NOT DO
- Do not add T2 (breadth < 40%: 29.5%)
- Do not trade S3 as live capital
- Do not use intraday preview as order source
- Do not base orders on AFL visuals

## C. A3 Action Board

### Group 1: New T1 Candidates
| Symbol | Action | Rank | Close | PB | TP1 | Trail | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CTR | NEW_T1_MANUAL_REVIEW_BREADTH | 0.93 | 90.00 | 86.40 | 106.20 | 86.00 |  |
| VEA | NEW_T1_MANUAL_REVIEW_BREADTH | 0.88 | 35.20 | pending* | pending* | pending* | Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. |

*Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known.*

### Group 2: T2 / Pullback
| Symbol | Action | Close | Rank |
| --- | --- | --- | --- |
| KSV | NO_T2_BREADTH | 158.60 | 2.99 |
| TRC | NO_T2_BREADTH | 74.90 | 0.99 |
| SAB | NO_T2_BREADTH | 47.75 | 0.96 |
| VTO | NO_T2_BREADTH | 12.10 | 0.95 |
| DXS | NO_T2_BREADTH | 8.05 | 0.95 |
| BID | NO_T2_BREADTH | 43.30 | 0.93 |
| PSI | NO_T2_BREADTH | 8.70 | 0.89 |
| OIL | NO_T2_BREADTH | 14.80 | 0.88 |
| VCB | NO_T2_BREADTH | 64.20 | 0.85 |
| VGI | NO_T2_BREADTH | 96.00 | 0.85 |
| LPB | NO_T2_BREADTH | 54.00 | 0.77 |
| MSB | NO_T2_BREADTH | 15.00 | 0.58 |
| PHP | NO_T2_BREADTH | 36.80 | 0.44 |
| FUEVN100 | NO_T2_BREADTH | 26.94 | 0.44 |
| QNS | NO_T2_BREADTH | 48.80 | 0.42 |
| POW | NO_T2_BREADTH | 14.05 | 0.38 |
| ILS | NO_T2_BREADTH | 28.00 | 0.37 |

### Group 3: Exits
| Symbol | Action | Close | Trail | Reason |
| --- | --- | --- | --- | --- |
| EIB | TRAIL_EXIT | 21.95 | 22.41 | Close 21.95 < trail 22.414 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | TRAIL_EXIT | 20.80 | 22.76 | Close 20.8 < trail 22.762 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | TRAIL_EXIT | 15.75 | 16.87 | Close 15.75 < trail 16.868 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | TRAIL_EXIT | 7.60 | 8.31 | Close 7.6 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | TRAIL_EXIT | 26.70 | 27.01 | Close 26.7 < trail 27.014 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | TRAIL_EXIT | 14.10 | 14.56 | Close 14.1 < trail 14.564 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | TRAIL_EXIT | 11.20 | 11.29 | Close 11.2 < trail 11.286 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | TRAIL_EXIT | 76.50 | 78.98 | Close 76.5 < trail 78.982 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | TRAIL_EXIT | 13.15 | 13.40 | Close 13.15 < trail 13.405 (2.5xATR14). Exit remaining per A3 rules. |
| KOS | TRAIL_EXIT | 37.80 | 38.43 | Close 37.8 < trail 38.432 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | TRAIL_EXIT | 80.00 | 83.29 | Close 80.0 < trail 83.286 (2.5xATR14). Exit remaining per A3 rules. |
| VPL | TRAIL_EXIT | 91.70 | 92.74 | Close 91.7 < trail 92.736 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | TRAIL_EXIT | 41.70 | 44.58 | Close 41.7 < trail 44.575 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | TRAIL_EXIT | 14.10 | 14.37 | Close 14.1 < trail 14.366 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | TRAIL_EXIT | 27.50 | 28.91 | Close 27.5 < trail 28.911 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | TRAIL_EXIT | 15.60 | 17.01 | Close 15.6 < trail 17.014 (2.5xATR14). Exit remaining per A3 rules. |
| TDP | TRAIL_EXIT | 28.80 | 29.19 | Close 28.8 < trail 29.189 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | TRAIL_EXIT | 34.80 | 36.59 | Close 34.8 < trail 36.595 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | TRAIL_EXIT | 58.30 | 61.38 | Close 58.3 < trail 61.379 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | TRAIL_EXIT | 38.50 | 40.29 | Close 38.5 < trail 40.286 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | TRAIL_EXIT | 31.25 | 33.95 | Close 31.25 < trail 33.955 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | TRAIL_EXIT | 11.45 | 13.10 | Close 11.45 < trail 13.102 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | TRAIL_EXIT | 139.00 | 146.71 | Close 139.0 < trail 146.714 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | TRAIL_EXIT | 6.00 | 6.72 | Close 6.0 < trail 6.721 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | TRAIL_EXIT | 30.75 | 33.73 | Close 30.75 < trail 33.73 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | TRAIL_EXIT | 11.80 | 13.33 | Close 11.8 < trail 13.329 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | TRAIL_EXIT | 15.40 | 19.60 | Close 15.4 < trail 19.598 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | TRAIL_EXIT | 6.80 | 8.36 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | TRAIL_EXIT | 35.90 | 36.30 | Close 35.9 < trail 36.295 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | TRAIL_EXIT | 2.69 | 2.84 | Close 2.69 < trail 2.844 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | TRAIL_EXIT | 22.75 | 23.23 | Close 22.75 < trail 23.23 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | TRAIL_EXIT | 172.10 | 175.95 | Close 172.1 < trail 175.946 (2.5xATR14). Exit remaining per A3 rules. |
| CDC | TRAIL_EXIT | 20.80 | 20.90 | Close 20.8 < trail 20.904 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | TRAIL_EXIT | 34.65 | 36.19 | Close 34.65 < trail 36.191 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | TRAIL_EXIT | 7.30 | 7.43 | Close 7.3 < trail 7.432 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | TRAIL_EXIT | 40.70 | 42.95 | Close 40.7 < trail 42.95 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | TRAIL_EXIT | 18.20 | 19.65 | Close 18.2 < trail 19.646 (2.5xATR14). Exit remaining per A3 rules. |
| VHM | TP1_PARTIAL | 147.40 | 154.77 | Close 147.4 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |
| PVP | TRAIL_EXIT | 17.45 | 18.85 | Close 17.45 < trail 18.848 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | TRAIL_EXIT | 24.15 | 27.62 | Close 24.15 < trail 27.621 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | TRAIL_EXIT | 112.00 | 191.36 | Close 112.0 < trail 191.361 (2.5xATR14). Exit remaining per A3 rules. |

## G. Market Context
- VNINDEX regime: BULL
- A3 breadth: 0.2955
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
| vnindex_raw | 2026-05-27 | 2026-05-27 | no |
| ex_vin_proxy | 2026-05-27 | 2026-05-27 | no |
| vin_group | 2026-05-27 | 2026-05-27 | no |
#### v1.3 breadth staleness (read-only)
- Breadth status: **OK**
- Breadth as-of: **2026-05-27**
- Index as-of: **2026-05-27**
- Breadth lag (sessions): **0**
- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._
- VNINDEX raw: **CORRECTION_RISK** (dist 10/25/50: 4/6/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 4/6/8)
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
| End date | 2026-05-27 (close 1874.43) |
| VNINDEX return | -2.45% |
| Drawdown from peak | -2.45% |
| Detection | config_override |
| Universe n | 272 |
| Outperform (RS>0) | 176 |
| Leaders (RS≥+3%) | 83 |

**Definitions:** `RS leg` = stock return − VNINDEX return over correction anchor→end. `RS20 before/after` = 20d RS vs VNINDEX at anchor date vs end date; `Δ RS20` = after − before (pp). `Close (anchor→end)` = kVND close on anchor bar → end bar. Hold/T1/S3/A3 columns crosswalk Phase36 `final_action` (display only).

#### Top leaders (RS≥+3%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VVS | 105.0→120.5 | +14.76% | +17.22% | -21.59% | -7.73% | +13.86% | Y | — | — | — | — | —/— |
| ILS | 24.4→28.0 | +14.75% | +17.21% | +26.59% | +23.30% | -3.29% | — | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| C69 | 15.9→17.6 | +10.69% | +13.15% | -10.67% | +10.25% | +20.92% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.7 | +10.38% | +12.83% | -14.41% | +6.20% | +20.61% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.6 | +9.80% | +12.26% | -43.19% | -13.84% | +29.35% | Y | Y | not_in_scan | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.76% | -0.72% | +16.36% | +17.08% | Y | — | — | — | — | —/— |
| SSB | 16.5→17.9 | +8.48% | +10.94% | -11.16% | +6.37% | +17.53% | Y | — | WATCH_ONLY | — | none | N/Y |
| ACB | 23.3→25.2 | +8.15% | +10.61% | -11.14% | +6.55% | +17.69% | Y | Y | not_in_scan | — | — | —/— |
| MSB | 13.9→15.0 | +7.91% | +10.37% | +1.23% | +17.91% | +16.68% | Y | Y | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| VND | 16.45→17.75 | +7.90% | +10.36% | -10.59% | +8.43% | +19.02% | Y | Y | not_in_scan | — | — | —/— |
| VGI | 89.2→96.0 | +7.62% | +10.08% | -16.17% | +2.53% | +18.70% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| NAF | 49.9→53.3 | +6.81% | +9.27% | -9.21% | +4.61% | +13.82% | Y | — | — | — | — | —/— |
| OCB | 11.25→12.0 | +6.67% | +9.12% | -11.24% | +3.66% | +14.90% | Y | — | — | — | — | —/— |
| PET | 47.0→50.0 | +6.38% | +8.84% | -11.31% | +5.93% | +17.24% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.0 | +6.01% | +8.46% | -10.63% | +2.07% | +12.70% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |

#### RS improving + positive RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VVS | 105.0→120.5 | +14.76% | +17.22% | -21.59% | -7.73% | +13.86% | Y | — | — | — | — | —/— |
| C69 | 15.9→17.6 | +10.69% | +13.15% | -10.67% | +10.25% | +20.92% | Y | — | — | — | — | —/— |
| NVB | 10.6→11.7 | +10.38% | +12.83% | -14.41% | +6.20% | +20.61% | Y | — | — | — | — | —/— |
| PC1 | 17.85→19.6 | +9.80% | +12.26% | -43.19% | -13.84% | +29.35% | Y | Y | not_in_scan | — | — | —/— |
| POM | 4.3→4.7 | +9.30% | +11.76% | -0.72% | +16.36% | +17.08% | Y | — | — | — | — | —/— |
| SSB | 16.5→17.9 | +8.48% | +10.94% | -11.16% | +6.37% | +17.53% | Y | — | WATCH_ONLY | — | none | N/Y |
| ACB | 23.3→25.2 | +8.15% | +10.61% | -11.14% | +6.55% | +17.69% | Y | Y | not_in_scan | — | — | —/— |
| MSB | 13.9→15.0 | +7.91% | +10.37% | +1.23% | +17.91% | +16.68% | Y | Y | NO_T2_BREADTH | — | lead_1_5 | Y/Y |
| VND | 16.45→17.75 | +7.90% | +10.36% | -10.59% | +8.43% | +19.02% | Y | Y | not_in_scan | — | — | —/— |
| VGI | 89.2→96.0 | +7.62% | +10.08% | -16.17% | +2.53% | +18.70% | Y | — | NO_T2_BREADTH | — | after_a3 | Y/Y |
| NAF | 49.9→53.3 | +6.81% | +9.27% | -9.21% | +4.61% | +13.82% | Y | — | — | — | — | —/— |
| OCB | 11.25→12.0 | +6.67% | +9.12% | -11.24% | +3.66% | +14.90% | Y | — | — | — | — | —/— |
| PET | 47.0→50.0 | +6.38% | +8.84% | -11.31% | +5.93% | +17.24% | Y | — | — | — | — | —/— |
| CTR | 84.9→90.0 | +6.01% | +8.46% | -10.63% | +2.07% | +12.70% | Y | — | NEW_T1_MR | Y | lead_1_5 | Y/Y |
| VAB | 10.2→10.8 | +5.88% | +8.34% | -10.14% | +4.23% | +14.37% | Y | — | — | — | — | —/— |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FUEVN100 | 26.44→26.94 | +1.89% | +4.35% | -4.41% | +1.68% | +6.09% | Y | — | NO_T2_BREADTH | — | same_day | Y/Y |
| VPB | 27.55→28.05 | +1.81% | +4.27% | -7.49% | +1.80% | +9.29% | Y | — | HOLD_T1_ONLY | — | lead_1_5 | N/Y |
| VGT | 11.7→11.9 | +1.71% | +4.16% | -14.62% | -2.79% | +11.83% | Y | — | — | — | — | —/— |
| CTF | 17.9→18.2 | +1.68% | +4.13% | -9.32% | -3.29% | +6.03% | Y | — | — | — | — | —/— |
| BVH | 67.1→68.1 | +1.49% | +3.95% | -18.99% | -6.29% | +12.70% | Y | — | — | — | — | —/— |
| DPG | 40.1→40.7 | +1.50% | +3.95% | -17.08% | -9.16% | +7.92% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| EVF | 13.65→13.85 | +1.47% | +3.92% | -9.66% | +4.58% | +14.24% | Y | — | — | — | — | —/— |
| GEG | 14.15→14.35 | +1.41% | +3.87% | -16.63% | -2.85% | +13.78% | Y | — | — | — | — | —/— |
| PAT | 66.6→67.5 | +1.35% | +3.81% | -16.99% | -3.03% | +13.96% | Y | — | — | — | — | —/— |
| DSE | 22.45→22.75 | +1.34% | +3.79% | -14.29% | -5.15% | +9.14% | Y | — | TRAIL_EXIT | — | same_day | N/N |
| HNM | 7.5→7.6 | +1.33% | +3.79% | -14.47% | -2.44% | +12.03% | Y | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| CTS | 28.05→28.4 | +1.25% | +3.70% | -8.22% | +6.44% | +14.66% | Y | — | — | — | — | —/— |
| NBC | 8.6→8.7 | +1.16% | +3.62% | -23.91% | -6.58% | +17.33% | Y | — | — | — | — | —/— |
| CMG | 27.7→28.0 | +1.08% | +3.54% | -14.16% | -0.42% | +13.74% | Y | — | — | — | — | —/— |
| NKG | 13.8→13.95 | +1.09% | +3.54% | -16.53% | -4.60% | +11.93% | Y | — | — | — | — | —/— |

#### Weakest RS
| Symbol | Close (anchor→end) | Ret leg | RS leg | RS20 before | RS20 after | Δ RS20 | Impr | Hold | final_action | T1 | S3 lead | A3/S3 cloud |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TAL | 45.95→31.45 | -31.56% | -29.10% | -5.77% | -31.71% | -25.94% | — | — | — | — | — | —/— |
| TCX | 51.2→43.0 | -16.02% | -13.56% | -10.70% | -15.65% | -4.95% | — | Y | not_in_scan | — | — | —/— |
| CRC | 8.21→7.17 | -12.67% | -10.21% | -18.98% | -24.46% | -5.48% | — | — | — | — | — | —/— |
| PVP | 19.85→17.45 | -12.09% | -9.64% | +28.21% | -4.20% | -32.41% | — | — | TRAIL_EXIT | — | same_day | Y/Y |
| HPA | 38.45→33.95 | -11.70% | -9.25% | -7.30% | -10.61% | -3.31% | — | — | — | — | — | —/— |
| REE | 60.3→53.3 | -11.61% | -9.15% | -16.72% | -15.59% | +1.13% | Y | — | — | — | — | —/— |
| BMP | 157.2→139.0 | -11.58% | -9.12% | +1.48% | -6.58% | -8.06% | — | — | TRAIL_EXIT | — | lead_1_5 | N/N |
| BSR | 31.75→28.25 | -11.02% | -8.57% | +12.50% | +11.86% | -0.64% | — | — | WATCH_ONLY | — | none | Y/Y |
| NVL | 17.3→15.4 | -10.98% | -8.53% | -7.05% | -21.96% | -14.91% | — | — | TRAIL_EXIT | — | lead_1_5 | Y/Y |
| VIW | 26.7→23.8 | -10.86% | -8.41% | -34.26% | -48.02% | -13.76% | — | — | — | — | — | —/— |
| PVD | 33.7→30.15 | -10.53% | -8.08% | -6.87% | -5.12% | +1.75% | Y | — | — | — | — | —/— |
| PIV | 8.1→7.3 | -9.88% | -7.42% | +7.49% | -1.14% | -8.63% | — | — | WATCH_ONLY | — | none | Y/Y |
| FTS | 26.65→24.05 | -9.76% | -7.30% | -12.87% | -10.21% | +2.66% | Y | — | — | — | — | —/— |
| HHS | 13.0→11.8 | -9.23% | -6.78% | -15.03% | -12.42% | +2.61% | Y | — | TRAIL_EXIT | — | lead_6_10 | N/N |
| HPG | 26.55→24.15 | -9.04% | -6.58% | -15.22% | -14.58% | +0.64% | — | — | TRAIL_EXIT | — | same_day | N/N |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## RS C3 Context (RS line acceleration)

**FACTS** (context only; does not change final_action)

> **OOS3 regime active:** C3 IC near zero in 2024+. Use as sort/display only — hard filter not operative.

_Data as of: 2026-05-25_

| Symbol | C3 Rating | C3 Zone | #Top50 | T2 Context | Late Chase | final_action | EMA dist% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DXS | 99 | EXTREME_RS | — | Y | — | NO_T2_BREADTH | +0.90% |
| CII | 98 | EXTREME_RS | #1 | — | — | WATCH_ONLY | — |
| VCG | 98 | EXTREME_RS | #2 | — | — | TRAIL_EXIT | -3.01% |
| APS | 98 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| LPB | 97 | EXTREME_RS | #3 | Y | — | NO_T2_BREADTH | +4.56% |
| L40 | 96 | EXTREME_RS | — | — | — | WATCH_ONLY | — |
| DXG | 93 | EXTREME_RS | #4 | — | — | WATCH_ONLY | — |
| HHS | 93 | EXTREME_RS | #5 | — | — | TRAIL_EXIT | -5.91% |
| TCH | 93 | EXTREME_RS | #6 | — | — | TRAIL_EXIT | -3.67% |
| NVL | 92 | EXTREME_RS | #7 | — | — | TRAIL_EXIT | -6.05% |
| GEX | 91 | EXTREME_RS | #8 | — | — | WATCH_ONLY | — |
| NRC | 90 | EXTREME_RS | — | — | — | TRAIL_EXIT | -4.50% |
| ASM | 89 | LEADER_ZONE | — | — | — | WATCH_ONLY | — |
| VIX | 88 | LEADER_ZONE | #9 | — | — | WATCH_ONLY | — |
| HUT | 87 | LEADER_ZONE | #10 | — | — | TRAIL_EXIT | -1.57% |

_RS C3 is review-ranking context only and does not set or override final_action. IC near zero in OOS3 2024+. Use as sort/prioritization display only._

**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet` · **classification:** REVIEW_RANKING_ONLY


## H. Delta vs Previous