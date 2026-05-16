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

## S3 Research-Only — RESEARCH_ONLY (no capital at all)

- EMA21/55 signals tracked for awareness only
- No position size output
- No paper-trade capital allocation
- strategy_classification = S3_RESEARCH_ONLY in scan output
- Label all S3 signals: RESEARCH_ONLY in dashboard
- Revisit only if MAR can be moved above 0.30 through structural improvement

---

## final_action Enum (Complete)

| final_action | Meaning | T1 | T2 |
|-------------|---------|-----|-----|
| NEW_T1 | Normal entry, all gates clear | Yes | Per pullback rule |
| NEW_T1_MANUAL_REVIEW_BREADTH | Defense zone — T1 allowed with operator review | Yes (review) | No |
| WAIT_PB | T1 entered, watching for ≥4% pullback | Hold | Pending |
| ADD_T2 | Pullback ≥4% hit within window | — | Yes |
| HOLD_T1_ONLY | No T2 (window expired or breadth blocked) | Hold | No |
| NO_T2_BREADTH | T2 blocked by breadth (caution/defense) | — | No |
| SKIP_LIQUIDITY | ADV cap too low for even T1 | No | No |
| SKIP_VNINDEX_BEAR | Regime gate: VNINDEX bear | No | No |
| WATCH_ONLY | S3/PTS signal only, no A3 | Watchlist | No |
