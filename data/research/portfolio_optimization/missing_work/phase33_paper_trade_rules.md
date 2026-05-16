# Phase33 Paper Trade Rules

Generated: 2026-05-16

## A3 DP-First — PRODUCTION_CANDIDATE (real capital)

**Entry conditions (ALL must be true):**
1. A3 signal within 40 bars (a3_active = True)
2. A3 cloud still bullish (a3_cloud_bull = True)
3. VNINDEX regime = bull (EMA20 > EMA100)
4. A3 breadth ≥ 40% (breadth_zone = normal)
5. recommendation = full_T1 or partial_T1
6. final_action = NEW_T1

**Position sizing:**
- Slot = portfolio / 20 (× 1.25 if GK10)
- T1 = 50% of slot at entry
- T2 = 50% of slot on ≥4% pullback within 30 bars
- T1 capped: min(T1, adv50_VND × 10%)

**Breadth caution zone (35–40%):**
- Allow T1 for existing planned entries only
- No T2 adds
- No new initiations

**Defense zone (<35%):**
- No new entries
- No T2 adds
- Restore when breadth > 45%

**Exit:**
- TP1: +18% on T1 tranche (sell 50%)
- Trail: 2.5×ATR14 from highest close since entry
- Max hold: 250 bars (~1 year)
- Min sell lock: 5 bars (T+3 settlement)

## PTS Shadow — PAPER_TRADE_SHADOW (no real capital)

- Same entry as A3 DP
- T2 triggered by strength add if no pullback within 30 bars
- Default: OFF
- Track on paper only

## S3 Research-Only — RESEARCH_ONLY (no capital at all)

- EMA21/55 signals tracked for awareness only
- No position size output
- No paper-trade capital allocation
- Label all S3 signals: RESEARCH_ONLY in dashboard
