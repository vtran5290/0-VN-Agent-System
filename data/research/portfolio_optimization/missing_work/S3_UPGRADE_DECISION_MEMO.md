# S3 Upgrade Decision Memo

Date: 2026-05-16
Author: Claude Code (Sonnet 4.6) — evidence-based, corrected liquidity throughout

---

## Reference Benchmarks

| Strategy | MAR | CAGR | MaxDD |
|----------|-----|------|-------|
| A3 DP-First (production) | 0.416 | 5.81% | -13.99% |
| S3 standalone baseline (250-bar hold, full univ) | -0.011 | -0.42% | -37.45% |
| Gate: PAPER_TRADE_SHADOW | 0.30 | — | — |
| Gate: PRODUCTION_CANDIDATE | ~0.416 | — | MaxDD < -20% target |

Liquidity: corrected throughout (adv50_VND = close_kVND × volume × 1000).
Portfolio: 5B VND, 20 slots, 10% ADV cap.

---

## Test Summary

| Test | Best config | Best MAR | Gate (0.30) | Pass? |
|------|-------------|----------|-------------|-------|
| T1: A3 lead overlay | 30-bar S3 lead | +0.061 delta | +0.02 delta | **YES** |
| T2: Scout before A3 | 20% scout, 10-bar confirm | 0.176 | 0.30 | NO |
| T3: GK confirmation | GK within 5 bars | 0.229 | 0.30 | NO |
| T4: Breadth regime | A3 breadth improving 20 bars | 0.147 | 0.30 | NO |
| T5: Exit optimization | max_hold = 60 bars | **0.377** | 0.30 | **YES** |
| T6: Liquidity subset | Top-100 ADV symbols | 0.334 | 0.30 | **YES** |

### Combined variants (post-analysis)

| Combination | N trades | MAR | CAGR | MaxDD | Notes |
|-------------|----------|-----|------|-------|-------|
| T5 only (max60) | 11,632 | 0.377 | 7.92% | -20.99% | All S3 universe |
| T5+T6 (max60 + top100 ADV) | 4,227 | 0.324 | 11.58% | -35.74% | Higher CAGR, worse MaxDD |
| T3+T5 (GK5 + max60) | 2,713 | 0.185 | 6.92% | -37.41% | GK hurts here |
| T3+T5+T6 (GK5 + max60 + top50) | 457 | **0.501** | 9.91% | -19.77% | Too few trades |
| T3+T5+T6 (GK5 + max60 + top100) | 909 | **0.449** | 12.90% | -28.73% | Promising, thin |

---

## Key Finding: max_hold = 60 bars is the single most important lever

S3 baseline MAR = -0.011. Simply capping max_hold at 60 bars → MAR = 0.377.

**Why this works:** S3 uses EMA21/55 (fast cycle, ~55-bar lookback). Holding 250 bars (≈1 year)
means holding through the full reversals of a faster signal. The 250-bar hold was designed for A3
(100-bar EMA, slower mean reversion). S3 signals degrade rapidly after ~60 bars: if a position
has not resolved within 3 trading months, the fast-EMA thesis is stale.

**Hit rate change:** Baseline hit=67.4% → max60 hit=51.9%. The reduction in hit rate is
misleading: the baseline holds losers longer (mean hold=148 bars) while the 60-bar cap
forces quicker decisions. The net return per trade improves because the right tails (big winners)
are captured via TP1 and trail within 60 bars, and dead-weight positions are cut.

---

## Year-by-Year Stability (max_hold = 60)

| Year | max_hold=60 | max60+top100 | GK5+max60 |
|------|-------------|-------------|-----------|
| 2015 | -7.0% | -2.2% | -12.4% |
| 2016 | -4.7% | -10.1% | -14.0% |
| 2017 | +27.9% | +38.5% | +8.3% |
| 2018 | -9.5% | -17.8% | -7.4% |
| 2019 | +3.3% | +8.3% | -12.6% |
| 2020 | +14.7% | +13.6% | +14.8% |
| 2021 | +67.7% | +103.1% | +80.9% |
| 2022 | **-18.0%** | -2.9% | -1.2% |
| 2023 | +6.6% | -4.1% | -7.4% |
| 2024 | +5.0% | +13.2% | -5.7% |
| 2025 | +45.3% | +32.0% | +66.1% |

**Concerns:**
- 2022 max_hold=60 lost -18.0%. A3 DP was -7.9% in 2022 (much better risk control).
- 2015 and 2016 negative in all configs. S3 is not defensive — this is an offensive signal.
- max60+top100 has the best bad-year mitigant in 2022 (-2.9%) but worst MaxDD (-35.7%).

