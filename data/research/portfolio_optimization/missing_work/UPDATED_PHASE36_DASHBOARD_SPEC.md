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
- panel_asof_date: 2026-06-08
- scan_date: 2026-06-08
- VNINDEX regime_bull: False
- pct_cloud_bull_a3: 25.8% (defense)
- pct_cloud_bull_s3: 26.1%

## Panel 2 — A3 production actions

- TRAIL_EXIT: 51
- SKIP_VNINDEX_BEAR: 48

## Panel 3 — A3 ranked candidates

- None today.

## Panel 4 — Hold / monitor

- KSV: TRAIL_EXIT
- EIB: TRAIL_EXIT
- TCH: TRAIL_EXIT
- VCG: TRAIL_EXIT
- MSB: TRAIL_EXIT
- DRI: TRAIL_EXIT
- SHI: TRAIL_EXIT
- HCM: TRAIL_EXIT
- SAB: TRAIL_EXIT
- TRC: TRAIL_EXIT
- TDP: TRAIL_EXIT
- VCB: TRAIL_EXIT
- ILS: TRAIL_EXIT
- CTR: TRAIL_EXIT
- OIL: TRAIL_EXIT
- VPL: TRAIL_EXIT
- PVS: TRAIL_EXIT
- BID: TRAIL_EXIT
- VGI: TRAIL_EXIT
- ORS: TRAIL_EXIT
- HDB: TRAIL_EXIT
- MWG: TRAIL_EXIT
- NAB: TRAIL_EXIT
- GVR: TRAIL_EXIT
- TCB: TRAIL_EXIT
- VPB: TRAIL_EXIT
- VHC: TRAIL_EXIT
- BMP: TRAIL_EXIT
- DXS: TRAIL_EXIT
- SMC: TRAIL_EXIT
- MSN: TRAIL_EXIT
- NRC: TRAIL_EXIT
- HHS: TRAIL_EXIT
- VRE: TRAIL_EXIT
- LPB: TRAIL_EXIT
- KBC: TRAIL_EXIT
- PVP: TRAIL_EXIT
- QNS: TRAIL_EXIT
- PHP: TRAIL_EXIT
- BAF: TRAIL_EXIT
- DLG: TRAIL_EXIT
- POW: TRAIL_EXIT
- VJC: TRAIL_EXIT
- E1VFVN30: TRAIL_EXIT
- DPG: TRAIL_EXIT
- HNG: TRAIL_EXIT
- FUEVN100: TRAIL_EXIT
- CTG: TRAIL_EXIT
- HPG: TRAIL_EXIT
- DSE: TRAIL_EXIT
- CDC: TRAIL_EXIT

## Panel 5 — S3 paper-shadow

- PAPER_S3_SHADOW: 0
- NO REAL CAPITAL / NO DNSE

## Panel 6 — Phase36 research overlays (not production)

- s3_t2_warning_flag count: 0
- gk10 (lead_best_125x theoretical): 3

## Panel 7 — Warnings

- breadth defense: manual T1 review
- S3 contamination: use final_action only for live capital

## Panel 8 — Group rotation context (dashboard only)

## Group Rotation Context (dashboard only)

> **DASHBOARD ONLY** — does not change `final_action`, OMS, or order routing. `execution_allowed_flag=false` for all groups.

- **Snapshot date:** 2026-05-25
- **SSOT:** `data\research\group_rotation\group_rotation_latest.csv`
- **P1 cache freshness:**
  - **stock_daily_cloud_panel** last date: `2026-05-25`
  - **group_breadth_turn_events** last date: `2026-05-22`

### Validated groups (Tier A/B, score ≥ 0.5)

_No Tier A/B groups with score ≥ 0.5 today._

### Research-only (Tier D — not validated rotation signals)

| Group | Layer | Score | Badge | Breadth EW | Note |
| --- | --- | --- | --- | --- | --- |
| rubber | theme_tag | 1.15 | GROUP_RESEARCH_ONLY | 60.0% | Research-only / not validated enough for ranking priority. |
| fmcg | theme_tag | 0.88 | GROUP_RESEARCH_ONLY | 55.6% | Research-only / not validated enough for ranking priority. |
| chem | theme_tag | 0.83 | GROUP_RESEARCH_ONLY | 50.0% | Research-only / not validated enough for ranking priority. |
| tech | theme_tag | 0.76 | GROUP_RESEARCH_ONLY | 33.3% | Research-only / not validated enough for ranking priority. |
| state_owned | flag_bucket | 0.57 | GROUP_RESEARCH_ONLY | 37.5% | Research-only / not validated enough for ranking priority. |
| agri | theme_tag | 0.56 | GROUP_RESEARCH_ONLY | 33.3% | Research-only / not validated enough for ranking priority. |

_Full card:_ `data/research/reports/group_rotation_card_latest.md` · _Do not use group breadth as an A3 hard filter (OI-GR-4)._

