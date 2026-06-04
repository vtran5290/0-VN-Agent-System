# Cloud Daily Report — 2026-05-25 16:07 UTC

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
| Anchor date | 2026-05-18 (close 1927.94) |
| End date | 2026-05-25 (close 1886.03) |
| VNINDEX return | -2.17% |
| Drawdown from peak | -2.17% |
| Detection | peak_in_lookback |
| Universe n | 272 |
| Outperform (RS>0) | 156 |
| Leaders (RS≥+3%) | 44 |

**Definitions:** `rs_pct` = stock return − VNINDEX return (anchor→end). `rs_improving_flag` = RS 20d at end > RS 20d at anchor + 1pp.

#### Top leaders (RS≥+3%)
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| POM | +11.90% | +14.08% | +13.09% | Yes | No |
| C69 | +11.87% | +14.05% | +11.03% | Yes | No |
| PC1 | +10.76% | +12.94% | -26.06% | Yes | No |
| VIW | +9.88% | +12.05% | -23.48% | Yes | No |
| NNC | +8.04% | +10.21% | -0.06% | Yes | No |
| NVB | +7.41% | +9.58% | +3.91% | Yes | No |
| F88 | +6.05% | +8.23% | -4.29% | No | No |
| VPL | +5.86% | +8.04% | +12.52% | Yes | Yes |
| DVM | +5.80% | +7.97% | -15.66% | Yes | No |
| HHP | +5.71% | +7.89% | +14.53% | Yes | No |
| VND | +5.71% | +7.88% | +4.80% | Yes | No |
| VGS | +5.70% | +7.88% | -5.15% | Yes | No |
| CTR | +5.38% | +7.56% | +6.69% | Yes | No |
| DHA | +4.96% | +7.13% | +7.79% | Yes | No |
| HSG | +4.58% | +6.76% | -22.62% | Yes | No |

#### RS improving + positive RS
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| POM | +11.90% | +14.08% | +13.09% | Yes | No |
| C69 | +11.87% | +14.05% | +11.03% | Yes | No |
| PC1 | +10.76% | +12.94% | -26.06% | Yes | No |
| VIW | +9.88% | +12.05% | -23.48% | Yes | No |
| NNC | +8.04% | +10.21% | -0.06% | Yes | No |
| NVB | +7.41% | +9.58% | +3.91% | Yes | No |
| VPL | +5.86% | +8.04% | +12.52% | Yes | Yes |
| DVM | +5.80% | +7.97% | -15.66% | Yes | No |
| HHP | +5.71% | +7.89% | +14.53% | Yes | No |
| VND | +5.71% | +7.88% | +4.80% | Yes | No |
| VGS | +5.70% | +7.88% | -5.15% | Yes | No |
| CTR | +5.38% | +7.56% | +6.69% | Yes | No |
| DHA | +4.96% | +7.13% | +7.79% | Yes | No |
| HSG | +4.58% | +6.76% | -22.62% | Yes | No |
| TIG | +4.55% | +6.72% | +1.44% | Yes | No |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| PAN | +1.98% | +4.15% | +1.84% | Yes | No |
| SBT | +1.95% | +4.12% | +0.65% | Yes | No |
| VHC | +1.69% | +3.87% | -5.08% | Yes | No |
| VJC | +1.58% | +3.75% | -2.63% | Yes | No |
| BMS | +1.40% | +3.57% | -4.88% | Yes | No |
| CTD | +1.37% | +3.54% | -10.05% | Yes | No |
| ABB | +1.31% | +3.48% | +2.48% | Yes | No |
| FMC | +1.29% | +3.46% | -11.80% | Yes | No |
| PAC | +1.13% | +3.31% | -5.22% | Yes | No |
| CTF | +1.11% | +3.28% | -0.44% | Yes | No |
| NKG | +1.09% | +3.27% | -6.03% | Yes | No |
| PHP | +1.10% | +3.27% | +1.82% | Yes | No |
| ELC | +0.93% | +3.10% | -10.23% | Yes | No |
| MSN | +0.92% | +3.09% | -3.83% | Yes | No |
| KSV | +0.92% | +3.09% | +0.63% | Yes | No |

#### Weakest RS
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| PVD | -16.20% | -14.03% | -7.50% | No | No |
| BSR | -15.70% | -13.52% | +7.12% | No | No |
| TCX | -14.06% | -11.89% | -16.11% | No | No |
| PVP | -13.75% | -11.58% | -2.98% | No | No |
| OIL | -13.53% | -11.36% | -2.89% | No | No |
| PVT | -13.04% | -10.87% | -2.67% | No | No |
| GVR | -12.72% | -10.55% | +3.19% | No | No |
| PVC | -12.50% | -10.33% | -10.81% | No | No |
| PLX | -12.07% | -9.90% | +0.25% | No | No |
| GAS | -11.83% | -9.65% | +3.45% | No | No |
| FTS | -11.81% | -9.63% | -12.03% | No | No |
| HID | -11.04% | -8.87% | -7.70% | Yes | No |
| PLC | -10.66% | -8.48% | -4.66% | No | No |
| PVS | -10.59% | -8.41% | -1.55% | No | No |
| DCM | -10.33% | -8.16% | -11.58% | No | No |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## H. Delta vs Previous