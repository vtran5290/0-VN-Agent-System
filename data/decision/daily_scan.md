# Daily Scan — Phase36 A3 — as-of 2026-05-19
_Generated: 2026-05-19T15:08:18Z · SSOT CSV: `data/research/portfolio_optimization/missing_work/phase36_daily_scan_20260519.csv` · 99 symbols in scan output_

**Production rule:** OMS and capital decisions use **`final_action` only**. `a3_rank_score` is review sort order only (not a buy signal).

## Portfolio NAV & positions (operator)

**FACTS** (`data/trading/live/portfolio_state.json` — port excludes cash; NAV is user-updated, not inferred)

| Metric | Value |
| --- | --- |
| NAV (user-updated) | 4,397,660,045 VND |
| Cost basis (positions) | 4,243,198,100 VND |
| Implied cash | 154,461,945 VND |
| Cash % | 3.5% |
| Position count | 10 |
| Portfolio as-of | 2026-05-19 |
| positions_path | data/raw/current_positions_derived.json |

### Holdings detail

| Symbol | Shares | Avg entry (VND) | Market value (VND) | % NAV | Sector |
| --- | --- | --- | --- | --- | --- |
| STB | 14500 | 70103 | 1048350044 | 23.8% | Ngân hàng |
| MSB | 30400 | 13386 | 439279994 | 10.0% | Ngân hàng |
| BID | 3000 | 43433 | 132750000 | 3.0% | Ngân hàng |
| VCB | 4500 | 64600 | 280800007 | 6.4% | Ngân hàng |
| CTG | 8000 | 36490 | 286399994 | 6.5% | Ngân hàng |
| HCM | 20000 | 28337 | 600000000 | 13.6% | CTCK |
| TCX | 6600 | 51243 | 335279995 | 7.6% | CTCK |
| VIX | 8000 | 19070 | 154000000 | 3.5% | CTCK |
| DXG | 40000 | 14608 | 640000000 | 14.6% | BDS |
| PDR | 28000 | 16609 | 471800011 | 10.7% | BDS |

## Market regime & breadth
**FACTS**

| Metric | Value |
| --- | --- |
| VNINDEX regime | Bull |
| A3 cloud breadth | 31.8% |
| S3 cloud breadth | 32.5% |
| Breadth zone | defense |
| T1 permission | Yes (manual review when flagged) |
| T2 permission | Blocked |
| Plain NEW_T1 count | 0 |

**INTERPRETATION:** Breadth &lt;40% → defense posture. No automatic new T1; manual review on flagged names; T2 adds blocked.

## VNINDEX Distribution Risk Lens

**FACTS** (market context only; does not change final_action)

- Primary view: **ex_vin_proxy**
- VNINDEX raw: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 3/4/9)
- ex-VIN proxy: **CAUTION** (dist 10/25/50: 2/3/7)
- VIN distortion flag: **True**
- VIN group warning: **CAUTION**
- Distribution Risk Lens is market context only and does not change final_action.
- _ex-VIN proxy drawdown/correction probabilities are close-based; high/low are synthetic from close when native OHLC is unavailable._
- P(25D return < 0) ex-VIN: **32.8% (base 39.2%)**
- P(-5% correction within 25D) ex-VIN: **36.1% (base 40.4%)**
- P(-10% correction within 75D) ex-VIN: **39.0% (base 44.2%)**
- Comparison: VNINDEX raw may be VIN-skewed when distortion_flag is true; prefer ex_vin_proxy for broad market context.

**As-of (lens):** 2026-05-19 · **method:** distribution_risk_lens_v1.2

_Distribution Risk Lens is market context only and does not change final_action._

## final_action summary

| final_action | Count | Operator label |
| --- | --- | --- |
| TRAIL_EXIT | 35 | SELL / EXIT |
| WATCH_ONLY | 35 | WATCH ONLY |
| NO_T2_BREADTH | 16 | HOLD T1 / BLOCK ADD |
| NEW_T1_MANUAL_REVIEW_BREADTH | 7 | MANUAL REVIEW |
| HOLD_T1_ONLY | 5 | HOLD / MONITOR |
| TP1_PARTIAL | 1 | TRIM |

## New entry candidates (review sort)

| # | Symbol | final_action | Close | Rank | ED | S3 lead | S3 fresh | Rank reason | Trigger | TP1 | Trail |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | KOS | NEW_T1_MR | 38.70 | 0.972 | 0.972 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | 37.15 | 45.67 | 38.20 |
| 2 | NTP | NEW_T1_MR | 61.10 | 0.958 | 0.958 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | pending* | pending* | pending* |
| 3 | GSP | NEW_T1_MR | 11.50 | 0.929 | 0.929 | none | No | high_ed_score|liq_warn_near|no_s3_support_but_a3_valid | 11.04 | 13.57 | 11.27 |
| 4 | TCB | NEW_T1_MR | 32.60 | 0.897 | 0.897 | lead_6_10 | No | high_ed_score|liq_ok | 31.30 | 38.47 | 31.75 |
| 5 | OIL | NEW_T1_MR | 15.60 | 0.843 | 0.843 | none | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid | pending* | pending* | pending* |
| 6 | TRC | NEW_T1_MR | 75.10 | 0.459 | 0.959 | same_day | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | pending* | pending* | pending* |
| 7 | CTG | NEW_T1_MR | 35.80 | 0.457 | 0.957 | same_day | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | pending* | pending* | pending* |

