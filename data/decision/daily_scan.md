# Daily Scan — Phase36 A3 — as-of 2026-05-22
_Generated: 2026-05-22T14:34:43Z · SSOT CSV: `data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv` · 102 symbols in scan output_

**Production rule:** OMS and capital decisions use **`final_action` only**. `a3_rank_score` is review sort order only (not a buy signal).

## Portfolio NAV & positions (operator)

**FACTS** (`data/trading/live/portfolio_state.json` — port excludes cash; NAV is user-updated, not inferred)

| Metric | Value |
| --- | --- |
| NAV (user-updated) | 5,267,649,955 VND |
| Cost basis (positions) | 5,296,381,800 VND |
| Implied cash | -28,731,845 VND |
| Cash % | -0.5% |
| Position count | 11 |
| Portfolio as-of | 2026-05-23 |
| positions_path | data/raw/current_positions_derived.json |

### Holdings detail

| Symbol | Shares | Avg entry (VND) | Market value (VND) | % NAV | Sector |
| --- | --- | --- | --- | --- | --- |
| STB | 14500 | 70103 | 1032399956 | 19.6% | Ngân hàng |
| MSB | 40000 | 13922 | 575999985 | 10.9% | Ngân hàng |
| VCB | 15500 | 64735 | 984250000 | 18.7% | Ngân hàng |
| BID | 14000 | 44093 | 602000000 | 11.4% | Ngân hàng |
| HCM | 15000 | 29050 | 427500000 | 8.1% | CTCK |
| TCX | 6600 | 51243 | 336600000 | 6.4% | CTCK |
| VIX | 18000 | 18920 | 333899986 | 6.3% | CTCK |
| HSG | 15000 | 12600 | 189000006 | 3.6% | CTCK |
| OIL | 5000 | 15500 | 78000002 | 1.5% | Energy / DTC |
| PC1 | 15000 | 20620 | 309000006 | 5.9% | Energy / DTC |
| PVS | 10000 | 41200 | 399000015 | 7.6% | Energy / DTC |

## Market regime & breadth
**FACTS**

| Metric | Value |
| --- | --- |
| VNINDEX regime | Bull |
| A3 cloud breadth | 31.1% |
| S3 cloud breadth | 31.0% |
| Breadth zone | defense |
| T1 permission | Yes (manual review when flagged) |
| T2 permission | Blocked |
| Plain NEW_T1 count | 0 |

**INTERPRETATION:** Breadth &lt;40% → defense posture. No automatic new T1; manual review on flagged names; T2 adds blocked.

## VNINDEX Distribution Risk Lens

**FACTS** (market context only; does not change final_action)


- Primary view: **ex_vin_proxy**
- Lens report status: **OK**
#### Index view freshness
| View | Last data date | Requested as-of | Stale |
| --- | --- | --- | --- |
| vnindex_raw | 2026-05-22 | 2026-05-22 | no |
| ex_vin_proxy | 2026-05-22 | 2026-05-22 | no |
| vin_group | 2026-05-22 | 2026-05-22 | no |
- VNINDEX raw: **CORRECTION_RISK** (dist 10/25/50: 4/5/9)
- ex-VIN proxy: **DISTRIBUTION_CLUSTER** (dist 10/25/50: 4/5/8)
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

**Requested as-of:** 2026-05-22 · **method:** distribution_risk_lens_v1.2

_Distribution Risk Lens is market context only and does not change final_action._

## final_action summary

| final_action | Count | Operator label |
| --- | --- | --- |
| TRAIL_EXIT | 40 | SELL / EXIT |
| WATCH_ONLY | 36 | WATCH ONLY |
| NO_T2_BREADTH | 13 | HOLD T1 / BLOCK ADD |
| NEW_T1_MANUAL_REVIEW_BREADTH | 6 | MANUAL REVIEW |
| HOLD_T1_ONLY | 6 | HOLD / MONITOR |
| TP1_PARTIAL | 1 | TRIM |

## New entry candidates (review sort)

| # | Symbol | final_action | Close | Rank | ED | S3 lead | S3 fresh | Rank reason | Trigger | TP1 | Trail |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | NTP | NEW_T1_MR | 60.60 | 1.000 | 1.000 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | 58.18 | 71.51 | 58.92 |
| 2 | BID | NEW_T1_MR | 43.00 | 0.936 | 0.936 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | pending* | pending* | pending* |
| 3 | VGI | NEW_T1_MR | 94.20 | 0.915 | 0.915 | none | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid | pending* | pending* | pending* |
| 4 | DXS | NEW_T1_MR | 8.08 | 0.908 | 0.908 | lead_6_10 | No | high_ed_score|liq_ok | pending* | pending* | pending* |
| 5 | VCB | NEW_T1_MR | 63.50 | 0.359 | 0.859 | same_day | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | pending* | pending* | pending* |
| 6 | CTR | NEW_T1_MR | 93.00 | 0.223 | 0.723 | same_day | No | liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | pending* | pending* | pending* |

