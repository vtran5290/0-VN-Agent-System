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
| S3_best_dp | **RESEARCH_ONLY / WATCHLIST_ONLY** | 0.190 | No capital allocation. EMA21/55 tracking only. |

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

### S3_best_dp — RESEARCH_ONLY / WATCHLIST_ONLY

- Strategy: EMA21/55 cloud breakout, full 272-symbol universe
- Best DP config: d3%/w20/fast_ema quality/t1=60%
- MAR = 0.190 after corrected liquidity at 5B/10%
- **Does NOT consume paper-trade capital**
- **Does NOT generate trade recommendations with position size**
- Correct usage: watchlist / signal awareness / regime supplementary context
- Can optionally run as a no-capital educational sleeve if explicitly labeled "S3 RESEARCH_ONLY"
- Revisit condition: only reopen if structural improvement (new parameter space, different universe, or market structure change) can move MAR above 0.30

---

## What S3 Is NOT

S3 is not a "shadow paper-trade book." This language implies capital allocation at 1× or 0.5×.
S3 is a watchlist indicator. It tells you EMA21/55 signals are present; it does not size positions.
If S3 was ever described as "shadow paper-trade book" in prior memos, that wording is superseded by this document.

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

Backtest evidence (see BREADTH_RULE_FINAL.md):
- hard_40 gate: MAR 0.416 → 0.344. Blocked 1741 trades: 1125 winners vs 616 losers (1.8:1).
- Breadth blocks more winners than losers. Hard gate is net harmful.
- VNINDEX regime gate (EMA20 > EMA100) already filters bear markets.

| A3 breadth | Zone | T1 Permission | T2 Permission |
|------------|------|--------------|--------------|
| ≥ 40% | Normal | YES — full entries | YES — full T2 |
| 35–40% | Caution | YES — allow T1 | Reduced — 30–40% of slot |
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