**\* Pending entry (NTP, OIL, TRC, CTG):** Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. pb_trigger_price / tp1_price / trail_price will be computed after fill.

**Why (typical):** A3 cloud breakout; regime bull; breadth defense → T1 with operator review; T2 blocked.

### Per-symbol final_action_reason

| Symbol | Reason |
| --- | --- |
| KOS | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| NTP | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| GSP | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| TCB | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| OIL | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| TRC | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| CTG | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |

## Portfolio holdings

| Symbol | In scan | final_action | Rank | Close | Reason |
| --- | --- | --- | --- | --- | --- |
| BID | Yes | WATCH_ONLY | — | 44.25 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| CTG | Yes | NEW_T1_MR | 0.457 | 35.80 | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed w… |
| DXG | Yes | WATCH_ONLY | — | 16.00 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| HCM | Yes | NO_T2_BREADTH | 0.576 | 30.00 | T1 in position (bar 22). T2 blocked: breadth defense (<35%). |
| MSB | Yes | NO_T2_BREADTH | 0.533 | 14.45 | T1 in position (bar 16). T2 blocked: breadth defense (<35%). |
| PDR | No | — | — | — | Not in Phase36 scan universe today |
| STB | No | — | — | — | Not in Phase36 scan universe today |
| TCX | No | — | — | — | Not in Phase36 scan universe today |
| VCB | No | — | — | — | Not in Phase36 scan universe today |
| VIX | Yes | WATCH_ONLY | — | 19.25 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |

## Exits & trims (A3 production)

### TRAIL_EXIT (35)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| EIB | 21.70 | 22.35 | 2.901 | Close 21.7 < trail 22.352 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | 16.40 | 16.73 | 2.861 | Close 16.4 < trail 16.725 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | 21.10 | 22.40 | 2.809 | Close 21.1 < trail 22.396 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | 14.10 | 14.42 | 1.000 | Close 14.1 < trail 14.421 (2.5xATR14). Exit remaining per A3 rules. |
| VTO | 12.05 | 12.08 | 0.995 | Close 12.05 < trail 12.08 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | 13.00 | 13.42 | 0.989 | Close 13.0 < trail 13.418 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | 14.40 | 14.43 | 0.983 | Close 14.4 < trail 14.429 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | 26.70 | 27.05 | 0.956 | Close 26.7 < trail 27.05 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | 76.50 | 78.66 | 0.921 | Close 76.5 < trail 78.661 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | 15.80 | 16.91 | 0.919 | Close 15.8 < trail 16.907 (2.5xATR14). Exit remaining per A3 rules. |
| MCH | 131.00 | 143.12 | 0.880 | Close 131.0 < trail 143.125 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | 16.70 | 19.03 | 0.878 | Close 16.7 < trail 19.027 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | 6.20 | 6.69 | 0.864 | Close 6.2 < trail 6.686 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | 41.90 | 44.68 | 0.855 | Close 41.9 < trail 44.682 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | 36.55 | 36.71 | 0.855 | Close 36.55 < trail 36.711 (2.5xATR14). Exit remaining per A3 rules. |
| LPB | 51.60 | 51.88 | 0.848 | Close 51.6 < trail 51.875 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | 58.60 | 61.31 | 0.835 | Close 58.6 < trail 61.307 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | 7.40 | 8.31 | 0.828 | Close 7.4 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | 31.65 | 33.82 | 0.783 | Close 31.65 < trail 33.82 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | 11.70 | 13.13 | 0.775 | Close 11.7 < trail 13.129 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | 24.40 | 29.19 | 0.743 | Close 24.4 < trail 29.193 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | 8.21 | 10.29 | 0.722 | Close 8.21 < trail 10.293 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | 78.20 | 83.27 | 0.718 | Close 78.2 < trail 83.268 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | 141.10 | 147.38 | 0.696 | Close 141.1 < trail 147.375 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | 6.80 | 8.36 | 0.654 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | 23.00 | 23.31 | 0.482 | Close 23.0 < trail 23.311 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | 36.17 | 36.28 | 0.461 | Close 36.17 < trail 36.283 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | 172.00 | 177.34 | 0.449 | Close 172.0 < trail 177.339 (2.5xATR14). Exit remaining per A3 rules. |
| REE | 53.70 | 69.09 | 0.441 | Close 53.7 < trail 69.093 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | 17.50 | 19.81 | 0.436 | Close 17.5 < trail 19.807 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | 2.67 | 2.85 | 0.431 | Close 2.67 < trail 2.853 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | 34.70 | 36.15 | 0.379 | Close 34.7 < trail 36.146 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | 26.25 | 27.99 | 0.326 | Close 26.25 < trail 27.988 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | 40.50 | 43.01 | 0.314 | Close 40.5 < trail 43.013 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | 121.30 | 179.68 | -0.239 | Close 121.3 < trail 179.682 (2.5xATR14). Exit remaining per A3 rules. |
### TP1_PARTIAL (1)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| VHM | 157.00 | 152.36 | 0.249 | Close 157.0 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |

