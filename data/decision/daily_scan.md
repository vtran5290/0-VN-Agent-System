# Daily Scan — Phase36 A3 — as-of 2026-05-18
_Generated: 2026-05-19T04:27:34Z · SSOT CSV: `data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv` · 97 symbols in scan output_

**Production rule:** OMS and capital decisions use **`final_action` only**. `a3_rank_score` is review sort order only (not a buy signal).

## Market regime & breadth
**FACTS**

| Metric | Value |
| --- | --- |
| VNINDEX regime | Bull |
| A3 cloud breadth | 31.8% |
| S3 cloud breadth | 31.3% |
| Breadth zone | defense |
| T1 permission | Yes (manual review when flagged) |
| T2 permission | Blocked |
| Plain NEW_T1 count | 0 |

**INTERPRETATION:** Breadth &lt;40% → defense posture. No automatic new T1; manual review on flagged names; T2 adds blocked.

## final_action summary

| final_action | Count | Operator label |
| --- | --- | --- |
| WATCH_ONLY | 34 | WATCH ONLY |
| TRAIL_EXIT | 29 | SELL / EXIT |
| NO_T2_BREADTH | 18 | HOLD T1 / BLOCK ADD |
| NEW_T1_MANUAL_REVIEW_BREADTH | 10 | MANUAL REVIEW |
| HOLD_T1_ONLY | 5 | HOLD / MONITOR |
| TP1_PARTIAL | 1 | TRIM |

## New entry candidates (review sort)

| # | Symbol | final_action | Close | Rank | ED | S3 lead | S3 fresh | Rank reason | Trigger | TP1 | Trail |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | KSV | NEW_T1_MR | 163.00 | 2.834 | 0.834 | lead_11_20 | No | high_ed_score|liq_ok | 156.48 | 192.34 | 152.43 |
| 2 | KOS | NEW_T1_MR | 38.70 | 0.969 | 0.969 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | pending* | pending* | pending* |
| 3 | TCB | NEW_T1_MR | 34.00 | 0.903 | 0.903 | lead_6_10 | No | high_ed_score|liq_ok | pending* | pending* | pending* |
| 4 | SHI | NEW_T1_MR | 14.75 | 0.898 | 0.898 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | 14.16 | 17.41 | 14.49 |
| 5 | BMP | NEW_T1_MR | 154.50 | 0.891 | 0.891 | lead_1_5 | Yes | high_ed_score|s3_lead_5d|liq_ok | 148.32 | 182.31 | 149.48 |
| 6 | GSP | NEW_T1_MR | 11.70 | 0.834 | 0.834 | none | No | high_ed_score|liq_warn_near|no_s3_support_but_a3_valid | pending* | pending* | pending* |
| 7 | PVS | NEW_T1_MR | 42.50 | 0.673 | 0.673 | none | No | liq_ok|no_s3_support_but_a3_valid | 40.80 | 50.15 | 40.12 |
| 8 | OIL | NEW_T1_MR | 17.00 | 0.361 | 0.361 | none | No | liq_ok|no_s3_support_but_a3_valid | pending* | pending* | pending* |
| 9 | QNS | NEW_T1_MR | 48.80 | 0.351 | 0.851 | same_day | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | 46.85 | 57.58 | 47.87 |
| 10 | TRC | NEW_T1_MR | 77.00 | 0.327 | 0.827 | same_day | No | high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context | pending* | pending* | pending* |

**\* Pending entry (KOS, TCB, GSP, OIL, TRC):** Signal confirmed at today's close; planned fill is next session open. Entry levels are pending until the next-open fill price is known. pb_trigger_price / tp1_price / trail_price will be computed after fill.

**Why (typical):** A3 cloud breakout; regime bull; breadth defense → T1 with operator review; T2 blocked.

### Per-symbol final_action_reason

| Symbol | Reason |
| --- | --- |
| KSV | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| KOS | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| TCB | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| SHI | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| BMP | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| GSP | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| PVS | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| OIL | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| QNS | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |
| TRC | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed with operator review. T2 bloc… |

## Portfolio holdings

| Symbol | In scan | final_action | Rank | Close | Reason |
| --- | --- | --- | --- | --- | --- |
| BID | No | — | — | — | Not in Phase36 scan universe today |
| DPR | Yes | WATCH_ONLY | — | 43.50 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| DXG | Yes | WATCH_ONLY | — | 15.90 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| GVR | Yes | NO_T2_BREADTH | 0.451 | 39.30 | T1 in position (bar 7). T2 blocked: breadth defense (<35%). |
| HCM | Yes | NO_T2_BREADTH | 0.600 | 29.60 | T1 in position (bar 21). T2 blocked: breadth defense (<35%). |
| HDB | Yes | NO_T2_BREADTH | 0.909 | 27.45 | T1 in position (bar 14). T2 blocked: breadth defense (<35%). |
| MSB | Yes | NO_T2_BREADTH | 0.689 | 13.90 | T1 in position (bar 15). T2 blocked: breadth defense (<35%). |
| NVL | Yes | TRAIL_EXIT | 0.997 | 17.15 | Close 17.15 < trail 19.062 (2.5xATR14). Exit remaining per A3 rules. |
| PDR | No | — | — | — | Not in Phase36 scan universe today |
| PHR | Yes | WATCH_ONLY | — | 70.30 | S3 EMA21/55 signal only — use s3_shadow_action (paper). No A3 capital. |
| PVS | Yes | NEW_T1_MR | 0.673 | 42.50 | A3 cloud breakout. Regime=bull. Breadth=defense (defense). T1 allowed w… |
| STB | No | — | — | — | Not in Phase36 scan universe today |
| TCX | No | — | — | — | Not in Phase36 scan universe today |
| VPB | Yes | NO_T2_BREADTH | 0.977 | 27.45 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |

