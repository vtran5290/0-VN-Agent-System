# Phase36 Daily Operator Report

**Decision: CONDITIONAL_NO_CHANGE** — A3 production logic unchanged.

Today's A3 NEW_T1 candidates are sorted by `a3_rank_score` DESC for operator review. This sorting does **not** change `final_action`, size, or risk checks.

- A3 is the only production candidate.
- Phase36 ranking changes review order only.
- `a3_rank_score` does not create orders.
- S3 remains paper-shadow / radar only.
- S3 lead does not gate A3.
- T2 policy is unchanged.
- Exit policy is unchanged: A3 trail remains 2.5× ATR14.
- S3 satellite remains paper research only.

## Panel 1 — Data health

- scan_schema_version: phase36
- panel_asof_date: 2026-05-19
- scan_date: 2026-05-19
- VNINDEX regime_bull: True
- pct_cloud_bull_a3: 31.8% (defense)
- pct_cloud_bull_s3: 32.5%

## Panel 2 — A3 production actions

- TRAIL_EXIT: 35
- WATCH_ONLY: 35
- NO_T2_BREADTH: 16
- NEW_T1_MANUAL_REVIEW_BREADTH: 7
- HOLD_T1_ONLY: 5
- TP1_PARTIAL: 1

## Panel 3 — A3 ranked candidates

- #1 **KOS** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.972 reason=high_ed_score|s3_lead_5d|liq_ok ed=0.972 lead=lead_1_5
- #2 **NTP** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.958 reason=high_ed_score|s3_lead_5d|liq_ok ed=0.958 lead=lead_1_5
- #3 **GSP** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.929 reason=high_ed_score|liq_warn_near|no_s3_support_but_a3_valid ed=0.9295 lead=none
- #4 **TCB** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.897 reason=high_ed_score|liq_ok ed=0.8975 lead=lead_6_10
- #5 **OIL** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.843 reason=high_ed_score|liq_ok|no_s3_support_but_a3_valid ed=0.843 lead=none
- #6 **TRC** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.459 reason=high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context ed=0.9585 lead=same_day
- #7 **CTG** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.457 reason=high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context ed=0.9565 lead=same_day

## Panel 4 — Hold / monitor

- ORS: HOLD_T1_ONLY
- TDP: HOLD_T1_ONLY
- NAB: HOLD_T1_ONLY
- VGI: HOLD_T1_ONLY
- CDC: HOLD_T1_ONLY
- KSV: NO_T2_BREADTH
- PVS: NO_T2_BREADTH
- PSI: NO_T2_BREADTH
- VRE: NO_T2_BREADTH
- VPB: NO_T2_BREADTH
- SAB: NO_T2_BREADTH
- VPL: NO_T2_BREADTH
- HCM: NO_T2_BREADTH
- MSB: NO_T2_BREADTH
- FUEVN100: NO_T2_BREADTH
- POW: NO_T2_BREADTH
- QNS: NO_T2_BREADTH
- ILS: NO_T2_BREADTH
- HNG: NO_T2_BREADTH
- PHP: NO_T2_BREADTH
- PVP: NO_T2_BREADTH
- EIB: TRAIL_EXIT
- TCH: TRAIL_EXIT
- VCG: TRAIL_EXIT
- DRI: TRAIL_EXIT
- VTO: TRAIL_EXIT
- HHS: TRAIL_EXIT
- SHI: TRAIL_EXIT
- HDB: TRAIL_EXIT
- MSN: TRAIL_EXIT
- HUT: TRAIL_EXIT
- MCH: TRAIL_EXIT
- NVL: TRAIL_EXIT
- NRC: TRAIL_EXIT
- DGW: TRAIL_EXIT
- GVR: TRAIL_EXIT
- LPB: TRAIL_EXIT
- VHC: TRAIL_EXIT
- HNM: TRAIL_EXIT
- KBC: TRAIL_EXIT
- SMC: TRAIL_EXIT
- HDG: TRAIL_EXIT
- CRC: TRAIL_EXIT
- MWG: TRAIL_EXIT
- BMP: TRAIL_EXIT
- AAV: TRAIL_EXIT
- DSE: TRAIL_EXIT
- E1VFVN30: TRAIL_EXIT
- VJC: TRAIL_EXIT
- REE: TRAIL_EXIT
- MIG: TRAIL_EXIT
- DLG: TRAIL_EXIT
- BAF: TRAIL_EXIT
- HPG: TRAIL_EXIT
- DPG: TRAIL_EXIT
- GEE: TRAIL_EXIT
- VHM: TP1_PARTIAL

## Panel 5 — S3 paper-shadow

- PAPER_S3_SHADOW: 59
- NO REAL CAPITAL / NO DNSE

## Panel 6 — Phase36 research overlays (not production)

- s3_t2_warning_flag count: 16
- gk10 (lead_best_125x theoretical): 12

## Panel 7 — Warnings

- breadth defense: manual T1 review
- S3 contamination: use final_action only for live capital
