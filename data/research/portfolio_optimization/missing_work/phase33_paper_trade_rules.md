# Phase34 Paper Trade Rules

Generated: 2026-05-16

## A3 DP-First — PRODUCTION_CANDIDATE (real capital)

**Entry conditions (ALL must be true):**
1. A3 signal within 40 bars (a3_active = True)
2. A3 cloud still bullish (a3_cloud_bull = True)
3. VNINDEX regime = bull (EMA20 > EMA100) — ONLY hard T1 block
4. recommendation = full_T1 or partial_T1 (liquidity check)
5. final_action != SKIP_LIQUIDITY and != SKIP_VNINDEX_BEAR

**Breadth is NOT a hard entry condition. It controls T2 and signals operator review.**

**Position sizing:**
- Slot = portfolio / 20 (× 1.25 if GK10)
- T1 = 50% of slot at entry
- T2 = 50% of slot on ≥4% pullback within 30 bars (subject to breadth_t2_permission)
- T1 capped: min(T1, adv50_VND × 10%)

**Breadth zones (advisory for T1, binding for T2):**
- Normal (≥40%): T1 allowed, T2 allowed
- Caution (35–40%): T1 allowed, T2 blocked (breadth_t2_permission=False)
- Defense (<35%): T1 allowed with operator review (NEW_T1_MANUAL_REVIEW_BREADTH), T2 blocked
- VNINDEX bear: T1 hard blocked (SKIP_VNINDEX_BEAR)

**Exit:**
- TP1: +18% on T1 tranche (sell 50%)
- Trail: 2.5×ATR14 from highest close since entry
- Max hold: 250 bars (~1 year)
- Min sell lock: 5 bars (T+3 settlement)

## PTS Shadow — PAPER_TRADE_SHADOW (no real capital)

- Same entry conditions as A3 DP
- T2 triggered by strength add if no pullback within 30 bars
- Default: OFF. Must be explicitly enabled.
- strategy_classification = PTS_SHADOW in scan output
- Track on paper only. No capital until MAR > 0.35 on live paper data.

## S3 Research-Only — RESEARCH_ONLY (no capital at all)

- EMA21/55 signals tracked for awareness only
- No position size output
- No paper-trade capital allocation
- strategy_classification = S3_RESEARCH_ONLY in scan output
- Label all S3 signals: RESEARCH_ONLY in dashboard