**\* Pending entry (BID, VGI, DXS, VCB, CTR):** Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. pb_trigger_price / tp1_price / trail_price will be computed after fill.

**Why (typical):** A3 cloud breakout; regime bull; breadth defense → T1 with operator review; T2 blocked.

### Per-symbol final_action_reason

| Symbol | Reason |
| --- | --- |
| NTP | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| BID | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| VGI | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| DXS | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| VCB | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| CTR | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |

## Portfolio holdings

| Symbol | In scan | final_action | Rank | Close | Reason |
| --- | --- | --- | --- | --- | --- |
| BID | Yes | NEW_T1_MR | 0.936 | 43.00 | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed w… |
| HCM | Yes | TRAIL_EXIT | 0.909 | 28.50 | Close 28.5 < trail 28.67 (2.5xATR14). Exit remaining per A3 rules. |
| HSG | Yes | WATCH_ONLY | — | 12.60 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| MSB | Yes | NO_T2_BREADTH | 0.677 | 14.40 | T1 in position (bar 19). T2 blocked: breadth defense (<35%). |
| OIL | Yes | NO_T2_BREADTH | 0.887 | 15.60 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| PC1 | No | — | — | — | Not in Phase36 scan universe today |
| PVS | Yes | TRAIL_EXIT | 0.982 | 39.90 | Close 39.9 < trail 40.25 (2.5xATR14). Exit remaining per A3 rules. |
| STB | No | — | — | — | Not in Phase36 scan universe today |
| TCX | No | — | — | — | Not in Phase36 scan universe today |
| VCB | Yes | NEW_T1_MR | 0.359 | 63.50 | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed w… |
| VIX | Yes | WATCH_ONLY | — | 18.55 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |

## Exits & trims (A3 production)

### TRAIL_EXIT (40)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| VCG | 21.00 | 22.59 | 2.846 | Close 21.0 < trail 22.593 (2.5xATR14). Exit remaining per A3 rules. |
| EIB | 21.20 | 22.39 | 2.834 | Close 21.2 < trail 22.387 (2.5xATR14). Exit remaining per A3 rules. |
| TCH | 15.65 | 16.82 | 2.731 | Close 15.65 < trail 16.823 (2.5xATR14). Exit remaining per A3 rules. |
| PVS | 39.90 | 40.25 | 0.982 | Close 39.9 < trail 40.25 (2.5xATR14). Exit remaining per A3 rules. |
| DRI | 14.00 | 14.53 | 0.971 | Close 14.0 < trail 14.529 (2.5xATR14). Exit remaining per A3 rules. |
| GSP | 11.25 | 11.26 | 0.969 | Close 11.25 < trail 11.259 (2.5xATR14). Exit remaining per A3 rules. |
| VTO | 11.85 | 12.08 | 0.941 | Close 11.85 < trail 12.08 (2.5xATR14). Exit remaining per A3 rules. |
| GVR | 35.30 | 36.72 | 0.941 | Close 35.3 < trail 36.72 (2.5xATR14). Exit remaining per A3 rules. |
| ORS | 13.20 | 13.30 | 0.933 | Close 13.2 < trail 13.298 (2.5xATR14). Exit remaining per A3 rules. |
| SHI | 14.20 | 14.37 | 0.930 | Close 14.2 < trail 14.366 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | 76.00 | 78.50 | 0.918 | Close 76.0 < trail 78.5 (2.5xATR14). Exit remaining per A3 rules. |
| HCM | 28.50 | 28.67 | 0.909 | Close 28.5 < trail 28.67 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | 59.00 | 61.40 | 0.907 | Close 59.0 < trail 61.396 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | 15.60 | 16.96 | 0.891 | Close 15.6 < trail 16.961 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | 6.20 | 6.74 | 0.891 | Close 6.2 < trail 6.739 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | 7.40 | 8.31 | 0.872 | Close 7.4 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | 31.70 | 33.89 | 0.857 | Close 31.7 < trail 33.893 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | 79.40 | 83.48 | 0.853 | Close 79.4 < trail 83.482 (2.5xATR14). Exit remaining per A3 rules. |
| HDB | 25.85 | 26.95 | 0.850 | Close 25.85 < trail 26.952 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | 41.25 | 44.62 | 0.834 | Close 41.25 < trail 44.62 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | 8.28 | 10.32 | 0.827 | Close 8.28 < trail 10.325 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | 31.50 | 33.71 | 0.826 | Close 31.5 < trail 33.712 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | 11.60 | 13.12 | 0.810 | Close 11.6 < trail 13.12 (2.5xATR14). Exit remaining per A3 rules. |
| BMP | 138.00 | 147.07 | 0.691 | Close 138.0 < trail 147.071 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | 11.95 | 13.27 | 0.685 | Close 11.95 < trail 13.266 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | 6.80 | 8.36 | 0.654 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | 15.50 | 19.18 | 0.637 | Close 15.5 < trail 19.179 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | 23.15 | 29.23 | 0.607 | Close 23.15 < trail 29.229 (2.5xATR14). Exit remaining per A3 rules. |
| HNG | 7.20 | 7.34 | 0.495 | Close 7.2 < trail 7.343 (2.5xATR14). Exit remaining per A3 rules. |
| E1VFVN30 | 35.82 | 36.21 | 0.490 | Close 35.82 < trail 36.213 (2.5xATR14). Exit remaining per A3 rules. |
| POW | 13.60 | 13.75 | 0.461 | Close 13.6 < trail 13.746 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | 22.60 | 23.26 | 0.460 | Close 22.6 < trail 23.257 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | 17.55 | 19.73 | 0.459 | Close 17.55 < trail 19.727 (2.5xATR14). Exit remaining per A3 rules. |
| PVP | 18.05 | 18.62 | 0.449 | Close 18.05 < trail 18.616 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | 170.10 | 176.54 | 0.412 | Close 170.1 < trail 176.536 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | 2.64 | 2.85 | 0.407 | Close 2.64 < trail 2.855 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | 34.60 | 36.13 | 0.406 | Close 34.6 < trail 36.129 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | 40.65 | 42.64 | 0.382 | Close 40.65 < trail 42.638 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | 26.35 | 27.93 | 0.382 | Close 26.35 < trail 27.934 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | 108.80 | 178.20 | -0.463 | Close 108.8 < trail 178.2 (2.5xATR14). Exit remaining per A3 rules. |
### TP1_PARTIAL (1)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| VHM | 153.80 | 154.11 | 0.428 | Close 153.8 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |

## Hold T1 / block T2 adds

### NO_T2_BREADTH (13)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| KSV | 160.00 | 2.938 | T1 in position (bar 4). T2 blocked: breadth defense (<35%). |
| KOS | 38.30 | 0.983 | T1 in position (bar 3). T2 blocked: breadth defense (<35%). |
| TRC | 74.90 | 0.981 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| PSI | 8.60 | 0.920 | T1 in position (bar 14). T2 blocked: breadth defense (<35%). |
| SAB | 48.10 | 0.916 | T1 in position (bar 10). T2 blocked: breadth defense (<35%). |
| OIL | 15.60 | 0.887 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| LPB | 53.20 | 0.765 | T1 in position (bar 26). T2 blocked: breadth defense (<35%). |
| VPL | 93.40 | 0.759 | T1 in position (bar 9). T2 blocked: breadth defense (<35%). |
| MSB | 14.40 | 0.677 | T1 in position (bar 19). T2 blocked: breadth defense (<35%). |
| ILS | 26.30 | 0.531 | T1 in position (bar 6). T2 blocked: breadth defense (<35%). |
| FUEVN100 | 26.60 | 0.489 | T1 in position (bar 13). T2 blocked: breadth defense (<35%). |
| PHP | 36.60 | 0.450 | T1 in position (bar 14). T2 blocked: breadth defense (<35%). |
| QNS | 48.60 | 0.416 | T1 in position (bar 4). T2 blocked: breadth defense (<35%). |
### HOLD_T1_ONLY (6)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| TDP | 29.40 | 0.989 | A3 signal active (bar 12). Cloud turned bear. Hold T1. Monitor trail st… |
| VPB | 26.80 | 0.903 | A3 signal active (bar 5). Cloud turned bear. Hold T1. Monitor trail sto… |
| TCB | 32.20 | 0.875 | A3 signal active (bar 3). Cloud turned bear. Hold T1. Monitor trail sto… |
| NAB | 12.30 | 0.752 | A3 signal active (bar 9). Cloud turned bear. Hold T1. Monitor trail sto… |
| CTG | 34.80 | 0.421 | A3 signal active (bar 2). Cloud turned bear. Hold T1. Monitor trail sto… |
| CDC | 22.10 | 0.263 | A3 signal active (bar 22). Cloud turned bear. Hold T1. Monitor trail st… |

## Vingroup names in scan (distortion check)

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Prefer breadth-based health for broad-market conclusions.

| Symbol | final_action | Rank | Close |
| --- | --- | --- | --- |
| VRE | TRAIL_EXIT | 0.857 | 31.70 |
| VPL | NO_T2_BREADTH | 0.759 | 93.40 |
| VHM | TP1_PARTIAL | 0.428 | 153.80 |
| VIC | WATCH_ONLY | — | 216.50 |

## Decision layer

### Top 3 actions
- Priority exit review: PVS, HCM (TRAIL_EXIT).
- No automatic NEW_T1; work manual-review queue only.
- Holdings flagged for manual T1 review: BID, VCB.

### Top 3 risks
- Defense breadth (<40%) with possible bull index — weak participation.
- Holdings not in scan: PC1, STB, TCX.
- Zero plain NEW_T1 — all new entries require operator sign-off.

### Watchlist updates
- Coverage gap: PC1, STB, TCX
- Manual-review queue: NTP, BID, VGI, DXS, VCB, CTR (sort: a3_rank_score DESC).

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
