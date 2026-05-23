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
- panel_asof_date: 2026-05-22
- scan_date: 2026-05-22
- VNINDEX regime_bull: True
- pct_cloud_bull_a3: 31.1% (defense)
- pct_cloud_bull_s3: 31.0%

## Panel 2 — A3 production actions

- TRAIL_EXIT: 40
- WATCH_ONLY: 36
- NO_T2_BREADTH: 13
- NEW_T1_MANUAL_REVIEW_BREADTH: 6
- HOLD_T1_ONLY: 6
- TP1_PARTIAL: 1

## Panel 3 — A3 ranked candidates

- #1 **NTP** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=1.0 reason=high_ed_score|s3_lead_5d|liq_ok ed=0.9995 lead=lead_1_5
- #2 **BID** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.936 reason=high_ed_score|s3_lead_5d|liq_ok ed=0.9365 lead=lead_1_5
- #3 **VGI** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.915 reason=high_ed_score|liq_ok|no_s3_support_but_a3_valid ed=0.9155 lead=none
- #4 **DXS** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.908 reason=high_ed_score|liq_ok ed=0.908 lead=lead_6_10
- #5 **VCB** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.359 reason=high_ed_score|liq_ok|no_s3_support_but_a3_valid|s3_same_day_context ed=0.859 lead=same_day
- #6 **CTR** `NEW_T1_MANUAL_REVIEW_BREADTH` rank=0.223 reason=liq_ok|no_s3_support_but_a3_valid|s3_same_day_context ed=0.723 lead=same_day

## Panel 4 — Hold / monitor

- TDP: HOLD_T1_ONLY
- VPB: HOLD_T1_ONLY
- TCB: HOLD_T1_ONLY
- NAB: HOLD_T1_ONLY
- CTG: HOLD_T1_ONLY
- CDC: HOLD_T1_ONLY
- KSV: NO_T2_BREADTH
- KOS: NO_T2_BREADTH
- TRC: NO_T2_BREADTH
- PSI: NO_T2_BREADTH
- SAB: NO_T2_BREADTH
- OIL: NO_T2_BREADTH
- LPB: NO_T2_BREADTH
- VPL: NO_T2_BREADTH
- MSB: NO_T2_BREADTH
- ILS: NO_T2_BREADTH
- FUEVN100: NO_T2_BREADTH
- PHP: NO_T2_BREADTH
- QNS: NO_T2_BREADTH
- VCG: TRAIL_EXIT
- EIB: TRAIL_EXIT
- TCH: TRAIL_EXIT
- PVS: TRAIL_EXIT
- DRI: TRAIL_EXIT
- GSP: TRAIL_EXIT
- VTO: TRAIL_EXIT
- GVR: TRAIL_EXIT
- ORS: TRAIL_EXIT
- SHI: TRAIL_EXIT
- MSN: TRAIL_EXIT
- HCM: TRAIL_EXIT
- VHC: TRAIL_EXIT
- HUT: TRAIL_EXIT
- NRC: TRAIL_EXIT
- HNM: TRAIL_EXIT
- VRE: TRAIL_EXIT
- MWG: TRAIL_EXIT
- HDB: TRAIL_EXIT
- DGW: TRAIL_EXIT
- CRC: TRAIL_EXIT
- KBC: TRAIL_EXIT
- SMC: TRAIL_EXIT
- BMP: TRAIL_EXIT
- HHS: TRAIL_EXIT
- AAV: TRAIL_EXIT
- NVL: TRAIL_EXIT
- HDG: TRAIL_EXIT
- HNG: TRAIL_EXIT
- E1VFVN30: TRAIL_EXIT
- POW: TRAIL_EXIT
- DSE: TRAIL_EXIT
- MIG: TRAIL_EXIT
- PVP: TRAIL_EXIT
- VJC: TRAIL_EXIT
- DLG: TRAIL_EXIT
- BAF: TRAIL_EXIT
- DPG: TRAIL_EXIT
- HPG: TRAIL_EXIT
- GEE: TRAIL_EXIT
- VHM: TP1_PARTIAL

## Panel 5 — S3 paper-shadow

- PAPER_S3_SHADOW: 58
- NO REAL CAPITAL / NO DNSE

## Panel 6 — Phase36 research overlays (not production)

- s3_t2_warning_flag count: 13
- gk10 (lead_best_125x theoretical): 16

## Panel 7 — Warnings

- breadth defense: manual T1 review
- S3 contamination: use final_action only for live capital
