# Final Decision Memo — VN EMA-Cloud Strategy
## Clean Classification Document

Generated: 2026-05-16 | Updated: 2026-05-16 (breadth wording patch)
Scope: A3 EMA20/100 + S3 EMA21/55, corrected ADV50 (Phase 3.1), ex-VIN3 / full universe

---

## Candidate Classifications

| Candidate | Classification | MAR @ 5B/10% | Role |
|-----------|---------------|--------------|------|
| DP_A3_pb_only | **PRODUCTION_CANDIDATE** | 0.416 | Primary live strategy |
| PTS_A3_pb4w30_str6w10 | **PAPER_TRADE_SHADOW** | 0.343 | Aggressive/shadow mode, not default |
| A3_pos15_baseline | **PAPER_TRADE_SHADOW** | 0.201 | Benchmark only, superseded by DP |
| S3_best_dp (max_hold=250) | **REJECTED / RESEARCH_ONLY** | 0.190 | Stale config — do not use. Superseded by S3_max60. |
| **S3_max60** | **PAPER_TRADE_SHADOW** | **0.377** | **S3 paper shadow — max_hold=60 bars. No real capital.** |
| S3_GK5_max60_top100 | FUTURE_RETEST_REQUIRED | 0.449* | *MAR unverified. No supporting CSV in package. Re-run required. |

---

## Classification Rationale

### DP_A3_pb_only — PRODUCTION_CANDIDATE

- Strategy: EMA20/100 cloud breakout, ex-VIN3 universe
- Entry mode: DP-first — T1=50% at cloud breakout, T2=50% on ≥4% pullback within 30 bars
- Exit: TP1 +18% (sell T1 half), trail 2.5×ATR14, max_hold 250 bars
- Regime gate: VNINDEX EMA20 > EMA100 (bull mode only)
- GK10 overlay: ×1.25 position size when Garman-Klass buy within 10 days
- Max positions: 20 concurrent slots
- ADV cap: `effective_T1 = min(T1_target, adv50_VND × participation)`
- `adv50_VND = panel["value"].rolling(50).fillna(close_kVND × volume × 1000)`
- Vietnam settlement: T+3, min_sell_lock = 5 bars
- Reference portfolio: 5B VND at 10% ADV participation

**Why this and not PTS as default:**
After Phase 3.1 corrected-liquidity audit, PTS MAR dropped from 0.72 → 0.343 because:
1. PTS ledger lacked `adv50_value` → ADV cap was silently skipped (phantom 0% exclusion)
2. Once corrected, PTS strength-add phase captures lower-quality entries than DP pullback
3. DP pullback selects structurally better price levels (confirmed drawdown, institutional support)

### PTS_A3_pb4w30_str6w10 — PAPER_TRADE_SHADOW

- Same A3 EMA20/100 entry universe as DP
- T1=50% at cloud breakout, then:
  - Phase 1: look 30 bars for ≥4% pullback (T2 add)
  - Phase 2: if no pullback, look 10 more bars for ≥6% strength add (cloud+EMA bullish)
- Default = OFF. Operator must manually choose PTS mode.
- Useful in: strong uptrending markets where pullbacks don't materialize but momentum confirms
- Does NOT deploy real capital until MAR recovers above 0.35 on live paper data

### A3_pos15_baseline — PAPER_TRADE_SHADOW

- Full position at cloud breakout (no pullback wait)
- 15 slots, no dual-path scaling
- Kept only for benchmark comparison
- Superseded by DP in all MAR and MaxDD metrics

### S3_best_dp (max_hold=250) — REJECTED / RESEARCH_ONLY

- MAR = 0.190 (max_hold=250), effectively -0.011 in some configs
- Superseded by S3_max60. Do not use this config for any paper shadow.
- Kept in classification table for history only.

### S3_max60 — PAPER_TRADE_SHADOW (Updated 2026-05-16)

- Strategy: EMA21/55 cloud breakout, full universe (no VIN3 exclusion)
- Config change: **max_hold = 60 bars** (not 250). Everything else from S3 baseline unchanged.
- MAR = 0.377 after corrected liquidity at 5B/10% — gate (0.30) passed
- TP1: 18% (sell 50%), trail: 3.5×ATR14, regime gate: VNINDEX EMA20>EMA100
- **PAPER ONLY — no real capital, no DNSE route, no live order intent**
- Track P&L separately from A3. Never combine A3/S3 results.
- max_hold=60 hard rule: S3 uses EMA55 (fast cycle). Positions past 60 bars ride full signal reversal.
- A3 priority overlay: when multiple A3 signals fire same day, rank those with a3_s3_lead_5d=True first. S3 never blocks A3 T1.

