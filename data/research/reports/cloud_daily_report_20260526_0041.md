# Cloud Daily Report — 2026-05-26 00:41 UTC

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

**Definitions:** `rs_pct` = stock return − VNINDEX return (anchor→end). `rs_improving_flag` = RS 20d at end > RS 20d at anchor + 1pp.

#### Top leaders (RS≥+3%)
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| C69 | +12.58% | +14.43% | +11.03% | Yes | No |
| PC1 | +9.52% | +11.37% | -26.06% | Yes | No |
| NVB | +9.43% | +11.29% | +3.91% | Yes | No |
| POM | +9.30% | +11.15% | +13.09% | Yes | No |
| CTR | +8.36% | +10.21% | +6.69% | Yes | No |
| VPL | +8.26% | +10.11% | +12.52% | Yes | Yes |
| ILS | +8.20% | +10.05% | +35.24% | Yes | No |
| VND | +6.99% | +8.84% | +4.80% | Yes | No |
| NNC | +5.88% | +7.73% | -0.06% | Yes | No |
| VGI | +5.83% | +7.68% | +0.84% | Yes | No |
| F88 | +5.41% | +7.26% | -4.29% | No | No |
| DHA | +4.96% | +6.81% | +7.79% | Yes | No |
| VCB | +4.94% | +6.79% | +5.69% | Yes | No |
| LPB | +4.85% | +6.71% | +13.35% | Yes | No |
| KSV | +4.58% | +6.43% | +0.63% | Yes | No |

#### RS improving + positive RS
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| C69 | +12.58% | +14.43% | +11.03% | Yes | No |
| PC1 | +9.52% | +11.37% | -26.06% | Yes | No |
| NVB | +9.43% | +11.29% | +3.91% | Yes | No |
| POM | +9.30% | +11.15% | +13.09% | Yes | No |
| CTR | +8.36% | +10.21% | +6.69% | Yes | No |
| VPL | +8.26% | +10.11% | +12.52% | Yes | Yes |
| ILS | +8.20% | +10.05% | +35.24% | Yes | No |
| VND | +6.99% | +8.84% | +4.80% | Yes | No |
| NNC | +5.88% | +7.73% | -0.06% | Yes | No |
| VGI | +5.83% | +7.68% | +0.84% | Yes | No |
| DHA | +4.96% | +6.81% | +7.79% | Yes | No |
| VCB | +4.94% | +6.79% | +5.69% | Yes | No |
| LPB | +4.85% | +6.71% | +13.35% | Yes | No |
| KSV | +4.58% | +6.43% | +0.63% | Yes | No |
| TIG | +4.55% | +6.40% | +1.44% | Yes | No |

#### Defensive flat (ret −1%…+2%, RS≥+1%)
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| ABB | +1.97% | +3.82% | +2.48% | Yes | No |
| TSA | +1.95% | +3.80% | +1.07% | Yes | No |
| PAN | +1.82% | +3.67% | +1.84% | Yes | No |
| VGT | +1.71% | +3.56% | -2.38% | Yes | No |
| TV1 | +1.70% | +3.55% | -21.88% | Yes | No |
| CTF | +1.68% | +3.53% | -0.44% | Yes | No |
| MBS | +1.55% | +3.40% | -2.05% | Yes | No |
| VFS | +1.53% | +3.38% | +1.55% | Yes | No |
| VJC | +1.46% | +3.31% | -2.63% | Yes | No |
| FUEVN100 | +1.36% | +3.21% | +1.14% | Yes | No |
| BIC | +1.30% | +3.15% | -2.81% | Yes | No |
| DPG | +1.25% | +3.10% | -5.79% | Yes | No |
| PSI | +1.18% | +3.03% | +5.95% | Yes | No |
| NBC | +1.16% | +3.01% | -10.92% | Yes | No |
| MIG | +1.16% | +3.01% | -0.97% | Yes | No |

#### Weakest RS
| Symbol | Ret | RS | RS20 end | Improving | VIN |
| --- | --- | --- | --- | --- | --- |
| TCX | -15.23% | -13.38% | -16.11% | No | No |
| PVP | -13.10% | -11.25% | -2.98% | No | No |
| REE | -13.10% | -11.25% | -20.68% | No | No |
| HPA | -12.09% | -10.24% | -11.41% | No | No |
| BMP | -11.32% | -9.47% | -8.61% | No | No |
| BSR | -11.18% | -9.33% | +7.12% | No | No |
| PVD | -10.98% | -9.13% | -7.50% | No | No |
| NVL | -10.40% | -8.55% | -18.88% | No | No |
| FTS | -10.32% | -8.47% | -12.03% | No | No |
| HPG | -9.23% | -7.38% | -16.09% | No | No |
| GVR | -9.14% | -7.29% | +3.19% | No | No |
| DIG | -9.03% | -7.18% | -5.43% | Yes | No |
| PIV | -8.64% | -6.79% | -4.18% | No | No |
| DRI | -8.61% | -6.76% | +4.61% | No | No |
| PVT | -8.52% | -6.67% | -2.67% | No | No |

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Flag VIN names separately; do not treat VPL as broad-market proof.

## H. Delta vs Previous