## Exits & trims (A3 production)

### TRAIL_EXIT (29)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| TCH | 16.65 | 16.70 | 2.921 | Close 16.65 < trail 16.698 (2.5xATR14). Exit remaining per A3 rules. |
| EIB | 21.70 | 22.34 | 2.891 | Close 21.7 < trail 22.343 (2.5xATR14). Exit remaining per A3 rules. |
| VCG | 21.20 | 22.38 | 2.813 | Close 21.2 < trail 22.379 (2.5xATR14). Exit remaining per A3 rules. |
| NVL | 17.15 | 19.06 | 0.997 | Close 17.15 < trail 19.062 (2.5xATR14). Exit remaining per A3 rules. |
| VRE | 33.10 | 33.37 | 0.916 | Close 33.1 < trail 33.366 (2.5xATR14). Exit remaining per A3 rules. |
| MSN | 76.50 | 78.48 | 0.913 | Close 76.5 < trail 78.482 (2.5xATR14). Exit remaining per A3 rules. |
| HUT | 15.80 | 16.85 | 0.911 | Close 15.8 < trail 16.854 (2.5xATR14). Exit remaining per A3 rules. |
| MCH | 132.00 | 143.21 | 0.905 | Close 132.0 < trail 143.214 (2.5xATR14). Exit remaining per A3 rules. |
| HHS | 13.35 | 13.39 | 0.877 | Close 13.35 < trail 13.391 (2.5xATR14). Exit remaining per A3 rules. |
| HNM | 7.50 | 8.31 | 0.875 | Close 7.5 < trail 8.311 (2.5xATR14). Exit remaining per A3 rules. |
| MZG | 13.20 | 13.28 | 0.859 | Close 13.2 < trail 13.279 (2.5xATR14). Exit remaining per A3 rules. |
| DGW | 42.00 | 44.68 | 0.852 | Close 42.0 < trail 44.682 (2.5xATR14). Exit remaining per A3 rules. |
| VHC | 59.00 | 61.31 | 0.851 | Close 59.0 < trail 61.307 (2.5xATR14). Exit remaining per A3 rules. |
| NRC | 6.20 | 6.67 | 0.850 | Close 6.2 < trail 6.668 (2.5xATR14). Exit remaining per A3 rules. |
| KBC | 32.05 | 33.89 | 0.822 | Close 32.05 < trail 33.891 (2.5xATR14). Exit remaining per A3 rules. |
| SMC | 11.80 | 13.10 | 0.793 | Close 11.8 < trail 13.102 (2.5xATR14). Exit remaining per A3 rules. |
| MWG | 79.00 | 83.23 | 0.738 | Close 79.0 < trail 83.232 (2.5xATR14). Exit remaining per A3 rules. |
| HDG | 24.45 | 29.19 | 0.728 | Close 24.45 < trail 29.193 (2.5xATR14). Exit remaining per A3 rules. |
| CRC | 8.21 | 10.29 | 0.694 | Close 8.21 < trail 10.293 (2.5xATR14). Exit remaining per A3 rules. |
| AAV | 6.80 | 8.36 | 0.654 | Close 6.8 < trail 8.357 (2.5xATR14). Exit remaining per A3 rules. |
| DSE | 22.95 | 23.28 | 0.491 | Close 22.95 < trail 23.284 (2.5xATR14). Exit remaining per A3 rules. |
| MIG | 17.85 | 19.87 | 0.472 | Close 17.85 < trail 19.87 (2.5xATR14). Exit remaining per A3 rules. |
| DLG | 2.69 | 2.85 | 0.461 | Close 2.69 < trail 2.855 (2.5xATR14). Exit remaining per A3 rules. |
| VJC | 171.10 | 176.50 | 0.418 | Close 171.1 < trail 176.5 (2.5xATR14). Exit remaining per A3 rules. |
| DPG | 41.40 | 42.79 | 0.401 | Close 41.4 < trail 42.789 (2.5xATR14). Exit remaining per A3 rules. |
| BAF | 34.80 | 36.12 | 0.381 | Close 34.8 < trail 36.12 (2.5xATR14). Exit remaining per A3 rules. |
| HPG | 26.45 | 28.00 | 0.345 | Close 26.45 < trail 28.005 (2.5xATR14). Exit remaining per A3 rules. |
| REE | 52.80 | 69.24 | 0.316 | Close 52.8 < trail 69.236 (2.5xATR14). Exit remaining per A3 rules. |
| GEE | 119.80 | 179.43 | -0.357 | Close 119.8 < trail 179.432 (2.5xATR14). Exit remaining per A3 rules. |
### TP1_PARTIAL (1)

