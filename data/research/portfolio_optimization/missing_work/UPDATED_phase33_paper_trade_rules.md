# Phase34 Paper Trade Rules (Updated 2026-05-16)

Supersedes: phase33_paper_trade_rules.md
Change: Breadth removed from hard T1 entry conditions. T1 allowed in defense zone with review.

---

## A3 DP-First — PRODUCTION_CANDIDATE (real capital)

**Entry conditions (ALL must be true):**
1. A3 signal within 40 bars (a3_active = True)
2. A3 cloud still bullish (a3_cloud_bull = True)
3. VNINDEX regime = bull (EMA20 > EMA100) — ONLY hard T1 block
4. recommendation = full_T1 or partial_T1 (liquidity check)
5. final_action ≠ SKIP_LIQUIDITY and ≠ SKIP_VNINDEX_BEAR

**Breadth is NOT a hard entry condition. It controls T2 and signals operator review.**

**Position sizing:**
- Slot = portfolio / 20 (× 1.25 if GK10)
- T1 = 50% of slot at entry
- T2 = 50% of slot on ≥4% pullback within 30 bars (subject to breadth_t2_permission)
- T1 capped: min(T1, adv50_VND × 10%)

**Breadth zones (advisory, not blocking for T1):**

| breadth_zone | breadth_t1_permission | breadth_t2_permission | final_action |
|-------------|----------------------|-----------------------|--------------|
| normal (≥40%) | True | True | NEW_T1 |
| caution (35–40%) | True | False (T2 blocked) | NEW_T1 |
| defense (<35%) | True (review req'd) | False | NEW_T1_MANUAL_REVIEW_BREADTH |
| VNINDEX bear | False | False | SKIP_VNINDEX_BEAR |

**Defense zone behavior (breadth < 35%):**
- T1 entries may proceed only with explicit operator confirmation
- final_action = NEW_T1_MANUAL_REVIEW_BREADTH
- No T2 adds (breadth_t2_permission = False)
- Operator checks: VNINDEX regime OK? Signal quality OK? Sector concentration OK?

**Exit:**
- TP1: +18% on T1 tranche (sell 50%)
- Trail: 2.5×ATR14 from highest close since entry
- Max hold: 250 bars (~1 year)
- Min sell lock: 5 bars (T+3 settlement)

---

## PTS Shadow — PAPER_TRADE_SHADOW (no real capital)

- Same entry conditions as A3 DP
- T2 triggered by strength add if no pullback within 30 bars
- Default: OFF. Must be explicitly enabled.
- strategy_classification = PTS_SHADOW in scan output
- Track on paper only. No capital until MAR > 0.35 on live paper data.

---

## S3 Shadow — PAPER_TRADE_SHADOW (paper capital only — Updated 2026-05-16)

**Hard rules (DO NOT VIOLATE):**
- max_hold = **60 bars** — not 250, not 90, not 180
- No real capital. No DNSE route. No live order intent.
- strategy_classification = S3_PAPER_SHADOW in scan output
- Track P&L separately from A3. Never combine.
- S3 is A3 priority signal only — when multiple A3 fire same day, rank a3_s3_lead_5d=True first.
- S3 never blocks A3 T1.

**Entry (paper shadow only):**
1. S3 EMA21/55 cloud breakout within 10 bars (s3_active = True)
2. S3 cloud still bullish (s3_cloud_bull = True)
3. VNINDEX regime = bull (EMA20 > EMA100)
4. Assign paper slot (same slot size as A3 for tracking — paper VND only)

**Exit:**
- TP1: +18% (sell 50% of paper position)
- Trail: 3.5×ATR14 from highest close since entry
- Max hold: **60 bars** (hard, enforced in code and manually)
- Min sell lock: 5 bars (T+3)

**S3 RESEARCH_ONLY (old max_hold=250 config):**
- strategy_classification = S3_RESEARCH_ONLY
- MAR=0.190 — classified REJECTED/RESEARCH_ONLY
- No capital, no paper position. Watchlist display only.

---

## final_action Enum (Complete — Phase35)

| final_action | Meaning | Real T1 | Paper T1 |
|-------------|---------|---------|---------|
| NEW_T1 | Normal A3 entry, all gates clear | Yes | — |
| NEW_T1_MANUAL_REVIEW_BREADTH | Defense zone — A3 T1 with operator review | Yes (review) | — |
| WAIT_PB | A3 T1 entered, watching for ≥4% pullback | Hold | — |
| ADD_T2 | A3 pullback ≥4% hit within window | — T2 Yes | — |
| HOLD_T1_ONLY | No T2 (window expired or breadth blocked) | Hold | — |
| NO_T2_BREADTH | T2 blocked by breadth (caution/defense) | — | — |
| SKIP_LIQUIDITY | ADV cap too low for even T1 | No | — |
| SKIP_VNINDEX_BEAR | Regime gate: VNINDEX bear | No | — |
| NEW_S3_SHADOW | S3 max60 new paper shadow entry | No | Yes (paper) |
| S3_SHADOW_HOLD | S3 paper position held | No | Hold |
| S3_SHADOW_EXIT | S3 paper position exit trigger | No | Exit |
| WATCH_ONLY | S3 old config (max_hold=250) — no capital | No | No |
