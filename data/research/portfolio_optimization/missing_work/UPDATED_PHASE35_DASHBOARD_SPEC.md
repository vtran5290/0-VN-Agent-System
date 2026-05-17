# Phase35 Dashboard Specification

Date: 2026-05-16 | Supersedes: FINAL_DASHBOARD_SPEC.md

---

## Panel 1: Regime & Breadth Status

| Field | Display | Source |
|-------|---------|--------|
| VNINDEX regime | BULL / BEAR (color coded) | regime_bull from scan |
| A3 breadth | % value + sparkline (20-bar trend) | pct_cloud_bull_a3 |
| Breadth zone | NORMAL / CAUTION / DEFENSE (color coded) | breadth_zone |
| S3 breadth | % value (reference only, labeled RESEARCH) | pct_cloud_bull_s3 |

Alert rules:
- VNINDEX bear → RED banner: "NO NEW ENTRIES — REGIME GATE ACTIVE"
- Defense (<35%) → ORANGE banner: "BREADTH DEFENSE — MANUAL REVIEW REQUIRED FOR NEW T1"
- Caution (35-40%) → YELLOW: "BREADTH CAUTION — T2 BLOCKED"

---

## Panel 2: Sector L4 Concentration (DASHBOARD_WARNING_ONLY)

- Table: sector_l4, count of active A3 signals in that sector, sector_l4_stress_flag
- Sort: by count descending
- Alert: if any single L4 > 30% of active live positions → "CONCENTRATION ALERT: [sector]"
- Source: sector_l4 field from Phase35 scan

---

## Panel 3: Liquidity Health

- Distribution of liq_warn_T1: OK | WARN_NEAR | WARN_OVER | CRITICAL (bar chart)
- Skip rate: count(recommendation=skip) / total active A3 signals
- Mean adv50_B_VND for active setups
- Alert: if skip_rate > 20% → "HIGH SKIP RATE"

---

## Panel 4: Active A3 DP Setups (PRODUCTION)

Sort: NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH first (a3_s3_lead_5d=True ranked above a3_s3_lead_5d=False within same action), then WAIT_PB, then HOLD_T1_ONLY, then adv50 desc

| Column | Source |
|--------|--------|
| Symbol | symbol |
| Close (kVND) | close_kVND |
| A3 bars | a3_bars_since |
| S3 Lead | a3_s3_lead_5d (show star if True) |
| GK10 | gk10 (show star if True) |
| ADV50 (B VND) | adv50_B_VND |
| T1 Target (M) | target_T1_M |
| Liq Warn | liq_warn_T1 |
| PB Trigger | pb_trigger_price |
| TP1 | tp1_price |
| Trail Stop | trail_price |
| Final Action | final_action (color coded) |
| Reason | final_action_reason |

Filter: in_a3_universe=True AND strategy_classification=A3_PRODUCTION

Color coding:
- NEW_T1 → green
- NEW_T1_MANUAL_REVIEW_BREADTH → orange (requires review)
- WAIT_PB / NO_T2_BREADTH → yellow
- HOLD_T1_ONLY → blue
- SKIP_* → grey

---

## Panel 5: PTS Shadow Setups (PAPER_TRADE_SHADOW — no real capital)

Label prominently: "PAPER TRADE SHADOW — NO REAL CAPITAL"

Same columns as Panel 4. Only shows when PTS mode is ON.
Filter: strategy_classification=PTS_SHADOW

---

## Panel 6: S3 Shadow Setups — PAPER_TRADE_SHADOW (NEW — Phase35)

Label prominently: "S3 PAPER SHADOW — max_hold=60 BARS — NO REAL CAPITAL — PAPER ONLY"

| Column | Source |
|--------|--------|
| Symbol | symbol |
| Close (kVND) | close_kVND |
| S3 bars | s3_bars_since |
| Shadow bars held | s3_shadow_bars_since |
| Max hold remaining | s3_shadow_max_hold_remaining (RED if ≤ 5) |
| S3 Cloud | s3_cloud_bull |
| Paper TP1 | s3_shadow_tp1_price |
| Paper Trail | s3_shadow_trail_price |
| Paper P&L % | s3_shadow_paper_pnl_pct |
| Shadow Action | s3_shadow_final_action (color coded) |
| Sector L4 | sector_l4 |

Filter: strategy_classification=S3_PAPER_SHADOW AND s3_shadow_active=True

Color coding:
- NEW_S3_SHADOW → green (paper entry signal)
- S3_SHADOW_HOLD → blue
- S3_SHADOW_EXIT → red (exit triggered)
- max_hold_remaining ≤ 5 → RED ALERT "MAX HOLD APPROACHING"

Alert banner: "NO REAL CAPITAL — PAPER TRACKING ONLY — max_hold=60 HARD RULE"

---

## Panel 7: GK5+top100 Research Monitor (PARALLEL_PAPER_RESEARCH)

Label prominently: "RESEARCH MONITOR ONLY — NOT FOR SHADOW DEPLOYMENT"

| Column | Source |
|--------|--------|
| Symbol | symbol |
| Close (kVND) | close_kVND |
| GK5+top100 | s3_gk5_top100 (show if True) |
| S3 bars | s3_bars_since |
| ADV50 (B VND) | adv50_B_VND |
| Sector L4 | sector_l4 |

Filter: s3_gk5_top100=True

Note: This panel is for research tracking. MAR=0.449 but MaxDD=-28.73% — not ready for shadow.

---

## Panel 8: Open Positions Tracker

Input: manual or from paper trade log

A3 open positions (real capital after approval):

| Column |
|--------|
| Symbol |
| Entry date |
| Entry price (ep1) |
| Current close |
| Bars held |
| P&L % |
| Trail stop |
| Status: WAIT_TP1 / WAIT_TRAIL / APPROACHING_MAX_HOLD |

S3 shadow open positions (paper only, from s3_shadow_positions.csv):
- Same columns
- "PAPER" badge on every row
- max_hold_remaining column — RED if ≤ 5

---

## Panel 9: Paper Trade P&L

Two separate equity curves:
1. **A3 paper P&L** (toward real capital gate)
2. **S3 shadow paper P&L** (research assessment only)

NEVER combine into a single equity curve.

Each curve shows:
- Monthly return table
- MAR running (trailing 12M)
- Drawdown chart vs VNINDEX benchmark

---

## Panel 10: Data Health

| Check | Expected | Alert if |
|-------|----------|----------|
| Last scan date | Today | > 1 day stale |
| ADV50 unit confirmed | ratio=1000 (Phase 3.1) | ratio check fails |
| Missing adv50 count | < 5% of universe | > 5% |
| Missing sector_l4 | 71 unknowns (expected) | count increases |
| Regime data fresh | Last VNINDEX date = today | stale |
| S3 shadow max_hold enforcement | All s3_shadow_bars_since ≤ 60 | any > 60 → CRITICAL |
| S3/A3 P&L separation | Separate ledger files exist | files merged or missing |