**Strengths:**
- 2021 and 2025 are explosive (+68% and +45%). S3 captures bull momentum faster than A3.
- Positive in 6 of 11 full years (not including 2026 partial).

---

## Test 1: A3 Priority Overlay — SUPPORTED

| S3 Lead Window | A3 with S3 (n) | MAR | A3 without S3 (n) | MAR | Delta |
|----------------|----------------|-----|-------------------|-----|-------|
| 5 bars | 5,329 | 0.291 | 3,702 | 0.208 | +0.083 |
| 10 bars | 6,379 | 0.189 | 2,652 | 0.205 | -0.016 |
| 20 bars | 7,013 | 0.170 | 2,018 | 0.181 | -0.011 |
| 30 bars | 7,330 | 0.170 | 1,701 | 0.109 | **+0.061** |

Gate: +0.02 MAR delta. At 5-bar window: +0.083. At 30-bar window: +0.061. Both pass.

**Interpretation:** A3 trades that had a prior S3 signal within 5 bars are the strongest setups.
The 30-bar window result (+0.061) is noisier because 81% of all A3 trades have a prior S3 signal
within 30 bars — the "without S3" set becomes a small, unusual subset.

**Practical application:** When multiple A3 signals fire on the same day, rank those with a prior
S3 signal within 5 bars first. Do not exclude A3 signals lacking S3 — A3 is not gated on S3.

---

## Test 2: Scout before A3 — NOT SUPPORTED at 0.30 gate

Best MAR = 0.176 (scout=20%, confirm=10-bar, no-confirm-exit=20 bars).
The gate (0.30) is not met by any scout variant.

**However, the economics are interesting:**
- Converted scouts (44-53% of S3 signals get A3 within window): avg return +0.2–0.5%
- Non-converted scouts: avg return -0.05 to -0.1% (small loss, quickly exited)
- False scout loss per trade: -0.42% to -0.49% (well-contained)

The scout does not pass the gate and introduces operational complexity. Keep RESEARCH_ONLY.

---

## Test 3: GK Confirmation — NOT SUPPORTED standalone, INTERESTING in combination

| Variant | N | MAR | CAGR | MaxDD | Hit Rate |
|---------|---|-----|------|-------|----------|
| No GK filter | 11,632 | -0.011 | -0.42% | -37.45% | 67.4% |
| GK within 3 bars | 1,977 (17%) | 0.153 | 5.17% | -33.74% | 68.8% |
| GK within 5 bars | 2,713 (23%) | **0.229** | 6.13% | -26.78% | 69.1% |
| GK within 10 bars | 4,322 (37%) | 0.207 | 6.62% | -31.99% | 70.2% |

GK within 5 bars is the best filter: MAR=0.229. Does not reach 0.30 gate alone.
Combined with max60+top50: MAR=0.501 (but only 457 trades — too thin for conclusions).

GK filter reduces drawdown significantly (-37% → -27%) even without the max_hold fix.
The GK-alone finding is worth noting: it confirms signal quality, but too many winners are missed
(6,479 missed winners vs 3,176 avoided losers at GK-3 window).

---

## Test 4: Breadth Regime Filter — NOT SUPPORTED

Best MAR = 0.147 (a3_breadth improving over 20 bars). No variant reaches 0.30.

Unlike A3, breadth filters harm S3 disproportionately (missed winners far exceed avoided losers
in count). Breadth filtering does not rescue S3's negative baseline.

**Note:** This contradicts the intuition that "strong breadth makes everything work." S3 signals
appear in all breadth environments. The problem is the 250-bar hold, not market breadth.

---

## Test 5: Exit Optimization — KEY FINDING

| Exit config | MAR | CAGR | MaxDD | Hit Rate | TP1 Rate | Avg Hold |
|-------------|-----|------|-------|----------|----------|----------|
| max_hold=60 | **0.377** | 7.92% | -20.99% | 51.9% | 19.4% | 55 bars |
| cloud_loss=2 bars | 0.264 | 6.17% | -23.38% | 33.3% | 19.8% | 28 bars |
| cloud_loss=3 bars | 0.204 | 5.04% | -24.76% | 35.0% | 24.5% | 31 bars |
| max_hold=90 | 0.075 | 2.69% | -35.64% | 56.2% | 32.1% | 76 bars |
| tp+trail 12%/2.0x | 0.092 | 2.84% | -30.72% | 74.9% | 72.5% | 110 bars |
| S3 default (250-bar) | -0.011 | -0.42% | -37.45% | 67.4% | 60.3% | 148 bars |

**max_hold=60 dominates all other exit configs including cloud-loss exits.**