## Hold T1 / block T2 adds

### NO_T2_BREADTH (16)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| KSV | 159.00 | 2.965 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| PVS | 40.00 | 0.988 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| PSI | 8.60 | 0.877 | T1 in position (bar 11). T2 blocked: breadth defense (<35%). |
| VRE | 33.50 | 0.869 | T1 in position (bar 8). T2 blocked: breadth defense (<35%). |
| VPB | 26.75 | 0.864 | T1 in position (bar 2). T2 blocked: breadth defense (<35%). |
| SAB | 48.50 | 0.850 | T1 in position (bar 7). T2 blocked: breadth defense (<35%). |
| VPL | 91.50 | 0.788 | T1 in position (bar 6). T2 blocked: breadth defense (<35%). |
| HCM | 30.00 | 0.576 | T1 in position (bar 22). T2 blocked: breadth defense (<35%). |
| MSB | 14.45 | 0.533 | T1 in position (bar 16). T2 blocked: breadth defense (<35%). |
| FUEVN100 | 26.91 | 0.418 | T1 in position (bar 10). T2 blocked: breadth defense (<35%). |
| POW | 14.00 | 0.402 | T1 in position (bar 6). T2 blocked: breadth defense (<35%). |
| QNS | 48.70 | 0.375 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| ILS | 26.10 | 0.374 | T1 in position (bar 3). T2 blocked: breadth defense (<35%). |
| HNG | 7.40 | 0.362 | T1 in position (bar 18). T2 blocked: breadth defense (<35%). |
| PHP | 37.50 | 0.283 | T1 in position (bar 11). T2 blocked: breadth defense (<35%). |
| PVP | 19.25 | 0.183 | T1 in position (bar 14). T2 blocked: breadth defense (<35%). |
### HOLD_T1_ONLY (5)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| ORS | 13.40 | 0.985 | A3 signal active (bar 17). Cloud turned bear. Hold T1. Monitor trail st… |
| TDP | 29.35 | 0.976 | A3 signal active (bar 9). Cloud turned bear. Hold T1. Monitor trail sto… |
| NAB | 12.30 | 0.671 | A3 signal active (bar 6). Cloud turned bear. Hold T1. Monitor trail sto… |
| VGI | 101.50 | 0.453 | A3 signal active (bar 20). Cloud turned bear. Hold T1. Monitor trail st… |
| CDC | 21.90 | 0.232 | A3 signal active (bar 19). Cloud turned bear. Hold T1. Monitor trail st… |

## Vingroup names in scan (distortion check)

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Prefer breadth-based health for broad-market conclusions.

| Symbol | final_action | Rank | Close |
| --- | --- | --- | --- |
| VRE | NO_T2_BREADTH | 0.869 | 33.50 |
| VPL | NO_T2_BREADTH | 0.788 | 91.50 |
| VHM | TP1_PARTIAL | 0.249 | 157.00 |
| VIC | WATCH_ONLY | — | 225.10 |

## Decision layer

### Top 3 actions
- No automatic NEW_T1; work manual-review queue only.
- Holdings flagged for manual T1 review: CTG.
- Hold NO_T2_BREADTH names; no T2 adds until breadth improves.

### Top 3 risks
- Defense breadth (<40%) with possible bull index — weak participation.
- Holdings not in scan: PDR, STB, TCX, VCB.
- Zero plain NEW_T1 — all new entries require operator sign-off.

### Watchlist updates
- Coverage gap: PDR, STB, TCX, VCB
- Manual-review queue: KOS, NTP, GSP, TCB, OIL, TRC, CTG (sort: a3_rank_score DESC).

## Signals to monitor next session
- `pct_cloud_bull_a3` vs 40% (exit defense → T2 may unlock)
- Holdings with TRAIL_EXIT / NEW_T1_MR vs prices and trails
- Names missing from scan universe (coverage gap)
- VNINDEX regime flip (bear → SKIP_VNINDEX_BEAR on new T1)

## If X happens → do Y
- **Breadth ≥ 40%** → re-run scan; reassess T2 on NO_T2_BREADTH names
- **TRAIL_EXIT persists** → execute exit discipline per A3 plan (not rank score)
- **Approve manual T1** → size via execution layer only after review
- **Holding still missing from CSV** → fix panel/universe before trusting portfolio coverage

---

**Related:** `phase36_daily_operator_report.md` (panels) · `docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` · `data/decision/weekly_report.md` (macro/policy weekly)