### S3_GK5_max60_top100 — PARALLEL_PAPER_RESEARCH

- MAR = 0.449 but MaxDD = -28.73% (high)
- Research monitor only. Not appropriate for shadow deployment at current MaxDD level.
- Run in parallel to S3_max60 shadow. Assess if MaxDD improves over 12 months of live paper.

---

## What S3 Is (Updated 2026-05-16)

S3_max60 is now a PAPER_TRADE_SHADOW — paper capital allocation only, never real capital.
S3_best_dp (max_hold=250) is REJECTED. That config is stale and produces MAR well below gate.
If code or config references S3 with max_hold=250 or MAR=0.190, update to use S3_max60 (MAR=0.377).

---

## Liquidity Rules (Non-negotiable, post Phase 3.1)

```
adv50_VND = panel["value"].rolling(50, min_periods=20).mean()
             .fillna(close_kVND × volume_shares × 1000)

max_trade_VND = adv50_VND × participation_rate

effective_T1  = min(T1_target_VND, max_trade_VND)
liq_warning   = OK | WARN_NEAR | WARN_OVER | CRITICAL

If adv50_value is missing from trade ledger:
  → must call _tag_adv50(trades_df, adv50_map) before equity simulation
  → never skip ADV cap silently
```

---

## Breadth Operating Rules (Evidence-Based, Updated 2026-05-16)

**CRITICAL: A3 breadth is NOT a hard T1 entry block.**

Backtest evidence (see UPDATED_BREADTH_RULE_FINAL.md):
- hard_40 gate: MAR 0.416 → 0.344. Blocked 1741 trades: 1125 winners vs 616 losers (1.8:1).
- Breadth blocks more winners than losers. Hard gate is net harmful.
- VNINDEX regime gate (EMA20 > EMA100) already filters bear markets.

| A3 breadth | Zone | T1 Permission | T2 Permission |
|------------|------|--------------|--------------|
| ≥ 40% | Normal | YES — full entries | YES — full T2 |
| 35–40% | Caution | YES — allow T1 | NO — T2 blocked (`breadth_t2_permission = False`) |
| < 35% | Defense | YES — allow T1, manual review required | NO — block T2 |
| VNINDEX bear (EMA20 < EMA100) | Bear | NO — hard block (only hard block) | NO |

**Only VNINDEX bear regime is a hard T1 block. Breadth controls T2 aggression only.**

---

## Deployment Checklist (Before Real Capital)

- [ ] A3 DP paper trade running ≥ 3 months with MAR tracking
- [ ] ADV50 corrected formula confirmed live (panel value column, not close×vol)
- [ ] Regime gate confirmed live (EMA20 > EMA100 on VNINDEX)
- [ ] Breadth monitoring live (pct_cloud_bull_20_100 computed daily)
- [ ] Position limit: max 20 concurrent, adv50-capped T1
- [ ] T+3 settlement and 5-bar min lock confirmed in execution system
- [ ] GK10 overlay configured (optional, off by default)
- [ ] PTS mode: OFF by default, paper-only if switched on

---

## Key Numbers for Operations

| Metric | Value |
|--------|-------|
| Reference portfolio | 5B VND |
| ADV participation | 10% (reference), up to 20% in high-liquidity names |
| Max positions | 20 |
| T1 fraction | 50% of slot |
| T2 pullback depth | ≥4% |
| T2 pullback window | 30 bars |
| TP1 | +18% (exit 50% of position) |
| Trail multiplier | 2.5×ATR14 |
| Max hold | 250 bars (~1 year) |
| Min sell lock | 5 bars (T+3 settlement constraint) |
| GK10 mult | 1.25× (optional) |
| Breadth T1 block | None (breadth is T2 control only) |
| Regime T1 block | VNINDEX EMA20 < EMA100 |

---

## Open Items

See UPDATED_FINAL_OPEN_ITEMS.md for complete list of done / rejected / pending / optional items.
