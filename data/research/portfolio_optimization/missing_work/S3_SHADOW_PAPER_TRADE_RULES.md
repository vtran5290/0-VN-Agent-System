# S3 Shadow Paper Trade Rules

Date: 2026-05-17 | Classification: PAPER_TRADE_SHADOW | Config: max_hold=60 | Updated: Phase35+36

---

## S3 Shadow Hard Rules (DO NOT VIOLATE)

| Rule | Value | Enforcement |
|------|-------|-------------|
| max_hold | **60 bars** | Code + manual check daily |
| Real capital | **NEVER** | Hard block in order router |
| DNSE route | **NEVER** | Hard block in order router |
| Live order intent | **NEVER** | strategy_classification = S3_PAPER_SHADOW |
| P&L tracking | **Separate from A3** | Never combine in same equity curve |
| S3 blocking A3 T1 | **NEVER** | a3_s3_lead_5d is ranking only |

---

## Entry Rules (Paper Shadow)

**ALL must be true before logging a paper shadow entry:**

1. S3 EMA21/55 cloud breakout within last 2 bars (`s3_shadow_active = True`)
2. S3 cloud still bullish (`s3_cloud_bull = True`)
3. VNINDEX regime = bull (`regime_bull = True`)
4. `strategy_classification` = S3_PAPER_SHADOW in scan output
5. `s3_shadow_action` = NEW_S3_SHADOW

**Paper slot size:**
- Use same slot formula as A3 for tracking: `portfolio / 20 slots`
- Do NOT apply GK multiplier to S3 shadow (GK multiplier is A3-only)
- T1 = 50% of paper slot at breakout bar
- No T2 for S3 shadow (max_hold=60 makes T2 window impractical)

---

## Exit Rules

| Condition | Action | Priority |
|-----------|--------|----------|
| Close ≥ entry × 1.18 | Paper-sell 50% (TP1) | 1 |
| Close < peak − 3.5×ATR14 | Paper-exit remaining | 2 |
| Bars held ≥ 60 | **Force exit remaining** | **3 — hard max_hold** |
| Cloud turns bear AND bars held > 10 | Optional early exit | 4 |
| Bars held < 5 | No exits (T+3 settlement) | Lock |

**max_hold=60 is unconditional.** If TP1 not hit and trail not hit at bar 60, exit regardless.

---

## S3 as A3 Priority Lead (Phase35+36)

When multiple A3 signals fire on the same day, rank by `a3_rank_score` (descending):

| s3_lead_bucket | s3_lead_quality | Ranking boost |
|----------------|-----------------|---------------|
| lead_11_20 | best | +2.0 |
| lead_21_30 | good | +1.0 |
| lead_6_10 | neutral | 0.0 |
| lead_1_5 | neutral | 0.0 |
| same_bar_0 | chase | -0.5 |
| no_s3_lead | none | 0.0 |

`a3_rank_score = quality_boost + ed_score` where `ed_score = max(0, 1 - abs(ema_dist_pct)/20)`.
Higher `a3_rank_score` = higher priority within same `final_action` bucket.

`a3_s3_lead_5d = True` (≤ 5 bars) → `a3_priority_boost_from_s3 = True` (legacy boolean, still in scan).

This rule **never blocks** an A3 signal. It only re-orders same-day NEW_T1 candidates.

---

## Daily Checklist (S3 Shadow)

1. Run Phase35 scan (same script as A3, now includes S3 shadow fields)
2. Check `s3_shadow_action` column for NEW_S3_SHADOW entries
3. For each NEW_S3_SHADOW: confirm `regime_bull = True` and cloud = True
4. Log paper entry to `data/trading/live/s3_shadow_paper_trades.csv`
5. For held positions: check `s3_shadow_max_hold_remaining` — exit if ≤ 0
6. Check `s3_shadow_trail_price` against current close for exit triggers
7. Update `data/trading/live/s3_shadow_positions.csv` with current state

---

## Performance Gates (12-Month Shadow Period)

| Gate | Threshold | Status |
|------|-----------|--------|
| Minimum shadow duration | 12 months | NOT STARTED |
| Completed trades | ≥ 10 (T1 entered AND exited) | NOT STARTED |
| Rolling MAR | ≥ 0.35 | NOT STARTED |
| 12-month MaxDD | ≤ -25% | NOT STARTED |
| Bear year performance | ≥ -18% | NOT STARTED |

No production upgrade discussion until ALL 5 gates are met.
Evidence-driven only. No automatic upgrade.