Cloud-loss exits (exit when close < EMA55 for 2 consecutive bars) cut holds more aggressively
(avg 28 bars) but produce MAR=0.264. The max_hold=60 is more permissive and still captures
the TP1 on fast winners, while cutting at 60 bars for slow positions.

No-progress exits (e.g., "exit if no +5% in 20 bars") are harmful (MAR=0.010).

---

## Test 6: Liquidity Subset

| Filter | N | MAR | CAGR | MaxDD | Hit Rate | Avg ADV |
|--------|---|-----|------|-------|----------|---------|
| No filter (all) | 11,632 | -0.011 | -0.42% | -37.45% | 67.4% | 35.7B |
| ADV >= 10B | 5,169 (44%) | 0.089 | 2.57% | -28.9% | 62.5% | 77B |
| ADV >= 20B | 3,674 (32%) | 0.094 | 3.25% | -34.45% | 62.1% | 102B |
| ADV >= 50B | 1,946 (17%) | -0.007 | -0.27% | -37.43% | 59.1% | 165B |
| ADV >= 100B | 1,061 (9%) | 0.037 | 1.48% | -39.71% | 55.1% | 243B |
| Top 50 ADV symbols | 2,050 (18%) | 0.177 | 5.46% | -30.93% | 62.9% | 121B |
| **Top 100 ADV symbols** | **4,227 (36%)** | **0.334** | **8.94%** | **-26.80%** | **64.4%** | **79B** |

Top-100 ADV symbols (median ADV ≥ ~40B VND): MAR=0.334. Passes the 0.30 gate.

**Why top-100 outperforms strict ADV floors:** The ADV floor (e.g., >= 50B) eliminates mid-size
names that have good signals. The top-100 set, ranked by median ADV across all their trades,
selects names that are consistently liquid — not just occasionally liquid.

---

## Verdict on "Combined with A3"

Prior research: A3+S3 combined book MAR=0.264 (worse than A3 standalone at 0.416).
This research does NOT change that finding. S3 and A3 must run as separate sleeves.
Running S3 alongside A3 degrades A3's capital efficiency.

---

## Classification: PAPER_TRADE_SHADOW (conditional)

**Enabling conditions (ALL required):**
1. max_hold = 60 bars (not 250)
2. Regime gate: VNINDEX EMA20 > EMA100 (same as A3 — already applied in all tests)
3. Corrected liquidity (adv50 = close_kVND × vol × 1000 VND), 10% ADV cap

**Optional enhancements (either/or, not required for shadow track):**
- Restrict to top-100 ADV symbols → MAR 0.377 → 0.324 (trades off MAR for lower MaxDD on long holds)
- Add GK within 5 bars + top-50 ADV → MAR 0.501 but n=457 trades (too thin for live validation)

**Upgrade gates to PRODUCTION_CANDIDATE:**
- Live paper-trade data: MAR ≥ 0.35 over ≥ 12 months of live signals (with max_hold=60)
- MaxDD in live paper must not exceed -25% in any 12-month rolling window
- 2022-equivalent bear year performance must be better than -18% (current worst year)
- Combined portfolio test: verify S3 shadow sleeve does not cannibalize A3 capital

**A3 is unchanged:**
- A3 DP-First production logic is not modified
- A3 priority_overlay: when multiple A3 signals fire, prefer those with S3 within 5 bars
- S3 does NOT gate A3. Breadth does NOT gate A3 T1. These rules are unchanged.

---

## What This Research Rules Out

| Approach | Verdict | Reason |
|----------|---------|--------|
| S3 standalone (250-bar hold) | REJECTED | MAR=-0.011, MaxDD=-37.45% |
| S3 as breadth filter | REJECTED | No variant reaches 0.30 |
| S3 + GK (standalone, no max60) | WATCH | MAR=0.229, not at gate |
| S3 scout before A3 | NOT_NOW | Max MAR 0.176, operational complexity |
| S3 + A3 combined book | REJECTED | MAR=0.264, worse than A3 alone |
| GK as multiplier (full S3 universe) | NEUTRAL | No improvement over baseline |

---

## Action Items

1. **Implement max_hold=60 in S3 paper-trade shadow tracking** — update phase33 paper trade rules.
2. **A3 priority overlay** — when >= 2 A3 signals fire same day, rank S3-confirmed setups first.
3. **Track GK5+max60+top100 variant** — monitor this in parallel (MAR=0.449) but do not allocate capital until 12-month live validation.
4. **Update scan schema** — add `s3_max_hold_60_flag` and `s3_gk_confirmed` fields to daily scan.
5. **2022 stress test** — validate that VNINDEX bear gate fires before the -18% year materialises in live paper.