| Symbol | Close | Trail | Rank | Reason |
| --- | --- | --- | --- | --- |
| VHM | 154.00 | 151.50 | 0.322 | Close 154.0 >= TP1 145.14 (+18%). Take partial per A3 DP-first. |

## Hold T1 / block T2 adds

### NO_T2_BREADTH (18)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| VPB | 27.45 | 0.977 | T1 in position (bar 1). T2 blocked: breadth defense (<35%). |
| VTO | 12.20 | 0.931 | T1 in position (bar 7). T2 blocked: breadth defense (<35%). |
| HDB | 27.45 | 0.909 | T1 in position (bar 14). T2 blocked: breadth defense (<35%). |
| PSI | 8.60 | 0.865 | T1 in position (bar 10). T2 blocked: breadth defense (<35%). |
| SAB | 48.40 | 0.844 | T1 in position (bar 6). T2 blocked: breadth defense (<35%). |
| VPL | 90.40 | 0.828 | T1 in position (bar 5). T2 blocked: breadth defense (<35%). |
| LPB | 52.30 | 0.760 | T1 in position (bar 22). T2 blocked: breadth defense (<35%). |
| DRI | 14.90 | 0.717 | T1 in position (bar 20). T2 blocked: breadth defense (<35%). |
| MSB | 13.90 | 0.689 | T1 in position (bar 15). T2 blocked: breadth defense (<35%). |
| HCM | 29.60 | 0.600 | T1 in position (bar 21). T2 blocked: breadth defense (<35%). |
| GVR | 39.30 | 0.451 | T1 in position (bar 7). T2 blocked: breadth defense (<35%). |
| E1VFVN30 | 36.42 | 0.422 | T1 in position (bar 13). T2 blocked: breadth defense (<35%). |
| PHP | 36.40 | 0.413 | T1 in position (bar 10). T2 blocked: breadth defense (<35%). |
| FUEVN100 | 26.99 | 0.395 | T1 in position (bar 9). T2 blocked: breadth defense (<35%). |
| POW | 14.30 | 0.282 | T1 in position (bar 5). T2 blocked: breadth defense (<35%). |
| HNG | 7.60 | 0.207 | T1 in position (bar 17). T2 blocked: breadth defense (<35%). |
| ILS | 27.00 | 0.102 | T1 in position (bar 2). T2 blocked: breadth defense (<35%). |
| PVP | 20.00 | -0.060 | T1 in position (bar 13). T2 blocked: breadth defense (<35%). |
### HOLD_T1_ONLY (5)

| Symbol | Close | Rank | Reason |
| --- | --- | --- | --- |
| TDP | 29.55 | 0.993 | A3 signal active (bar 8). Cloud turned bear. Hold T1. Monitor trail sto… |
| ORS | 13.55 | 0.961 | A3 signal active (bar 16). Cloud turned bear. Hold T1. Monitor trail st… |
| NAB | 12.35 | 0.658 | A3 signal active (bar 5). Cloud turned bear. Hold T1. Monitor trail sto… |
| VGI | 97.50 | 0.609 | A3 signal active (bar 19). Cloud turned bear. Hold T1. Monitor trail st… |
| CDC | 21.60 | 0.275 | A3 signal active (bar 18). Cloud turned bear. Hold T1. Monitor trail st… |

## Vingroup names in scan (distortion check)

> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. Prefer breadth-based health for broad-market conclusions.

| Symbol | final_action | Rank | Close |
| --- | --- | --- | --- |
| VRE | TRAIL_EXIT | 0.916 | 33.10 |
| VPL | NO_T2_BREADTH | 0.828 | 90.40 |
| VHM | TP1_PARTIAL | 0.322 | 154.00 |
| VIC | WATCH_ONLY | — | 225.00 |

## Decision layer

### Top 3 actions
- Priority exit review: NVL (TRAIL_EXIT).
- No automatic NEW_T1; work manual-review queue only.
- Holdings flagged for manual T1 review: PVS.

### Top 3 risks
- Defense breadth (<40%) with possible bull index — weak participation.
- Holdings not in scan: BID, PDR, STB, TCX.
- Zero plain NEW_T1 — all new entries require operator sign-off.

### Watchlist updates
- Coverage gap: BID, PDR, STB, TCX
- Manual-review queue: KSV, KOS, TCB, SHI, BMP, GSP, PVS, OIL, QNS, TRC (sort: a3_rank_score DESC).

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
